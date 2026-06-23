# プレゼント提案エンジン — 進捗メモ（再開はここを読む）

## いまどこ？
**Phase1 walking skeleton ＋ UI（人/カレンダー/贈答履歴/学習）完成。鍵ゼロで動く。**
2026-06-23 時点。

UI 3画面（タブ式）：
- 🎁 **提案**：相手を選んで提案。履歴から学習した語・被り回避件数を表示
- 👪 **人**：相手を登録（名前/関係/誕生日/絵文字アイコン/色/メモ/避けたいもの）＋贈答記録
- 📅 **カレンダー**：誕生日にその人のアイコン、🎁で贈答日。誕生日タップ→その人の提案へ

**デザイン**：案B（クリーム＆クレイ＝Claude風・セリフ見出し）が標準。右上⚙️設定で案D（ダーク）に切替。
- テーマはCSS変数。`body.theme-dark`で全変数を上書き。選択は localStorage("theme")。
- 4案の見本は `mockups/`（gallery.html）。案A=ローズ/案C=ミニマルも残してある。
- **アイコンはオリジナルSVG線画に差し替え済み**（`frontend/icons.js`：`icon(key,size)` / `OCCASION_ICON` / `AVATARS`）。
  currentColorでテーマ自動追従。絵文字は廃止（タブ/ギア/アバター/行事/カレンダー/手作り等）。
  人の`icon`は絵文字でなくキー（woman/man/music…）。旧データは移行済み。
  見本：mockups/icons_sample.html、再生成比較：mockups/icons_v1_vs_v2.html。

**ゼロ提案は絶対に出さない（最重要UX）**：
- `select()` はフォールバック階段（予算→評価→性別→avoid/dup の順に緩める／在庫＝届くことは死守）。
  在庫候補が1つでもあれば必ず非空。返り値は (選定, relax_level)。
- 緩めた時は `RELAX_NOTES` で正直に一言（例「ご予算では少なかったので少し上の価格帯も含めました」）。
- 万一候補ゼロ(relax_level=-1)でも行き止まりにせず `followup`（追い質問＋予算を広げて再提案ボタン）。
- 「条件に合う提案が見つかりませんでした」の冷たい表示は廃止。
- 動作確認：予算500円でも5件返ることを確認。

**手作り(make)の扱い（重要方針）**：
- 手作りは**商品提案しない**（カタログ/購入リンク/検索リンクを出さない・儲けゼロ）。
- 提案結果の下に「🎨 手作りを一緒に考える」導線。`POST /api/handmade`。
  - want空欄 → 相手の好みに合わせた“作る方向”を提案（`layers/handmade.py:suggest_ideas`）
  - want指定 → 一緒に詰める質問を返す（`plan_for`）
- 本格的な対話は Claude 差し替え前提（いまテンプレ）。

**リマインド（実装済み・ブラウザ内表示）**：4段階。`GET /api/reminders` → トップに帯表示。
- 1か月前=お知らせ / 2週間前=念押し(配送・手作り着手) / 3日前=最終確認 / 当日=お祝い
- 対象行事：
  - 本人：誕生日 / 記念日(結婚・交際💕)
  - 関係で自動：母の日(5月第2日曜=mother) / 父の日(6月第3日曜=father) / 敬老の日(9月第3月曜=grand親)
    / バレンタイン2-14・ホワイトデー3-14(partner)
  - 全体：クリスマス12-25 / お中元7-1 / お歳暮12-1
  - 子・孫(child/grandchild)＝**生年月日から学校行事を自動生成**：
    幼稚園入園(年少)・卒園・小/中/高の入学卒業・成人(二十歳のつどい=1月第2月曜)。大学は入学年齢が人で違うので除外。
    学齢は4/1基準（1/1〜4/1生まれ=誕生年+6、4/2〜=+7）。`child_milestones()`。
- 言い回し：贈る系は「○○への母の日」、本人の行事は「○○の誕生日/入学」、記念日は「○○との記念日」。
- カップル層＋祖父母→孫を主要ターゲットに想定。relation に grandchild(孫) 追加。
- 振袖の予約：女性のみ・成人式の半年前にリマインド（専用メッセージ。配送でなく予約が肝）。
- 一回きりの予定（出産祝い等）：人ごとに選択肢から登録（手打ちは「その他」のみ）。
  `store.occasions` / `GET·POST /api/occasions` `DELETE /api/occasions/{id}`。reminders に合流。

**性別（登録必須）**：
- Person.gender = female/male/other。関係から自明な時(母/祖母=女, 父/祖父=男)は**入力欄を出さない**（`AUTO_GENDER`/`resolve_gender`）。
- 提案アイテムが性別で変わる：Item.target_gender とゲートで不一致を除外（男女問わずは常に通す）。mock に男性=財布/女性=スカーフのデモ商品あり。
- ロジック：`backend/layers/reminders.py`。しきい値 NOTICE_MAX/PUSH_MAX/FINAL_MAX で調整可
- プッシュ通知はアプリ化(Capacitor)段階で本物に。今はブラウザ内のみ
- 動作確認：当日/3日/14日/30日の4段階を確認済み（実データは窓内に無ければ空表示）

**学習ループ（実装済み・ルールベース）**：
- もらった → タイトル/カテゴリを好みヒントに（Fit が拾う）
- あげた → 被り回避（同一＋酷似 sim≥0.5 をゲートで除外／Novelty で別カテゴリ加点）
保存は `data/store.json`（people[] / events[]）。

```
①ヒアリング → ②取得 → ③選定(ゲート→スコア→MMR) → ④語り → 提案3〜5件
```

実際に動く：フォーム入力 → 提案カード3〜5件（理由＋実データ根拠＋リンク）が出る。

## 起動方法
```
cd C:\Users\eriyo\gift_advisor
python -m uvicorn backend.app:app --reload --port 8011
```
ブラウザ（Chrome）で http://127.0.0.1:8011/ を開く。

## ファイル構成
```
gift_advisor/
  backend/
    app.py              APIゲートウェイ（提案 / people / events / 静的配信）
    models.py           データモデル（§4 ＋ Person / GiftEvent）
    store.py            JSON保存（data/store.json）DB不要
    mock_data.py        ②のダミー実在風データ（←楽天APIに差し替える場所）
    layers/
      acquire.py        ②取得層（fetch_candidates を本物APIに差し替え）
      select.py         ③選定層（ゲート→スコア→MMR / LLM不使用 / 本物ロジック）
      narrate.py        ④語り層（いまTemplateNarrator / ←Claudeに差し替え）
  frontend/
    index.html          タブ式UIの骨組み
    styles.css          見た目
    app.js              画面ロジック（提案/人/カレンダー/履歴/学習表示）
  data/store.json       登録データ（自動生成）
  requirements.txt      fastapi, uvicorn

API: GET/POST /api/people, DELETE /api/people/{id}
     GET/POST /api/events, DELETE /api/events/{id}
     POST /api/suggest（person_id を渡すと履歴学習＋被り回避が効く）
```

## いまの暫定（＝あとで本物に差し替える3か所）
1. **②データ**：`mock_data.py` のダミー → **楽天 Web Service API**。
   差し替えは `acquire.py:fetch_candidates()` の中だけ。`RAKUTEN_APP_ID` をenvで読む。
   → **次にやるならここが最優先**（仕様書の walking skeleton step1）。要：楽天アプリID取得。
2. **③Fit**：いま「相手の語が商品テキストに含まれるか（部分一致）」の暫定。
   → **embedding（multilingual-e5 等）の cosine** に差し替え。`select.py:_fit()`。
3. **④語り**：いまテンプレ文。→ **Claude** に差し替え。`narrate.py` の TODO 参照。
   抽象インターフェース `Narrator` 経由なので差し替えやすい。ガードレール（創作禁止）は実装済み方針。

## 仕様書どおり実装済みの要点
- ゲート：予算オーバー / 在庫なし / 評価★3.0未満 / 去年贈ったもの / avoid語 を足切り。
- スコア：`wF.40 wQ.25 wT.15 wN.10 wB.10`。Quality=レビューのベイズ補正+ランキング。
  Trend=新着/急上昇を**年代で重み可変**（高齢ほど定番寄り）。Budget=上限寄り加点。
- MMR（λ=0.7）で多様性。**最低1件は非EC（体験/手作り）**を強制。
- LLMは①深掘りと④語りの2か所だけ（②③では絶対使わない）。

## まだ作っていない（仕様書の残り）
- ①の動的深掘り質問（`POST /api/hearing/followup`）※未実装
- ③のNovelty/履歴注入（GiftEvent連携）※スコア式は用意、履歴入力はまだ
- Yahoo/Amazonルート、非ECの本物化
- Phase2（思い出アーカイブ/カレンダー/複数人/手紙/法人）は席のみ

## 動作確認済み
- 10候補 → ゲートで在庫切れ・低評価・予算オーバー除外 → 5件確定。
- 「音楽/お茶/甘いもの」入力 → お茶好きに刺さる抹茶テリーヌが1位に浮上（Fit効作動）。
