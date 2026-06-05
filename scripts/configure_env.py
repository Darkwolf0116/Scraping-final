#!/usr/bin/env python
"""Inyecta la configuración del ecosistema en el config.toml GLOBAL de OpenFang.

Estrategia: gemma + inyección de contexto (el RAG lo hace el orquestador, no el
agente), por lo que NO se configura tool-calling, ni servidor MCP, ni el adaptador
Telegram nativo de OpenFang. Fusiona de forma idempotente (vía tomlkit):
  - api_listen = 127.0.0.1:4200
  - [default_model] -> ollama / AGENT_MODEL (gemma4:e4b), base_url .../v1

Además copia el manifiesto del agente a ~/.openfang/agents/<name>/agent.toml para
que esté disponible como plantilla (`openfang agent new <name>`). El orquestador
también lo crea por API si hiciera falta.

Uso: uv run python scripts/configure_env.py
"""

from __future__ import annotations

import os
import shutil
import sys

import tomlkit
from tomlkit import table

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.env import AGENT_MODEL, AGENT_NAME, OLLAMA_BASE_URL  # noqa: E402
from rag.paths import AGENT_MANIFEST  # noqa: E402


def openfang_home() -> str:
    home = os.environ.get("OPENFANG_HOME")
    if home:
        return os.path.expanduser(home)
    base = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(base, ".openfang")


def main() -> None:
    home = openfang_home()
    os.makedirs(home, exist_ok=True)
    config_path = os.path.join(home, "config.toml")

    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            doc = tomlkit.parse(f.read())
        print(f"Config existente: {config_path}")
    else:
        doc = tomlkit.document()
        print(f"Config nuevo: {config_path}")

    # Puerto fijo conocido (lo usa el orquestador vía OPENFANG_BASE_URL).
    doc["api_listen"] = "127.0.0.1:4200"

    # Modelo por defecto: Ollama local (gemma del usuario).
    dm = doc.get("default_model")
    if not isinstance(dm, dict):
        dm = table()
        doc["default_model"] = dm
    dm["provider"] = "ollama"
    dm["model"] = AGENT_MODEL
    dm["base_url"] = OLLAMA_BASE_URL.rstrip("/") + "/v1"
    dm["api_key_env"] = ""

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(doc))

    # Copia el manifiesto como plantilla en ~/.openfang/agents/<name>/agent.toml
    agents_dir = os.path.join(home, "agents", AGENT_NAME)
    os.makedirs(agents_dir, exist_ok=True)
    shutil.copyfile(AGENT_MANIFEST, os.path.join(agents_dir, "agent.toml"))

    print(f"[ok] default_model -> ollama/{AGENT_MODEL} ({dm['base_url']})")
    print(f"[ok] manifiesto del agente copiado a {agents_dir}\\agent.toml")
    print(f"\nConfig escrito en: {config_path}")
    print("Siguiente: inicia Ollama y el daemon (openfang start), luego prueba:")
    print('  uv run python scripts/telegram_bot.py --ask "¿Qué incluye el chequeo Gold?"')


if __name__ == "__main__":
    main()
