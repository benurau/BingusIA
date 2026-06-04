param(
    [switch]$Dev,
    [switch]$Server,
    [string]$Python = "python"
)

Write-Host "=== Bingus IA Install ===" -ForegroundColor Cyan
Write-Host ""

# Check Python
$pyVersion = & $Python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python not found. Make sure it's on PATH or pass -Python <path>" -ForegroundColor Red
    exit 1
}
Write-Host "Using: $pyVersion"

# Upgrade pip
Write-Host "`n[1/3] Upgrading pip..." -ForegroundColor Yellow
& $Python -m pip install --upgrade pip | Out-Null

# Install core deps
Write-Host "[2/3] Installing core dependencies..." -ForegroundColor Yellow
if ($Dev -or $Server) {
    $extras = @()
    if ($Dev) { $extras += "dev" }
    if ($Server) { $extras += "server" }
    $extraStr = ($extras -join ",")
    & $Python -m pip install -e ".[$extraStr]"
} else {
    & $Python -m pip install -e .
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install failed" -ForegroundColor Red
    exit 1
}

# Verify key imports
Write-Host "[3/3] Verifying install..." -ForegroundColor Yellow
& $Python -c "import httpx; print('  httpx:', httpx.__version__)"
if ($Dev) {
    & $Python -c "import pytest; print('  pytest:', pytest.__version__)"
}
if ($Server) {
    & $Python -c "import fastapi; print('  fastapi:', fastapi.__version__)"
}

Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "Run: python main.py"
