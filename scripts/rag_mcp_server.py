#!/usr/bin/env python
"""Servidor MCP (stdio) que expone la búsqueda RAG institucional a OpenFang.

OpenFang lo arranca como subproceso (config.toml -> [[mcp_servers]] type="stdio")
y la herramienta queda disponible para los agentes como:
    mcp_rag_buscar_institucional

El servidor consulta el índice vectorial local (data/rag_index.sqlite),
embebiendo la consulta con el mismo modelo de Ollama usado en la ingesta.
"""

from __future__ import annotations

import os
import sys

# Permite importar el paquete rag/ al ejecutarse como subproceso.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from rag.index import search  # noqa: E402

mcp = FastMCP("rag")

# Umbral de relevancia: por debajo se considera "sin coincidencia útil".
# (Consultas pertinentes puntúan ~0.5-0.65; ajenas al corpus ~0.2.)
MIN_SCORE = 0.35


@mcp.tool()
def buscar_institucional(query: str, k: int = 5) -> str:
    """Busca en la base de conocimiento de la Fundación Valle del Lili.

    Cubre sedes, especialistas, servicios/especialidades y páginas institucionales
    (p. ej. el chequeo médico preventivo). Úsala SIEMPRE antes de responder sobre
    horarios, sedes, especialistas, servicios o procedimientos. Devuelve los
    fragmentos más relevantes junto con su sección y URL de origen.

    Args:
        query: La pregunta o términos de búsqueda del usuario, en español.
        k: Número de fragmentos a devolver (por defecto 5).
    """
    try:
        results = search(query, k=k)
    except FileNotFoundError as e:
        return f"[error] {e}"
    results = [r for r in results if r["score"] >= MIN_SCORE]
    if not results:
        return (
            "Sin resultados relevantes en la base de conocimiento institucional para esa "
            "consulta. Informa al usuario que no dispones de esa información y, si procede, "
            "sugiere contactar a la Fundación."
        )
    blocks = []
    for i, r in enumerate(results, 1):
        blocks.append(
            f"### Resultado {i} — sección: {r['seccion']} (relevancia {r['score']})\n{r['text']}"
        )
    return "\n\n".join(blocks)


if __name__ == "__main__":
    mcp.run()  # transporte stdio por defecto
