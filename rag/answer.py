"""RAG por inyección de contexto -> Gemini. Núcleo del bot (sin tool-calling).

answer(query):
  1. Embede la consulta UNA sola vez (1 embedding de Gemini, muy barato).
  2. Recupera fragmentos relevantes; refuerza con perfiles de especialistas
     cuando la consulta los necesita.
  3. Inyecta datos corporativos (data/institucional.json) si la pregunta lo amerita.
  4. UNA sola llamada al LLM con un prompt corto y acotado (costo mínimo).
"""

from __future__ import annotations

import json
import os

from .embeddings import embed_one
from .index import search_vec
from .llm import chat
from .paths import DATA_DIR

MIN_SCORE = 0.35
TOP_K = 6
ESP_BOOST = 5  # perfiles de especialistas extra cuando la consulta los requiere

SYSTEM = """Eres el asistente virtual de la Fundación Valle del Lili (institución de salud en Cali, Colombia). Hablas en español colombiano, con calidez, claridad y precisión.

En cada turno recibes uno o más bloques de CONTEXTO (datos corporativos oficiales y/o fragmentos de la base de conocimiento) y la PREGUNTA DEL USUARIO. La búsqueda ya se hizo por ti.

CÓMO RESPONDER:
- Usa EXCLUSIVAMENTE la información de los bloques de CONTEXTO. No inventes ni completes con conocimiento general.
- Responde de forma completa y bien organizada: si el contexto trae varios datos relevantes (varios especialistas, sedes, o ítems de un servicio o chequeo), preséntalos todos con listas y negritas; no te quedes en una sola frase.
- Especialistas/doctores: lista nombre y especialidad de los que aparezcan; incluye teléfono/extensión y cómo agendar si está en el contexto.
- Sedes/horarios/contactos: da los datos concretos del bloque de datos corporativos.
- Cuando exista, menciona la fuente (línea "Fuente:" o URL del fragmento).
- Si saludan, saluda breve y ofrece ayuda.
- Si el CONTEXTO no contiene la respuesta, dilo con amabilidad ("No tengo esa información específica") y sugiere contactar a la Fundación o consultar el directorio médico. NUNCA inventes nombres, teléfonos, direcciones, horarios ni precios.
- Si preguntan algo ajeno a la Fundación, aclara con cortesía que solo ayudas con información institucional.

Sé cordial y honesto: es preferible decir que no sabes algo a dar información incorrecta sobre salud."""

# --- Datos corporativos estructurados (data/institucional.json) ---
_INST_PATH = os.path.join(DATA_DIR, "institucional.json")
_INST_CACHE: dict | None = None


def _institucional() -> dict:
    global _INST_CACHE
    if _INST_CACHE is None:
        try:
            with open(_INST_PATH, encoding="utf-8") as f:
                _INST_CACHE = json.load(f)
        except Exception:  # noqa: BLE001
            _INST_CACHE = {}
    return _INST_CACHE


# palabra clave (en la pregunta) -> claves del JSON corporativo a incluir
_CORP_MAP = {
    "sede": ["sedes_y_ubicaciones"], "ubicaci": ["sedes_y_ubicaciones"],
    "direcci": ["sedes_y_ubicaciones"], "dónde queda": ["sedes_y_ubicaciones"],
    "donde queda": ["sedes_y_ubicaciones"], "dónde está": ["sedes_y_ubicaciones"],
    "horario": ["horarios_atencion"], "urgencia": ["horarios_atencion", "contactos_clave"],
    "contacto": ["contactos_clave"], "teléfono": ["contactos_clave"],
    "telefono": ["contactos_clave"], "whatsapp": ["contactos_clave"],
    "correo": ["contactos_clave"], "email": ["contactos_clave"], "línea": ["contactos_clave"],
    "cita": ["contactos_clave"], "agendar": ["contactos_clave"],
    "eps": ["convenios_eps_y_aseguradoras"], "aseguradora": ["convenios_eps_y_aseguradoras"],
    "convenio": ["convenios_eps_y_aseguradoras"], "prepagada": ["medicina_prepagada"],
    "banco de sangre": ["servicios_de_apoyo"], "capilla": ["servicios_de_apoyo"],
    "parqueadero": ["servicios_de_apoyo"], "telemedicina": ["servicios_digitales"],
    "app": ["servicios_digitales"], "nit": ["informacion_corporativa"],
    "acreditaci": ["informacion_corporativa"],
}

# pistas de que la consulta busca profesionales/doctores
_DOCTOR_HINTS = (
    "especialista", "doctor", "doctora", "médic", "medic", "profesional",
    "quién atiende", "quien atiende", "qué profesional", "directorio",
)


def _corporate_context(query: str) -> dict:
    q = query.lower()
    data = _institucional()
    out: dict = {}
    for kw, secs in _CORP_MAP.items():
        if kw in q:
            for k in secs:
                if k not in out and data.get(k) is not None:
                    out[k] = data[k]
    return out


def retrieve(query: str, k: int = TOP_K) -> list[dict]:
    """Fragmentos relevantes; con refuerzo de especialistas si la consulta lo pide."""
    qvec = embed_one(query)
    base = [r for r in search_vec(qvec, k=k) if r["score"] >= MIN_SCORE]
    if any(h in query.lower() for h in _DOCTOR_HINTS):
        seen = {(r["title"], r.get("heading")) for r in base}
        for r in search_vec(qvec, k=ESP_BOOST * 2, seccion="especialistas"):
            if r["score"] < MIN_SCORE:
                continue
            key = (r["title"], r.get("heading"))
            if key not in seen:
                base.append(r)
                seen.add(key)
            if len(base) >= k + ESP_BOOST:
                break
    return base


def build_messages(query: str, results: list[dict]) -> list[dict]:
    parts: list[str] = []
    corp = _corporate_context(query)
    if corp:
        parts.append(
            "DATOS CORPORATIVOS OFICIALES (sedes/horarios/contactos):\n"
            + json.dumps(corp, ensure_ascii=False, indent=2)
        )
    if results:
        parts.append(
            "FRAGMENTOS DE LA BASE DE CONOCIMIENTO:\n"
            + "\n\n---\n\n".join(r["text"] for r in results)
        )
    if not parts:
        parts.append("(No se encontró información en la base de conocimiento de la Fundación.)")
    user = "\n\n".join(parts) + f"\n\nPREGUNTA DEL USUARIO: {query}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def answer(query: str, k: int = TOP_K) -> str:
    return chat(build_messages(query, retrieve(query, k=k)))
