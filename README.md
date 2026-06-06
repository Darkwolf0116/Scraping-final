# Agent OS (OpenFang) — Fundación Valle del Lili

Sistema Operativo Agéntico sobre **OpenFang** para la **Fundación Valle del Lili**,
con **Google Gemini** como único proveedor de modelo (chat + embeddings; sin Ollama
ni modelos locales). Implementa la **RUTA B** del proyecto:

1. **Entorno + OpenFang + Gemini** — kernel agéntico nativo en Rust, modelo en la nube.
2. **Migración del conocimiento** a la memoria del OS — **Vector Store** (RAG) + **Structured KV Store**.
3. **Operaciones autónomas (Hands System)** — `HAND.toml` del **Collector Regulatorio** (Opción B/C).
4. **Despliegue en canales** — bridge nativo de **Telegram** (público + interno).

---

## Arquitectura

```
Telegram ──► [channels.telegram] (bridge nativo de OpenFang)
   │
   ├─ chat público ─► agente "asistente-publico"  (Gemini 2.5 Flash-Lite)
   │                     │
   │                     ├─► MCP buscar_institucional()      → Vector Store (RAG)
   │                     └─► MCP consultar_datos_corporativos → KV Store nativo
   │
   └─ grupo interno ─► agente "asistente-interno"
                          └─► MCP buscar_regulatorio()       → índice regulatorio

Hand autónomo "collector-regulatorio"  (corre solo, schedule semanal)
   └─ vigila MinSalud/Supersalud/Invima → borradores → [aprobación HITL] → índice regulatorio
                                                          dashboard: http://127.0.0.1:4200
```

---

## Cómo funciona (flujo de una consulta)

1. El usuario escribe por **Telegram**; el *bridge* nativo de OpenFang entrega el mensaje al agente `asistente-publico`.
2. El agente (Gemini) **decide llamar una herramienta** (*tool-calling*): para médicos/servicios usa `buscar_institucional`; para sedes/horarios/contactos, `consultar_datos_corporativos`.
3. La herramienta vive en un **servidor MCP** (Python) que consulta el RAG: convierte la pregunta en un *embedding* y rankea por **similitud de coseno** contra el Vector Store (SQLite).
4. El agente recibe los fragmentos relevantes y **Gemini redacta** la respuesta usando *solo* ese contexto. **Regla de oro: no inventa.**
5. La respuesta vuelve al usuario por Telegram.

**Dos rutas de ejecución** comparten el mismo cerebro RAG (`rag/`):

- **OpenFang (nativa):** `make start` → con *tool-calling*, Hands y dashboard. Es la ruta oficial de la RUTA B.
- **Directa (mínimo costo):** `make start-directo` → `rag/answer.py` hace la búsqueda e inyecta el contexto en **una sola llamada** a Gemini, sin el bucle de agente.

> Para entender la lógica a fondo (función por función), ver **[explicación.md](explicación.md)**.

---

## Requisitos

- **Google Gemini API key** (gratis en https://aistudio.google.com/apikey) — único proveedor.
- **OpenFang** instalado: `curl -fsSL https://openfang.sh/install | sh` (~32 MB, 2 GB RAM).
- **uv** (gestor de entorno Python) y Python >= 3.13.
- **Un bot de Telegram**: créalo con [@BotFather](https://t.me/BotFather) (`/newbot`) y copia el **token**.

> Este proyecto **no usa Ollama**. Toda la inteligencia (chat y embeddings) corre
> contra la API de Gemini.

---

## Puesta en marcha — solo dos comandos

```bash
copy .env.example .env     # edita .env: pega GEMINI_API_KEY y TELEGRAM_BOT_TOKEN

make setup                 # (1) offline: deps + índices RAG/regulatorio + config OpenFang
make start                 # (2) levanta OpenFang + Telegram + dashboard + activa el Hand
```

- `make setup` deja todo listo sin tocar nada del daemon (deps, Vector Store,
  índice regulatorio de demo y `~/.openfang/config.toml`).
- `make start` arranca OpenFang (daemon + bridge de Telegram + **dashboard en
  http://127.0.0.1:4200**) y registra/activa el Hand `collector-regulatorio`.
  Ctrl+C lo detiene.

> Si aún no tienes el scraping: `make run` (genera los `.md` de `output/`) antes de `make setup`.
> ¿Mínimo costo y sin OpenFang? `make start-directo` (responde sin el bucle de agente).

---

## Módulo 2 — Memoria del OS (Vector Store + KV Store)

OpenFang asimila la identidad corporativa en dos de sus capas de memoria:

| Capa | Contenido | Cómo se carga |
|------|-----------|---------------|
| **Vector Store** (semántico) | Especialistas, servicios, chequeos, páginas (scraping) | `make setup` → `data/rag_index.sqlite` |
| **Structured KV Store** (nativo del agente) | Sedes, horarios, contactos, EPS, NIT | `make kv` *(una vez, con el daemon arriba)* |

El agente recupera de cada capa con su herramienta MCP (`buscar_institucional` /
`consultar_datos_corporativos`). El Vector Store lo crea `make setup`; el KV nativo
se carga una vez con `make kv` después de `make start`.

---

## Módulo 3 — Hands System (operaciones autónomas)

Un **Hand** es un paquete de capacidad **autónomo**: corre solo en su horario,
construye conocimiento y reporta al dashboard. Aquí se implementa un Hand
**personalizado** (Opción B/C): **inteligencia regulatoria de salud**.

```
hands/collector-regulatorio/
├── HAND.toml          # manifiesto: id, tools, [[settings]], [agent] (con el playbook
│                      #   inline en system_prompt) y [dashboard] — esquema real de OpenFang
├── SKILL.md           # conocimiento experto (regulación de salud CO), se inyecta solo
└── samples/           # normas de ejemplo para la demo (semilla del índice)
```

**Qué hace:** vigila MinSalud, Supersalud, Invima e INS, detecta normativa nueva
relevante para una IPS, la resume y deja **borradores** para aprobación humana
(**HITL**) antes de exponerla al agente interno.

**`make start` registra y activa el Hand automáticamente.** Para gestionarlo a mano:

```bash
openfang hand status   collector-regulatorio     # métricas en http://127.0.0.1:4200
openfang hand pause    collector-regulatorio
openfang hand activate collector-regulatorio
```

### Pipeline HITL (borrador → aprobación → índice)

`make setup` ya siembra el índice regulatorio con las normas de ejemplo. En operación,
el Hand deja borradores nuevos en `data/pending_regulatory/` con `estado: pendiente`;
el ciclo humano (HITL) es:

```bash
# Un humano revisa y aprueba un borrador:
uv run python scripts/ingest_regulatory.py --approve <archivo.md>

# Reconstruir el índice regulatorio con lo APROBADO:
make regulatory
```

Tras esto, el agente interno responde normativa vía `buscar_regulatorio`.

> **Otras Hands de OpenFang** (Opción A "Lead", Browser, Collector, etc.) se activan
> igual: `openfang hand activate <nombre>`. Aquí se priorizó el Collector regulatorio
> por ser el más auténtico para una institución de salud.

---

## Módulo 4 — Canales (Telegram)

`configure_env.py` escribe en `~/.openfang/config.toml` el **bridge nativo de Telegram**:

- **Chat público** → `asistente-publico` (atención al usuario).
- **Grupo interno** (`TELEGRAM_INTERNAL_GROUP_ID`) → `asistente-interno` (regulatorio).

Crea el bot con **@BotFather** (`/newbot`), pega el `TELEGRAM_BOT_TOKEN` en `.env` y
ejecuta `make setup` (que genera el config). Un cliente escribe al bot y es atendido
por el agente con el contexto ingerido (RAG interno del OS).

---

## Economía de tokens (Gemini cobra por token)

Palancas ya aplicadas para mantener el costo bajo:

- **Modelo `*-flash-lite`** por defecto (chat y agentes) — el tier más barato.
- **Thinking desactivado** (`thinking_budget=0`) en todas las llamadas de chat.
- **Skills bundled suprimidos** en los agentes (`skills = ["__sin_skills__"]`): evita
  reinyectar ~20K tokens/mensaje del bucle de agente de OpenFang.
- **Hand acotado:** schedule **semanal**, `max_items_per_run`, `max_iterations` y
  resúmenes breves → cada corrida autónoma tiene un costo techo.
- **Embeddings** solo al ingerir y 1 por consulta (muy barato).
- **Ruta directa opcional** (`make start-directo`): responde sin el bucle de agente
  de OpenFang; es la opción de **mínimo costo** si no necesitas Hands ni dashboard.

Mide el costo real por consulta:

```bash
make test     # imprime tokens y ~COP por pregunta
```

---

## Variables de entorno (`.env`)

| Variable | Ejemplo | Descripción |
|----------|---------|-------------|
| `GEMINI_API_KEY` | `AIza...` | **(Requerido)** API key de Google Gemini |
| `GEMINI_CHAT_MODEL` | `gemini-2.5-flash-lite` | Modelo de chat. **Debe existir en el catálogo de OpenFang** y soportar *tools* |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Modelo de embeddings (RAG) |
| `TELEGRAM_BOT_TOKEN` | `86035...` | Token del bot (@BotFather) |
| `AGENT_NAME` | `asistente-publico` | Agente público por defecto |
| `TELEGRAM_INTERNAL_GROUP_ID` | `-100...` | *(opcional)* grupo interno → agente regulatorio |
| `TELEGRAM_ADMIN_CHAT_ID` | `12345` | *(opcional)* admin que aprueba borradores (HITL) |

---

## Estructura

```
.
├── output/                       # .md scrapeados (entrada del RAG)
├── data/
│   ├── institucional.json        # datos corporativos (KV)
│   ├── rag_index.sqlite          # Vector Store (generado)
│   ├── pending_regulatory/       # borradores del Hand (HITL)
│   └── regulatory_index.sqlite   # índice regulatorio aprobado (generado)
├── rag/                          # paquete RAG (Gemini)
│   ├── env.py · paths.py         # entorno y rutas
│   ├── chunking.py               # troceo por cabeceras
│   ├── embeddings.py             # embeddings con Gemini
│   ├── index.py                  # índice SQLite + búsqueda coseno
│   ├── llm.py                    # chat con Gemini (thinking off)
│   └── answer.py                 # RAG por inyección de contexto (ruta directa)
├── agents/
│   ├── public_agent.toml         # manifiesto agente público
│   └── internal_agent.toml       # manifiesto agente interno (regulatorio)
├── hands/
│   └── collector-regulatorio/    # Hand autónomo (HAND.toml + SKILL.md + samples/)
├── scripts/
│   ├── ingest_docs.py            # Vector Store
│   ├── ingest_kv.py              # KV Store nativo
│   ├── ingest_regulatory.py      # pipeline HITL → índice regulatorio
│   ├── configure_env.py          # genera config.toml de OpenFang
│   ├── rag_mcp_server.py         # herramientas MCP del RAG
│   ├── telegram_bot.py           # ruta directa (bajo costo, sin agente OpenFang)
│   └── smoke_test.py             # prueba de humo + costo real
├── start_bot.ps1                 # launcher de `make start` (orquesta OpenFang)
├── Makefile                      # comandos (setup, start, kv, ...)
├── README.md                     # esta guía
├── explicación.md                # documentación técnica a fondo
├── guión_sustentación.md         # guión de sustentación (4 integrantes)
└── .env.example
```

## Comandos (Makefile)

**Flujo principal — solo dos:**

```bash
make setup    # (1) prepara todo offline (deps + índices + config OpenFang)
make start    # (2) levanta el Agent OS (OpenFang + Telegram + dashboard + Hand)
```

**Avanzados (opcionales):**

```bash
make start-directo   # ruta sin OpenFang (mínimo costo de tokens)
make kv              # cargar institucional.json al KV nativo (daemon arriba)
make rebuild         # reconstruir el Vector Store (RAG)
make regulatory      # reconstruir el índice regulatorio (borradores aprobados)
make test            # prueba de humo (tokens + costo)
make help            # lista todos los targets

openfang status                   # estado del daemon y agentes
openfang chat asistente-publico   # chat directo con el agente
```

---

## Documentación adicional

- **[explicación.md](explicación.md)** — documentación técnica completa: arquitectura,
  pipeline de datos, cada script con sus funciones clave, decisiones de diseño (gotchas)
  y flujo end-to-end.
- **[guión_sustentación.md](guión_sustentación.md)** — guión de la sustentación (15 min,
  repartido entre los 4 integrantes) con demo en vivo y batería de preguntas del jurado.

---

## Solución de problemas

**El agente responde pero NO usa las herramientas (da datos genéricos o "no tengo acceso").**
Casi siempre es el **modelo**: el ID en `GEMINI_CHAT_MODEL` y en los manifiestos de `agents/`
debe existir en el catálogo de OpenFang y soportar *tools*. Por ejemplo, `gemini-3.1-flash-lite`
(sin `-preview`) **no existe** → OpenFang no habilita *tool-calling*; usa `gemini-2.5-flash-lite`.
Si el agente "aprendió" a responder mal, limpia su sesión (en Telegram: comando `/new`) y reintenta.

**El agente no encuentra especialistas / datos ("inconveniente técnico").**
Significa que el servidor MCP `rag` no está cargado en el daemon. OpenFang ejecuta los
MCP en un sandbox que limpia el entorno, por lo que el RAG se lanza con el **python del
venv** (no `uv`) y reenvía `GEMINI_API_KEY` vía la lista `env`. Si lo ves: `make start`
(regenera el config y reinicia el daemon). Verifica con `openfang logs` que el servidor
`rag` arrancó y expone `buscar_institucional`.

**`Daemon already running`.** Un daemon viejo no aplica la config nueva. `make start` ya
lo detiene y reinicia solo; si lo haces a mano: `openfang stop` y vuelve a arrancar.

**`make start` cambia config/daemon cada vez.** Es intencional: regenerar el config es
gratis (no usa API) y garantiza que el MCP y el bridge queden correctos.
