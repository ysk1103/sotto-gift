"""② 取得層。検索意図 → 正規化された候補プール。

楽天 Web Service（IchibaItem Search）を叩いて共通スキーマ(Item)に正規化する。
環境変数 RAKUTEN_APP_ID が無いときは、今まで通りダミーデータで動く（鍵ゼロでも開発可）。
Yahoo / ギフトモール / アソビュー も、同じ「市場アダプタ→Itemに正規化」の形で後から足す。
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from ..models import Item, SearchIntent
from ..mock_data import MOCK_ITEMS

# 2026年刷新後の新エンドポイント（旧 app.rakuten.co.jp は2026/5に停止）
RAKUTEN_ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"


def fetch_candidates(intent: SearchIntent) -> list[Item]:
    """検索意図に合う候補を集めて共通スキーマ(Item)で返す（目安30〜60件）。"""
    app_id = os.getenv("RAKUTEN_APP_ID")
    access_key = os.getenv("RAKUTEN_ACCESS_KEY")    # 新方式は accessKey(pk_) も必須
    if not (app_id and access_key):
        return list(MOCK_ITEMS)             # 鍵が無ければダミー（従来通り動く）
    try:
        items = _fetch_rakuten(intent, app_id, access_key)
        return items or list(MOCK_ITEMS)    # 0件ならダミーにフォールバック（ゼロ提案を出さない）
    except Exception as e:                   # 通信失敗等でもアプリは止めない
        print(f"[acquire] 楽天API失敗→ダミーで継続: {e}")
        return list(MOCK_ITEMS)


def _fetch_rakuten(intent: SearchIntent, app_id: str, access_key: str) -> list[Item]:
    # 楽天はキーワードをANDで扱うので、全部繋ぐと0件になる。
    # 興味語ごとに「○○ ギフト」で検索して束ねる（関連性＋件数を両立）。
    terms = [k for k in intent.keywords if k][:3]
    queries = [f"{t} ギフト" for t in terms] or ["プレゼント ギフト"]
    pool: dict[str, Item] = {}
    for q in queries:
        for it in _search(q, intent, app_id, access_key):
            pool.setdefault(it.url or it.title, it)   # URLで重複排除
    return list(pool.values())


def _search(keyword: str, intent: SearchIntent, app_id: str, access_key: str) -> list[Item]:
    params = {
        "applicationId": app_id,
        "accessKey": access_key,
        "format": "json",
        "keyword": keyword,
        "hits": 20,
        "minPrice": max(2000, intent.budget_min),     # 下限2000円（安すぎ除外と整合）
        "availability": 1,                            # 在庫ありのみ＝届く
        "imageFlag": 1,                               # 画像ありのみ
        "sort": "standard",                           # 売れ筋ベースの関連順
    }
    if intent.budget_max and intent.budget_max < 1_000_000:
        params["maxPrice"] = intent.budget_max
    affiliate_id = os.getenv("RAKUTEN_AFFILIATE_ID")  # あれば成果リンク（収益化）
    if affiliate_id:
        params["affiliateId"] = affiliate_id

    # 注意: Referer/Origin を付けると 503 "Authentication service error" になる → 付けない
    url = RAKUTEN_ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "gift-advisor/1.0"})
    with urllib.request.urlopen(req, timeout=8) as res:
        data = json.loads(res.read().decode("utf-8"))

    items: list[Item] = []
    for entry in data.get("Items", []):
        r = entry.get("Item", entry)
        imgs = r.get("mediumImageUrls") or r.get("smallImageUrls") or []
        image_url = (imgs[0].get("imageUrl") if imgs and isinstance(imgs[0], dict) else "") or ""
        image_url = image_url.split("?")[0]           # サイズ指定パラメータを除去
        items.append(Item(
            title=r.get("itemName", ""),
            price=int(r.get("itemPrice", 0) or 0),
            in_stock=(int(r.get("availability", 1)) == 1),
            rating=float(r.get("reviewAverage", 0) or 0),
            review_count=int(r.get("reviewCount", 0) or 0),
            url=r.get("affiliateUrl") or r.get("itemUrl", ""),
            image_url=image_url,
            category=r.get("genreId", "") and str(r.get("genreId")) or "楽天",
            description=(r.get("itemCaption", "") or "")[:120],
            shop_name=r.get("shopName", ""),
            type="buy",
        ))
    return items
