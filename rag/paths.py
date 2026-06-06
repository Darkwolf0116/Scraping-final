"""Resolución de rutas absoluta y agnóstica a la ubicación del clon.

Regla del blueprint: nunca usar rutas relativas estáticas. La raíz del
repositorio se calcula dinámicamente en tiempo de ejecución.
"""

import os

# rag/ vive en la raíz del repo -> ROOT_DIR es el padre de este archivo.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT_DIR, "data")
INDEX_PATH = os.path.join(DATA_DIR, "rag_index.sqlite")
# Índice de normativa aprobada (alimentado por la Hand + aprobación HITL).
REGULATORY_INDEX_PATH = os.path.join(DATA_DIR, "regulatory_index.sqlite")
# Borradores de normativa pendientes de aprobación (HITL).
PENDING_REGULATORY_DIR = os.path.join(DATA_DIR, "pending_regulatory")
# Manifiesto del agente (define la "persona"/system_prompt; fuente única).
AGENT_MANIFEST = os.path.join(ROOT_DIR, "agents", "public_agent.toml")
INTERNAL_AGENT_MANIFEST = os.path.join(ROOT_DIR, "agents", "internal_agent.toml")


def scraped_data_dir() -> str:
    """Carpeta con los .md scrapeados.

    Por defecto ``<repo>/output``. Se puede sobreescribir con la variable de
    entorno ``SCRAPED_DATA_DIR`` (relativa al repo o absoluta).
    """
    val = (os.environ.get("SCRAPED_DATA_DIR") or "").strip()
    if not val:
        return os.path.join(ROOT_DIR, "output")
    if os.path.isabs(val):
        return val
    return os.path.abspath(os.path.join(ROOT_DIR, val))
