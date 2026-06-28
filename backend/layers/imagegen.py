"""手作りギフトの「完成イメージ」生成（Gemini 画像生成 / 有料会員向け）。

方針：手描き・イラスト風で固定（実物との差で期待外れになりにくい・温かい）。
既製品やロゴ・文字は描かせない。鍵が無い/失敗時は None（呼び出し側で丁寧に案内）。
"""

from __future__ import annotations

import base64
import json
import os
import urllib.request

_MODEL = "gemini-2.5-flash-image"   # 画像生成対応モデル（要・クレジット）


def _prompt(title: str, materials: list[str]) -> str:
    mats = "、".join([m for m in (materials or []) if m][:5])
    base = f"手作りの「{title}」の完成イメージ。"
    if mats:
        base += f"{mats}などを使った、"
    base += (
        "温かみのある手作りギフト。やわらかい水彩イラスト風、手描きの優しい雰囲気、"
        "淡い色合い、背景はシンプル。実在のブランドロゴや既製品パッケージは描かない。"
        "文字や文章は一切入れない。"
    )
    return base


def generate(title: str, materials: list[str] | None = None) -> bytes | None:
    """完成イメージのPNGバイト列を返す。鍵無し/失敗時は None。"""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    try:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{_MODEL}:generateContent?key={key}")
        body = {
            "contents": [{"parts": [{"text": _prompt(title, materials or [])}]}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as res:
            data = json.loads(res.read().decode("utf-8"))
        for part in data["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                return base64.b64decode(part["inlineData"]["data"])
        return None
    except Exception as e:
        print(f"[imagegen] 失敗: {e}")
        return None
