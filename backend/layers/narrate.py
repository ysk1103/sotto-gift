"""④ 語り層（仕様書 §5-④ / §6）。LLM使用箇所その2。

確定商品 + 実データ + RecipientProfile → 提案カード(JSON)。
ガードレール：与えた商品データのみを根拠にする。価格/スペック/在庫/レビュー数を創作しない。

LLM は抽象化インターフェース(Narrator)経由。Claude / Gemini / テンプレを差し替え可能。
ハルシネーション防止のため、LLMには「理由文」だけ書かせ、価格・リンク・画像・evidence
は我々の実データから組み立てる（＝商品名/価格/リンクをLLMに発明させない）。
プロバイダは env NARRATE_PROVIDER（claude|gemini|template）。未指定なら鍵の有無で自動判定。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from ..models import Item, RecipientProfile, SuggestionCard

CLAUDE_MODEL_DEFAULT = "claude-haiku-4-5"          # コスト配慮で既定Haiku
GEMINI_MODEL_DEFAULT = "gemini-2.5-flash-lite"     # 無料枠で動く最安級・高速


def _evidence(it: Item) -> list[str]:
    ev: list[str] = []
    if it.review_count:
        ev.append(f"★{it.rating}（レビュー{it.review_count:,}件）")
    if it.ranking_rank:
        ev.append(f"ランキング{it.ranking_rank}位")
    if it.is_new:
        ev.append("新着")
    if it.list_price and it.list_price > it.price:
        ev.append(f"通常{it.list_price:,}円→{it.price:,}円")
    else:
        ev.append(f"{it.price:,}円")
    return ev


def _matched_points(it: Item, profile: RecipientProfile) -> list[str]:
    text = it.text()
    return [w for w in (profile.free_text + profile.likes) if w and w in text]


def _card(it: Item, reason: str) -> SuggestionCard:
    return SuggestionCard(
        name=it.title, type=it.type, reason=reason,
        evidence=_evidence(it), url=it.url, image_url=it.image_url, price=it.price,
    )


def _build_payload(profile: RecipientProfile, items: list[Item]) -> dict:
    return {
        "相手プロフィール": {
            "関係": profile.relation, "年代": profile.age_band,
            "好き・最近のこと": profile.free_text + profile.likes,
        },
        "商品": [
            {
                "index": i, "name": it.title, "type": it.type,
                "price": it.price, "rating": it.rating, "review_count": it.review_count,
                "ranking": it.ranking_rank, "is_new": it.is_new,
                "matched_points": _matched_points(it, profile), "desc": it.description[:80],
            }
            for i, it in enumerate(items)
        ],
    }


# 文体指示（自然な日本語の肝。プロバイダ共通で同条件）
_SYSTEM = (
    "あなたはギフト提案アプリの語り部です。与えられた『相手プロフィール』と『商品データ』だけを"
    "根拠に、なぜこの品がこの相手に合うのかを日本語で1〜2文書きます。"
    "口調は、親しい人にそっと薦めるような自然で温かい話し言葉。硬い・機械的な定型文や"
    "『〜です。〜あります。』の繰り返しを避け、商品ごとに表現を変える。"
    "厳守：価格・在庫・レビュー数・スペックなどの数値や事実を新しく創作しない。誇張しない。"
    "matched_points（相手の好みと商品の一致点）があれば自然に織り込む。"
    "各商品について {index, reason} を返す。reason は日本語。"
)


class Narrator:
    def narrate(self, profile: RecipientProfile, items: list[Item]) -> list[SuggestionCard]:
        raise NotImplementedError


class TemplateNarrator(Narrator):
    """鍵不要のテンプレ語り部。フォールバック兼用。"""

    def _reason(self, it: Item, profile: RecipientProfile) -> str:
        matched = _matched_points(it, profile)
        ev = _evidence(it)
        hook = f"「{matched[0]}」というお相手に、" if matched else "お相手の雰囲気に合わせて、"
        if it.type == "experience":
            return f"{hook}モノより一緒の時間を贈る案です。{ev[0]}と評価も安定しています。"
        return f"{hook}{it.description}{ev[0]}と裏付けもあります。"

    def narrate(self, profile: RecipientProfile, items: list[Item]) -> list[SuggestionCard]:
        return [_card(it, self._reason(it, profile)) for it in items]


def _apply(profile: RecipientProfile, items: list[Item], reasons: dict[int, str]) -> list[SuggestionCard]:
    tmpl = TemplateNarrator()
    return [_card(it, reasons.get(i) or tmpl._reason(it, profile)) for i, it in enumerate(items)]


# ---- Claude ----
_CLAUDE_SCHEMA = {
    "type": "object",
    "properties": {"reasons": {"type": "array", "items": {
        "type": "object",
        "properties": {"index": {"type": "integer"}, "reason": {"type": "string"}},
        "required": ["index", "reason"], "additionalProperties": False}}},
    "required": ["reasons"], "additionalProperties": False,
}


class ClaudeNarrator(Narrator):
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("ANTHROPIC_MODEL", CLAUDE_MODEL_DEFAULT)

    def narrate(self, profile, items):
        if not items:
            return []
        try:
            import anthropic
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model=self.model, max_tokens=1500, system=_SYSTEM,
                messages=[{"role": "user", "content": json.dumps(_build_payload(profile, items), ensure_ascii=False)}],
                output_config={"format": {"type": "json_schema", "schema": _CLAUDE_SCHEMA}},
            )
            text = next(b.text for b in resp.content if b.type == "text")
            reasons = {r["index"]: r["reason"] for r in json.loads(text)["reasons"]}
        except Exception as e:
            print(f"[narrate] Claude失敗→テンプレで継続: {e}")
            return TemplateNarrator().narrate(profile, items)
        return _apply(profile, items, reasons)


# ---- Gemini（依存ライブラリ不要・REST）----
_GEMINI_SCHEMA = {
    "type": "OBJECT",
    "properties": {"reasons": {"type": "ARRAY", "items": {
        "type": "OBJECT",
        "properties": {"index": {"type": "INTEGER"}, "reason": {"type": "STRING"}},
        "required": ["index", "reason"]}}},
    "required": ["reasons"],
}


class GeminiNarrator(Narrator):
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("GEMINI_MODEL", GEMINI_MODEL_DEFAULT)

    def narrate(self, profile, items):
        if not items:
            return []
        try:
            key = os.environ["GEMINI_API_KEY"]
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{self.model}:generateContent?key={key}")
            body = {
                "systemInstruction": {"parts": [{"text": _SYSTEM}]},
                "contents": [{"parts": [{"text": json.dumps(_build_payload(profile, items), ensure_ascii=False)}]}],
                "generationConfig": {"responseMimeType": "application/json", "responseSchema": _GEMINI_SCHEMA},
            }
            req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
            data = None
            for attempt in range(3):                     # 503/429は一時的なのでリトライ
                try:
                    with urllib.request.urlopen(req, timeout=20) as res:
                        data = json.loads(res.read().decode("utf-8"))
                    break
                except urllib.error.HTTPError as he:
                    if he.code in (503, 429) and attempt < 2:
                        time.sleep(2); continue
                    raise
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            reasons = {r["index"]: r["reason"] for r in json.loads(text)["reasons"]}
        except Exception as e:
            print(f"[narrate] Gemini失敗→テンプレで継続: {e}")
            return TemplateNarrator().narrate(profile, items)
        return _apply(profile, items, reasons)


def get_narrator() -> Narrator:
    """env NARRATE_PROVIDER 優先、なければ鍵の有無で自動判定。"""
    provider = (os.getenv("NARRATE_PROVIDER") or "").lower()
    if provider == "claude":
        return ClaudeNarrator()
    if provider == "gemini":
        return GeminiNarrator()
    if provider == "template":
        return TemplateNarrator()
    if os.getenv("ANTHROPIC_API_KEY"):
        return ClaudeNarrator()
    if os.getenv("GEMINI_API_KEY"):
        return GeminiNarrator()
    return TemplateNarrator()
