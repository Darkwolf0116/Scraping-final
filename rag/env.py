"""Carga de variables de entorno desde <repo>/.env y valores por defecto."""

import os

from dotenv import load_dotenv

from .paths import ROOT_DIR

# Carga <repo>/.env si existe (las variables del sistema tienen prioridad).
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=False)

# --- Ollama (local) ---
OLLAMA_BASE_URL = (os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL") or "embeddinggemma:latest"
# Modelo de chat (cerebro del agente). Gemma local del usuario; NO requiere
# tool-calling porque el contexto RAG se inyecta en el prompt.
AGENT_MODEL = os.environ.get("AGENT_MODEL") or "gemma4:e4b"

# --- OpenFang (daemon REST) ---
# El orquestador delega la redacción de la respuesta aquí.
OPENFANG_BASE_URL = (os.environ.get("OPENFANG_BASE_URL") or "http://127.0.0.1:4200").rstrip("/")
OPENFANG_API_KEY = os.environ.get("OPENFANG_API_KEY") or ""
# Nombre del agente OpenFang (gemma) que redacta las respuestas.
AGENT_NAME = os.environ.get("AGENT_NAME") or "asistente-publico"

# --- Telegram (orquestador) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or ""
