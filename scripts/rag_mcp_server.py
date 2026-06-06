#!/usr/bin/env python
"""Servidor MCP (stdio) con dos herramientas para el agente:

1. consultar_datos_corporativos — Lee data/institucional.json (sedes,
   horarios, contactos, EPS, info corporativa). Primera capa de memoria.

2. buscar_institucional — Búsqueda RAG vectorial sobre documentos
   scrapeados (especialidades, servicios, procedimientos). Segunda capa.

El agente decide qué herramienta usar según la pregunta del usuario.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp.server.fastmcp import FastMCP

from rag.index import search
from rag.paths import REGULATORY_INDEX_PATH

mcp = FastMCP("rag")

MIN_SCORE = 0.35

# ── Ruta al JSON corporativo ──────────────────────────────────────────
JSON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "institucional.json"))

# Cache del JSON en memoria para evitar leer disco en cada llamada
_JSON_CACHE: dict | None = None


def _load_json() -> dict:
    global _JSON_CACHE
    if _JSON_CACHE is not None:
        return _JSON_CACHE
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        _JSON_CACHE = json.load(f)
    return _JSON_CACHE


@mcp.tool()
def consultar_datos_corporativos(seccion: str = "") -> str:
    """Datos ADMINISTRATIVOS/corporativos de la Fundación Valle del Lili.

    Úsala SOLO para:
      - Sedes y ubicaciones (direcciones, ciudades)
      - Horarios de atención (urgencias, consulta externa, laboratorio, visitas)
      - Contactos (teléfonos, WhatsApp, correos)
      - EPS y aseguradoras en convenio
      - Información corporativa (nombre legal, NIT, acreditaciones)
      - Servicios de apoyo (banco de sangre, capilla, parqueaderos) y digitales (telemedicina, app)

    NO la uses para listar médicos/doctores/especialistas ni para describir una
    especialidad o servicio clínico: para eso usa `buscar_institucional`.

    Args:
        seccion: "sedes", "horarios", "contactos", "eps", "corporativa",
            "banco de sangre", "telemedicina". Vacío = todas las secciones.
    """
    data = _load_json()
    if not seccion:
        return json.dumps(data, indent=2, ensure_ascii=False)

    q = seccion.lower().strip()

    # Mapeo de palabras clave a secciones del JSON
    MAPPING = {
        "corporativa":        ["informacion_corporativa"],
        "sede":               ["sedes_y_ubicaciones"],
        "ubicacion":          ["sedes_y_ubicaciones"],
        "direccion":          ["sedes_y_ubicaciones"],
        "horario":            ["horarios_atencion"],
        "contacto":           ["contactos_clave"],
        "telefono":           ["contactos_clave"],
        "telefónico":         ["contactos_clave"],
        "teléfono":           ["contactos_clave"],
        "whatsapp":           ["contactos_clave"],
        "email":              ["contactos_clave"],
        "correo":             ["contactos_clave"],
        "eps":                ["convenios_eps_y_aseguradoras"],
        "aseguradora":        ["convenios_eps_y_aseguradoras"],
        "prepagada":          ["convenios_eps_y_aseguradoras", "medicina_prepagada"],
        "servicio destacado": ["servicios_destacados"],
        "banco de sangre":    ["servicios_de_apoyo", "banco_de_sangre"],
        "capilla":            ["servicios_de_apoyo", "capilla"],
        "parqueadero":        ["servicios_de_apoyo", "parqueaderos"],
        "alimentacion":       ["servicios_de_apoyo", "alimentacion"],
        "telemedicina":       ["servicios_digitales"],
        "app":                ["servicios_digitales"],
        "digital":            ["servicios_digitales"],
    }

    keys_to_return: list[str] = []
    for keyword, sections in MAPPING.items():
        if keyword in q:
            keys_to_return.extend(sections)

    if not keys_to_return:
        # Fallback: buscar en todas las secciones si la palabra clave coincide
        keys_to_return = [k for k in data if any(q in k.lower().replace("_", " ") for k in data)]

    if not keys_to_return:
        return (
            f"No encontré la sección '{seccion}' en los datos corporativos. "
            "Secciones disponibles: sedes, horarios, contactos, eps, corporativa, "
            "servicios destacados, banco de sangre, capilla, parqueaderos, telemedicina."
        )

    result = {}
    for key in keys_to_return:
        value = data.get(key)
        if value is not None:
            result[key] = value

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def buscar_institucional(query: str, k: int = 8, seccion: str = "") -> str:
    """Herramienta PRINCIPAL de la Fundación Valle del Lili. Úsala para:
      - MÉDICOS, DOCTORES, ESPECIALISTAS y cualquier ESPECIALIDAD (cardiología, pediatría,
        dermatología, etc.) -> filtra con seccion="especialistas"
      - Especialidades y servicios clínicos (qué hacen, qué tratan, procedimientos)
      - Chequeos médicos (Basic, Advance, Gold)
      - Páginas institucionales

    Si la pregunta menciona un médico, doctor, especialista o una especialidad, DEBES
    usar esta herramienta con seccion="especialistas" (NO consultar_datos_corporativos).

    Args:
        query: La pregunta o términos de búsqueda del usuario, en español.
        k: Número de fragmentos a devolver (por defecto 15).
        seccion: Filtrar por sección (ej: "especialistas", "servicios", "sedes", "pages").
            Vacío devuelve todas las secciones.
    """
    try:
        if seccion:
            # Filtrar la sección DENTRO del ranking: si no, los perfiles de
            # especialistas se pierden cuando otra sección (p.ej. servicios)
            # domina el top-20 global de la búsqueda sin filtrar.
            results = search(query, k=max(k, 10), seccion=seccion)
        else:
            results = search(query, k=max(k, 20))
    except FileNotFoundError as e:
        return f"[error] {e}"
    results = [r for r in results if r["score"] >= MIN_SCORE]
    results = results[:k]
    if not results:
        return (
            "Sin resultados relevantes en la base de conocimiento documental para esa "
            "consulta. Informa al usuario que no dispones de esa información y, si procede, "
            "sugiere contactar a la Fundación."
        )
    blocks = []
    for i, r in enumerate(results, 1):
        blocks.append(
            f"### Resultado {i} — sección: {r['seccion']} (relevancia {r['score']})\n{r['text']}"
        )
    return "\n\n".join(blocks)


@mcp.tool()
def buscar_regulatorio(query: str, k: int = 6) -> str:
    """Busca en la base de NORMATIVA DE SALUD aprobada de la Fundación Valle del Lili.

    Cubre decretos y resoluciones de MinSalud, circulares de Supersalud y alertas de
    Invima recopiladas por la Hand recolectora y aprobadas por el administrador (HITL).
    ÚSALA para preguntas sobre normativa, regulación, decretos, circulares o resoluciones.
    Uso exclusivo del personal interno.

    Args:
        query: La pregunta o términos de búsqueda, en español.
        k: Número de fragmentos a devolver (por defecto 6).
    """
    try:
        results = search(query, k=k, path=REGULATORY_INDEX_PATH)
    except FileNotFoundError:
        return (
            "Aún no hay normativa indexada. La Hand recolectora debe ejecutarse y el "
            "administrador aprobar al menos un reporte (HITL) antes de que haya contenido "
            "regulatorio disponible."
        )
    results = [r for r in results if r["score"] >= MIN_SCORE]
    if not results:
        return "Sin resultados en la base regulatoria para esa consulta."
    blocks = []
    for i, r in enumerate(results, 1):
        blocks.append(
            f"### Norma {i} — {r.get('title', '')} (relevancia {r['score']})\n{r['text']}"
        )
    return "\n\n".join(blocks)


if __name__ == "__main__":
    mcp.run()
