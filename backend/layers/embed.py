"""embedding（Fit計算用）。Gemini の無料 embedding API を使う（依存ライブラリ不要）。

転売ツールの名寄せ層と同じ技術。GEMINI_API_KEY が無ければ None を返し、
③選定層は部分一致Fitに自動フォールバックする（鍵ゼロでも動く）。
同じテキストは使い回す（プロセス内キャッシュ）＝楽天の人気商品が重複しても無駄打ちしない。
"""

from __future__ import annotations

import json
import math
import os
import urllib.request

from ..models import Item, RecipientProfile

EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")   # 多言語・無料枠
_cache: dict[str, list[float]] = {}


def cosine(a: list[float], b: list[float]) -> float:
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return s / (na * nb) if na and nb else 0.0


def _batch_embed(texts: list[str], key: str) -> list[list[float]]:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{EMBED_MODEL}:batchEmbedContents?key={key}")
    body = {"requests": [
        {"model": f"models/{EMBED_MODEL}", "content": {"parts": [{"text": t}]}}
        for t in texts
    ]}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode("utf-8"))
    return [e["values"] for e in data["embeddings"]]


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """テキスト群をベクトル化。鍵なし/失敗時は None（→部分一致フォールバック）。"""
    key = os.getenv("GEMINI_API_KEY")
    if not key or not texts:
        return None
    out: list[list[float] | None] = [None] * len(texts)
    missing, idx = [], []
    for i, t in enumerate(texts):
        if t in _cache:
            out[i] = _cache[t]
        else:
            missing.append(t); idx.append(i)
    if missing:
        try:
            vecs = _batch_embed(missing, key)
        except Exception as e:
            print(f"[embed] 失敗→部分一致Fitで継続: {e}")
            return None
        for n, t in enumerate(missing):
            _cache[t] = vecs[n]
            out[idx[n]] = vecs[n]
    return out  # type: ignore[return-value]


def attach_embeddings(profile: RecipientProfile, items: list[Item]) -> None:
    """相手像と候補商品にベクトルを付与（ベストエフォート。失敗なら付けない＝Fitは部分一致）。"""
    texts = [profile.text()] + [it.text() for it in items]
    vecs = embed_texts(texts)
    if not vecs:
        return
    profile.embedding = vecs[0]
    for it, v in zip(items, vecs[1:]):
        it.embedding = v
