"""Índice vectorial local en SQLite + búsqueda por similitud de coseno."""

from __future__ import annotations

import json
import os
import sqlite3

import numpy as np

from .embeddings import EMBEDDING_MODEL, embed, embed_one
from .paths import INDEX_PATH


def _to_blob(vec) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def _from_blob(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)


def build(chunks, path: str = INDEX_PATH, model: str | None = None) -> tuple[int, int]:
    """Embede los chunks y (re)escribe el índice SQLite. Devuelve (n_chunks, dim)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    texts = [c.text for c in chunks]
    vecs = embed(texts, model=model) if texts else []
    dim = len(vecs[0]) if vecs else 0

    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """CREATE TABLE chunks(
                id INTEGER PRIMARY KEY,
                text TEXT, title TEXT, url TEXT, seccion TEXT,
                heading TEXT, categorias TEXT, source TEXT, embedding BLOB)"""
        )
        conn.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
        conn.executemany(
            "INSERT INTO chunks(text,title,url,seccion,heading,categorias,source,embedding)"
            " VALUES(?,?,?,?,?,?,?,?)",
            [
                (
                    c.text, c.title, c.url, c.seccion, c.heading,
                    json.dumps(c.categorias, ensure_ascii=False), c.source, _to_blob(v),
                )
                for c, v in zip(chunks, vecs)
            ],
        )
        conn.executemany(
            "INSERT INTO meta(key,value) VALUES(?,?)",
            [("embedding_model", model or EMBEDDING_MODEL), ("dim", str(dim)), ("count", str(len(chunks)))],
        )
        conn.commit()
    finally:
        conn.close()
    return len(chunks), dim


# Caché en memoria (el servidor MCP es de larga vida): {path: (mtime, (meta, matriz))}
_CACHE: dict = {}


def _load(path: str):
    mtime = os.path.getmtime(path)
    cached = _CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(
            "SELECT text,title,url,seccion,heading,categorias,embedding FROM chunks"
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        data = ([], None)
    else:
        meta = [
            {
                "text": r[0], "title": r[1], "url": r[2], "seccion": r[3],
                "heading": r[4], "categorias": json.loads(r[5] or "[]"),
            }
            for r in rows
        ]
        mat = np.vstack([_from_blob(r[6]) for r in rows]).astype(np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        data = (meta, mat / norms)
    _CACHE[path] = (mtime, data)
    return data


def search(query: str, k: int = 5, path: str = INDEX_PATH, model: str | None = None) -> list[dict]:
    """Devuelve los k chunks más similares a la consulta (con su score de coseno)."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Índice no encontrado: {path}. Ejecuta primero: uv run python scripts/ingest_docs.py"
        )
    meta, mat = _load(path)
    if not meta:
        return []
    q = np.asarray(embed_one(query, model=model), dtype=np.float32)
    nq = np.linalg.norm(q)
    if nq > 0:
        q = q / nq
    scores = mat @ q
    order = np.argsort(-scores)[: max(1, k)]
    results = []
    for i in order:
        item = dict(meta[int(i)])
        item["score"] = round(float(scores[int(i)]), 4)
        results.append(item)
    return results
