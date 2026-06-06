"""Índice vectorial local en SQLite + búsqueda por similitud de coseno."""

from __future__ import annotations

import json
import os
import sqlite3

import numpy as np

from .embeddings import active_model, embed, embed_one
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
            [("embedding_model", model or active_model()), ("dim", str(dim)), ("count", str(len(chunks)))],
        )
        conn.commit()
    finally:
        conn.close()
    return len(chunks), dim


# Caché en memoria del índice: {path: (mtime, (meta, matriz_normalizada))}
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


def search_vec(qvec, k: int = 5, seccion: str | None = None, path: str = INDEX_PATH) -> list[dict]:
    """Ranking por coseno a partir de un vector de consulta YA calculado.

    Permite reutilizar un mismo embedding para varias búsquedas (p. ej. general
    + filtrada por sección) sin re-embeber, lo que ahorra llamadas.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Índice no encontrado: {path}. Ejecuta: uv run python scripts/ingest_docs.py"
        )
    meta, mat = _load(path)
    if not meta:
        return []
    q = np.asarray(qvec, dtype=np.float32)
    nq = np.linalg.norm(q)
    if nq > 0:
        q = q / nq
    scores = mat @ q
    order = np.argsort(-scores)
    results: list[dict] = []
    for i in order:
        i = int(i)
        if seccion and meta[i]["seccion"] != seccion:
            continue
        item = dict(meta[i])
        item["score"] = round(float(scores[i]), 4)
        results.append(item)
        if len(results) >= max(1, k):
            break
    return results


def search(query: str, k: int = 5, seccion: str | None = None, path: str = INDEX_PATH, model: str | None = None) -> list[dict]:
    """Embede la consulta y devuelve los k chunks más similares (con score)."""
    return search_vec(embed_one(query, model=model), k=k, seccion=seccion, path=path)
