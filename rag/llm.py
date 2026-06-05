"""Generación directa con gemma vía Ollama (/api/chat).

OpenFang infla el prompt (~20K tokens de skills + bucle de agente) y desborda a
gemma4:e4b (4B local), que colapsa devolviendo "I". Para un modelo local, el
camino fiable es hablar con Ollama directamente con un prompt corto y controlado.
"""

from __future__ import annotations

import requests

from .env import AGENT_MODEL, OLLAMA_BASE_URL


def health(timeout: int = 3) -> bool:
    """True si el servidor de Ollama responde."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=timeout)
        return r.status_code == 200
    except requests.RequestException:
        return False


def chat(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.2,
    num_ctx: int = 8192,
    num_predict: int = 768,
    timeout: int = 300,
) -> str:
    """Completa un chat con gemma vía Ollama y devuelve el texto de la respuesta.

    num_ctx holgado (8192) para que el system + contexto RAG + pregunta no se trunquen.
    """
    model = model or AGENT_MODEL
    r = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            },
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["message"]["content"].strip()
