#!/usr/bin/env python
"""Genera ~/.openfang/config.toml para OpenFang (nativo): Gemini + bridge nativo de
Telegram + ruteo público/interno por bindings + servidor MCP de RAG.

Uso:
    uv run python scripts/configure_env.py
    uv run python scripts/configure_env.py --persist   (guarda claves como variables de sistema)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

import tomlkit
from tomlkit import aot, table

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.env import (  # noqa: E402
    AGENT_NAME,
    GEMINI_API_KEY,
    GEMINI_CHAT_MODEL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_INTERNAL_GROUP_ID,
)
from rag.paths import AGENT_MANIFEST, INTERNAL_AGENT_MANIFEST, ROOT_DIR  # noqa: E402

INTERNAL_AGENT_NAME = "asistente-interno"


def openfang_home() -> str:
    home = os.environ.get("OPENFANG_HOME")
    if home:
        return os.path.expanduser(home)
    base = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(base, ".openfang")


def persist_var(name: str, value: str) -> None:
    try:
        subprocess.run(["setx", name, value], check=True, capture_output=True, text=True)
        print(f"  {name} guardada en el sistema (persistente)")
    except Exception as e:  # noqa: BLE001
        print(f"  aviso: no se pudo guardar {name}: {e}")


def fwd(p: str) -> str:
    return p.replace("\\", "/")


def copy_manifest(home: str, name: str, manifest: str) -> str:
    d = os.path.join(home, "agents", name)
    os.makedirs(d, exist_ok=True)
    shutil.copyfile(manifest, os.path.join(d, "agent.toml"))
    return d


def main() -> None:
    ap = argparse.ArgumentParser(description="Configura OpenFang (Gemini + Telegram + RAG + bindings)")
    ap.add_argument(
        "--persist",
        action="store_true",
        help="Guarda GEMINI_API_KEY / GOOGLE_GENERATIVE_AI_API_KEY / TELEGRAM_BOT_TOKEN como variables de sistema (setx)",
    )
    args = ap.parse_args()

    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY no está definida en .env")
        sys.exit(1)
    if not TELEGRAM_BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN no está definido en .env")
        sys.exit(1)

    if args.persist:
        print("Persistiendo variables en el sistema...")
        persist_var("GEMINI_API_KEY", GEMINI_API_KEY)
        persist_var("GOOGLE_GENERATIVE_AI_API_KEY", GEMINI_API_KEY)
        persist_var("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)

    home = openfang_home()
    os.makedirs(home, exist_ok=True)
    config_path = os.path.join(home, "config.toml")

    doc = tomlkit.document()
    doc["api_listen"] = "127.0.0.1:4200"
    doc["log_level"] = "info"

    # --- Proveedor LLM por defecto: Gemini ---
    dm = table()
    dm["provider"] = "gemini"
    dm["model"] = GEMINI_CHAT_MODEL
    dm["api_key_env"] = "GEMINI_API_KEY"
    doc["default_model"] = dm

    # --- Canal Telegram (bridge nativo) -> agente público por defecto ---
    channels = table()
    tg = table()
    tg["bot_token_env"] = "TELEGRAM_BOT_TOKEN"
    tg["default_agent"] = AGENT_NAME
    tg["allowed_users"] = []
    tg["poll_interval_secs"] = 1
    channels["telegram"] = tg
    doc["channels"] = channels

    # --- Ruteo: grupo privado -> agente interno (si está configurado) ---
    routed_internal = False
    if TELEGRAM_INTERNAL_GROUP_ID:
        bindings = aot()
        b = table()
        b["agent"] = INTERNAL_AGENT_NAME
        mr = tomlkit.inline_table()
        mr["channel"] = "telegram"
        mr["channel_id"] = str(TELEGRAM_INTERNAL_GROUP_ID)
        b["match_rule"] = mr
        bindings.append(b)
        doc["bindings"] = bindings
        routed_internal = True

    # --- Servidor MCP de RAG (stdio) ---
    # OpenFang ejecuta los MCP en un sandbox con env_clear(): solo conserva una
    # allowlist (SAFE_ENV_VARS) + lo que se liste en `env`. Por eso NO usamos
    # `uv run` (necesita APPDATA/LOCALAPPDATA que el sandbox elimina y fallaría
    # silenciosamente): apuntamos directo al python del venv (solo necesita PATH)
    # y reenviamos las variables imprescindibles (incluida la clave de Gemini).
    rag_script = fwd(os.path.join(ROOT_DIR, "scripts", "rag_mcp_server.py"))
    venv_py_win = os.path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")
    venv_py_nix = os.path.join(ROOT_DIR, ".venv", "bin", "python")
    if os.path.exists(venv_py_win):
        command, args_list = fwd(venv_py_win), [rag_script]
    elif os.path.exists(venv_py_nix):
        command, args_list = fwd(venv_py_nix), [rag_script]
    else:  # fallback si no hay venv
        command, args_list = "uv", ["run", "--directory", fwd(ROOT_DIR), "python", rag_script]
    env_list = [
        "GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY",
        "SystemRoot", "SystemDrive", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP",
    ]
    mcp_toml = f'''
[[mcp_servers]]
name = "rag"
timeout_secs = 30
env = {json.dumps(env_list)}

[mcp_servers.transport]
type = "stdio"
command = "{command}"
args = {json.dumps(args_list)}
'''

    with open(config_path, "w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(doc))
        f.write(mcp_toml)

    # --- Copiar manifiestos de los agentes a ~/.openfang/agents/ ---
    copy_manifest(home, AGENT_NAME, AGENT_MANIFEST)
    if os.path.exists(INTERNAL_AGENT_MANIFEST):
        copy_manifest(home, INTERNAL_AGENT_NAME, INTERNAL_AGENT_MANIFEST)

    print(f"[ok] Config escrito en: {config_path}")
    print(f"  Proveedor:  Gemini / {GEMINI_CHAT_MODEL}")
    print(f"  Telegram:   bridge nativo -> {AGENT_NAME}")
    if routed_internal:
        print(f"  Interno:    grupo {TELEGRAM_INTERNAL_GROUP_ID} -> {INTERNAL_AGENT_NAME}")
    else:
        print("  Interno:    (define TELEGRAM_INTERNAL_GROUP_ID en .env para activar el bot interno)")
    print(f"  MCP RAG:    {rag_script}")
    print("\nSiguiente: openfang start   (el agente se auto-spawnea; el bot queda activo en Telegram)")


if __name__ == "__main__":
    main()
