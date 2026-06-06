#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Arranca el Agent OS (OpenFang) completo: daemon + bridge de Telegram + dashboard,
    y registra/activa el Hand "collector-regulatorio".
.DESCRIPTION
    Un solo comando (make start):
      1. Carga .env y verifica claves.
      2. Regenera ~/.openfang/config.toml (aplica el MCP de RAG vía python del venv).
      3. Asegura el índice RAG.
      4. Detiene cualquier daemon previo (para que apliquen config y entorno nuevos).
      5. Lanza 'openfang start' (daemon + Telegram + dashboard en :4200).
      6. Instala y activa el Hand (best-effort).
    Ctrl+C detiene el daemon.
#>

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Test-Port($p) {
    try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("127.0.0.1", $p); $c.Close(); return $true }
    catch { return $false }
}

Write-Host "=== Agent OS (OpenFang) - Fundacion Valle del Lili ===" -ForegroundColor Cyan
Write-Host ""

# 1) Cargar .env a variables de proceso (las hereda el daemon que lancemos)
Write-Host "[1/6] Cargando .env..." -ForegroundColor Yellow
Get-Content "$Root\.env" | ForEach-Object {
    if ($_ -match "^\s*([^#=]+)=(.*)$") {
        [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
    }
}
if (-not $env:GEMINI_API_KEY) { Write-Error "Falta GEMINI_API_KEY en .env"; exit 1 }
if (-not $env:TELEGRAM_BOT_TOKEN) { Write-Error "Falta TELEGRAM_BOT_TOKEN en .env"; exit 1 }
# El SDK de Gemini tambien lee GOOGLE_GENERATIVE_AI_API_KEY; lo sincronizamos.
if (-not $env:GOOGLE_GENERATIVE_AI_API_KEY) { $env:GOOGLE_GENERATIVE_AI_API_KEY = $env:GEMINI_API_KEY }
Write-Host "  GEMINI_API_KEY     OK"
Write-Host "  TELEGRAM_BOT_TOKEN OK"

# 2) Regenerar config (gratis, sin API): asegura el MCP de RAG con el python del venv
Write-Host "[2/6] Regenerando config de OpenFang..." -ForegroundColor Yellow
uv run python "$Root\scripts\configure_env.py"

# 3) Asegurar el indice RAG
Write-Host "[3/6] Verificando indice RAG..." -ForegroundColor Yellow
if (-not (Test-Path "$Root\data\rag_index.sqlite")) {
    Write-Host "  Indice no encontrado; construyendolo..." -ForegroundColor Yellow
    uv run python "$Root\scripts\ingest_docs.py"
}

# 4) Detener cualquier daemon previo (si no, no aplican config ni entorno nuevos)
Write-Host "[4/6] Comprobando daemon previo..." -ForegroundColor Yellow
if (Test-Port 4200) {
    Write-Host "  Daemon previo en :4200; deteniendolo (openfang stop)..." -ForegroundColor DarkYellow
    try { openfang stop } catch { Write-Host "  aviso: 'openfang stop' fallo ($_)" -ForegroundColor DarkYellow }
    for ($i = 0; $i -lt 15; $i++) { if (-not (Test-Port 4200)) { break }; Start-Sleep -Seconds 1 }
}

# 5) Lanzar el daemon de OpenFang en segundo plano
Write-Host "[5/6] Iniciando OpenFang (daemon + Telegram + dashboard)..." -ForegroundColor Green
try {
    $proc = Start-Process -FilePath "openfang" -ArgumentList "start" `
        -WorkingDirectory $Root -NoNewWindow -PassThru
} catch {
    Write-Host "  No se encontro 'openfang'. Instalalo:  curl -fsSL https://openfang.sh/install | sh" -ForegroundColor Red
    Write-Host "  Alternativa sin OpenFang (mas barata):  make start-directo" -ForegroundColor Red
    exit 1
}
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    if ($proc.HasExited) { Write-Error "OpenFang termino inesperadamente."; exit 1 }
    if (Test-Port 4200) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if ($ready) {
    Start-Sleep -Seconds 3  # margen para que el agente y el MCP se inicialicen
    Write-Host "  OpenFang activo. Dashboard: http://127.0.0.1:4200" -ForegroundColor Green
} else {
    Write-Host "  Aviso: el dashboard no respondio aun; continuo igual." -ForegroundColor DarkYellow
}

# 6) Registrar y activar el Hand (best-effort: si falla, el daemon sigue corriendo)
Write-Host "[6/6] Registrando y activando el Hand collector-regulatorio..." -ForegroundColor Yellow
try { openfang hand install "$Root\hands\collector-regulatorio" } catch { Write-Host "  aviso: 'hand install' fallo ($_)" -ForegroundColor DarkYellow }
try { openfang hand activate collector-regulatorio } catch { Write-Host "  aviso: 'hand activate' fallo; activalo desde el dashboard ($_)" -ForegroundColor DarkYellow }

Write-Host ""
Write-Host "Listo. El bot responde en Telegram. Ctrl+C para detener." -ForegroundColor Cyan
Write-Host "  (carga el KV nativo una vez con:  make kv)" -ForegroundColor DarkGray
Write-Host ""

# Mantener el daemon en primer plano hasta Ctrl+C
try { $proc.WaitForExit() }
finally { if (-not $proc.HasExited) { $proc.Kill() } }
