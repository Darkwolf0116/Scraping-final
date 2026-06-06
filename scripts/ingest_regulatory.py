#!/usr/bin/env python
"""Pipeline HITL del Collector Hand: borradores de normativa -> índice regulatorio.

Cierra el ciclo de RUTA B (Módulo 3 + memoria):
  1. El Hand "collector-regulatorio" deja borradores .md en data/pending_regulatory/
     con frontmatter `estado: pendiente`.
  2. Un humano los revisa y cambia a `estado: aprobado` (Human-In-The-Loop).
  3. Este script embebe SOLO los aprobados y (re)construye data/regulatory_index.sqlite,
     que el agente interno consulta vía la herramienta MCP `buscar_regulatorio`.

Uso:
    uv run python scripts/ingest_regulatory.py
    uv run python scripts/ingest_regulatory.py --from hands/collector-regulatorio/samples --all
    uv run python scripts/ingest_regulatory.py --approve MinSalud-Decreto-780-2016.md

Notas de costo: embeber consume API de embeddings de Gemini (muy barato), pero solo
se ejecuta cuando tú lo corres, no en cada mensaje del bot.
"""

from __future__ import annotations

import argparse
import os
import sys

import frontmatter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.chunking import Chunk, clean_md  # noqa: E402
from rag.embeddings import active_model  # noqa: E402
from rag.index import build  # noqa: E402
from rag.paths import PENDING_REGULATORY_DIR, REGULATORY_INDEX_PATH  # noqa: E402


def _draft_to_chunk(path: str) -> Chunk | None:
    """Convierte un borrador .md (con frontmatter) en un Chunk para el índice."""
    with open(path, encoding="utf-8") as f:
        post = frontmatter.load(f)
    m = post.metadata
    titulo = str(m.get("titulo") or m.get("title") or os.path.basename(path))
    entidad = str(m.get("entidad") or "")
    tipo = str(m.get("tipo") or "")
    numero = str(m.get("numero") or "")
    fecha = str(m.get("fecha") or "")
    fuente = str(m.get("fuente") or m.get("url") or "")
    body = clean_md(post.content)
    if not body:
        return None
    encabezado = f"[{tipo} {numero}] {titulo}".strip()
    if entidad:
        encabezado += f" — {entidad}"
    if fecha:
        encabezado += f" ({fecha})"
    text = f"{encabezado}\nFuente: {fuente}\n\n{body}"
    return Chunk(
        text=text,
        title=encabezado,
        url=fuente,
        seccion="regulatorio",
        source=os.path.basename(path),
        heading=None,
        categorias=[c for c in (entidad, tipo) if c],
    )


def _set_estado(path: str, estado: str) -> None:
    with open(path, encoding="utf-8") as f:
        post = frontmatter.load(f)
    post.metadata["estado"] = estado
    with open(path, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))


def main() -> None:
    ap = argparse.ArgumentParser(description="Pipeline HITL: borradores regulatorios -> índice")
    ap.add_argument("--from", dest="src", default=PENDING_REGULATORY_DIR,
                    help="Carpeta de borradores .md (por defecto data/pending_regulatory).")
    ap.add_argument("--all", action="store_true",
                    help="Ingerir TODOS los borradores, sin exigir estado=aprobado (demo).")
    ap.add_argument("--approve", metavar="ARCHIVO.md",
                    help="Marca un borrador como aprobado (estado=aprobado) y termina.")
    args = ap.parse_args()

    src = args.src
    if not os.path.isabs(src):
        src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", src))

    if args.approve:
        path = os.path.join(src, args.approve)
        if not os.path.exists(path):
            print(f"[ERROR] No existe el borrador: {path}")
            sys.exit(1)
        _set_estado(path, "aprobado")
        print(f"[ok] Aprobado (HITL): {args.approve}")
        print("     Ahora ejecuta: uv run python scripts/ingest_regulatory.py")
        return

    if not os.path.isdir(src):
        print(f"[ERROR] No existe la carpeta de borradores: {src}")
        print("        Activa el Hand (openfang hand activate collector-regulatorio) o usa --from.")
        sys.exit(1)

    files = sorted(f for f in os.listdir(src) if f.endswith(".md"))
    chunks: list[Chunk] = []
    omitidos = 0
    for fn in files:
        path = os.path.join(src, fn)
        with open(path, encoding="utf-8") as f:
            estado = str(frontmatter.load(f).metadata.get("estado", "")).lower()
        if not args.all and estado != "aprobado":
            print(f"  - {fn}: estado='{estado or 'pendiente'}' (pendiente de aprobación HITL, omitido)")
            omitidos += 1
            continue
        c = _draft_to_chunk(path)
        if c:
            chunks.append(c)
            print(f"  + {fn}: indexado")

    if not chunks:
        print("\n[ERROR] Ningún borrador aprobado para indexar.")
        print("        Aprueba con: uv run python scripts/ingest_regulatory.py --approve <archivo.md>")
        print("        o usa --all para una demo rápida con todos los borradores.")
        sys.exit(1)

    print(f"\nEmbeddings de {len(chunks)} normas con '{active_model()}'...")
    n, dim = build(chunks, path=REGULATORY_INDEX_PATH)
    print(f"\n[ok] Índice regulatorio construido: {n} normas (dim={dim})")
    print(f"     Archivo: {REGULATORY_INDEX_PATH}")
    if omitidos:
        print(f"     ({omitidos} borradores pendientes de aprobación quedaron fuera)")
    print("     El agente interno ya puede consultarlas vía buscar_regulatorio().")


if __name__ == "__main__":
    main()
