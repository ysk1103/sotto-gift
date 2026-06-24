"""HaikuとGeminiの「語り（理由文）」を同条件で出し比べる検証スクリプト。

同じ相手プロフィール・同じ商品を両モデルに渡し、生成された理由を並べて表示する。
鍵は .env（ANTHROPIC_API_KEY / GEMINI_API_KEY）から読む。片方しか無ければその片方だけ出す。

実行: python compare_narrators.py
"""

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from backend.app import _load_dotenv  # noqa: E402  (.env を読む副作用)
_load_dotenv()

from backend.layers.narrate import ClaudeNarrator, GeminiNarrator, TemplateNarrator  # noqa: E402
from backend.mock_data import MOCK_ITEMS  # noqa: E402
from backend.models import RecipientProfile  # noqa: E402

# 同じ入力（相手＋商品3点）を両モデルに渡す
profile = RecipientProfile(relation="mother", age_band="60s",
                           free_text=["音楽", "お茶", "甘いもの"])
items = [it for it in MOCK_ITEMS if it.type == "buy"][:3]

print("=" * 70)
print(f"相手: {profile.relation} / {profile.age_band} / 好き: {'・'.join(profile.free_text)}")
print("=" * 70)

runs = [("テンプレ(鍵不要)", TemplateNarrator())]
if os.getenv("ANTHROPIC_API_KEY"):
    runs.append(("Claude Haiku", ClaudeNarrator()))
else:
    print("※ ANTHROPIC_API_KEY 未設定 → Haikuはスキップ")
if os.getenv("GEMINI_API_KEY"):
    runs.append(("Gemini Flash", GeminiNarrator()))
else:
    print("※ GEMINI_API_KEY 未設定 → Geminiはスキップ")

results = {label: nar.narrate(profile, items) for label, nar in runs}

for i, it in enumerate(items):
    print(f"\n■ {it.title}（{it.price:,}円 / ★{it.rating}）")
    for label, _ in runs:
        print(f"  [{label}] {results[label][i].reason}")
