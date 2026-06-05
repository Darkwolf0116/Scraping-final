"""Embeddings vía la API local de Ollama (mismo modelo en ingesta y consulta)."""

from __future__ import annotations

import requests

from .env import EMBEDDING_MODEL, OLLAMA_BASE_URL


def embed(texts, model: str | None = None, batch_size: int = 16) -> list[list[float]]:
    """Devuelve los vectores de embedding de ``texts`` (str o lista de str)."""
    if isinstance(texts, str):
        texts = [texts]
    model = model or EMBEDDING_MODEL
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/embed",
            json={"model": model, "input": batch},
            timeout=300,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings")
        if not embeddings:
            raise RuntimeError(f"Ollama no devolvió embeddings (modelo {model!r}): {data}")
        out.extend(embeddings)
    return out


def embed_one(text: str, model: str | None = None) -> list[float]:
    return embed([text], model=model)[0]
