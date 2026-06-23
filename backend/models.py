"""データモデル（仕様書 §4）。

Phase1で実際に使うものだけ実装。GiftEvent などは席だけ用意して中身は触らない。
すべて dataclass で軽量に持つ（DB はまだ使わない）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# 関係から自明に決まる性別（母・祖母＝女性、父・祖父＝男性）。
# それ以外（パートナー/友人/子/孫/きょうだい/その他）は登録時に手入力。
RELATION_GENDER = {
    "mother": "female", "grandmother": "female",
    "father": "male", "grandfather": "male",
}

# 関係の日本語ラベル（名前が未入力のとき表示名に使う）
RELATION_LABEL = {
    "mother": "母", "father": "父", "grandmother": "祖母", "grandfather": "祖父",
    "partner": "パートナー", "friend": "友人", "child": "子ども", "grandchild": "孫",
    "sibling": "きょうだい", "other": "相手",
}


def display_name(person: dict) -> str:
    """名前が無ければ関係名（「母」等）で成り立たせる。"""
    name = (person.get("name") or "").strip()
    return name or RELATION_LABEL.get(person.get("relation", ""), "相手")


def resolve_gender(relation: str, gender: str = "") -> str:
    """明示の性別があればそれを、無ければ関係から推定する。"""
    return gender or RELATION_GENDER.get(relation, "")


# --- ② 取得層が返す共通スキーマ（実在商品 1件） ---
@dataclass
class Item:
    title: str
    price: int                     # 実売価格（セール中ならセール価格）
    in_stock: bool
    rating: float          # 0.0〜5.0
    review_count: int
    url: str
    image_url: str
    category: str
    description: str = ""
    list_price: int = 0                  # 通常価格（0=不明）。安すぎ判定はこちらで見る
    target_gender: str = ""              # ""=男女問わず / "female" / "male"
    ranking_rank: Optional[int] = None   # ランキング順位（あれば）
    is_new: bool = False
    # type: 買えるもの / 体験 / 手作り（非ECは "experience" | "make"）
    type: str = "buy"

    def text(self) -> str:
        """Fit 計算や類似度に使うテキスト（title + 説明 + カテゴリ）。"""
        return f"{self.title} {self.description} {self.category}"


# --- ① ヒアリング層の出力：相手像 ---
@dataclass
class RecipientProfile:
    relation: str = "mother"        # 関係性
    gender: str = ""                # "female" | "male" | "other"
    age_band: str = "60s"           # 年代
    free_text: list[str] = field(default_factory=list)   # 自由記述（燃料）
    likes: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    # embedding は後で（Fit を embedding に差し替えるときに使う）

    def text(self) -> str:
        return " ".join(self.free_text + self.likes)


# --- ① ヒアリング層の出力：検索意図 ---
@dataclass
class SearchIntent:
    keywords: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    budget_min: int = 0
    budget_max: int = 100_000
    # delivery_deadline は Phase1 ではゲートで簡易扱い（在庫のみ見る）


# --- 登録した相手（仕様書 §4 Person） ---
@dataclass
class Person:
    id: str
    name: str
    relation: str = "mother"
    gender: str = ""                # "female" | "male" | "other"（登録必須）
    birthday: str = ""              # "MM-DD" or "YYYY-MM-DD"（年は任意）
    anniversary: str = ""           # 記念日（結婚・交際など）"MM-DD" or "YYYY-MM-DD"
    age_band: str = "60s"
    icon: str = "🎁"               # アバターのアイコンキー（写真が無い時に表示）
    photo_url: str = ""            # 顔写真（data URL）。あれば優先表示・プレミアム特典
    color: str = "#e8638c"
    notes: str = ""                # 自由記述（RecipientProfile.free_text の素）
    likes: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)


# --- 贈答イベント（あげた/もらったを同一構造で / 仕様書 §4 GiftEvent） ---
@dataclass
class GiftEvent:
    id: str
    person_id: str
    direction: str                 # "gave" | "received"
    title: str
    category: str = ""
    price: int = 0
    source_url: str = ""
    reaction: str = ""             # 喜ばれ度合い・メモ（gave のとき）
    date: str = ""                 # "YYYY-MM-DD"
    photo_url: str = ""            # 写真（data URL）。記録は有料会員のみ


# --- ④ 語り層の出力：提案カード1枚 ---
@dataclass
class SuggestionCard:
    name: str
    type: str               # "buy" | "experience" | "make"
    reason: str
    evidence: list[str]     # 使った実データ点
    url: str
    image_url: str
    price: int
