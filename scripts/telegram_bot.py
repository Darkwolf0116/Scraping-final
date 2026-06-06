#!/usr/bin/env python
"""Orquestador del bot público de Telegram (RAG local + Gemini, SIN tool-calling).

Por cada mensaje: búsqueda RAG (1 embedding de Gemini) -> inyección de contexto
(+ datos corporativos) -> UNA llamada a Gemini -> respuesta. Registra el costo
real de cada mensaje (tokens y ~COP) en consola.

NO usa el bucle de agente de OpenFang (que reinyecta ~20K tokens de skills y
encarece cada mensaje). Esta es la ruta óptima en costo y latencia.

Uso:
    uv run python scripts/telegram_bot.py
    uv run python scripts/telegram_bot.py --ask "¿Qué incluye el chequeo Gold?"
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.answer import answer  # noqa: E402
from rag.env import TELEGRAM_BOT_TOKEN  # noqa: E402
from rag.llm import LAST_USAGE, estimate_cost_usd, health  # noqa: E402

TG_MAX = 4096
USD_TO_COP = 4000  # referencia aproximada solo para mostrar el costo
WELCOME = (
    "¡Hola! Soy el asistente virtual de la Fundación Valle del Lili. "
    "Puedo ayudarte con información sobre sedes, horarios, especialistas, servicios y "
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


def _tg(token: str, method: str, payload: dict) -> None:
    """Llamada genérica a la Bot API (silenciosa). NO consume tokens del LLM."""
    try:
        requests.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=15)
    except requests.RequestException:
        pass


def react(token: str, chat_id: int, message_id: int, emoji: str = "👀") -> None:
    """Reacciona con un emoji al mensaje del usuario (acuse de recibo). Gratis."""
    _tg(token, "setMessageReaction", {
        "chat_id": chat_id,
        "message_id": message_id,
        "reaction": [{"type": "emoji", "emoji": emoji}],
    })


def _typing_loop(token: str, chat_id: int, stop: threading.Event) -> None:
    """Mantiene visible el indicador 'escribiendo…' hasta que la respuesta esté lista."""
    while not stop.is_set():
        _tg(token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
        stop.wait(4)  # el indicador dura ~5s; lo refrescamos cada 4s


def _log_cost() -> None:
    if not LAST_USAGE:
        return
    inp = LAST_USAGE.get("input", 0)
    out = LAST_USAGE.get("output", 0) + LAST_USAGE.get("thoughts", 0)
    usd = estimate_cost_usd(LAST_USAGE.get("model", ""), inp, out)
    print(f"    tokens in/out={inp}/{out}  ~${usd:.6f}  (~COP {usd * USD_TO_COP:.2f})")


def _check_backends() -> None:
    if not health():
        print("[ERROR] Proveedor de chat no disponible (¿falta GEMINI_API_KEY en .env?).")
        sys.exit(1)
    try:
        from rag.embeddings import embed_one

        embed_one("ping")
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] El backend de embeddings (Gemini) falló: {e}")
        print("        Verifica GEMINI_API_KEY en .env y tu conexión a internet.")
        sys.exit(1)


def run_loop(token: str) -> None:
    _check_backends()
    print("Bot en marcha. Escuchando mensajes (Ctrl+C para salir).")
    base = f"https://api.telegram.org/bot{token}"
    offset = None
    while True:
        try:
            resp = requests.get(f"{base}/getUpdates", params={"timeout": 30, "offset": offset}, timeout=40)
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
            message_id = msg.get("message_id")
            if not text or chat_id is None:
                continue
            if text.startswith("/start") or text.startswith("/help"):
                send(token, chat_id, WELCOME)
                continue
            print(f"  [{chat_id}] {text!r}")
            # Acuse de recibo (reacción) + indicador "escribiendo…" — ambos gratis.
            if message_id is not None:
                react(token, chat_id, message_id, "👀")
            stop = threading.Event()
            typing = threading.Thread(target=_typing_loop, args=(token, chat_id, stop), daemon=True)
            typing.start()
            t0 = time.time()
            try:
                reply = answer(text)
            except Exception as e:  # noqa: BLE001
                print(f"  aviso: error generando respuesta: {e}")
                reply = "Lo siento, ocurrió un error procesando tu consulta. Intenta de nuevo."
            finally:
                stop.set()  # detiene el indicador de escritura
            send(token, chat_id, reply)
            print(f"    respondido en {time.time() - t0:.1f}s")
            _log_cost()


def main() -> None:
    ap = argparse.ArgumentParser(description="Bot público de Telegram (RAG local + Gemini)")
    ap.add_argument("--ask", help="Modo prueba: responde una sola consulta y termina (sin Telegram).")
    args = ap.parse_args()

    if args.ask:
        _check_backends()
        print(answer(args.ask))
        _log_cost()
        return

    if not TELEGRAM_BOT_TOKEN:
        print("[ERROR] Falta TELEGRAM_BOT_TOKEN en .env.")
        print('        Prueba sin Telegram:  uv run python scripts/telegram_bot.py --ask "..."')
        sys.exit(1)
    run_loop(TELEGRAM_BOT_TOKEN)


if __name__ == "__main__":
    main()
