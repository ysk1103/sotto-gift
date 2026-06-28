"""シンプルなJSONファイル保存（DB不要 / 中身が目で見える）。

data/store.json に people[] と events[] を持つ。単一ユーザー前提の素朴な実装。
あとで本格運用するなら SQLite 等に差し替える（この store.py の関数だけ直せば済む形）。
"""

from __future__ import annotations

import contextvars
import json
import os
import uuid
from pathlib import Path
from threading import Lock

# 現在のリクエストのユーザー（ログイン者のGoogle sub）。未ログイン/ローカルは "main"。
# ログインを被せると自動で「ユーザーごとの保存領域」に分かれる（後方互換）。
_current_user = contextvars.ContextVar("current_user", default="main")


def set_current_user(uid: str | None) -> None:
    _current_user.set(uid or "main")


def _uid() -> str:
    return _current_user.get()

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_STORE = _DATA_DIR / "store.json"
_lock = Lock()

# DATABASE_URL があれば本番＝Postgresに保存（再起動で消えない）。無ければローカル＝JSONファイル。
_DATABASE_URL = os.getenv("DATABASE_URL")
_table_ready = False


def _connect():
    """都度新しい接続を開く（リクエストごと＝スレッド安全。共有接続の競合を避ける）。"""
    import psycopg
    conn = psycopg.connect(_DATABASE_URL, autocommit=True, connect_timeout=10)
    global _table_ready
    if not _table_ready:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS appstate (id text PRIMARY KEY, data jsonb NOT NULL)")
        _table_ready = True
    return conn


def _apply_defaults(data: dict) -> dict:
    data.setdefault("people", [])
    data.setdefault("events", [])
    data.setdefault("occasions", [])
    data.setdefault("shown", {})       # {person_id: [過去に提案した品名, ...]（新しい順）}
    s = data.setdefault("settings", {})                   # アプリ設定
    s.setdefault("subscribed", False)                     # 有料サブスク状態（暫定フラグ）
    s.setdefault("tone", "warm")                          # 提案の語り口（warm/plain/polite）
    s.setdefault("default_budget_min", 0)                 # デフォルト予算（0=未設定）
    s.setdefault("default_budget_max", 0)
    data.setdefault("usage", {"date": "", "count": 0})    # 無料の1日提案回数（コスト防衛）
    data.setdefault("memos", {})       # {"YYYY-MM-DD": メモ本文}
    return data


def _load() -> dict:
    if _DATABASE_URL:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT data FROM appstate WHERE id=%s", (_uid(),))
            row = cur.fetchone()
        data = row[0] if row else {}
    elif _STORE.exists():
        with open(_STORE, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    return _apply_defaults(data)


def _save(data: dict) -> None:
    if _DATABASE_URL:
        from psycopg.types.json import Jsonb
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO appstate (id, data) VALUES (%s, %s) "
                "ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data",
                (_uid(), Jsonb(data)))
        return
    _DATA_DIR.mkdir(exist_ok=True)
    with open(_STORE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---------- People ----------
def list_people() -> list[dict]:
    return _load()["people"]


def get_person(pid: str) -> dict | None:
    return next((p for p in _load()["people"] if p["id"] == pid), None)


def upsert_person(person: dict) -> dict:
    with _lock:
        data = _load()
        if not person.get("id"):
            person["id"] = new_id()
            data["people"].append(person)
        else:
            for i, p in enumerate(data["people"]):
                if p["id"] == person["id"]:
                    data["people"][i] = person
                    break
            else:
                data["people"].append(person)
        _save(data)
    return person


def reorder_people(ids: list[str]) -> None:
    """idsの順に並べ替える（左＝大切な人）。idsに無い人は末尾に。"""
    with _lock:
        data = _load()
        order = {pid: i for i, pid in enumerate(ids)}
        data["people"].sort(key=lambda p: order.get(p["id"], 10**9))
        _save(data)


def delete_person(pid: str) -> None:
    with _lock:
        data = _load()
        data["people"] = [p for p in data["people"] if p["id"] != pid]
        data["events"] = [e for e in data["events"] if e["person_id"] != pid]
        data["occasions"] = [o for o in data["occasions"] if o["person_id"] != pid]
        data.get("shown", {}).pop(pid, None)
        _save(data)


# ---------- GiftEvents ----------
def list_events(person_id: str | None = None) -> list[dict]:
    events = _load()["events"]
    if person_id:
        events = [e for e in events if e["person_id"] == person_id]
    return events


def upsert_event(event: dict) -> dict:
    with _lock:
        data = _load()
        if not event.get("id"):
            event["id"] = new_id()
            data["events"].append(event)
        else:
            for i, e in enumerate(data["events"]):
                if e["id"] == event["id"]:
                    data["events"][i] = event
                    break
            else:
                data["events"].append(event)
        _save(data)
    return event


def delete_event(eid: str) -> None:
    with _lock:
        data = _load()
        data["events"] = [e for e in data["events"] if e["id"] != eid]
        _save(data)


# ---------- 一回きりの予定（出産祝い等のカスタム行事） ----------
def list_occasions(person_id: str | None = None) -> list[dict]:
    occ = _load()["occasions"]
    if person_id:
        occ = [o for o in occ if o["person_id"] == person_id]
    return occ


def add_occasion(occ: dict) -> dict:
    with _lock:
        data = _load()
        occ["id"] = new_id()
        data["occasions"].append(occ)
        _save(data)
    return occ


def delete_occasion(oid: str) -> None:
    with _lock:
        data = _load()
        data["occasions"] = [o for o in data["occasions"] if o["id"] != oid]
        _save(data)


# ---------- 提案済み履歴（「またこれ？」防止のローテーション用） ----------
def get_shown(person_id: str) -> list[str]:
    return _load().get("shown", {}).get(person_id, [])


def push_shown(person_id: str, titles: list[str], cap: int = 24) -> None:
    """提案した品名を新しい順で記録（重複は最新を残す・上限cap）。"""
    with _lock:
        data = _load()
        d = data.setdefault("shown", {})
        d[person_id] = list(dict.fromkeys(list(titles) + d.get(person_id, [])))[:cap]
        _save(data)


# ---------- 設定（会員状態など） ----------
def get_settings() -> dict:
    return _load()["settings"]


def set_subscribed(value: bool) -> dict:
    with _lock:
        data = _load()
        data["settings"]["subscribed"] = bool(value)
        _save(data)
        return data["settings"]


def set_subscription(uid: str, subscribed: bool, customer_id: str | None = None) -> None:
    """Stripe Webhookから、指定ユーザーの会員状態を更新（ログインセッション外から呼ぶ）。"""
    token = _current_user.set(uid)
    try:
        data = _load()
        data["settings"]["subscribed"] = bool(subscribed)
        if customer_id:
            data["settings"]["stripe_customer_id"] = customer_id
        _save(data)
    finally:
        _current_user.reset(token)


_ALLOWED_SETTINGS = {"subscribed", "tone", "default_budget_min", "default_budget_max"}


def update_settings(patch: dict) -> dict:
    """設定を部分更新（許可キーのみ）。会員・語り口・デフォルト予算など。"""
    with _lock:
        data = _load()
        for k, v in patch.items():
            if k in _ALLOWED_SETTINGS:
                data["settings"][k] = v
        _save(data)
        return data["settings"]


# ---------- 無料の1日提案回数（API破産防止） ----------
def get_usage_count(today: str) -> int:
    u = _load()["usage"]
    return u.get("count", 0) if u.get("date") == today else 0


def bump_usage(today: str) -> int:
    with _lock:
        data = _load()
        u = data["usage"]
        if u.get("date") != today:
            u["date"] = today; u["count"] = 0
        u["count"] += 1
        _save(data)
        return u["count"]


# ---------- 日付メモ ----------
def get_memos() -> dict:
    return _load()["memos"]


def get_memo(date: str) -> str:
    return _load()["memos"].get(date, "")


def set_memo(date: str, text: str) -> None:
    with _lock:
        data = _load()
        if text.strip():
            data["memos"][date] = text
        else:
            data["memos"].pop(date, None)
        _save(data)
