"""手作り相談フロー（商品提案はしない / 儲けゼロ）。

方針：手作りはカタログから薦めない。相手の好みに合わせて
「何を作りたいか」を聞き出し、一緒にアイデアを練る。リンク・購入導線は出さない。

本格的な“一緒に考える”対話は LLM（Claude）に差し替える前提。
ここはその前の暫定テンプレ。インターフェースは語り層(narrate)と同じ思想で差し替え可能に。
"""

from __future__ import annotations

from ..models import RecipientProfile

# 手作りの定番アーキタイプ（商品ではなく“作る方向性”）。
# keys にプロファイルの語が当たれば、その人向けに優先的に出す。
_ARCHETYPES = [
    {
        "title": "プレイリスト＋手書きライナーノーツ",
        "keys": ["音楽", "ライブ", "曲", "バンド", "歌", "コンサート"],
        "why": "音楽が好きな人へ。思い出の曲を集めて、なぜ選んだかを手書きで添える。",
        "materials": ["スマホ/音楽アプリ", "厚紙かノート", "ペン"],
        "steps": ["相手を思い出す曲を10曲ほど選ぶ", "1曲ごとに一言エピソードを書く", "QRコードかプレイリスト名を表紙に"],
        "tip": "「この曲、昔よく流れてたよね」の一言が刺さる。",
    },
    {
        "title": "手作りお菓子＋レシピカード",
        "keys": ["甘いもの", "お菓子", "スイーツ", "お茶", "コーヒー", "グルメ", "料理", "和菓子"],
        "why": "甘いもの・お茶が好きな人へ。一緒に味わえる時間ごと贈る。",
        "materials": ["相手の好きな味の材料", "ラッピング袋", "メッセージカード"],
        "steps": ["相手の好きな味を思い出す", "少量で試作→本番", "レシピと一言を添えて包む"],
        "tip": "甘さ控えめ等、相手の好みに寄せると“分かってる”感が出る。",
    },
    {
        "title": "思い出フォトブック",
        "keys": ["写真", "旅行", "家族", "思い出", "孫", "ペット"],
        "why": "一緒の時間を振り返れる人へ。写真とメッセージで一冊に。",
        "materials": ["写真（プリント or データ）", "アルバム/台紙", "ペン・シール"],
        "steps": ["年代やテーマで写真を選ぶ", "各ページに一言メモ", "最後のページに手紙"],
        "tip": "完璧に作り込まず“手書きの余白”を残すと温かい。",
    },
    {
        "title": "手編み・布の小物",
        "keys": ["寒", "冷え", "編み物", "裁縫", "実用", "あったか"],
        "why": "冷えやすい・実用重視の人へ。身につけるたび思い出す。",
        "materials": ["毛糸 or 布", "編み針/針糸", "簡単な型紙"],
        "steps": ["小さいもの(コースター等)から", "相手の好きな色で", "タグに名前や日付"],
        "tip": "大物は挫折しがち。完成できる小ささに。",
    },
]

# 相手が分からなくても誰にでも提案できる土台（最後に足す）。
_UNIVERSAL = [
    {
        "title": "手紙・感謝のメッセージ",
        "why": "普段言えない感謝を言葉で。何にでも添えられる王道。",
        "materials": ["便箋かカード", "ペン"],
        "steps": ["具体的な思い出を3つ書き出す", "感謝を一言で", "清書して渡す"],
        "tip": "抽象的な“ありがとう”より、具体的な出来事を1つ。",
    },
    {
        "title": "声/動画のメッセージ",
        "why": "離れていても気持ちが伝わる。手紙が苦手な人にも。",
        "materials": ["スマホ"],
        "steps": ["伝えたいことを箇条書き", "30秒〜1分で録る", "家族で順番に一言ずつでも"],
        "tip": "うまく話せなくてOK。素のままが一番伝わる。",
    },
]


def _profile_terms(profile: RecipientProfile) -> list[str]:
    return profile.free_text + profile.likes


def suggest_ideas(profile: RecipientProfile, limit: int = 4) -> list[dict]:
    """相手に合わせた“作る方向性”を返す（商品・リンクなし）。

    TODO(Claude 差し替え): プロファイルを渡して対話的に深掘り・具体化する。
    """
    terms = _profile_terms(profile)
    tailored, rest = [], []
    for a in _ARCHETYPES:
        hit = any(any(k in t or t in k for t in terms) for k in a["keys"])
        (tailored if hit else rest).append({k: v for k, v in a.items() if k != "keys"})
    ideas = tailored + _UNIVERSAL + rest
    # 重複タイトルを除いて limit 件
    seen, out = set(), []
    for i in ideas:
        if i["title"] in seen:
            continue
        seen.add(i["title"])
        out.append(i)
        if len(out) >= limit:
            break
    return out


def plan_for(profile: RecipientProfile, want: str) -> dict:
    """“これを作りたい”が決まっている場合の、一緒に考える叩き台。

    TODO(Claude 差し替え): want と相手プロファイルから具体的な手順・工夫を対話で詰める。
    """
    terms = "・".join(_profile_terms(profile)[:3]) or "相手の好きなこと"
    return {
        "title": want,
        "why": f"「{want}」を、{terms}に寄せて作る方向で一緒に考えましょう。",
        "questions": [
            "完成はいつまで？（締切で作れる範囲が変わる）",
            "予算と、かけられる時間はどれくらい？",
            f"{terms} の中で、特に喜びそうな要素はどれ？",
        ],
        "next": "上が決まれば、材料・手順・相手に合わせた工夫を具体化します。",
    }
