"""シンプルなJSONファイル保存（DB不要 / 中身が目で見える）。

data/store.json に people[] と events[] を持つ。単一ユーザー前提の素朴な実装。
あとで本格運用するなら SQLite 等に差し替える（この store.py の関数だけ直せば済む形）。
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from threading import Lock

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_STORE = _DATA_DIR / "store.json"
_lock = Lock()


def _load() -> dict:
    if not _STORE.exists():
        return {"people": [], "events": [], "occasions": []}
    with open(_STORE, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("people", [])
    data.setdefault("events", [])
    data.setdefault("occasions", [])
    return data


def _save(data: dict) -> None:
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


def delete_person(pid: str) -> None:
    with _lock:
        data = _load()
        data["people"] = [p for p in data["people"] if p["id"] != pid]
        data["events"] = [e for e in data["events"] if e["person_id"] != pid]
        data["occasions"] = [o for o in data["occasions"] if o["person_id"] != pid]
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
