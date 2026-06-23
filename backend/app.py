"""APIゲートウェイ（仕様書 §7 ＋ Phase2 UI の人/カレンダー/履歴）。

提案系:
  POST /api/suggest          ヒアリング/相手 → ②取得→③選定→④語り → 提案3〜5件
人の登録:
  GET/POST /api/people, DELETE /api/people/{id}
贈答履歴（あげた/もらった）:
  GET/POST /api/events, DELETE /api/events/{id}

商品API/LLM/embedding の呼び出しはすべてここ（サーバ側）。鍵をクライアントに出さない。
起動: python -m uvicorn backend.app:app --reload --port 8011
"""

from __future__ import annotations

import os
import random
import re
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from datetime import date

from . import store
from .layers import handmade, reminders
from .layers.acquire import fetch_candidates
from .layers.narrate import get_narrator
from .layers.select import select
from .models import RecipientProfile, SearchIntent, resolve_gender

app = FastAPI(title="プレゼント提案エンジン")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def _split(text: str) -> list[str]:
    return [t.strip() for t in re.split(r"[、,\n]", text or "") if t.strip()]


# ============================ 提案 ============================
class SuggestRequest(BaseModel):
    person_id: str | None = None        # 登録済みの相手を使う場合
    # 相手を指定しない/上書きする場合のフォーム値
    relation: str = "mother"
    gender: str = ""
    age_band: str = "60s"
    budget_min: int = 0
    budget_max: int = 100_000
    free_text: str = ""
    keywords: list[str] = []


def _build_inputs(req: SuggestRequest):
    """フォーム＋登録済みの相手・贈答履歴から profile / intent / 学習材料を作る。"""
    free = _split(req.free_text)
    relation, age_band, gender = req.relation, req.age_band, req.gender
    likes: list[str] = []
    avoid: list[str] = []
    gave_history: list[str] = []        # 被り回避（あげたものの名前）
    gave_categories: set[str] = set()   # Novelty 用（あげたカテゴリ）
    learned: list[str] = []             # もらったものから推定した好み

    person = store.get_person(req.person_id) if req.person_id else None
    if person:
        relation = person.get("relation", relation)
        age_band = person.get("age_band", age_band)
        gender = person.get("gender", gender)
        free = _split(person.get("notes", "")) + free
        likes = person.get("likes", [])
        avoid = person.get("avoid", [])
        for e in store.list_events(person["id"]):
            if e["direction"] == "gave":
                gave_history.append(e["title"])
                if e.get("category"):
                    gave_categories.add(e["category"])
            elif e["direction"] == "received":
                # もらったもの → センス推定（タイトル・カテゴリを好みヒントに）
                learned += _split(e["title"])
                if e.get("category"):
                    learned.append(e["category"])

    profile = RecipientProfile(
        relation=relation, gender=resolve_gender(relation, gender), age_band=age_band,
        free_text=free + learned, likes=likes, avoid=avoid,
    )
    keywords = req.keywords or (free + likes + learned)
    budget_min = max(2000, req.budget_min)                  # 下限は一律2,000円（それ未満は想定外）
    budget_max = max(budget_min, req.budget_max)
    intent = SearchIntent(keywords=keywords, budget_min=budget_min, budget_max=budget_max)
    return profile, intent, gave_history, gave_categories, learned


# 緩めた度合いに応じた正直な一言（ゼロ提案の代わりに必ず提案＋説明）
RELAX_NOTES = {
    0: "",
    1: "ご予算に近いものが少なかったので、少し上の価格帯も含めています。",
    2: "条件に合うものが少なめだったので、評価の幅を少し広げています。",
    3: "ぴったりは少なめだったので、性別問わず幅広く選びました。",
    4: "条件が厳しめだったので、近いものを幅広く集めました。",
}


FREE_DAILY_LIMIT = 5             # 無料の1日提案回数（コスト防衛・チューニング前提）


@app.post("/api/suggest")
def suggest(req: SuggestRequest):
    subscribed = store.get_settings()["subscribed"]
    today = date.today().isoformat()
    # 無料は1日上限。超えたら ②③④ を一切回さず即返す（＝API費用ゼロ）
    if not subscribed:
        used = store.get_usage_count(today)
        if used >= FREE_DAILY_LIMIT:
            return {
                "count": 0, "cards": [], "limited": True, "subscribed": False,
                "remaining_today": 0,
                "limit_message": f"無料は1日{FREE_DAILY_LIMIT}回まで。日付が変わればまた使えます。プレミアムなら回数制限なし。",
            }
        store.bump_usage(today)

    profile, intent, gave_history, gave_categories, learned = _build_inputs(req)

    shown = store.get_shown(req.person_id) if req.person_id else []         # 既出（ローテーション用）

    candidates = fetch_candidates(intent)                                  # ②
    selected, relax_level = select(candidates, profile, intent, gave_history, gave_categories, shown)  # ③
    items = [it for it, _s, _p in selected]
    cards = get_narrator().narrate(profile, items)                         # ④

    if req.person_id and items:                                            # 出した物を記録→次回は別の顔ぶれ
        store.push_shown(req.person_id, [it.title for it in items])

    # 万一ゼロ（在庫候補が皆無）でも行き止まりにしない → 追い質問で提案につなぐ
    followup = None
    if not cards:
        followup = {
            "message": "もう少しだけ教えてください。すぐに提案します。",
            "question": "ご予算を上げても大丈夫ですか？ または相手の好きなことを一言。",
            "suggest_budget_max": max(intent.budget_max * 2, 5000),
        }

    return {
        "count": len(cards),
        "cards": [asdict(c) for c in cards],
        "subscribed": subscribed,                            # 無料は free_visible 件超をぼかす
        "free_visible": FREE_SUGGEST_VISIBLE,
        "limited": False,
        "remaining_today": None if subscribed else max(0, FREE_DAILY_LIMIT - store.get_usage_count(today)),
        "relax_level": relax_level,
        "relax_note": RELAX_NOTES.get(relax_level, ""),
        "followup": followup,
        "learned_from_history": learned,        # 履歴から学習した語（UIで「○○から学習」表示用）
        "avoided_count": len(gave_history),     # 被り回避に使った件数
        "debug": [
            {"title": it.title, "score": round(sc, 3),
             "parts": {k: round(v, 3) for k, v in parts.items()}}
            for it, sc, parts in selected
        ],
    }


# ===================== 手作り（商品提案しない / 一緒に考える） =====================
class HandmadeRequest(BaseModel):
    person_id: str | None = None
    free_text: str = ""
    want: str = ""          # 作りたいものが決まっていれば


def _profile_only(req: HandmadeRequest) -> RecipientProfile:
    free = _split(req.free_text)
    likes: list[str] = []
    age_band, relation = "60s", "mother"
    person = store.get_person(req.person_id) if req.person_id else None
    if person:
        free = _split(person.get("notes", "")) + free
        likes = person.get("likes", [])
        age_band = person.get("age_band", age_band)
        relation = person.get("relation", relation)
        for e in store.list_events(person["id"]):
            if e["direction"] == "received":
                free += _split(e["title"])
    return RecipientProfile(relation=relation, age_band=age_band, free_text=free, likes=likes)


@app.post("/api/handmade")
def handmade_help(req: HandmadeRequest):
    profile = _profile_only(req)
    if req.want.strip():
        return {"mode": "plan", "plan": handmade.plan_for(profile, req.want.strip())}
    return {"mode": "ideas", "ideas": handmade.suggest_ideas(profile)}


# ============================ 人 ============================
class PersonIn(BaseModel):
    id: str | None = None
    name: str = ""                  # 任意（空なら関係名で表示）
    relation: str = "mother"
    gender: str = ""
    birthday: str = ""
    anniversary: str = ""
    age_band: str = "60s"
    icon: str = "🎁"
    photo_url: str = ""
    color: str = "#e8638c"
    notes: str = ""
    likes: list[str] = []
    avoid: list[str] = []


@app.get("/api/people")
def get_people():
    return store.list_people()


FREE_PEOPLE_LIMIT = 2


@app.post("/api/people")
def save_person(p: PersonIn):
    data = p.model_dump()
    # 無料は2人まで（新規登録のときだけ判定。既存の編集は通す）
    is_new = not data.get("id")
    if is_new and not store.get_settings()["subscribed"]:
        if len(store.list_people()) >= FREE_PEOPLE_LIMIT:
            raise HTTPException(402, f"無料会員は{FREE_PEOPLE_LIMIT}人まで。プレミアムで無制限になります")
    data["gender"] = resolve_gender(data["relation"], data.get("gender", ""))  # 関係から自動補完
    return store.upsert_person(data)   # 顔写真(photo_url)は無料でもOK


@app.delete("/api/people/{pid}")
def remove_person(pid: str):
    store.delete_person(pid)
    return {"ok": True}


# ============================ 贈答イベント ============================
class EventIn(BaseModel):
    id: str | None = None
    person_id: str
    direction: str                 # "gave" | "received"
    title: str
    category: str = ""
    price: int = 0
    source_url: str = ""
    reaction: str = ""
    date: str = ""
    photo_url: str = ""


@app.get("/api/events")
def get_events(person_id: str | None = None):
    return store.list_events(person_id)        # 閲覧は無料でも可


@app.post("/api/events")
def save_event(e: EventIn):
    if not store.get_settings()["subscribed"]:                 # 記録は有料会員のみ
        raise HTTPException(402, "プレミアム会員限定の機能です")
    if e.direction not in ("gave", "received"):
        raise HTTPException(400, "direction は gave か received")
    return store.upsert_event(e.model_dump())


@app.delete("/api/events/{eid}")
def remove_event(eid: str):
    store.delete_event(eid)
    return {"ok": True}


# ============================ その他 ============================
FREE_SUGGEST_VISIBLE = 2          # 無料は提案2件まで表示、3件目以降はぼかし


class SettingsIn(BaseModel):
    subscribed: bool


@app.get("/api/settings")
def get_settings():
    s = store.get_settings()
    return {**s, "free_people_limit": FREE_PEOPLE_LIMIT, "free_suggest_visible": FREE_SUGGEST_VISIBLE}


@app.post("/api/settings")
def update_settings(s: SettingsIn):
    return store.set_subscribed(s.subscribed)


@app.get("/api/reminders")
def get_reminders():
    return reminders.upcoming(store.list_people(), date.today(), store.list_occasions())


@app.get("/api/calendar")
def get_calendar(y: int, m: int):
    return reminders.month_events(store.list_people(), store.list_occasions(),
                                  store.list_events(), y, m, store.get_memos())


class MemoIn(BaseModel):
    date: str
    text: str = ""


@app.get("/api/memos")
def get_memo(date: str):
    return {"date": date, "text": store.get_memo(date)}


@app.post("/api/memos")
def save_memo(m: MemoIn):
    store.set_memo(m.date, m.text)
    return {"ok": True}


# 一回きりの予定（出産祝い等）
class OccasionIn(BaseModel):
    person_id: str
    label: str
    date: str


@app.get("/api/occasions")
def get_occasions(person_id: str | None = None):
    return store.list_occasions(person_id)


@app.post("/api/occasions")
def save_occasion(o: OccasionIn):
    return store.add_occasion(o.model_dump())


@app.delete("/api/occasions/{oid}")
def remove_occasion(oid: str):
    store.delete_occasion(oid)
    return {"ok": True}


@app.get("/api/surprise")
def surprise():
    """隠しギミック：タイトルタップでランダム1点（在庫あり・2000円以上）。"""
    pool = [it for it in fetch_candidates(SearchIntent(budget_min=2000, budget_max=99999999))
            if it.in_stock and (it.list_price or it.price) >= 2000]
    if not pool:
        raise HTTPException(404, "候補がありません")
    card = get_narrator().narrate(RecipientProfile(), [random.choice(pool)])[0]
    return asdict(card)


@app.get("/api/health")
def health():
    return {"ok": True, "rakuten_key": bool(os.getenv("RAKUTEN_APP_ID"))}


# フロント（buildless）。/ で index.html、その他静的ファイルも配信。
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
