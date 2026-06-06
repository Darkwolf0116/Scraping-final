"""Embeddings para el RAG con Google Gemini (único proveedor).

La interfaz embed()/embed_one() la comparten rag/index.py y el resto del RAG.
Los embeddings de Gemini son muy baratos; solo se consumen al ingerir documentos
y al resolver una consulta (un vector por pregunta).
"""

from __future__ import annotations

from .env import GEMINI_API_KEY, GEMINI_EMBEDDING_MODEL

_GEMINI_BATCH_SIZE = 100  # límite de la API


def active_model() -> str:
    """Nombre del modelo de embeddings activo (para registrar en el índice)."""
    return GEMINI_EMBEDDING_MODEL


def _gemini_embed(texts: list[str], model: str | None = None) -> list[list[float]]:
    import re
    import time

    from google import genai as gemini_client
    from google.genai.errors import ClientError

    if not GEMINI_API_KEY:
        raise RuntimeError("Falta GEMINI_API_KEY: define tu API key de Gemini en .env")

    client = gemini_client.Client(api_key=GEMINI_API_KEY)
    model = f"models/{model or GEMINI_EMBEDDING_MODEL}"
    out: list[list[float]] = []
    for i in range(0, len(texts), _GEMINI_BATCH_SIZE):
        batch = texts[i : i + _GEMINI_BATCH_SIZE]
        for attempt in range(5):
            try:
                result = client.models.embed_content(model=model, contents=batch)
                out.extend(e.values for e in result.embeddings)
                break
            except ClientError as e:
                if e.code != 429:
                    raise
                m = re.search(r"retry\s+in\s+(\d+(?:\.\d+)?)\s*s", str(e))
                wait = float(m.group(1)) + 1 if m else float(2 ** attempt)
                print(f"  límite de cuota alcanzado, esperando {wait:.0f}s...")
                time.sleep(wait)
        else:
            raise RuntimeError(f"Embedding falló tras 5 intentos (batch {i // _GEMINI_BATCH_SIZE})")
    return out


def embed(texts, model: str | None = None) -> list[list[float]]:
    """Vectores de embedding con Gemini."""
    if isinstance(texts, str):
        texts = [texts]
    return _gemini_embed(texts, model=model)


def embed_one(text: str, model: str | None = None) -> list[float]:
    return embed([text], model=model)[0]
