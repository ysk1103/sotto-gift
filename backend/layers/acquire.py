"""② 取得層。検索意図 → 正規化された候補プール。

各「市場アダプタ（楽天 / Yahoo / …）」が共通スキーマ(Item)に正規化して返す。
fetch_candidates が、鍵のある市場すべてから集めて1つのプールに束ね、横断で重複排除する。
鍵が1つも無ければ、今まで通りダミーデータで動く（鍵ゼロでも開発可）。

  楽天 : RAKUTEN_APP_ID + RAKUTEN_ACCESS_KEY（任意で RAKUTEN_AFFILIATE_ID）
  Yahoo: YAHOO_APP_ID（任意で YAHOO_AFFILIATE_ID＝ValueCommerce sid）
ギフトモール / アソビューは公開検索APIが無く、提携フィード待ち（後から同じ形で足す）。
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..models import Item, SearchIntent, is_premium
from ..mock_data import MOCK_ITEMS

# 2026年刷新後の新エンドポイント（旧 app.rakuten.co.jp は2026/5に停止）
RAKUTEN_ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
YAHOO_ENDPOINT = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"

# Yahoo は WAF が独自UA("gift-advisor/1.0"等)を bot 扱いして 403 を返すため、
# ブラウザ風 UA を送る（"Your Request was Forbidden" の回避）。
_BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _fetch_json(url: str, timeout: int = 8, retries: int = 2) -> dict:
    """GETしてJSONを返す。429/503（一時的なレート/混雑）は短い待ちでリトライ。

    並列で叩くと楽天が瞬間的に429を返すことがあるため、取りこぼさず拾い直す。
    """
    req = urllib.request.Request(url, headers={"User-Agent": _BROWSER_UA})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < retries:
                time.sleep(0.6 * (attempt + 1))
                continue
            raise


def _clean_title(t: str) -> str:
    """キーワード詰め込み商品名を見やすく整形（確実な宣伝ノイズだけ除去＋長さ上限）。"""
    t = re.sub(r"[【\[(（][^】\])）]*[】\])）]", "", t)       # 【...】[...](...)＝宣伝枠を除去
    t = re.sub(r"[★☆\\／]", " ", t)
    t = re.sub(r"(送料無料|あす楽|期間限定|ポイント\d+倍|P\d+倍|\d+%OFF|"
               r"遅れてごめん\S*|今だけ|数量限定|限定\d*)", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" 　/・|,")
    return (t[:48] + "…") if len(t) > 49 else t      # 表示はCSSで2行に整える。極端な長文だけ丸める


def _dedup_key(it: Item) -> str:
    return "".join(it.title.split())[:40].lower()


def _keywords(intent: SearchIntent) -> list[str]:
    # 市場はキーワードをANDで扱うので、全部繋ぐと0件になりがち。
    # 興味語ごとに「○○ ギフト」で検索して束ねる（関連性＋件数を両立）。
    terms = [k for k in intent.keywords if k][:3]
    queries = [f"{t} ギフト" for t in terms] or ["プレゼント ギフト"]
    if is_premium(intent):
        # 高級帯：百貨店寄りの品を1本だけ補充（直列なので増やしすぎない）。
        head = terms[0] if terms else "プレゼント"
        queries.append(f"{head} 百貨店 ギフト")
    return queries


def fetch_candidates(intent: SearchIntent) -> list[Item]:
    """鍵のある市場すべてから候補を集め、共通スキーマ(Item)で返す（目安30〜60件）。"""
    queries = _keywords(intent)
    # 「市場×キーワード」の検索を1本ずつ独立タスクにして全部並列で叩く。
    # 実測で楽天/Yahooとも複数同時に耐える（→キーワード分も待ち時間を畳む）。
    # 1本落ちてもそのタスクだけスキップし、残りで候補を埋める（ゼロ提案を出さない）。
    tasks: list[tuple[str, callable]] = []

    rkt_id, rkt_key = os.getenv("RAKUTEN_APP_ID"), os.getenv("RAKUTEN_ACCESS_KEY")
    if rkt_id and rkt_key:
        for q in queries:
            tasks.append(("楽天", lambda q=q: _search_rakuten(q, intent, rkt_id, rkt_key)))

    yahoo_id = os.getenv("YAHOO_APP_ID")
    if yahoo_id:
        for q in queries:
            tasks.append(("Yahoo", lambda q=q: _search_yahoo(q, intent, yahoo_id)))

    if not tasks:
        return list(MOCK_ITEMS)             # 鍵が無ければダミー（従来通り動く）

    results: list[Item] = []
    with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as ex:
        future_to_name = {ex.submit(fn): name for name, fn in tasks}
        for fut in as_completed(future_to_name):
            name = future_to_name[fut]
            try:
                results.extend(fut.result())
            except Exception as e:
                print(f"[acquire] {name}検索失敗→スキップ: {e}")

    pool: dict[str, Item] = {}
    for it in results:
        key = _dedup_key(it)
        cur = pool.get(key)
        # 同一商品が複数市場に出たら、レビューが多い＝根拠が厚い方を残す
        if cur is None or it.review_count > cur.review_count:
            pool[key] = it

    return list(pool.values()) or list(MOCK_ITEMS)   # 全滅時もゼロ提案を出さない


# ============ 楽天 市場アダプタ ============
def _search_rakuten(keyword: str, intent: SearchIntent, app_id: str, access_key: str) -> list[Item]:
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
    return _parse_rakuten(_fetch_json(url))


def _parse_rakuten(data: dict) -> list[Item]:
    items: list[Item] = []
    for entry in data.get("Items", []):
        r = entry.get("Item", entry)
        imgs = r.get("mediumImageUrls") or r.get("smallImageUrls") or []
        image_url = (imgs[0].get("imageUrl") if imgs and isinstance(imgs[0], dict) else "") or ""
        # 既定は128px と粗いので、楽天の画像リサイズ(_ex)で300px指定＝Retinaでも綺麗に
        if image_url:
            image_url = image_url.split("?")[0] + "?_ex=300x300"
        gid = str(r.get("genreId") or "")
        items.append(Item(
            title=_clean_title(r.get("itemName", "")),
            price=int(r.get("itemPrice", 0) or 0),
            in_stock=(int(r.get("availability", 1)) == 1),
            rating=float(r.get("reviewAverage", 0) or 0),
            review_count=int(r.get("reviewCount", 0) or 0),
            url=r.get("affiliateUrl") or r.get("itemUrl", ""),
            image_url=image_url,
            category=gid or "楽天",
            description=(r.get("itemCaption", "") or "")[:120],
            shop_name=r.get("shopName", ""),
            source="楽天",
            genre_id=gid,
            type="buy",
        ))
    return items


# ============ Yahoo!ショッピング 市場アダプタ（商品検索 V3） ============
def _search_yahoo(keyword: str, intent: SearchIntent, app_id: str) -> list[Item]:
    params = {
        "appid": app_id,
        "query": keyword,
        "results": 20,
        "in_stock": "true",                            # 在庫ありのみ＝届く
        "image_size": 600,                             # Retinaでも綺麗に（粗い画像対策）
        "sort": "-score",                              # おすすめ（売れ筋・関連）順
        "price_from": max(2000, intent.budget_min),    # 下限2000円
    }
    if intent.budget_max and intent.budget_max < 1_000_000:
        params["price_to"] = intent.budget_max
    affiliate_id = os.getenv("YAHOO_AFFILIATE_ID")     # ValueCommerce sid。あれば成果リンク
    if affiliate_id:
        params["affiliate_type"] = "vc"
        params["affiliate_id"] = affiliate_id

    url = YAHOO_ENDPOINT + "?" + urllib.parse.urlencode(params)
    return _parse_yahoo(_fetch_json(url))


def _parse_yahoo(data: dict) -> list[Item]:
    items: list[Item] = []
    for hit in data.get("hits", []):
        image = hit.get("image") or {}
        image_url = (image.get("medium") or image.get("small") or "").split("?")[0]
        review = hit.get("review") or {}
        seller = hit.get("seller") or {}
        genre = hit.get("genreCategory") or {}
        items.append(Item(
            title=_clean_title(hit.get("name", "")),
            price=int(hit.get("price", 0) or 0),
            in_stock=bool(hit.get("inStock", True)),
            rating=float(review.get("rate", 0) or 0),
            review_count=int(review.get("count", 0) or 0),
            url=hit.get("url", ""),                     # affiliate指定時は成果リンクが入る
            image_url=image_url,
            category=str(genre.get("name") or "Yahoo"),
            description=(hit.get("description", "") or "")[:120],
            shop_name=str(seller.get("name") or ""),
            source="Yahoo",
            genre_id=str(genre.get("id") or ""),
            type="buy",
        ))
    return items


# ============ 似た商品（同じジャンル）を取得 ============
def fetch_similar(source: str, genre_id: str, price: int = 0,
                  exclude_title: str = "", k: int = 5) -> list[Item]:
    """指定ジャンルの似た商品を最大k件。元商品と同じ市場・近い価格帯で集める。"""
    lo = max(2000, int(price * 0.6)) if price else 2000
    hi = int(price * 1.7) if price else 100000
    rkt_id, rkt_key = os.getenv("RAKUTEN_APP_ID"), os.getenv("RAKUTEN_ACCESS_KEY")
    yahoo_id = os.getenv("YAHOO_APP_ID")
    items: list[Item] = []
    try:
        if source == "Yahoo" and yahoo_id:
            items = _similar_yahoo(genre_id, lo, hi, yahoo_id)
        elif rkt_id and rkt_key:
            items = _similar_rakuten(genre_id, lo, hi, rkt_id, rkt_key)
        elif yahoo_id:
            items = _similar_yahoo(genre_id, lo, hi, yahoo_id)
    except Exception as e:
        print(f"[acquire] 似た商品の取得失敗: {e}")
        return []

    ex = "".join((exclude_title or "").split()).lower()
    seen, out = set(), []
    for it in items:
        key = _dedup_key(it)
        if not it.in_stock or "".join(it.title.split()).lower() == ex or key in seen:
            continue
        seen.add(key)
        out.append(it)
        if len(out) >= k:
            break
    return out


def _similar_rakuten(genre_id, lo, hi, app_id, access_key) -> list[Item]:
    params = {
        "applicationId": app_id, "accessKey": access_key, "format": "json",
        "hits": 12, "minPrice": lo, "maxPrice": hi,
        "availability": 1, "imageFlag": 1, "sort": "standard",
    }
    if genre_id and genre_id.isdigit():
        params["genreId"] = genre_id          # ジャンル指定＝同じ種類の商品
    else:
        params["keyword"] = "ギフト プレゼント"   # ジャンル不明時の保険
    affiliate_id = os.getenv("RAKUTEN_AFFILIATE_ID")
    if affiliate_id:
        params["affiliateId"] = affiliate_id
    url = RAKUTEN_ENDPOINT + "?" + urllib.parse.urlencode(params)
    return _parse_rakuten(_fetch_json(url))


def _similar_yahoo(genre_id, lo, hi, app_id) -> list[Item]:
    params = {
        "appid": app_id, "results": 12, "in_stock": "true",
        "image_size": 600, "sort": "-score", "price_from": lo, "price_to": hi,
    }
    if genre_id and genre_id.isdigit():
        params["genre_category_id"] = genre_id
    else:
        params["query"] = "ギフト プレゼント"
    affiliate_id = os.getenv("YAHOO_AFFILIATE_ID")
    if affiliate_id:
        params["affiliate_type"] = "vc"
        params["affiliate_id"] = affiliate_id
    url = YAHOO_ENDPOINT + "?" + urllib.parse.urlencode(params)
    return _parse_yahoo(_fetch_json(url))
