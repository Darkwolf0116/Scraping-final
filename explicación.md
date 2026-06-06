# Explicación detallada del repositorio

**Asistente corporativo de la Fundación Valle del Lili** — un Sistema Operativo
Agéntico (Agent OS) construido sobre **OpenFang**, con **Google Gemini** como único
proveedor de IA, que atiende usuarios por **Telegram** usando **RAG** (recuperación
aumentada por generación) sobre el contenido del sitio web de la Fundación.

Este documento explica, de arriba a abajo, **qué hace cada pieza, cómo encajan y por
qué se tomaron las decisiones clave**. Está pensado para que cualquier persona entienda
toda la lógica del repositorio sin tener que leer el código línea por línea.

---

## Índice

1. [Glosario de términos](#1-glosario-de-términos)
2. [Visión general: qué hace el sistema](#2-visión-general-qué-hace-el-sistema)
3. [Arquitectura y flujo de datos](#3-arquitectura-y-flujo-de-datos)
4. [Las dos rutas de ejecución](#4-las-dos-rutas-de-ejecución)
5. [El pipeline de datos paso a paso](#5-el-pipeline-de-datos-paso-a-paso)
6. [Módulo `scraper/` — extracción del sitio web](#6-módulo-scraper--extracción-del-sitio-web)
7. [Módulo `rag/` — el cerebro de la recuperación](#7-módulo-rag--el-cerebro-de-la-recuperación)
8. [Carpeta `scripts/` — orquestación y herramientas](#8-carpeta-scripts--orquestación-y-herramientas)
9. [Carpeta `agents/` — los agentes de OpenFang](#9-carpeta-agents--los-agentes-de-openfang)
10. [Carpeta `hands/` — operaciones autónomas (Hands System)](#10-carpeta-hands--operaciones-autónomas-hands-system)
11. [`start_bot.ps1` y `Makefile` — arranque](#11-start_botps1-y-makefile--arranque)
12. [Economía de tokens (por qué es barato)](#12-economía-de-tokens-por-qué-es-barato)
13. [Decisiones de diseño no obvias (gotchas)](#13-decisiones-de-diseño-no-obvias-gotchas)
14. [Flujo completo de un mensaje (end-to-end)](#14-flujo-completo-de-un-mensaje-end-to-end)
15. [Cómo correr todo](#15-cómo-correr-todo)

---

## 1. Glosario de términos

| Término | Qué significa aquí |
|---------|--------------------|
| **OpenFang** | "Agent OS": un sistema operativo para agentes de IA, escrito en Rust. Corre como un *daemon* (servicio en segundo plano), expone una API REST + dashboard en `http://127.0.0.1:4200`, conecta canales (Telegram), administra agentes, memoria, herramientas (MCP) y *Hands*. |
| **Daemon** | El proceso de OpenFang que queda corriendo y atiende todo. Se arranca con `openfang start`. |
| **Agente** | Una "persona" configurada (nombre, prompt de sistema, modelo, herramientas). Aquí hay dos: `asistente-publico` (atención al usuario) y `asistente-interno` (consultas regulatorias). |
| **LLM** | *Large Language Model*. Aquí siempre es **Gemini** (modelo `gemini-2.5-flash-lite`), en la nube. Genera el texto de las respuestas. |
| **RAG** | *Retrieval-Augmented Generation*. En vez de confiar en lo que el LLM "sabe", primero **se busca** información relevante en una base propia y se le **inyecta** como contexto. Evita que invente. |
| **Embedding** | Un vector de números (aquí de **3072 dimensiones**) que representa el "significado" de un texto. Textos parecidos tienen vectores cercanos. Se generan con `gemini-embedding-001`. |
| **Vector Store** | Base de datos de embeddings. Aquí es un archivo SQLite (`data/rag_index.sqlite`) con el texto + su vector. |
| **Similitud de coseno** | Métrica para medir qué tan "cercanos" son dos vectores (0 a 1). Es como se rankean los resultados de búsqueda. |
| **KV Store** | *Key-Value Store* (almacén clave-valor). Memoria estructurada del agente en OpenFang: cada sección corporativa (sedes, horarios…) es una entrada. |
| **Chunk** | Un "trozo" de texto indexable. Los documentos se parten en chunks coherentes (un perfil de médico, una sección de servicio…) antes de generar embeddings. |
| **MCP** | *Model Context Protocol*. Estándar para exponer **herramientas** a un agente. Aquí un servidor MCP en Python expone 3 herramientas de búsqueda al agente de OpenFang. |
| **Tool-calling** | La capacidad del LLM de "llamar" una herramienta (p. ej. `buscar_institucional`) en medio de su razonamiento, recibir el resultado y seguir. |
| **Hand** | Paquete de capacidad **autónoma** de OpenFang: corre solo en un horario, sin que nadie le escriba. Aquí: un vigilante de normativa de salud. |
| **HITL** | *Human-In-The-Loop*. Un humano aprueba antes de publicar. La Hand deja borradores; alguien los aprueba; recién ahí entran al índice. |
| **Bridge / canal** | El puente nativo de OpenFang que conecta el agente con Telegram (recibe y envía mensajes). |
| **Sesión** | La conversación de un usuario con un agente. Guarda el historial. Cada chat de Telegram tiene su sesión. |

---

## 2. Visión general: qué hace el sistema

1. **Se "raspa" (scrapea) el sitio web** de la Fundación Valle del Lili → produce archivos
   Markdown limpios (`output/`), organizados por sección (especialistas, servicios, sedes, páginas…).
2. **Se construye una base de conocimiento** a partir de esos `.md`:
   - un **Vector Store** semántico (para búsqueda por significado), y
   - un **KV Store** con datos corporativos estructurados (sedes, horarios, contactos…).
3. **OpenFang** levanta dos agentes y los conecta a **Telegram**.
4. Cuando un usuario escribe, el agente **llama herramientas de búsqueda (MCP)**, recupera
   el contexto relevante, y **Gemini** redacta la respuesta usando *solo* ese contexto.
5. Una **Hand autónoma** vigila normativa de salud y deja borradores para aprobación humana,
   que luego alimentan al agente interno.

La regla de oro de todo el diseño: **el LLM nunca inventa; solo redacta a partir de lo
que las herramientas le devuelven.**

---

## 3. Arquitectura y flujo de datos

```
                    ┌─────────────────────── INGESTA (una vez) ───────────────────────┐
                    │                                                                  │
  Sitio web  ──►  scraper/  ──►  output/*.md  ──►  rag/chunking  ──►  rag/embeddings   │
  (sitemap)        (main.py)     (frontmatter)      (Chunks)          (Gemini 3072-d)  │
                                                                          │            │
                                       data/rag_index.sqlite  ◄───────────┘            │
                                       data/institucional.json (KV corporativo)        │
                    └──────────────────────────────────────────────────────────────────┘

                    ┌──────────────────────── EJECUCIÓN (en vivo) ────────────────────┐
                    │                                                                  │
  Usuario ─► Telegram ─► [bridge OpenFang] ─► Agente "asistente-publico" (Gemini)      │
                                                  │                                    │
                                                  │ tool-calling (MCP)                 │
                                                  ▼                                    │
                                       scripts/rag_mcp_server.py                       │
                                         • buscar_institucional ─► rag/index (vector)  │
                                         • consultar_datos_corporativos ─► JSON KV     │
                                         • buscar_regulatorio ─► índice regulatorio    │
                                                  │                                    │
                                                  ▼                                    │
                                       Gemini redacta con el contexto ─► Telegram      │
                                                                                       │
  Hand "collector-regulatorio" (autónoma, semanal) ─► borradores ─► [HITL] ─► índice   │
                    └──────────────────────────────────────────────────────────────────┘
```

**Componentes y su rol:**

- **OpenFang (daemon)** — orquestador. Recibe de Telegram, ejecuta el bucle del agente
  (incluyendo tool-calling), administra memoria y la Hand. Config en `~/.openfang/config.toml`.
- **Gemini (nube)** — único proveedor: chat (`gemini-2.5-flash-lite`) y embeddings
  (`gemini-embedding-001`). No se usa Ollama ni ningún modelo local.
- **Servidor MCP (Python)** — el puente entre OpenFang y el RAG: expone las herramientas
  de búsqueda. OpenFang lo lanza como subproceso.
- **Paquete `rag/`** — toda la lógica de troceo, embeddings, índice y búsqueda.

---

## 4. Las dos rutas de ejecución

El repo soporta **dos formas de responder**, con el mismo cerebro RAG:

### Ruta A — OpenFang nativa (la de RUTA B del proyecto)
`make start` → daemon de OpenFang → bridge de Telegram → agente → **tool-calling** →
servidor MCP → RAG → Gemini. Incluye dashboard, Hands y memoria del OS.
**Es la ruta "oficial"** y la que usa el bot.

### Ruta B — Directa (mínimo costo)
`make start-directo` → `scripts/telegram_bot.py` → `rag/answer.py` → Gemini.
**No usa el bucle de agente de OpenFang.** Es más barata y simple: hace la búsqueda
en Python, inyecta el contexto y llama a Gemini **una sola vez** (sin tool-calling).
Útil cuando no necesitas Hands ni dashboard.

> Ambas rutas comparten `rag/` (embeddings, índice, búsqueda). La diferencia es **quién
> orquesta**: OpenFang (con tool-calling) o un script Python directo (inyección de contexto).

---

## 5. El pipeline de datos paso a paso

1. **Sitemap → URLs.** `scraper/sitemap.py` lee el `sitemap_index.xml` del sitio y saca
   todas las URLs, etiquetando cada una con su **sección** (folder).
2. **URLs → HTML → Markdown.** `scraper/fetcher.py` descarga cada página (5 hilos, con
   reintentos y *resume*) y `scraper/extractor.py` la convierte a Markdown limpio con
   **frontmatter YAML** (`title`, `categorias`, `seccion`, `url`). Salida en `output/<seccion>/*.md`.
3. **Markdown → Chunks.** `rag/chunking.py` parte cada `.md` en trozos coherentes según
   su estructura de cabeceras (reglas distintas por sección).
4. **Chunks → Embeddings → Índice.** `scripts/ingest_docs.py` genera el embedding de cada
   chunk con Gemini y los guarda en `data/rag_index.sqlite` (texto + metadatos + vector).
5. **Datos corporativos → KV.** `data/institucional.json` (sedes, horarios, contactos…) se
   carga en el KV nativo del agente con `scripts/ingest_kv.py`.
6. **Consulta.** En vivo, una pregunta se convierte en embedding, se compara por **coseno**
   contra el índice, y los chunks más cercanos se le pasan a Gemini como contexto.

---

## 6. Módulo `scraper/` — extracción del sitio web

Convierte el sitio público en el corpus de conocimiento. Entrada: el sitemap. Salida:
`output/<seccion>/<slug>.md`.

### `scraper/config.py`
Configuración del scraper. Lo importante:
- `SITEMAP_INDEX_URL` — el índice de sitemaps del sitio.
- `SITEMAP_TO_FOLDER` — mapea cada sitemap a una **carpeta/sección** (`especialistas-sitemap.xml → especialistas`, etc.). Esto define las secciones del corpus.
- `MAX_WORKERS=5`, `REQUEST_DELAY=0.5`, `REQUEST_TIMEOUT=30`, `MAX_RETRIES=3` — concurrencia y cortesía con el servidor.

### `scraper/sitemap.py`
Descubre **qué** páginas scrapear.
- `@dataclass SitemapEntry` — una URL con su `lastmod`, `folder` (sección) y `slug` (nombre de archivo).
- `parse_sitemap_index()` — lee el índice y devuelve la lista de sitemaps hijos.
- `parse_child_sitemap(url)` — de un sitemap saca todas las `SitemapEntry`.
- `collect_all_entries(category=None)` — **función principal**: recorre todos los sitemaps
  (o solo una `category`) y devuelve todas las entradas a procesar.

### `scraper/fetcher.py`
Descarga **en paralelo** y guarda.
- `scrape_all(entries)` — **función principal**: usa un `ThreadPoolExecutor` (5 hilos) para
  procesar todas las entradas; devuelve un resumen (`total/success/skipped/errors`).
- `_scrape_one(entry, ...)` — descarga una página; **si el `.md` ya existe, la salta**
  (esto es el *resume*: puedes reanudar un scraping interrumpido). Reintenta con *backoff*.
- `_rate_limit()` — respeta `REQUEST_DELAY` por hilo.
- `_sanitize_filename()` / `_output_path()` — calculan la ruta de salida segura.

### `scraper/extractor.py`
Convierte el HTML de cada página en Markdown limpio con metadatos. Es el archivo más grande
porque tiene lógica especial por tipo de página.
- `extract_content(html, url)` — **orquestador**: devuelve un dict con título, fecha,
  categorías, enlaces y cuerpo.
- `_extract_title`, `_extract_date`, `_extract_categories`, `_extract_content_links` — sacan
  cada metadato del HTML (con BeautifulSoup).
- `_clean_soup` / `_extract_body` — eliminan menús/ruido y extraen el contenido real.
- `_extract_specialist_profile(soup, url)` + `_build_specialist_markdown(profile)` — **lógica
  especial para perfiles de médicos**: extrae nombre, especialidades, sedes, extensión, etc.,
  incluso de bloques "shadow DOM". Por eso el bot puede listar nombres y extensiones.
- `format_markdown_file(url, section, data)` — arma el archivo final: **frontmatter YAML**
  (`title`, `categorias`, `seccion`, `url`) + el cuerpo en Markdown. Ese frontmatter es lo
  que luego lee el chunker.

### `main.py`
Punto de entrada del scraper. `python main.py [--category <seccion>]`:
1. `collect_all_entries()` → 2. imprime cuántas URLs por sección → 3. `scrape_all()` →
4. reporte final. `--category` permite scrapear solo una sección.

---

## 7. Módulo `rag/` — el cerebro de la recuperación

Paquete compartido por **todas** las rutas. Cada archivo tiene una responsabilidad.

### `rag/paths.py` — rutas absolutas
Calcula `ROOT_DIR` **dinámicamente** desde la ubicación del archivo (no rutas fijas), para
que funcione sin importar dónde se clone. Define:
- `INDEX_PATH` = `data/rag_index.sqlite` (Vector Store principal).
- `REGULATORY_INDEX_PATH` = `data/regulatory_index.sqlite` (normativa aprobada).
- `PENDING_REGULATORY_DIR` = `data/pending_regulatory/` (borradores de la Hand, HITL).
- `AGENT_MANIFEST` / `INTERNAL_AGENT_MANIFEST` — los `.toml` de los agentes.
- `scraped_data_dir()` — carpeta de los `.md` (por defecto `output/`, override con `SCRAPED_DATA_DIR`).

### `rag/env.py` — variables de entorno
Carga `.env` (con `python-dotenv`) y expone la configuración. Lo clave:
- `GEMINI_API_KEY` — la única credencial necesaria. Además **sincroniza**
  `GOOGLE_GENERATIVE_AI_API_KEY` (el SDK de Google la busca con ese nombre).
- `GEMINI_CHAT_MODEL` (por defecto `gemini-2.5-flash-lite`) y `GEMINI_EMBEDDING_MODEL`
  (`gemini-embedding-001`).
- `OPENFANG_BASE_URL`, `AGENT_NAME`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT_ID`,
  `TELEGRAM_INTERNAL_GROUP_ID`.

### `rag/embeddings.py` — vectores con Gemini
Convierte texto en vectores. **Solo Gemini** (se eliminó Ollama).
- `embed(texts)` / `embed_one(text)` — **API pública**: devuelven los vectores.
- `_gemini_embed(texts)` — llama a la API en **lotes de 100** y reintenta ante error 429
  (cuota) respetando el tiempo de espera que indica la API.
- `active_model()` — el nombre del modelo (se guarda en el índice para trazabilidad).

### `rag/chunking.py` — troceo inteligente
Parte cada `.md` en `Chunk`s coherentes. Las reglas importan mucho para la calidad:
- `@dataclass Chunk` — campos `text, title, url, seccion, source, heading, categorias`.
- `chunk_file(path)` — **entrada principal**: lee frontmatter + contenido y devuelve los chunks.
- Reglas por sección: **especialistas = 1 chunk por archivo** (el perfil completo, para no
  fragmentar a un médico); **servicios = 1 chunk por H2**; **sedes = por H3**; **pages =
  por H2/H3** (p. ej. chequeos Basic/Advance/Gold quedan separados).
- `_drop_noise()` — elimina secciones ruidosas ("Enlaces encontrados…", "Especialistas que
  pueden atenderte…") que ensuciaban el ranking.
- `MIN_CHARS=60` — descarta trozos sin texto útil.

### `rag/index.py` — Vector Store + búsqueda por coseno
El corazón de la recuperación. SQLite + NumPy.
- `build(chunks, path=INDEX_PATH)` — embebe los chunks y **(re)escribe** el índice SQLite
  (tabla `chunks` con texto+metadatos+vector, y tabla `meta` con modelo/dimensión/conteo).
- `search(query, k, seccion=None, path=INDEX_PATH)` — **función estrella**: embebe la
  consulta y devuelve los `k` chunks más similares (con su `score`). Acepta filtrar por
  `seccion` **dentro** del ranking (clave para que las búsquedas de especialistas no se
  "tapen" con servicios).
- `search_vec(qvec, ...)` — igual pero a partir de un vector ya calculado (permite reusar
  un mismo embedding para varias búsquedas y ahorrar llamadas).
- `_load(path)` — carga el índice a memoria **con caché** (por `mtime`) y deja la matriz de
  vectores **normalizada**, para que el coseno sea un simple producto matriz·vector.

### `rag/llm.py` — generación con Gemini
- `chat(messages, ...)` — **API pública** de chat.
- `_chat_gemini(...)` — llama a Gemini con **"thinking" desactivado** (`thinking_budget=0`):
  respuestas directas y mucho más baratas; si el modelo no acepta esa opción, reintenta sin ella.
- `LAST_USAGE` — guarda los tokens de la última llamada (para reportar costo real).
- `estimate_cost_usd(model, in, out)` — estima el costo según tarifas aproximadas (`_RATES`).
- `health()` — `True` si hay `GEMINI_API_KEY`.

### `rag/answer.py` — RAG por inyección de contexto (Ruta directa)
Implementa la **Ruta B** (sin OpenFang). Una sola llamada al LLM.
- `answer(query)` — **función principal**: `retrieve()` + `build_messages()` + `chat()`.
- `retrieve(query, k)` — busca los chunks relevantes y, si la pregunta menciona médicos
  (`_DOCTOR_HINTS`), **refuerza** con perfiles de especialistas (`ESP_BOOST=5`).
- `_corporate_context(query)` — si la pregunta toca sedes/horarios/contactos, inyecta esas
  secciones de `institucional.json` (mapa de palabras clave → claves del JSON).
- `build_messages()` — arma el prompt: bloque(s) de CONTEXTO + la pregunta. `SYSTEM` es el
  prompt de sistema (responder solo con el contexto, no inventar).
- Constantes: `MIN_SCORE=0.35` (umbral de relevancia), `TOP_K=6`.

---

## 8. Carpeta `scripts/` — orquestación y herramientas

### `scripts/ingest_docs.py` — construir el Vector Store
Recorre `output/<seccion>/*.md`, los trocea (`chunk_file`), valida que no haya ruido y
construye `data/rag_index.sqlite` (`build`). `--sections` permite indexar solo algunas.
Por defecto indexa `especialistas, sedes, servicios, pages` (se excluye `posts` porque metía
ruido). Es el comando que corres tras cada scraping.

### `scripts/ingest_kv.py` — cargar el KV nativo del OS
Lee `data/institucional.json` y **sube cada sección** (sedes, horarios, contactos…) al
**Structured KV Store** del agente en OpenFang, vía REST `PUT /api/memory/agents/{id}/kv/{key}`.
- `agent_id(name)` — resuelve el ID del agente por su nombre. Requiere el daemon corriendo.
Así el conocimiento corporativo vive como "memoria base" del agente en el OS.

### `scripts/ingest_regulatory.py` — pipeline HITL de normativa
Convierte los borradores **aprobados** de la Hand en el índice que consulta el agente interno.
- `_draft_to_chunk(path)` — convierte un `.md` con frontmatter (`titulo, entidad, tipo,
  numero, fecha, fuente, estado`) en un `Chunk` (sección `regulatorio`).
- `_set_estado(path, estado)` — usado por `--approve`: marca un borrador como `aprobado` (el paso humano).
- `main()` — lee los borradores; **solo indexa los que tienen `estado: aprobado`** (salvo
  `--all` para demo); construye `data/regulatory_index.sqlite`.
- Flags: `--approve <archivo>`, `--all`, `--from <carpeta>`.

### `scripts/configure_env.py` — generar la config de OpenFang
Escribe `~/.openfang/config.toml` (la fuente de verdad que lee el daemon). Define:
- `default_model` — proveedor Gemini + modelo + `api_key_env`.
- `[channels.telegram]` — el bridge (token, agente público por defecto).
- `[[bindings]]` — si hay `TELEGRAM_INTERNAL_GROUP_ID`, **rutea** ese grupo al agente interno.
- `[[mcp_servers]]` — registra el servidor MCP `rag`. **Detalle crítico**: el comando es el
  **`python.exe` del venv** (no `uv`), porque OpenFang ejecuta los MCP en un *sandbox* que
  limpia el entorno y `uv` necesita variables de Windows que ahí desaparecen. Además reenvía
  `GEMINI_API_KEY` (y otras) por la lista `env`.
- Copia los manifiestos de los agentes a `~/.openfang/agents/`.
- `--persist` guarda las claves como variables de sistema (`setx`).

### `scripts/rag_mcp_server.py` — el servidor MCP (las herramientas del agente)
Servidor **FastMCP por stdio** que expone 3 herramientas. Es lo que el agente "llama".
- `buscar_institucional(query, k, seccion)` — **herramienta principal**: médicos,
  especialidades, servicios, chequeos, páginas. Si se pide `seccion="especialistas"`, busca
  **filtrando la sección dentro del ranking** (así devuelve perfiles de médicos con nombres).
- `consultar_datos_corporativos(seccion)` — datos administrativos desde `institucional.json`
  (sedes, horarios, contactos, EPS, NIT). Tiene un mapeo de palabras clave → secciones del JSON.
- `buscar_regulatorio(query, k)` — busca en `regulatory_index.sqlite` (normativa aprobada);
  exclusivo del agente interno.
- `MIN_SCORE=0.35` — umbral de relevancia común.

### `scripts/telegram_bot.py` — bot de la Ruta directa
Bot de Telegram **sin OpenFang** (Ruta B). Por cada mensaje: `answer()` (RAG + 1 llamada a
Gemini) → respuesta. Incluye acuse de recibo (reacción 👀), indicador "escribiendo…" y
**registro de costo** por mensaje. `--ask "..."` responde una sola pregunta y termina (modo prueba).

### `scripts/smoke_test.py` — prueba de humo
Lanza varias preguntas tipo (chequeo Gold, cardiólogos, sedes, una fuera de dominio) y mide
**tokens y costo aproximado** por consulta. Sirve para validar calidad y costo rápidamente.

---

## 9. Carpeta `agents/` — los agentes de OpenFang

Cada `.toml` es el **manifiesto** de un agente (su identidad y comportamiento). OpenFang los
carga al arrancar.

### `agents/public_agent.toml` — `asistente-publico`
El bot de cara al público. Campos clave:
- `[model]` → `provider="gemini"`, `model="gemini-2.5-flash-lite"`, `temperature=0.1`.
- `system_prompt` — las **reglas del asistente**: usar siempre las herramientas antes de dar
  datos; para médicos usar `buscar_institucional(seccion="especialistas")`; **listar siempre
  los nombres** que devuelva la herramienta y **nunca** decir "no tengo acceso a un listado"
  si la herramienta sí devolvió datos; flujo síntoma→cita; responder solo con info de las herramientas.
- `skills = ["__sin_skills__"]` — **centinela**: una allowlist de skills que no coincide con
  ninguno, para **evitar que OpenFang inyecte los 61 skills bundled** (~20K tokens por mensaje
  que disparaban el costo).
- `[capabilities].tools` — las herramientas MCP que puede usar.

### `agents/internal_agent.toml` — `asistente-interno`
Consultor de **inteligencia regulatoria** para el personal interno. Mismo modelo económico y
el mismo centinela de skills. Puede usar `buscar_regulatorio` además de las institucionales.
Se activa enrutando un grupo privado de Telegram (`TELEGRAM_INTERNAL_GROUP_ID`).

---

## 10. Carpeta `hands/` — operaciones autónomas (Hands System)

Implementa el **Módulo 3 de RUTA B**. Una *Hand* trabaja sola, sin que nadie le escriba.

### `hands/collector-regulatorio/HAND.toml`
Manifiesto de la Hand, en el **esquema real de OpenFang** (igual que las Hands bundled):
- Campos a nivel raíz: `id`, `name`, `description`, `category`, `icon`, `tools`.
- `[[settings]]` — opciones configurables (`output_dir`, `update_frequency`, `max_items_per_run`)
  con su `setting_type` y opciones.
- `[agent]` — la configuración del agente de la Hand, **con el playbook completo dentro de
  `system_prompt`** (no hay archivo aparte). Usa `model="default"` (hereda el Gemini del daemon),
  `temperature=0.1`, `max_iterations=20`.
- `[dashboard]` + `[[dashboard.metrics]]` — qué métricas muestra en el dashboard (fuentes
  revisadas, borradores generados, última corrida).

El `system_prompt` es un **playbook por fases**: recuperar estado → programarse →
recolectar (web_search/web_fetch de MinSalud, Supersalud, Invima, INS) → extraer →
filtrar por relevancia → **escribir borradores** en `output_dir` con `estado: pendiente` →
reportar métricas. Tiene tope de ítems por corrida y resúmenes breves (control de costo).

### `hands/collector-regulatorio/SKILL.md`
**Conocimiento experto** del dominio (regulación de salud en Colombia): qué emite cada
entidad, jerarquía de normas, temas de alto impacto para una IPS (habilitación, RIPS,
farmacovigilancia…), cómo leer la vigencia, errores a evitar. OpenFang lo **inyecta solo** en
el contexto de la Hand. Se mantiene breve a propósito (cada token cuesta).

### `hands/collector-regulatorio/samples/`
Dos normas reales y estables (Decreto 780/2016, Resolución 3100/2019) en el formato de
borrador, **ya `aprobadas`**, para **sembrar** el índice regulatorio y poder hacer la demo sin
esperar a que la Hand recolecte. El ciclo completo es:

```
Hand ─► data/pending_regulatory/*.md (estado: pendiente)
         │
         ▼  un humano revisa y aprueba (HITL)
   ingest_regulatory.py --approve  →  estado: aprobado
         │
         ▼
   ingest_regulatory.py  →  data/regulatory_index.sqlite  ─► buscar_regulatorio
```

---

## 11. `start_bot.ps1` y `Makefile` — arranque

### `start_bot.ps1` (lo que ejecuta `make start`)
Launcher de PowerShell que levanta **todo el Agent OS en un comando**:
1. Carga `.env` al entorno del proceso (que heredará el daemon).
2. Regenera la config (`configure_env.py`) — gratis, asegura el MCP correcto.
3. Verifica/crea el índice RAG.
4. **Detiene cualquier daemon previo** (`openfang stop`) para que apliquen config y entorno nuevos.
5. Arranca `openfang start` en segundo plano y espera a que responda el puerto 4200.
6. **Instala y activa** la Hand (best-effort: si falla, el daemon sigue).
7. Queda en primer plano hasta `Ctrl+C` (que detiene el daemon).

### `Makefile` — los comandos
Flujo principal en **dos comandos**:
- `make setup` — todo lo offline: `uv sync` + Vector Store + índice regulatorio de demo + config de OpenFang.
- `make start` — levanta el Agent OS (lo de arriba).

Avanzados: `make start-directo` (ruta barata sin OpenFang), `make kv` (cargar el KV nativo),
`make rebuild` (reconstruir el índice), `make regulatory` (reconstruir el índice regulatorio
aprobado), `make test` (smoke test), `make help`.

---

## 12. Economía de tokens (por qué es barato)

El costo de Gemini fue una restricción de primer orden. Palancas aplicadas:
- **Modelo `gemini-2.5-flash-lite`** — el tier más barato con soporte de tool-calling.
- **"Thinking" desactivado** (`thinking_budget=0`) en todas las llamadas de chat.
- **Skills bundled suprimidos** (`skills=["__sin_skills__"]`) — ahorra ~20K tokens/mensaje.
- **Hand acotada** — schedule semanal, tope de ítems por corrida, resúmenes breves.
- **Embeddings solo al ingerir** y **1 por consulta** (muy baratos).
- **Ruta directa opcional** (`make start-directo`) que evita el bucle de agente.
- **Contexto acotado** — `TOP_K` chunks y filtros por sección; no se manda todo el corpus.

`scripts/smoke_test.py` imprime tokens y ~COP por consulta para vigilar el gasto.

---

## 13. Decisiones de diseño no obvias (gotchas)

Estas son las trampas que hicieron fallar el sistema y cómo se resolvieron (útil para no
repetirlas):

1. **El modelo debe estar en el catálogo de OpenFang.** `gemini-3.1-flash-lite` (sin
   `-preview`) **no existe** en el catálogo → OpenFang no habilita tool-calling → el agente
   responde sin llamar herramientas (e "inventa" que no puede). Solución: usar
   `gemini-2.5-flash-lite` (verificable en `GET /api/models`).
2. **Sandbox de los MCP.** OpenFang lanza los servidores MCP con el entorno **limpiado**
   (`env_clear()`) y solo una allowlist. `uv run` falla ahí (le faltan `APPDATA`/`LOCALAPPDATA`),
   así que el MCP se lanza con el **python del venv** directamente y se reenvía `GEMINI_API_KEY`
   por la lista `env`. Si el MCP no carga, el agente se queda sin herramientas.
3. **Orden del filtro en `buscar_institucional`.** Buscar el top-20 **global** y filtrar la
   sección **después** hacía que los servicios "taparan" a los especialistas (el agente recibía
   descripciones sin nombres). Solución: filtrar la `seccion` **dentro** de `search()`.
4. **Sesión "envenenada".** Si el agente, cuando las herramientas estaban rotas, "aprendió" a
   responder "no puedo listar médicos", se mantenía consistente con eso. Solución: prompt que
   **prohíbe** ese hedge + `temperature=0.1` + limpiar el historial de la sesión.
5. **`HAND.toml` real ≠ documentación web.** El esquema real pone los campos a nivel raíz,
   usa `[[settings]]` y mete el playbook **inline** en `[agent].system_prompt` (no hay
   `system-prompt.md`).
6. **Reiniciar tras cambiar config.** El daemon no aplica cambios de config/manifiestos hasta
   reiniciarse; `make start` ya hace `openfang stop` + arranque limpio.

---

## 14. Flujo completo de un mensaje (end-to-end)

Ejemplo: el usuario escribe *"¿Qué cardiólogos atienden?"* por Telegram.

1. **Telegram → OpenFang.** El bridge recibe el mensaje y lo entrega al agente
   `asistente-publico` (sesión del chat).
2. **El agente decide.** Gemini lee el `system_prompt` (que ordena usar
   `buscar_institucional(seccion="especialistas")` para médicos) y **llama la herramienta**.
3. **MCP → RAG.** `rag_mcp_server.py` ejecuta `buscar_institucional("cardiólogos", k=8,
   seccion="especialistas")` → `rag/index.search()` embebe la consulta (Gemini) y rankea por
   **coseno** contra `rag_index.sqlite`, filtrando especialistas → devuelve los perfiles.
4. **El agente redacta.** Gemini recibe los perfiles (nombres, especialidades, extensiones) y
   los **lista**, con el contacto al final (segunda iteración del bucle de agente).
5. **OpenFang → Telegram.** La respuesta vuelve al usuario.
6. **Costo.** Todo con `gemini-2.5-flash-lite`, "thinking" off y sin skills bundled → centavos.

(En la **Ruta directa**, los pasos 2–4 los hace `rag/answer.py` con una sola llamada a Gemini,
sin tool-calling.)

---

## 15. Cómo correr todo

```bash
# 0) Requisitos: Python 3.13, uv, OpenFang instalado, una GEMINI_API_KEY.
copy .env.example .env        # pega GEMINI_API_KEY y TELEGRAM_BOT_TOKEN

# 1) (si hace falta) generar el corpus
make run                      # scrapea el sitio -> output/*.md

# 2) preparar todo offline (deps + índices + config de OpenFang)
make setup

# 3) levantar el Agent OS (OpenFang + Telegram + dashboard + Hand)
make start                    # dashboard: http://127.0.0.1:4200 ; Ctrl+C para parar

# (una vez, con el daemon arriba) cargar el KV nativo
make kv

# pruebas
make test                     # smoke test con costo real
make start-directo            # ruta mínima de costo (sin OpenFang)
```

**Resumen de carpetas:**

```
scraper/   → extrae el sitio a output/*.md
rag/       → troceo, embeddings, índice y búsqueda (el cerebro del RAG)
scripts/   → ingesta, configuración, servidor MCP y bots
agents/    → manifiestos de los agentes de OpenFang
hands/     → la Hand autónoma (HAND.toml + SKILL.md + samples)
data/      → índices generados y datos corporativos (gitignored)
output/    → Markdown scrapeado (gitignored)
```

---

*Documento generado para entender la lógica completa del repositorio. Para el "cómo usarlo"
rápido, ver el `README.md`.*
