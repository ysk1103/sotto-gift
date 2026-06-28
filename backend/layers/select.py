"""③ 選定層（最重要 / 仕様書 §5-③）。LLM は一切使わない。

候補プール + RecipientProfile → 確定 3〜5件。
第1段 ゲート（足切り） → 第2段 スコア → 第3段 MMR 多様性選択。
"""

from __future__ import annotations

import re

from ..models import Item, RecipientProfile, SearchIntent, is_premium

# --- 調整パラメータ（仕様書 §5。初期値は仮、運用ログでチューニング前提） ---
RATING_FLOOR = 3.0           # ゲート：これ未満のレビュー評価は足切り
DUP_SIM = 0.5                # ゲート：あげた品とこの類似度以上は「酷似」として除外
BUDGET_FLOOR = 2000          # ゲート：これ未満は「プレゼント想定外」として常に除外（緩めない）

# スコア合成重み（Fit を主役に固定）。予算帯で配分を変える：
#   通常帯  … Trust は控えめ（ブランド信頼の方針を薄く反映）
#   高級帯  … Trust を主役級に上げ、百貨店・ブランド店を上位へ押し上げる
W_NORMAL = dict(fit=.38, quality=.22, trend=.13, novelty=.09, budget=.08, trust=.10)
W_PREMIUM = dict(fit=.32, quality=.18, trend=.08, novelty=.07, budget=.05, trust=.30)

# 信頼できる百貨店・ブランド店（店名の部分一致で判定）。ノーブランド激安を避ける拠り所。
TRUSTED_SHOPS = (
    "伊勢丹", "三越", "高島屋", "大丸", "松坂屋", "そごう", "西武", "阪急", "阪神",
    "東急百貨店", "小田急", "京王", "近鉄百貨店", "松屋", "名鉄百貨店", "岩田屋",
    "MOO:D MARK", "ムードマーク", "DEAN & DELUCA", "ディーン", "資生堂", "ロクシタン",
    "ゴディバ", "GODIVA", "ヨックモック", "とらや", "榮太樓", "HIGASHIYA",
    "ピエール", "ウェッジウッド", "WEDGWOOD", "ティファニー", "TIFFANY",
)

# ベイズ補正の事前分布（★4.7×3件のような薄いレビューを割り引く）
BAYES_PRIOR_MEAN = 3.5
BAYES_PRIOR_WEIGHT = 20

# 年代ごとの Trend 重み（高齢ほど定番寄り＝Trend を下げる）
AGE_TREND_FACTOR = {"20s": 1.0, "30s": 1.0, "40s": 0.9, "50s": 0.8, "60s": 0.6, "70s": 0.4, "80s": 0.3}

MMR_LAMBDA = 0.6          # 低いほど多様性重視（似た商品の連続を防ぐ）
RESULT_MIN, RESULT_MAX = 3, 5


# ============ テキスト類似（embedding 差し替え予定の暫定実装） ============
# 日本語はスペースで切れないので、語彙一致ではなく
#   Fit = 「相手の語が商品テキストに含まれるか（部分一致）」
#   item同士の sim = 文字バイグラムの Jaccard
# で暫定対応する。embedding に差し替えれば両方とも cosine に置き換わる。

def _cos(a, b) -> float:
    s = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return s / (na * nb) if na and nb else 0.0


def _fit(profile_terms: list[str], item_text: str) -> float:
    """部分一致Fit（embeddingが無い時のフォールバック）。相手の語が商品にどれだけ含まれるか。"""
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


def _trust(it: Item) -> float:
    """ブランド信頼度（0〜1）。百貨店・ブランド店＝高、実績の薄い無名店＝低。

    高級帯ではこれを主役級に効かせ、ノーブランド激安が上位に来るのを防ぐ。
    """
    name = it.shop_name or ""
    if any(s in name for s in TRUSTED_SHOPS):
        return 1.0                                   # 百貨店・有名ブランド店
    # ふるさと納税の返礼品（店名＝自治体名）はプレゼント用途に不適切＝強く下げる
    if "ふるさと" in name or "納税" in name or name.endswith(("市", "町", "村", "区", "郡")):
        return 0.15
    if it.review_count >= 50 and it.rating >= 4.0:
        return 0.7                                   # 無名でも実績十分なら信頼に足る
    if it.review_count < 5:
        return 0.35                                  # 実績が薄い＝ノーブランド激安リスク
    return 0.55


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
    w = W_PREMIUM if is_premium(intent) else W_NORMAL    # 予算帯で重み配分を切替

    # Fit: embedding(cosine)があれば意味ベース、無ければ部分一致。
    # cosは0.5付近に密集するので候補内でmin-max正規化して差を効かせる。
    use_emb = bool(profile.embedding) and any(it.embedding for it in items)
    cos_by = {}
    if use_emb:
        for it in items:
            if it.embedding:
                cos_by[id(it)] = _cos(profile.embedding, it.embedding)
        vals = list(cos_by.values())
        cmin, cmax = (min(vals), max(vals)) if vals else (0.0, 1.0)

    for it in items:
        if use_emb and id(it) in cos_by:
            fit = (cos_by[id(it)] - cmin) / (cmax - cmin) if cmax > cmin else 0.6
        else:
            fit = _fit(profile_terms, it.text())
        quality = _quality(it, max_reviews)
        trend = _trend(it, profile)
        novelty = _novelty(it, gave_categories)
        budget = _budget(it, intent)
        trust = _trust(it)                                # ブランド信頼（高級帯で主役級）
        fresh = _freshness(it.title, shown)               # 既出は減点＝ローテーション
        total = (w["fit"] * fit + w["quality"] * quality + w["trend"] * trend
                 + w["novelty"] * novelty + w["budget"] * budget + w["trust"] * trust) * fresh
        parts = {"fit": fit, "quality": quality, "trend": trend,
                 "novelty": novelty, "budget": budget, "trust": trust, "fresh": fresh}
        scored.append((it, total, parts))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


# ============ 第3段：MMR 多様性選択 ============
def _sim(a: Item, b: Item) -> float:
    cat = 1.0 if a.category == b.category else 0.0
    return 0.3 * cat + 0.7 * _overlap(a.title, b.title)   # 品名の似かた重視（似た商品を弾く）


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
