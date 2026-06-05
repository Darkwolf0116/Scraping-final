# Asistente Valle del Lili — Bot de Telegram con RAG local (OpenFang + Ollama/gemma)

Bot de Telegram que responde sobre la **Fundación Valle del Lili** (sedes, especialistas,
servicios y páginas como el chequeo médico preventivo) usando **RAG local** sobre el sitio
institucional ya scrapeado, y **gemma4:e4b** servido por **Ollama** — todo offline.

> Rama de trabajo: **`prueba`**.

---

## Arquitectura (resumen de decisiones)

El plan original asumía cosas de OpenFang que **no existen** en la versión actual
(ingesta semántica masiva por REST, dos bots de Telegram con tokens distintos,
`openfang hand install`, botones inline). Tras analizar el repo y la API reales de
OpenFang, el diseño se ajustó así:

1. **RAG como índice vectorial local propio.** No hay endpoint REST de ingesta semántica
   en OpenFang. `scripts/ingest_docs.py` trocea los `.md`, calcula *embeddings* con
   `embeddinggemma` (Ollama) y los guarda en `data/rag_index.sqlite`. La búsqueda es por
   similitud de coseno (`rag/index.py`).

2. **Generación directa con gemma vía Ollama.** Enrutar la generación por el bucle de
   agente de OpenFang infla el prompt a ~20.000 tokens (inyecta 61 *skills* + andamiaje de
   *tool-calling*), lo que **desborda a gemma4:e4b (4B local)** y la hace responder basura.
   Por eso el orquestador habla **directamente con Ollama** con un prompt corto y
   controlado: `system` + contexto RAG recuperado + pregunta. Grounding determinista, sin
   *tool-calling* (que Gemma tampoco soporta).

3. **OpenFang queda como infraestructura opcional** (daemon, dashboard, registro del
   agente). `agents/public_agent.toml` define la *persona*/reglas del asistente y es la
   **fuente única** del *system prompt* (el orquestador lo lee de ahí). `scripts/configure_env.py`
   y `scripts/rag_mcp_server.py` permiten integrarlo si se desea (ver más abajo).

```
Telegram ──► scripts/telegram_bot.py
                 │  1) rag.index.search()  ── embeddinggemma (Ollama) + coseno
                 │  2) arma prompt: system (de public_agent.toml) + contexto + pregunta
                 └► rag.llm.chat() ── gemma4:e4b (Ollama /api/chat) ──► respuesta
```

---

## Requisitos

- **Ollama** en marcha (`ollama serve`) con los modelos:
  - `gemma4:e4b` (chat) — `ollama pull gemma4:e4b`
  - `embeddinggemma:latest` (embeddings) — `ollama pull embeddinggemma`
- **uv** (gestiona el entorno y dependencias).
- Python ≥ 3.13 (lo provee `uv`).
- *(Opcional)* **OpenFang** para dashboard/daemon.

---

## Puesta en marcha

```bash
# 1) Dependencias
uv sync

# 2) (si hace falta) generar los .md del sitio en ./output
uv run python main.py            # scraper existente

# 3) Construir el índice RAG (embeddings locales)
uv run python scripts/ingest_docs.py

# 4) Configurar entorno
copy .env.example .env           # Windows  (cp en Unix)
#   edita .env y pega TELEGRAM_BOT_TOKEN (de @BotFather)

# 5a) Probar SIN Telegram (verifica RAG + gemma):
uv run python scripts/telegram_bot.py --ask "¿Qué incluye el chequeo Gold?"

# 5b) Arrancar el bot de Telegram:
uv run python scripts/telegram_bot.py
```

Prueba de humo completa (incluye una consulta fuera de dominio):

```bash
uv run python scripts/smoke_test.py
```

---

## Estructura

```
.
├── output/                       # .md scrapeados (entrada del RAG; generados por main.py)
├── data/rag_index.sqlite         # índice vectorial (generado; reconstruible)
├── rag/                          # paquete RAG
│   ├── paths.py                  # rutas absolutas (raíz calculada en runtime)
│   ├── env.py                    # carga de .env y valores por defecto
│   ├── chunking.py               # troceo por cabeceras + limpieza de ruido
│   ├── embeddings.py             # embeddings vía Ollama (embeddinggemma)
│   ├── index.py                  # índice SQLite + búsqueda por coseno
│   ├── llm.py                    # generación con gemma vía Ollama (/api/chat)
│   └── answer.py                 # RAG por inyección: search + prompt + gemma
├── scripts/
│   ├── ingest_docs.py            # construye el índice RAG
│   ├── telegram_bot.py           # orquestador del bot (long-polling)
│   ├── smoke_test.py             # prueba de humo end-to-end
│   ├── configure_env.py          # (opcional) configura OpenFang con gemma
│   └── rag_mcp_server.py         # (opcional) servidor MCP para modelos con tool-calling
├── agents/public_agent.toml      # persona + system prompt (fuente única)
└── .env.example
```

## Chunking (troceo) por sección

- **especialistas/**: 1 chunk por archivo (perfil completo); se conservan las categorías como metadato.
- **servicios/**: 1 chunk por encabezado H2; se elimina el bloque `## Especialistas que pueden atenderte`.
- **sedes/**: 1 chunk por especialidad (H3) de "Servicios destacados" + intro.
- **pages/**: 1 chunk por H2; si hay H3 (p. ej. Basic/Advance/Gold), 1 chunk por H3.
- En todos: se elimina `## Enlaces encontrados en esta página`.

## Criterios de aceptación

1. **Detección de archivos** — `ingest_docs.py` falla con un mensaje claro si no hay `.md`. ✓
2. **Limpieza** — ningún chunk contiene `## Enlaces encontrados...` ni el bloque de médicos. ✓ (verificado en la ingesta)
3. **Anti-alucinación** — si la búsqueda no recupera contexto (consulta fuera de dominio),
   el bot indica que no tiene esa información, en vez de inventar. ✓ (el system prompt lo exige
   y el umbral `MIN_SCORE` descarta resultados irrelevantes)

---

## Integración opcional con OpenFang

```bash
uv run python scripts/configure_env.py   # default_model -> ollama/gemma4:e4b, copia el agente
openfang start                            # dashboard en http://127.0.0.1:4200/
```

`rag_mcp_server.py` expone la búsqueda como herramienta MCP: útil **solo** si se usa un
modelo con *tool-calling* (no Gemma). No es necesario para el bot.

## Fase 2 (pendiente)

Bot interno restringido a un grupo privado, colector autónomo de normativa de salud
(MinSalud/Supersalud/Invima) y flujo HITL de aprobación por Telegram. Se implementará
sobre esta misma base (RAG local + gemma) usando el agendador/`cron` de OpenFang y
aprobación por **comando** (`/approve`), ya que el adaptador de Telegram de OpenFang no
soporta botones inline.
