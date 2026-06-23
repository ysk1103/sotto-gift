"""② 取得層。検索意図 → 正規化された候補プール。

Phase1 はダミーデータを返すだけ。
本物の楽天 Web Service API に差し替えるときは、この fetch_candidates() の中だけを
書き換える（戻り値の Item リストの形は変えない）。外側（③④）は無改修で動く。
"""

from ..models import Item, SearchIntent
from ..mock_data import MOCK_ITEMS


def fetch_candidates(intent: SearchIntent) -> list[Item]:
    """検索意図に合う候補を集めて共通スキーマ(Item)で返す。

    いまはモックを丸ごと返すだけ。実APIではここで
    楽天/Yahoo を叩いて正規化する（目安 30〜60件）。
    """
    # TODO(楽天差し替え): RAKUTEN_APP_ID を使い IchibaItem/Search を keywords で叩く。
    #   レスポンスを Item(title, price, in_stock, rating, review_count, ...) に正規化。
    return list(MOCK_ITEMS)
