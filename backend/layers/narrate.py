"""④ 語り層（仕様書 §5-④ / §6）。LLM使用箇所その2。

確定商品 + 実データ + RecipientProfile → 提案カード(JSON)。
ガードレール：与えた商品データのみを根拠にする。価格/スペック/在庫/レビュー数を創作しない。

LLM は抽象化インターフェース(Narrator)経由で呼ぶ。Claude/GPT/Gemini を差し替え可能に。
Phase1 はまず TemplateNarrator（鍵不要）で動かし、あとで ClaudeNarrator に差し替える。
"""

from __future__ import annotations

from ..models import Item, RecipientProfile, SuggestionCard


def _evidence(it: Item) -> list[str]:
    """カードに添える実データ点（実在の数字だけ）。"""
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
    """相手プロファイルの語と商品テキストの一致点（語りの素材）。"""
    text = it.text()
    return [w for w in (profile.free_text + profile.likes) if w and w in text]


class Narrator:
    """語りの抽象インターフェース。差し替え可能な部品。"""

    def narrate(self, profile: RecipientProfile, items: list[Item]) -> list[SuggestionCard]:
        raise NotImplementedError


class TemplateNarrator(Narrator):
    """鍵不要のテンプレ語り部。LLM 差し替え前の暫定。"""

    def narrate(self, profile: RecipientProfile, items: list[Item]) -> list[SuggestionCard]:
        cards: list[SuggestionCard] = []
        for it in items:
            matched = _matched_points(it, profile)
            ev = _evidence(it)
            if matched:
                hook = f"「{matched[0]}」というお相手に、"
            else:
                hook = "お相手の雰囲気に合わせて、"
            if it.type == "experience":
                reason = f"{hook}モノより一緒の時間を贈る案です。{ev[0]}と評価も安定しています。"
            else:
                reason = f"{hook}{it.description}{ev[0]}と裏付けもあります。"
            cards.append(SuggestionCard(
                name=it.title, type=it.type, reason=reason,
                evidence=ev, url=it.url, image_url=it.image_url, price=it.price,
            ))
        return cards


# TODO(Claude 差し替え): 下記を実装して get_narrator() を切り替える。
#   class ClaudeNarrator(Narrator):
#       - llm.generate(system, input) を呼ぶ。system にガードレール（創作禁止）を固定。
#       - input は {profile, items:[{name,price,rating,reviewCount,rankingNote,isNew,matchedPoints}]}
#       - 出力 JSON 配列を厳密パース（壊れたら部品回収→リトライ→Template フォールバック）。


def get_narrator() -> Narrator:
    """環境に応じて語り部を返す（いまは常にテンプレ）。"""
    return TemplateNarrator()
