"""リマインド計算（Phase2 カレンダー/通知）。

4段階：1か月前=お知らせ / 2週間前=念押し / 3日前=最終確認 / 当日=お祝い。
対象：登録した人の誕生日 ＋ 母の日(5月第2日曜)・父の日(6月第3日曜)・クリスマス(12/25)。
ブラウザ内表示用のデータを返すだけ（プッシュ通知はアプリ化の段階で）。
"""

from __future__ import annotations

from datetime import date, timedelta

from ..models import resolve_gender

# --- 段階のしきい値（日数） ---
NOTICE_MAX = 35          # これ以内で「お知らせ(約1か月前)」
PUSH_MAX = 14            # 「念押し(2週間前)」
FINAL_MAX = 3            # 「最終確認(3日前)」


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """その月の第n weekday を返す（weekday: 月=0 … 日=6）。"""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset + 7 * (n - 1))


def _mothers_day(y: int) -> date:
    return _nth_weekday(y, 5, 6, 2)     # 5月 第2日曜


def _fathers_day(y: int) -> date:
    return _nth_weekday(y, 6, 6, 3)     # 6月 第3日曜


def _keiro_day(y: int) -> date:
    return _nth_weekday(y, 9, 0, 3)     # 9月 第3月曜（敬老の日）


def _coming_of_age_day(y: int) -> date:
    return _nth_weekday(y, 1, 0, 2)     # 1月 第2月曜（成人の日/二十歳のつどい）


def _full_date(s: str) -> date | None:
    """'YYYY-MM-DD' を date に。年が無ければ学齢計算できないので None。"""
    s = (s or "").strip()
    if len(s) < 10:
        return None
    try:
        y, m, d = (int(x) for x in s[:10].split("-"))
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def _elementary_entry_year(bd: date) -> int:
    """小学校に入学する4月の暦年（日本の学齢: 4/1 基準）。

    1/1〜4/1 生まれ → 誕生年+6、4/2〜12/31 生まれ → 誕生年+7。
    """
    return bd.year + (6 if (bd.month, bd.day) <= (4, 1) else 7)


def child_milestones(bd: date, gender: str = "") -> list[tuple[str, date]]:
    """子の生年月日から、入園〜高校卒業＋成人の行事と日付を生成する。

    入学/入園は4月上旬、卒業/卒園は3月中旬で近似。
    大学は入学年齢が人により違うため入れない。
    振袖の予約は女性のみ・成人式の半年前。
    """
    e = _elementary_entry_year(bd)
    coming_of_age = _coming_of_age_day(bd.year + 20)
    items = [
        ("幼稚園入園", date(e - 3, 4, 8)),   # 3年保育の年少を想定
        ("幼稚園卒園", date(e, 3, 15)),
        ("小学校入学", date(e, 4, 8)),
        ("小学校卒業", date(e + 6, 3, 15)),
        ("中学校入学", date(e + 6, 4, 8)),
        ("中学校卒業", date(e + 9, 3, 15)),
        ("高校入学", date(e + 9, 4, 8)),
        ("高校卒業", date(e + 12, 3, 15)),
        ("成人（二十歳のつどい）", coming_of_age),
    ]
    if gender == "female":   # 振袖は予約が早いので成人式の半年前に
        items.append(("振袖の予約", coming_of_age - timedelta(days=180)))
    return items


def _next_from_fn(fn, today: date) -> date:
    d = fn(today.year)
    return d if d >= today else fn(today.year + 1)


def _next_md(month: int, day: int, today: date) -> date:
    """次に来る MM-DD の日付（今年か来年）。2/29 は 2/28 に丸める。"""
    def make(y):
        try:
            return date(y, month, day)
        except ValueError:
            return date(y, month, 28)
    d = make(today.year)
    return d if d >= today else make(today.year + 1)


def _parse_md(birthday: str) -> tuple[int, int] | None:
    b = birthday.strip()
    if not b:
        return None
    parts = (b[5:] if len(b) >= 10 else b).split("-")
    try:
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return None


def _stage(days: int) -> str | None:
    if days < 0:
        return None
    if days == 0:
        return "today"
    if days <= FINAL_MAX:
        return "final"
    if days <= PUSH_MAX:
        return "push"
    if days <= NOTICE_MAX:
        return "notice"
    return None


# 当日のお祝い文
_CELEBRATE = {
    "誕生日": "🎂 今日は{who}の誕生日！おめでとう㊗️",
    "記念日": "💕 今日は{who}との記念日。おめでとう！",
    "母の日": "🌷 今日は母の日。{who}にありがとうを。",
    "父の日": "👔 今日は父の日。{who}にありがとうを。",
    "敬老の日": "🎍 今日は敬老の日。{who}にありがとうを。",
    "バレンタイン": "💝 今日はバレンタイン。{who}に気持ちを。",
    "ホワイトデー": "🍬 今日はホワイトデー。{who}にお返しを。",
    "クリスマス": "🎄 メリークリスマス！",
    "お中元": "🎁 お中元の時期です。",
    "お歳暮": "🎁 お歳暮の時期です。",
}


def _message(stage: str, occasion: str, who: str, days: int) -> str:
    # 振袖は「配送」ではなく「予約」が肝なので専用メッセージ
    if occasion == "振袖の予約":
        if stage == "today":
            return f"👘 {who}の振袖、そろそろ予約を。成人式は約半年後、人気の柄は早く埋まります。"
        return f"👘 {who}の振袖予約を検討しどき（成人式の約半年前）。あと{days}日で本格シーズン。"
    if stage == "today":
        return _CELEBRATE.get(occasion, "今日は{who}の" + occasion).format(who=who or "")
    give_to = {"母の日", "父の日", "敬老の日", "バレンタイン", "ホワイトデー"}
    if not who:
        target = occasion
    elif occasion == "記念日":
        target = f"{who}との記念日"
    elif occasion in give_to:
        target = f"{who}への{occasion}"
    else:
        target = f"{who}の{occasion}"   # 誕生日・学校行事・成人など本人の行事
    if stage == "notice":
        return f"{target}まであと{days}日。そろそろ考えてみる？"
    if stage == "push":
        return f"{target}まであと{days}日。配送が混む前に注文を（手作りなら今から着手）。"
    if stage == "final":
        return f"{target}まであと{days}日。最終確認を。"
    return ""


def upcoming(people: list[dict], today: date, occasions: list[dict] | None = None) -> list[dict]:
    """表示すべきリマインドを近い順で返す。occasions=一回きりのカスタム予定。"""
    out: list[dict] = []
    people_by_id = {p["id"]: p for p in people}

    def add(d: date, occasion: str, person: dict | None):
        days = (d - today).days
        stage = _stage(days)
        if stage is None:
            return
        who = person["name"] if person else ""
        out.append({
            "occasion": occasion,
            "date": d.isoformat(),
            "days": days,
            "stage": stage,
            "person_id": person["id"] if person else None,
            "name": who,
            "icon": person["icon"] if person else {"クリスマス": "🎄", "お中元": "🎁", "お歳暮": "🎁"}.get(occasion, "🎁"),
            "color": person["color"] if person else "#e8638c",
            "message": _message(stage, occasion, who, days),
        })

    for p in people:
        md = _parse_md(p.get("birthday", ""))
        if md:
            add(_next_md(md[0], md[1], today), "誕生日", p)
        amd = _parse_md(p.get("anniversary", ""))
        if amd:
            add(_next_md(amd[0], amd[1], today), "記念日", p)
        rel = p.get("relation")
        if rel == "mother":
            add(_next_from_fn(_mothers_day, today), "母の日", p)
        if rel == "father":
            add(_next_from_fn(_fathers_day, today), "父の日", p)
        if rel in ("grandmother", "grandfather"):
            add(_next_from_fn(_keiro_day, today), "敬老の日", p)
        if rel == "partner":
            add(_next_md(2, 14, today), "バレンタイン", p)
            add(_next_md(3, 14, today), "ホワイトデー", p)
        # 子・孫は生年月日から学校行事＋成人を自動生成（一回きりの日付）
        if rel in ("child", "grandchild"):
            bd = _full_date(p.get("birthday", ""))
            if bd:
                gender = resolve_gender(rel, p.get("gender", ""))
                for occ, d in child_milestones(bd, gender):
                    add(d, occ, p)

    # 一回きりのカスタム予定（出産祝い等）
    for o in (occasions or []):
        d = _full_date(o.get("date", ""))
        if d:
            add(d, o.get("label", "お祝い"), people_by_id.get(o.get("person_id")))

    # 全体向け（人に紐づけない）
    add(_next_md(12, 25, today), "クリスマス", None)
    add(_next_md(7, 1, today), "お中元", None)
    add(_next_md(12, 1, today), "お歳暮", None)

    out.sort(key=lambda r: r["days"])
    return out
