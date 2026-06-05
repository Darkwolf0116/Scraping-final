"""RAG por inyección de contexto: busca, arma el prompt y genera con gemma (Ollama).

Es el núcleo reutilizable del bot: `answer(query)` funciona sin Telegram, lo que
permite verificar la cadena completa (búsqueda -> gemma) de forma directa.

El system prompt (la "persona" y las reglas anti-alucinación) se lee del manifiesto
del agente `agents/public_agent.toml`: fuente única, compartida con OpenFang.
"""

from __future__ import annotations

import tomllib

from .index import search
from .llm import chat
from .paths import AGENT_MANIFEST

# Umbral de relevancia: por debajo se descarta como "sin coincidencia útil".
# (Consultas pertinentes puntúan ~0.5-0.75; ajenas al corpus ~0.2.)
MIN_SCORE = 0.35
TOP_K = 4

_FALLBACK_SYSTEM = (
    "Eres el asistente virtual de la Fundación Valle del Lili. Responde ÚNICAMENTE "
    "con la información del CONTEXTO proporcionado; si no está, di que no la tienes. "
    "No inventes datos. Responde en español."
)


def _load_system_prompt() -> str:
    try:
        with open(AGENT_MANIFEST, "rb") as f:
            return tomllib.load(f)["model"]["system_prompt"]
    except Exception:  # noqa: BLE001
        return _FALLBACK_SYSTEM


SYSTEM = _load_system_prompt()


def retrieve(query: str, k: int = TOP_K) -> list[dict]:
    """Devuelve los fragmentos relevantes (score >= MIN_SCORE)."""
    return [r for r in search(query, k=k) if r["score"] >= MIN_SCORE]


def build_messages(query: str, results: list[dict]) -> list[dict]:
    if results:
        ctx = "\n\n---\n\n".join(r["text"] for r in results)
    else:
        ctx = "(No se encontró información en la base de conocimiento de la Fundación.)"
    user = (
        "CONTEXTO (fragmentos de la base de conocimiento de la Fundación Valle del Lili):\n"
        f"{ctx}\n\n"
        f"PREGUNTA DEL USUARIO: {query}"
    )
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def answer(query: str, k: int = TOP_K) -> str:
    """Responde la consulta: recupera contexto y lo redacta con gemma (Ollama)."""
    results = retrieve(query, k=k)
    return chat(build_messages(query, results))
