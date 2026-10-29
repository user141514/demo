param([switch]$BackendOnly, [switch]$FrontendOnly, [switch]$ProductionFrontend, [switch]$Check, [switch]$Live, [switch]$Mock)
$ErrorActionPreference = 'Stop'
if ($BackendOnly -and $FrontendOnly) { throw 'Choose only one service filter.' }
if ($Live -and $Mock) { throw 'Choose either -Live or -Mock.' }
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = $null
if (!$FrontendOnly) {
    $pythonPath = & (Join-Path $PSScriptRoot 'resolve_python.ps1')
    if (!$pythonPath) { throw 'Python environment resolution failed.' }
}
$nodeCommand = if (!$BackendOnly) { Get-Command node.exe -ErrorAction Stop }
$nextPath = Join-Path $projectRoot 'frontend\node_modules\next\dist\bin\next'
if (!$BackendOnly -and !(Test-Path -LiteralPath $nextPath)) { throw 'Run npm ci in frontend before starting.' }
if ($Check) {
    [PSCustomObject]@{ Python = $pythonPath; FrontendPort = 3001; BackendPort = 8000; BindAddress = '127.0.0.1' } | ConvertTo-Json
    exit 0
}
$runtimeDirectory = Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Force -Path $runtimeDirectory | Out-Null

function Assert-FreePort([int]$Port) {
    if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
        throw "Port $Port is already in use. Keep the existing service or stop it explicitly before restarting."
    }
}
function Wait-Healthy([string]$Url, [System.Diagnostics.Process]$Process) {
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($Process.HasExited) { throw 'Service exited during startup. Check .local logs.' }
        try {
            if ((Invoke-WebRequest -Uri $Url -NoProxy -TimeoutSec 2).StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    throw "Service did not become healthy: $Url. Check .local logs."
}

# AI follows configuration unless explicitly overridden. Payment stays mocked.
$env:APP_ENV = 'development'
if ($Live) { $env:LLM_MODE = 'live'; $env:LLM_REPORT_ENABLED = 'true' }
if ($Mock) { $env:LLM_MODE = 'mock'; $env:LLM_REPORT_ENABLED = 'false' }
$env:RAG_ENABLED = 'false'
$env:LIGHTRAG_ENABLED = 'false'
$env:PAYMENT_PROVIDER_MODE = 'mock'
$env:SMTP_ENABLED = 'false'
$env:FRONTEND_ORIGIN = 'http://localhost:3001'
$env:NEXT_TELEMETRY_DISABLED = '1'
$env:NEXT_PUBLIC_API_BASE_URL = ' '
$env:API_PROXY_TARGET = 'http://127.0.0.1:8000'
$started = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()
try {
    if (!$FrontendOnly) { Assert-FreePort 8000 }
    if (!$BackendOnly) { Assert-FreePort 3001 }
    if (!$FrontendOnly) {
        & $pythonPath -c 'import sys; sys.path.insert(0,sys.argv[1]); from app.core.config import settings; assert settings.llm_mode != "live" or (settings.openai_api_key and settings.openai_model), "Live mode requires a configured API key and model"' (Join-Path $projectRoot 'backend')
        if ($LASTEXITCODE -ne 0) { throw 'AI configuration validation failed; no backend was started.' }
        $backendProcess = Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000') -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDirectory 'backend.out.log') -RedirectStandardError (Join-Path $runtimeDirectory 'backend.err.log') -PassThru
        $started.Add($backendProcess)
        Wait-Healthy 'http://127.0.0.1:8000/health' $backendProcess
        Write-Output 'Backend ready: http://localhost:8000'
    }
    if (!$BackendOnly) {
        if ($ProductionFrontend -and !(Test-Path (Join-Path $projectRoot 'frontend\.next\BUILD_ID'))) { throw 'Run npm run build in frontend first.' }
        $frontendMode = if ($ProductionFrontend) { 'start' } else { 'dev' }
        $frontendProcess = Start-Process -FilePath $nodeCommand.Source -ArgumentList @(('"' + $nextPath + '"'), $frontendMode, '-p', '3001', '-H', '127.0.0.1') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDirectory 'frontend.out.log') -RedirectStandardError (Join-Path $runtimeDirectory 'frontend.err.log') -PassThru
        $started.Add($frontendProcess)
        Wait-Healthy 'http://127.0.0.1:3001/start' $frontendProcess
        Write-Output 'Frontend ready: http://localhost:3001/start'
    }
    $started | Select-Object Id, ProcessName | ConvertTo-Json | Set-Content (Join-Path $runtimeDirectory 'last-start.json')
} catch {
    foreach ($process in $started) {
        if (!$process.HasExited) { $process.Kill($true) }
    }
    throw
}
