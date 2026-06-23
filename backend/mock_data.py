"""② 取得層のダミーデータ（楽天APIの代役）。

ここは「実在風」の母の日商品を手で並べただけのもの。
本物の楽天 Web Service API に差し替えるときは acquire.py の fetch_candidates() を
書き換えるだけで、ここは丸ごと不要になる。
価格・レビュー・在庫・ランキング・新着フラグの形を本物と揃えてある。
"""

from .models import Item

# 母の日の候補プール（買えるもの中心 + 体験/手作りのアイデアも少し）
MOCK_ITEMS: list[Item] = [
    Item(
        title="今治タオル 上質ギフトセット 化粧箱入り",
        price=4800, in_stock=True, rating=4.6, review_count=1280,
        ranking_rank=2, is_new=False, category="タオル・日用品",
        description="ふんわり厚手のフェイスタオル2枚セット。毎日使える上質な定番ギフト。",
        url="https://example.com/imabari-towel", image_url="https://picsum.photos/seed/towel/400/300",
        type="buy",
    ),
    Item(
        title="ワイヤレスイヤホン ノイズキャンセリング",
        price=8900, in_stock=True, rating=4.3, review_count=540,
        ranking_rank=12, is_new=True, category="家電・オーディオ",
        description="音楽・ライブ映像の鑑賞に。長時間バッテリーと高音質。",
        url="https://example.com/earbuds", image_url="https://picsum.photos/seed/earbuds/400/300",
        type="buy",
    ),
    Item(
        title="名入れ 有田焼マグカップ",
        price=3500, in_stock=True, rating=4.7, review_count=8,
        ranking_rank=None, is_new=False, category="食器・キッチン",
        description="名前を入れられる職人の有田焼。無難な定番の名入れギフト。",
        url="https://example.com/mug", image_url="https://picsum.photos/seed/mug/400/300",
        type="buy",
    ),
    Item(
        title="プリザーブドフラワー BOXアレンジ 母の日カード付き",
        price=5200, in_stock=True, rating=4.5, review_count=2100,
        ranking_rank=1, is_new=False, category="花・ギフト",
        description="枯れずに長く飾れる花。母の日の鉄板で満足度が高い。",
        url="https://example.com/flower", image_url="https://picsum.photos/seed/flower/400/300",
        type="buy",
    ),
    Item(
        title="高級ハンドクリーム 3種アソート",
        price=2600, in_stock=True, rating=4.4, review_count=730,
        ranking_rank=20, is_new=False, category="コスメ・美容",
        description="香り違いの保湿ハンドクリーム。気軽に使えるご褒美コスメ。",
        url="https://example.com/handcream", image_url="https://picsum.photos/seed/cream/400/300",
        type="buy",
    ),
    Item(
        title="お取り寄せ スイーツ 抹茶テリーヌ",
        price=3800, in_stock=True, rating=4.8, review_count=960,
        ranking_rank=5, is_new=True, category="スイーツ・グルメ",
        description="濃厚な抹茶の焼き菓子。コーヒー・お茶好きに刺さる新作スイーツ。",
        url="https://example.com/sweets", image_url="https://picsum.photos/seed/sweets/400/300",
        type="buy",
    ),
    Item(
        title="ノイズ少なめ 卓上加湿器（在庫切れ）",
        price=4200, in_stock=False, rating=4.1, review_count=300,
        ranking_rank=None, is_new=False, category="家電・オーディオ",
        description="在庫切れ。ゲートで弾かれることの確認用ダミー。",
        url="https://example.com/humidifier", image_url="https://picsum.photos/seed/humid/400/300",
        type="buy",
    ),
    Item(
        title="激安ノーブランド靴下 5足組",
        price=900, in_stock=True, rating=2.7, review_count=40,
        ranking_rank=None, is_new=False, category="ファッション",
        description="評価が地雷ライン未満。ゲートで弾かれることの確認用ダミー。",
        url="https://example.com/socks", image_url="https://picsum.photos/seed/socks/400/300",
        type="buy",
    ),
    Item(
        title="美術館・庭園めぐり ペアチケット（体験）",
        price=6000, in_stock=True, rating=4.6, review_count=150,
        ranking_rank=None, is_new=False, category="体験・チケット",
        description="一緒に出かける時間そのものを贈る体験ギフト。落ち着いた趣味の人に。",
        url="https://www.google.com/search?q=美術館+ペアチケット+母の日", image_url="https://picsum.photos/seed/museum/400/300",
        type="experience",
    ),
    Item(
        title="メンズ 本革 二つ折り財布",
        price=7800, in_stock=True, rating=4.5, review_count=620,
        ranking_rank=8, is_new=False, category="ファッション小物",
        description="使うほど味が出る本革財布。落ち着いた色で長く使える。",
        url="https://example.com/wallet", image_url="https://picsum.photos/seed/wallet/400/300",
        type="buy", target_gender="male",
    ),
    Item(
        title="レディース シルク調 スカーフ",
        price=5400, in_stock=True, rating=4.4, review_count=410,
        ranking_rank=15, is_new=True, category="ファッション小物",
        description="顔まわりが華やぐ上品なスカーフ。装いのアクセントに。",
        url="https://example.com/scarf", image_url="https://picsum.photos/seed/scarf/400/300",
        type="buy", target_gender="female",
    ),
    Item(
        title="ブランド紅茶 詰め合わせ（タイムセール）",
        price=1780, in_stock=True, rating=4.6, review_count=520,
        list_price=3200, ranking_rank=18, is_new=False, category="スイーツ・グルメ",
        description="通常3,200円が今だけセール。お茶好きに喜ばれる定番の詰め合わせ。",
        url="https://example.com/tea-sale", image_url="https://picsum.photos/seed/tea/400/300",
        type="buy",
    ),
    # 注意: 手作り(make)は商品として提案しない（カタログに置かない）。
    #       手作りは layers/handmade.py の「一緒に考える」相談フローで扱う。
]
