"""手作り相談フロー（商品提案はしない / 儲けゼロ）。

方針：手作りはカタログから薦めない。相手の好みに合わせて
「何を作りたいか」を聞き出し、一緒にアイデアを練る。リンク・購入導線は出さない。

本格的な“一緒に考える”対話は LLM（Claude）に差し替える前提。
ここはその前の暫定テンプレ。インターフェースは語り層(narrate)と同じ思想で差し替え可能に。
"""

from __future__ import annotations

import json
import os

from ..models import RecipientProfile, RELATION_LABEL

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
    """相手に合わせた“作る方向性”を返す（商品・リンクなし）。LLMがあれば対話的に、無ければテンプレ。"""
    llm = _llm_ideas(profile, limit)
    return llm if llm else _template_ideas(profile, limit)


def plan_for(profile: RecipientProfile, want: str) -> dict:
    """“これを作りたい”が決まっている場合の、一緒に考える叩き台。LLM優先・テンプレ予備。"""
    return _llm_plan(profile, want) or _template_plan(profile, want)


def make_plan(profile: RecipientProfile, want: str, answers: str = "") -> dict:
    """作る物が決まった後、材料・手順まで具体化する（答え/希望があれば反映）。LLM優先・テンプレ予備。"""
    return _llm_make(profile, want, answers) or _template_make(profile, want)


def _template_make(profile: RecipientProfile, want: str) -> dict:
    terms = "・".join(_profile_terms(profile)[:3]) or "相手の好きなこと"
    return {
        "title": want,
        "why": f"「{want}」を、{terms}に寄せて手作りする方向です。",
        "materials": ["必要な材料を書き出す", "ラッピングやカード", "（相手の好きな色・味に寄せる）"],
        "steps": ["完成形のイメージを決める", "小さく試してから本番", "メッセージや日付を添えて仕上げる"],
        "tip": "難しいのは仕上げの工程。焦らず、接着や乾燥はしっかり時間を取ると失敗しにくい。",
        "source": "100円ショップ・手芸店・ホームセンターなど",
        "budget": "おおよそ 1,000〜3,000円",
    }


def _template_ideas(profile: RecipientProfile, limit: int = 4) -> list[dict]:
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


def _template_plan(profile: RecipientProfile, want: str) -> dict:
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


# ============ LLM（Claude）で“一緒に考える”を本物に ============
# 方針厳守：商品名・ブランド・購入リンク・通販の話は一切しない。手作りの方向だけ。
_HM_SYSTEM = (
    "あなたは手作りギフトの相談相手です。相手の人物像をふまえ、心のこもった"
    "手作りギフトの案を、温かく具体的に一緒に考えます。"
    "厳守：既製品・商品名・ブランド名・店・購入/通販・予算で買う話は一切しない。"
    "あくまで『自分の手で作る』方向だけを提案する。説教くさくせず、親しい人に話すように。"
)


def _profile_brief(profile: RecipientProfile) -> dict:
    return {
        "関係": RELATION_LABEL.get(profile.relation, profile.relation),
        "年代": profile.age_band,
        "好き・最近のこと": _profile_terms(profile),
    }


def _claude_json(prompt: str, schema: dict, max_tokens: int = 1500) -> dict | None:
    """ANTHROPIC_API_KEY があれば Claude で JSON 生成。無ければ/失敗時は None。"""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()
        model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
        resp = client.messages.create(
            model=model, max_tokens=max_tokens, system=_HM_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = next(b.text for b in resp.content if b.type == "text")
        return json.loads(text)
    except Exception as e:
        print(f"[handmade] Claude失敗→テンプレで継続: {e}")
        return None


_IDEA_ITEM = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "why": {"type": "string"},
        "materials": {"type": "array", "items": {"type": "string"}},
        "steps": {"type": "array", "items": {"type": "string"}},
        "tip": {"type": "string"},
        "source": {"type": "string"},     # 材料の調達先（店の種類。商品名・リンクは出さない）
        "budget": {"type": "string"},     # 材料費のおおよその目安（例：1,500〜3,000円）
    },
    "required": ["title", "why", "materials", "steps", "tip", "source", "budget"],
    "additionalProperties": False,
}

_IDEAS_SCHEMA = {
    "type": "object",
    "properties": {"ideas": {"type": "array", "items": _IDEA_ITEM}},
    "required": ["ideas"], "additionalProperties": False,
}

_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "why": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "string"}},
        "next": {"type": "string"},
    },
    "required": ["title", "why", "questions", "next"], "additionalProperties": False,
}


def _llm_ideas(profile: RecipientProfile, limit: int) -> list[dict] | None:
    prompt = (
        f"相手の人物像：{json.dumps(_profile_brief(profile), ensure_ascii=False)}\n"
        f"この相手が喜びそうな『手作りギフト』の案を{limit}個。"
        "それぞれ title（短い名前）, why（なぜこの相手に合うか1〜2文）, "
        "materials（材料3〜5個）, steps（作る手順3〜4個）, "
        "tip（作る上で特に難しい・失敗しやすいポイントと、それを乗り越える具体的なコツ。実用的な作成アドバイス）, "
        "source（材料の調達先＝店の種類。例：100円ショップ・手芸店・ホームセンター・スーパー。"
        "商品名やブランド名やURLは出さない）, budget（材料費のおおよその目安。例：1,500〜3,000円）。"
    )
    data = _claude_json(prompt, _IDEAS_SCHEMA, max_tokens=3500)   # 4件×材料/手順で長め
    if not data:
        return None
    return (data.get("ideas") or [])[:limit] or None


def _llm_plan(profile: RecipientProfile, want: str) -> dict | None:
    prompt = (
        f"相手の人物像：{json.dumps(_profile_brief(profile), ensure_ascii=False)}\n"
        f"作りたいもの：「{want}」\n"
        "これを相手に合わせて素敵に仕上げるために、まず一緒に決めたいことを整理します。"
        "title（作りたいもの）, why（この相手に向けてどう寄せるか1〜2文）, "
        "questions（決めるべきこと3つ・締切や相手の好みなど）, next（決まった後にやること1文）。"
    )
    return _claude_json(prompt, _PLAN_SCHEMA)


# ============ 手紙の文面を実際に生成 ============
_LETTER_LEN = {"short": "100〜150", "medium": "200〜300", "long": "400〜500"}
_LETTER_SCHEMA = {
    "type": "object",
    "properties": {"letter": {"type": "string"}},
    "required": ["letter"], "additionalProperties": False,
}


def _author_voice(g: str) -> str:
    if g == "female":
        return "書き手は女性です。やわらかく、気持ちを細やかに表す言葉づかいで書いてください。"
    if g == "male":
        return "書き手は男性です。誠実で落ち着いた、てらいのない素直な言葉づかいで書いてください。"
    return "自然で素直な、気持ちのこもった言葉づかいで書いてください。"


def write_letter(profile: RecipientProfile, relation: str, situation: str,
                 length: str = "medium", author_gender: str = "") -> str:
    """状況・文字数・書き手の性別に合わせて、手紙の本文を生成（LLM優先・テンプレ予備）。"""
    chars = _LETTER_LEN.get(length, _LETTER_LEN["medium"])
    rel = RELATION_LABEL.get(relation, "相手")
    terms = "・".join(_profile_terms(profile)[:4])
    sit = situation.strip() or "日頃の感謝を伝えたい"
    prompt = (
        f"贈る相手：{rel}。{('相手の好き・最近のこと：'+terms if terms else '')}\n"
        f"伝えたいこと・状況：{sit}\n"
        f"文字数の目安：{chars}字程度。\n"
        f"{_author_voice(author_gender)}\n"
        "この内容で、心のこもった手紙の本文を日本語で書いてください。"
        "宛名・日付・署名は入れず、本文だけ。事実を創作せず誇張しない。読みやすく適度に改行する。"
    )
    data = _claude_json(prompt, _LETTER_SCHEMA, max_tokens=1200)
    if data and data.get("letter"):
        return data["letter"]
    return (f"{sit}。\n\nいつも本当にありがとう。面と向かうと照れくさいけれど、"
            "あなたがそばにいてくれることに、心から感謝しています。\n\nこれからもよろしくね。")


def _llm_make(profile: RecipientProfile, want: str, answers: str) -> dict | None:
    ans = f"\n相手の答え・希望：{answers}" if answers else ""
    prompt = (
        f"相手の人物像：{json.dumps(_profile_brief(profile), ensure_ascii=False)}\n"
        f"作りたいもの：「{want}」{ans}\n"
        "この相手のために実際に作れるよう、材料と手順まで具体化してください。"
        "答え・希望があれば必ず反映する。title（作るもの）, why（この相手にどう寄せたか1〜2文）, "
        "materials（材料4〜6個）, steps（作る手順4〜6個・初めてでも分かるように）, "
        "tip（作る上で特に難しい・失敗しやすいポイントと、それを乗り越える具体的なコツ。実用的な作成アドバイス）, "
        "source（材料の調達先＝店の種類。例：100円ショップ・手芸店・ホームセンター・スーパー。"
        "商品名やブランド名やURLは出さない）, budget（材料費のおおよその目安。例：1,500〜3,000円）。"
    )
    return _claude_json(prompt, _IDEA_ITEM, max_tokens=1500)
