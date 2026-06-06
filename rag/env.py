"""Carga de variables de entorno desde <repo>/.env y valores por defecto."""

import os

from dotenv import load_dotenv

from .paths import ROOT_DIR

# Carga <repo>/.env si existe (las variables del sistema tienen prioridad).
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=False)

# --- Google Gemini (nube) — ÚNICO proveedor (chat + embeddings) ---
# Soporta tool-calling y 1M de contexto. No se usa Ollama ni modelos locales.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or ""
# El SDK google-genai también busca GOOGLE_GENERATIVE_AI_API_KEY; la sincronizamos.
if "GOOGLE_GENERATIVE_AI_API_KEY" not in os.environ and GEMINI_API_KEY:
    os.environ["GOOGLE_GENERATIVE_AI_API_KEY"] = GEMINI_API_KEY
GEMINI_CHAT_MODEL = os.environ.get("GEMINI_CHAT_MODEL") or "gemini-2.5-flash-lite"
GEMINI_EMBEDDING_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL") or "gemini-embedding-001"

# --- OpenFang (daemon REST) ---
OPENFANG_BASE_URL = (os.environ.get("OPENFANG_BASE_URL") or "http://127.0.0.1:4200").rstrip("/")
OPENFANG_API_KEY = os.environ.get("OPENFANG_API_KEY") or ""
AGENT_NAME = os.environ.get("AGENT_NAME") or "asistente-publico"

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or ""
# HITL / bot interno (rúbrica): chat del admin y grupo privado de la fundación.
TELEGRAM_ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID") or ""
TELEGRAM_INTERNAL_GROUP_ID = os.environ.get("TELEGRAM_INTERNAL_GROUP_ID") or ""
