"""③ 選定層（最重要 / 仕様書 §5-③）。LLM は一切使わない。

候補プール + RecipientProfile → 確定 3〜5件。
第1段 ゲート（足切り） → 第2段 スコア → 第3段 MMR 多様性選択。
"""

from __future__ import annotations

import re

from ..models import Item, RecipientProfile, SearchIntent

# --- 調整パラメータ（仕様書 §5。初期値は仮、運用ログでチューニング前提） ---
RATING_FLOOR = 3.0           # ゲート：これ未満のレビュー評価は足切り
DUP_SIM = 0.5                # ゲート：あげた品とこの類似度以上は「酷似」として除外
BUDGET_FLOOR = 2000          # ゲート：これ未満は「プレゼント想定外」として常に除外（緩めない）

# スコア合成重み（Fit を主役に固定、他はチューニング対象）
W_FIT, W_QUALITY, W_TREND, W_NOVELTY, W_BUDGET = 0.40, 0.25, 0.15, 0.10, 0.10

# ベイズ補正の事前分布（★4.7×3件のような薄いレビューを割り引く）
BAYES_PRIOR_MEAN = 3.5
BAYES_PRIOR_WEIGHT = 20

# 年代ごとの Trend 重み（高齢ほど定番寄り＝Trend を下げる）
AGE_TREND_FACTOR = {"20s": 1.0, "30s": 1.0, "40s": 0.9, "50s": 0.8, "60s": 0.6, "70s": 0.4, "80s": 0.3}

MMR_LAMBDA = 0.7
RESULT_MIN, RESULT_MAX = 3, 5


# ============ テキスト類似（embedding 差し替え予定の暫定実装） ============
# 日本語はスペースで切れないので、語彙一致ではなく
#   Fit = 「相手の語が商品テキストに含まれるか（部分一致）」
#   item同士の sim = 文字バイグラムの Jaccard
# で暫定対応する。embedding に差し替えれば両方とも cosine に置き換わる。

def _fit(profile_terms: list[str], item_text: str) -> float:
    """相手プロファイルの語が商品テキストにどれだけ反映されているか（0〜1）。

    TODO(embedding 差し替え): cosine(profile.embedding, item.embedding) にする。
    """
    terms = [t for t in profile_terms if t]
    if not terms:
        return 0.0
    hit = sum(1 for t in terms if t in item_text)
    return hit / len(terms)


def _bigrams(text: str) -> set[str]:
    s = re.sub(r"\s+", "", text.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else {s}


def _overlap(a: str, b: str) -> float:
    """文字バイグラムの Jaccard（0〜1）。item 同士の類似(MMR)に使う。"""
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / len(ba | bb)


# ============ 第1段：ゲート（足切り） ============
# 在庫（＝届くこと）だけは絶対に緩めない。それ以外はフォールバック階段で段階的に緩める。
def gate(items: list[Item], profile: RecipientProfile, intent: SearchIntent,
         gave_history: list[str] | None = None,
         budget: bool = True, rating: bool = True, dup: bool = True,
         avoid: bool = True, gender: bool = True) -> list[Item]:
    gave = set(gave_history or [])
    out: list[Item] = []
    for it in items:
        if not it.in_stock:                              # 在庫なし＝届かないので常に除外（死守）
            continue
        regular = it.list_price or it.price              # ギフトの“格”は通常価格で見る
        if regular < BUDGET_FLOOR:                        # 元から2000円未満＝想定外（床は緩めない）
            continue
        if budget and it.price > intent.budget_max:       # 上限：実際に払う額（セールで安いのは歓迎）
            continue
        if budget and regular < intent.budget_min:        # 下限：通常価格（セールで安い良品は弾かない）
            continue
        if rating and it.type == "buy" and it.rating < RATING_FLOOR:  # 地雷レビュー
            continue
        if dup and (it.title in gave or any(_overlap(it.title, g) >= DUP_SIM for g in gave)):
            continue                                     # 去年と同一・酷似
        if avoid and any(av and av in it.text() for av in profile.avoid):  # 避けたいもの
            continue
        if gender and it.target_gender and profile.gender and it.target_gender != profile.gender:
            continue                                     # 性別不一致（男女問わずは常に通す）
        out.append(it)
    return out


# ============ 第2段：スコア（0〜1 を重み付き合成） ============
def _quality(it: Item, max_reviews: int) -> float:
    bayes = ((BAYES_PRIOR_MEAN * BAYES_PRIOR_WEIGHT + it.rating * it.review_count)
             / (BAYES_PRIOR_WEIGHT + it.review_count)) / 5.0
    rank = (1.0 - (it.ranking_rank - 1) / 30.0) if it.ranking_rank else 0.5
    rank = max(0.0, min(1.0, rank))
    return 0.7 * bayes + 0.3 * rank


def _trend(it: Item, profile: RecipientProfile) -> float:
    base = 0.5
    if it.is_new:
        base += 0.3
    if it.ranking_rank and it.ranking_rank <= 5:
        base += 0.2
    base = min(1.0, base)
    return base * AGE_TREND_FACTOR.get(profile.age_band, 0.7)


def _novelty(it: Item, gave_categories: set[str]) -> float:
    if not gave_categories:
        return 0.5                                   # 履歴なし → 中立
    return 0.2 if it.category in gave_categories else 0.9


def _budget(it: Item, intent: SearchIntent) -> float:
    lo, hi = intent.budget_min, intent.budget_max
    if hi <= lo:
        return 0.5
    ratio = (it.price - lo) / (hi - lo)
    ratio = max(0.0, min(1.0, ratio))
    return 0.4 + 0.6 * ratio                          # 上限寄りを軽く加点（安すぎ減点）


def _freshness(title: str, shown: list[str]) -> float:
    """「またこれ？」防止。最近提案した物ほど強く減点（古い既出は徐々に復活）。

    未提案=1.0 / 直近に出した=0.3 / だいぶ前に出した=～0.8。これでローテーションする。
    """
    if title not in shown:
        return 1.0
    idx = shown.index(title)                      # 0 = 直近に提案
    return 0.3 + 0.5 * min(idx, 10) / 10


def score_items(items: list[Item], profile: RecipientProfile, intent: SearchIntent,
                gave_categories: set[str] | None = None,
                shown: list[str] | None = None) -> list[tuple[Item, float, dict]]:
    gave_categories = gave_categories or set()
    shown = shown or []
    max_reviews = max((it.review_count for it in items), default=1) or 1
    scored = []
    profile_terms = profile.free_text + profile.likes + intent.keywords
    for it in items:
        fit = _fit(profile_terms, it.text())
        quality = _quality(it, max_reviews)
        trend = _trend(it, profile)
        novelty = _novelty(it, gave_categories)
        budget = _budget(it, intent)
        fresh = _freshness(it.title, shown)               # 既出は減点＝ローテーション
        total = (W_FIT * fit + W_QUALITY * quality + W_TREND * trend
                 + W_NOVELTY * novelty + W_BUDGET * budget) * fresh
        parts = {"fit": fit, "quality": quality, "trend": trend,
                 "novelty": novelty, "budget": budget, "fresh": fresh}
        scored.append((it, total, parts))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


# ============ 第3段：MMR 多様性選択 ============
def _sim(a: Item, b: Item) -> float:
    cat = 1.0 if a.category == b.category else 0.0
    return 0.5 * cat + 0.5 * _overlap(a.text(), b.text())


def mmr_select(scored: list[tuple[Item, float, dict]], k: int = RESULT_MAX) -> list[tuple[Item, float, dict]]:
    selected: list[tuple[Item, float, dict]] = []
    pool = list(scored)
    while pool and len(selected) < k:
        best, best_val = None, -1e9
        for cand in pool:
            it, sc, _ = cand
            penalty = max((_sim(it, s[0]) for s in selected), default=0.0)
            val = MMR_LAMBDA * sc - (1 - MMR_LAMBDA) * penalty
            if val > best_val:
                best, best_val = cand, val
        selected.append(best)
        pool.remove(best)
    return selected


def _ensure_non_ec(selected, scored, k):
    """最終セットに最低1件は非EC（体験）を含める（仕様書 §5）。

    手作り(make)は商品提案しない方針のためここには含めない（別フローで扱う）。
    """
    if any(s[0].type == "experience" for s in selected):
        return selected
    non_ec = next((s for s in scored if s[0].type == "experience"), None)
    if non_ec is None:
        return selected
    if len(selected) >= k:
        selected = selected[:-1]              # 一番下を1枠空ける
    selected.append(non_ec)
    return selected


# フォールバック階段：上から順に試し、最初に RESULT_MIN 件以上揃った段を採用。
# 在庫(届くこと)は全段で死守。それ以外を段階的に緩めて「ゼロ提案」を絶対に出さない。
RELAX_LADDER = [
    dict(),                                                   # 0: 完全条件
    dict(budget=False),                                       # 1: 予算上限を緩める
    dict(budget=False, rating=False),                         # 2: 評価足切りも緩める
    dict(budget=False, rating=False, gender=False),           # 3: 性別も緩める
    dict(budget=False, rating=False, gender=False, avoid=False, dup=False),  # 4: 在庫以外ほぼ全部
]


def _ensure_surprise(selected, scored, k):
    """「鉄板ばかり」にしない。最終セットに“意外性”を最低1件入れる（仕様書：凡庸＝敵）。

    意外性＝新着、または上位と別カテゴリ。先頭(イチオシ)は守り、下位枠と入れ替える。
    """
    if any(s[0].is_new for s in selected):
        return selected
    top_cats = {s[0].category for s in selected[:2]}
    surprise = next((s for s in scored
                     if s not in selected and (s[0].is_new or s[0].category not in top_cats)), None)
    if surprise is None:
        return selected
    if len(selected) >= k:
        selected = selected[:-1]                  # 一番下を1枠空ける（先頭は守る）
    selected.append(surprise)
    return selected


def select(items: list[Item], profile: RecipientProfile, intent: SearchIntent,
           gave_history: list[str] | None = None,
           gave_categories: set[str] | None = None,
           shown: list[str] | None = None) -> tuple[list[tuple[Item, float, dict]], int]:
    """③ の入口。確定 3〜5件と「どこまで緩めたか(relax_level)」を返す。

    候補(items)が在庫ありで1つでもあれば、必ず非空で返す（ゼロ提案を出さない）。
    shown=過去に提案した品名（再提案でローテーションして「またこれ？」を防ぐ）。
    """
    best: tuple[int, list[Item]] | None = None
    for level, flags in enumerate(RELAX_LADDER):
        passed = gate(items, profile, intent, gave_history, **flags)
        if not passed:
            continue
        if best is None:
            best = (level, passed)
        if len(passed) >= RESULT_MIN:                        # 3件以上揃ったら、その段で確定
            best = (level, passed)
            break
    if best is None:                                         # 在庫ありが皆無＝候補自体が無い
        return [], -1
    level, passed = best
    scored = score_items(passed, profile, intent, gave_categories, shown)
    selected = mmr_select(scored, RESULT_MAX)
    selected = _ensure_non_ec(selected, scored, RESULT_MAX)
    selected = _ensure_surprise(selected, scored, RESULT_MAX)  # 意外性枠
    return selected[:RESULT_MAX], level
