#!/usr/bin/env python
"""Prueba de humo de la cadena RAG -> gemma (Ollama), sin Telegram.

Verifica:
  - Ollama responde,
  - la recuperación devuelve contexto para consultas del dominio,
  - una consulta fuera de dominio NO recupera contexto (el bot debe decir que no sabe).

Uso: uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.answer import answer, retrieve  # noqa: E402
from rag.llm import health  # noqa: E402

QUERIES = [
    "¿Qué incluye el chequeo médico preventivo Gold?",
    "¿Qué enfermedades trata el servicio de alergología?",
    "¿Cuál es la capital de Francia?",  # fuera de dominio -> debe responder que no sabe
]


def main() -> None:
    print("Ollama health:", health())
    for q in QUERIES:
        res = retrieve(q)
        print("\n" + "=" * 72)
        print("Q:", q)
        print("recuperados:", len(res), "scores:", [r["score"] for r in res[:5]])
        print("A:", answer(q))


if __name__ == "__main__":
    main()
