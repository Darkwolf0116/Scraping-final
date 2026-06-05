"""Troceo (chunking) de los .md scrapeados según su estructura de cabeceras.

Reglas (validadas contra los archivos reales de output/):
- especialistas/: 1 chunk por archivo (perfil completo).
- servicios/:     1 chunk por encabezado H2.
- sedes/:         1 chunk por H3 dentro de "Servicios destacados" (+ intro).
- pages/:         1 chunk por H2; si el H2 tiene H3 (p.ej. Basic/Advance/Gold),
                  1 chunk por H3 incluyendo sus sub-secciones H4.

Limpieza (AC#2): se eliminan por completo las secciones ruidosas
"## Enlaces encontrados en esta página" y "## Especialistas que pueden atenderte".
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import frontmatter

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
IMG_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
MIN_CHARS = 60  # descarta chunks de navegación/imágenes sin texto útil


@dataclass
class Chunk:
    text: str
    title: str
    url: str
    seccion: str
    source: str
    heading: str | None = None
    categorias: list = field(default_factory=list)


def clean_md(text: str) -> str:
    """Quita imágenes, convierte enlaces en su etiqueta y elimina reglas (---)."""
    text = IMG_RE.sub("", text)
    text = LINK_RE.sub(r"\1", text)
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s in ("---", "***", "___"):
            continue
        lines.append(line.rstrip())
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_noise(title: str | None) -> bool:
    if not title:
        return False
    t = title.strip().lower()
    return t.startswith("enlaces encontrados") or t.startswith("especialistas que pueden atenderte")


def parse_segments(content: str) -> list[dict]:
    """Divide el contenido en segmentos {level, title, lines} por cabeceras.

    El texto previo a la primera cabecera queda como segmento de nivel 0.
    """
    segments: list[dict] = []
    cur = {"level": 0, "title": None, "lines": []}
    for line in content.splitlines():
        m = HEADING_RE.match(line)
        if m:
            segments.append(cur)
            cur = {"level": len(m.group(1)), "title": m.group(2).strip(), "lines": []}
        else:
            cur["lines"].append(line)
    segments.append(cur)
    # conserva segmentos con título o con contenido real
    return [s for s in segments if s["title"] is not None or "".join(s["lines"]).strip()]


def _drop_noise(segments: list[dict]) -> list[dict]:
    """Elimina secciones ruidosas y todo su contenido subordinado."""
    out: list[dict] = []
    i, n = 0, len(segments)
    while i < n:
        s = segments[i]
        if is_noise(s["title"]):
            lvl = s["level"]
            i += 1
            while i < n and segments[i]["level"] > lvl:
                i += 1
            continue
        out.append(s)
        i += 1
    return out


def render_segments(segs: list[dict]) -> str:
    parts: list[str] = []
    for s in segs:
        if s["title"] is not None and s["level"] > 0:
            parts.append("#" * s["level"] + " " + s["title"])
        body = "\n".join(s["lines"]).strip()
        if body:
            parts.append(body)
    return "\n".join(parts).strip()


def _meta_header(meta: dict) -> str:
    cats = meta.get("categorias") or []
    cat_line = ("Categorías: " + ", ".join(cats) + "\n") if cats else ""
    return f"[{meta.get('seccion', '')}] {meta.get('title', '')}\n{cat_line}Fuente: {meta.get('url', '')}\n\n"


def _make_chunk(meta: dict, body: str, heading: str | None) -> Chunk | None:
    body = clean_md(body)
    # longitud útil sin contar las marcas de cabecera
    useful = re.sub(r"^#{1,6}\s+", "", body, flags=re.MULTILINE).strip()
    if len(useful) < MIN_CHARS:
        return None
    return Chunk(
        text=_meta_header(meta) + body,
        title=meta.get("title", ""),
        url=meta.get("url", ""),
        seccion=meta.get("seccion", ""),
        source=meta.get("source", ""),
        heading=heading,
        categorias=meta.get("categorias") or [],
    )


def _chunk_by_sections(meta: dict, segments: list[dict]) -> list[Chunk]:
    chunks: list[Chunk] = []
    n, i = len(segments), 0

    # preámbulo (niveles 0/1 antes del primer H2)
    pre = []
    while i < n and segments[i]["level"] in (0, 1):
        pre.append(segments[i])
        i += 1
    if pre:
        c = _make_chunk(meta, render_segments(pre), heading=meta.get("title"))
        if c:
            chunks.append(c)

    while i < n:
        seg = segments[i]
        if seg["level"] != 2:
            # cabecera huérfana (>=3) sin H2 padre: chunk independiente
            grp = [seg]
            i += 1
            while i < n and segments[i]["level"] > seg["level"]:
                grp.append(segments[i])
                i += 1
            c = _make_chunk(meta, render_segments(grp), heading=seg["title"])
            if c:
                chunks.append(c)
            continue

        h2 = seg
        i += 1
        children = []
        while i < n and segments[i]["level"] > 2:
            children.append(segments[i])
            i += 1

        # separa el intro del H2 y agrupa por H3 (cada grupo arrastra sus H4+)
        intro, h3_groups = [], []
        j, m = 0, len(children)
        while j < m and children[j]["level"] != 3:
            intro.append(children[j])
            j += 1
        while j < m:
            g = [children[j]]
            j += 1
            while j < m and children[j]["level"] > 3:
                g.append(children[j])
                j += 1
            h3_groups.append(g)

        if h3_groups:
            c = _make_chunk(meta, render_segments([h2] + intro), heading=h2["title"])
            if c:
                chunks.append(c)
            for g in h3_groups:
                text = "## " + h2["title"] + "\n" + render_segments(g)
                c = _make_chunk(meta, text, heading=f"{h2['title']} / {g[0]['title']}")
                if c:
                    chunks.append(c)
        else:
            c = _make_chunk(meta, render_segments([h2] + children), heading=h2["title"])
            if c:
                chunks.append(c)

    return chunks


def chunk_content(meta: dict, content: str) -> list[Chunk]:
    segments = _drop_noise(parse_segments(content))
    if meta.get("seccion") == "especialistas":
        c = _make_chunk(meta, render_segments(segments), heading=None)
        return [c] if c else []
    return _chunk_by_sections(meta, segments)


def chunk_file(path: str) -> list[Chunk]:
    with open(path, encoding="utf-8") as f:
        post = frontmatter.load(f)
    meta = dict(post.metadata)
    meta["source"] = os.path.basename(path)
    cats = meta.get("categorias")
    if isinstance(cats, str):
        meta["categorias"] = [cats]
    elif not isinstance(cats, list):
        meta["categorias"] = []
    else:
        meta["categorias"] = [str(c) for c in cats]
    return chunk_content(meta, post.content)
