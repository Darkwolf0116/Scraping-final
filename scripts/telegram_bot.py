#!/usr/bin/env python
"""Orquestador del bot público de Telegram (RAG local + gemma por Ollama).

Flujo por cada mensaje:
  1. Recibe el texto vía long-polling de la Bot API de Telegram.
  2. Ejecuta SIEMPRE la búsqueda RAG local (data/rag_index.sqlite).
  3. Inyecta los fragmentos recuperados en un prompt corto y genera la respuesta
     con gemma4:e4b directamente por Ollama (prompt acotado, grounding determinista).
  4. Devuelve la respuesta al chat de Telegram.

Requisitos: Ollama con gemma4:e4b + embeddinggemma, e índice RAG construido
(`uv run python scripts/ingest_docs.py`). TELEGRAM_BOT_TOKEN para el modo bot.

Uso:
    uv run python scripts/telegram_bot.py
    uv run python scripts/telegram_bot.py --ask "¿Qué incluye el chequeo Gold?"   # prueba sin Telegram
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.answer import answer  # noqa: E402
from rag.env import TELEGRAM_BOT_TOKEN  # noqa: E402
from rag.llm import health  # noqa: E402

TG_MAX = 4096
WELCOME = (
    "¡Hola! Soy el asistente virtual de la Fundación Valle del Lili. "
    "Puedo ayudarte con información sobre sedes, especialistas, servicios y "
    "el chequeo médico preventivo. ¿En qué puedo ayudarte?"
)


def _split(text: str, n: int = TG_MAX):
    return [text[i : i + n] for i in range(0, len(text), n)] or [""]


def send(token: str, chat_id: int, text: str) -> None:
    for part in _split(text):
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": part},
                timeout=30,
            )
        except requests.RequestException as e:
            print(f"  aviso: fallo al enviar a {chat_id}: {e}")


def _check_backends() -> None:
    if not health():
        print("[ERROR] Ollama no responde. Inícialo con: ollama serve")
        sys.exit(1)


def run_loop(token: str) -> None:
    _check_backends()
    print("Bot en marcha. Escuchando mensajes (Ctrl+C para salir).")

    base = f"https://api.telegram.org/bot{token}"
    offset = None
    while True:
        try:
            resp = requests.get(
                f"{base}/getUpdates",
                params={"timeout": 30, "offset": offset},
                timeout=40,
            )
            updates = resp.json().get("result", [])
        except requests.RequestException as e:
            print(f"  aviso: getUpdates falló ({e}); reintento en 3s")
            time.sleep(3)
            continue

        for upd in updates:
            offset = upd["update_id"] + 1
            msg = upd.get("message") or upd.get("edited_message") or {}
            text = (msg.get("text") or "").strip()
            chat_id = (msg.get("chat") or {}).get("id")
            if not text or chat_id is None:
                continue
            if text.startswith("/start") or text.startswith("/help"):
                send(token, chat_id, WELCOME)
                continue
            print(f"  [{chat_id}] {text!r}")
            try:
                reply = answer(text)
            except Exception as e:  # noqa: BLE001
                print(f"  aviso: error generando respuesta: {e}")
                reply = "Lo siento, ocurrió un error procesando tu consulta. Intenta de nuevo."
            send(token, chat_id, reply)


def main() -> None:
    ap = argparse.ArgumentParser(description="Bot público de Telegram (RAG local + gemma/Ollama)")
    ap.add_argument("--ask", help="Modo prueba: responde una sola consulta y termina (sin Telegram).")
    args = ap.parse_args()

    if args.ask:
        _check_backends()
        print(answer(args.ask))
        return

    if not TELEGRAM_BOT_TOKEN:
        print("[ERROR] Falta TELEGRAM_BOT_TOKEN en .env.")
        print("        Crea el bot con @BotFather y define el token, o prueba sin Telegram:")
        print('        uv run python scripts/telegram_bot.py --ask "¿Qué incluye el chequeo Gold?"')
        sys.exit(1)
    run_loop(TELEGRAM_BOT_TOKEN)


if __name__ == "__main__":
    main()
