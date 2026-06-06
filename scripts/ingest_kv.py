#!/usr/bin/env python
"""Carga data/institucional.json en el Structured KV Store NATIVO del agente público
de OpenFang vía PUT /api/memory/agents/{id}/kv/{key}  (rúbrica RUTA B, Módulo 2).

Cada sección del JSON (sedes, horarios, contactos, EPS, ...) queda como una entrada KV
del agente, de modo que el conocimiento corporativo vive en la memoria del OS.

Requiere el daemon de OpenFang corriendo y el agente ya spawneado.
Uso: uv run python scripts/ingest_kv.py
"""

from __future__ import annotations

import json
import os
import sys

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.env import AGENT_NAME, OPENFANG_API_KEY, OPENFANG_BASE_URL  # noqa: E402
from rag.paths import DATA_DIR  # noqa: E402

INST_PATH = os.path.join(DATA_DIR, "institucional.json")


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if OPENFANG_API_KEY:
        h["Authorization"] = f"Bearer {OPENFANG_API_KEY}"
    return h


def agent_id(name: str) -> str | None:
    r = requests.get(f"{OPENFANG_BASE_URL}/api/agents", headers=_headers(), timeout=10)
    r.raise_for_status()
    for a in r.json():
        if a.get("name") == name:
            return a.get("id")
    return None


def main() -> None:
    if not os.path.exists(INST_PATH):
        print(f"[ERROR] No existe {INST_PATH}")
        sys.exit(1)
    with open(INST_PATH, encoding="utf-8") as f:
        data = json.load(f)

    try:
        aid = agent_id(AGENT_NAME)
    except requests.RequestException as e:
        print(f"[ERROR] No se pudo contactar OpenFang en {OPENFANG_BASE_URL} ({e}).")
        print("        Arranca el daemon primero: openfang start")
        sys.exit(1)
    if not aid:
        print(f"[ERROR] Agente '{AGENT_NAME}' no encontrado en OpenFang.")
        print("        Arranca el daemon (openfang start) para que se spawnee desde el manifiesto.")
        sys.exit(1)

    print(f"Agente {AGENT_NAME} = {aid}")
    ok = 0
    for key, value in data.items():
        r = requests.put(
            f"{OPENFANG_BASE_URL}/api/memory/agents/{aid}/kv/{key}",
            headers=_headers(),
            json={"value": value},
            timeout=15,
        )
        if r.status_code < 300:
            size = len(json.dumps(value, ensure_ascii=False))
            print(f"  [ok] kv['{key}'] ({size} chars)")
            ok += 1
        else:
            print(f"  [fallo] kv['{key}']: {r.status_code} {r.text[:120]}")

    print(f"\n[ok] {ok}/{len(data)} secciones cargadas en el KV nativo del agente '{AGENT_NAME}'.")


if __name__ == "__main__":
    main()
