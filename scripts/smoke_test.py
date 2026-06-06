#!/usr/bin/env python
"""Prueba de humo del bot: RAG local -> Gemini, con costo REAL por consulta.

Verifica calidad, recuperación de especialistas, datos corporativos y costo.
Uso: uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.answer import answer, retrieve  # noqa: E402
from rag.llm import LAST_USAGE, estimate_cost_usd, health  # noqa: E402

QUERIES = [
    "¿Qué incluye el chequeo médico preventivo Gold?",
    "¿Qué cardiólogos atienden en la Fundación?",          # especialistas (refuerzo)
    "¿Cuáles son las sedes y sus horarios de atención?",   # datos corporativos
    "¿Quién ganó el mundial de fútbol de 2022?",           # fuera de dominio -> no sabe
]


def main() -> None:
    print("chat health:", health())
    total_usd = 0.0
    for q in QUERIES:
        res = retrieve(q)
        secs: dict = {}
        for r in res:
            secs[r["seccion"]] = secs.get(r["seccion"], 0) + 1
        print("\n" + "=" * 72)
        print("Q:", q)
        print("recuperados:", len(res), "por sección:", secs)
        print("A:", answer(q))
        if LAST_USAGE:
            inp = LAST_USAGE.get("input", 0)
            out = LAST_USAGE.get("output", 0) + LAST_USAGE.get("thoughts", 0)
            usd = estimate_cost_usd(LAST_USAGE.get("model", ""), inp, out)
            total_usd += usd
            print(f"[costo] tokens in/out={inp}/{out}  ~${usd:.6f}  (~COP {usd * 4000:.2f})")
    print("\n" + "=" * 72)
    print(f"TOTAL {len(QUERIES)} consultas: ~COP {total_usd * 4000:.1f}   (antes: ~COP 3000 por 8 con OpenFang)")


if __name__ == "__main__":
    main()
