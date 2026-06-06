.PHONY: help setup start start-directo
.PHONY: install run run-sedes run-category resume clean clean-output clean-all
.PHONY: persist rebuild kv regulatory test

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Flujo principal: solo dos comandos ───────────────────────────────────────
setup: ## (1) Prepara todo offline: deps + indices RAG/regulatorio + config OpenFang
	uv sync
	uv run python scripts/ingest_docs.py
	uv run python scripts/ingest_regulatory.py --from hands/collector-regulatorio/samples --all
	uv run python scripts/configure_env.py
	@echo "=== Listo. Ahora ejecuta: make start ==="

start: ## (2) Levanta el Agent OS (OpenFang + Telegram + dashboard + Hand)
	powershell -ExecutionPolicy Bypass -File start_bot.ps1

# ── Avanzado ─────────────────────────────────────────────────────────────────
start-directo: ## Ruta directa sin OpenFang (minimo costo de tokens)
	uv run python scripts/telegram_bot.py

kv: ## Carga institucional.json en el KV nativo de OpenFang (con el daemon arriba)
	uv run python scripts/ingest_kv.py

rebuild: ## Reconstruye el indice vectorial RAG desde output/
	uv run python scripts/ingest_docs.py

regulatory: ## Reconstruye el indice regulatorio desde borradores APROBADOS
	uv run python scripts/ingest_regulatory.py

persist: ## Persiste las claves de .env como variables de sistema (setx)
	uv run python scripts/configure_env.py --persist

test: ## Prueba de humo (Gemini + RAG) con costo real por consulta
	uv run python scripts/smoke_test.py

# ── Scraper ──────────────────────────────────────────────────────────────────
install: ## Instala dependencias con uv
	uv sync

run: ## Scrapea todas las secciones del sitio
	uv run python main.py

run-sedes: ## Prueba rapida: scrapea solo sedes
	uv run python main.py --category sedes

run-category: ## Scrapea una categoria (uso: make run-category CAT=servicios)
	uv run python main.py --category $(CAT)

resume: ## Reanuda un scraping interrumpido (omite archivos existentes)
	uv run python main.py

# ── Limpieza ─────────────────────────────────────────────────────────────────
clean-output: ## Borra los archivos scrapeados (output/)
	@if exist output rmdir /s /q output
	@echo Output cleaned.

clean: ## Borra venv y archivos cacheados
	@if exist .venv rmdir /s /q .venv
	@if exist __pycache__ rmdir /s /q __pycache__
	@for /d %%d in (scraper\__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
	@echo Cache cleaned.

clean-all: clean clean-output ## Borra todo (venv + output + cache)
	@echo All cleaned.
