#!/usr/bin/env python
"""Construye el índice RAG local a partir de los .md scrapeados (output/).

Reemplaza la "ingesta semántica por REST" del blueprint: OpenFang no expone
ingesta masiva en su API, así que el RAG se resuelve con un índice vectorial
local propio (consultado luego por el servidor MCP).

Uso:
    uv run python scripts/ingest_docs.py
    uv run python scripts/ingest_docs.py --sections especialistas,servicios
"""

from __future__ import annotations

import argparse
import os
import sys

# Permite importar el paquete rag/ al ejecutar el script directamente.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.chunking import chunk_file  # noqa: E402
from rag.embeddings import active_model  # noqa: E402
from rag.index import build  # noqa: E402
from rag.paths import INDEX_PATH, scraped_data_dir  # noqa: E402

# Núcleo institucional. Se EXCLUYE "posts" (blog/noticias): metía ruido y
# ahogaba los perfiles de especialistas en el ranking de búsqueda.
DEFAULT_SECTIONS = ["especialistas", "sedes", "servicios", "pages"]
NOISE = ("Enlaces encontrados en esta página", "Especialistas que pueden atenderte")


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingesta RAG (índice vectorial local)")
    ap.add_argument(
        "--sections",
        default=",".join(DEFAULT_SECTIONS),
        help="Secciones a indexar, separadas por coma (por defecto: %(default)s)",
    )
    args = ap.parse_args()
    sections = [s.strip() for s in args.sections.split(",") if s.strip()]

    root = scraped_data_dir()
    print(f"Carpeta de documentos: {root}")

    # AC#1: fallar con gracia si no hay datos del scraper.
    if not os.path.isdir(root):
        print(f"\n[ERROR] No existe la carpeta de documentos: {root}")
        print("        Ejecuta primero el scraper:  uv run python main.py")
        sys.exit(1)

    all_chunks = []
    for sec in sections:
        d = os.path.join(root, sec)
        if not os.path.isdir(d):
            print(f"  - {sec}: (carpeta no encontrada, se omite)")
            continue
        files = [f for f in os.listdir(d) if f.endswith(".md")]
        n_chunks = 0
        for fn in files:
            try:
                cs = chunk_file(os.path.join(d, fn))
            except Exception as e:  # noqa: BLE001
                print(f"    aviso: no se pudo procesar {sec}/{fn}: {e}")
                continue
            all_chunks.extend(cs)
            n_chunks += len(cs)
        print(f"  - {sec}: {len(files)} archivos -> {n_chunks} chunks")

    if not all_chunks:
        print("\n[ERROR] No se generó ningún chunk (¿carpeta vacía?).")
        print("        Ejecuta primero el scraper:  uv run python main.py")
        sys.exit(1)

    # AC#2: ningún chunk debe contener los bloques ruidosos.
    for c in all_chunks:
        for marker in NOISE:
            if marker in c.text:
                print(f"\n[ERROR] Chunk con contenido ruidoso ('{marker}') en {c.source}")
                sys.exit(2)

    print(f"\nGenerando embeddings de {len(all_chunks)} chunks con '{active_model()}'...")
    n, dim = build(all_chunks)
    print(f"\n[ok] Índice construido: {n} chunks (dim={dim})")
    print(f"     Archivo: {INDEX_PATH}")


if __name__ == "__main__":
    main()
