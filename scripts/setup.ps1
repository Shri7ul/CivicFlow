# CivicFlow Phase 1 local setup
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"

Write-Host "CivicFlow Phase 1 setup" -ForegroundColor Cyan

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js is required. Install Node.js 20.9 or newer."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is required. Install Node.js with npm."
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.11 or newer is required."
}

Write-Host "`n[1/3] Installing frontend dependencies..." -ForegroundColor Yellow
Push-Location (Join-Path $root "frontend")
try {
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install failed." }
}
finally {
    Pop-Location
}

Write-Host "`n[2/3] Preparing backend virtual environment..." -ForegroundColor Yellow
$backend = Join-Path $root "backend"
if (-not (Test-Path $python)) {
    Push-Location $backend
    try {
        python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Creating the virtual environment failed." }
    }
    finally {
        Pop-Location
    }
}

Push-Location $backend
try {
    & $python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Upgrading pip failed." }

    & $python -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) { throw "Installing backend dependencies failed." }
}
finally {
    Pop-Location
}

Write-Host "`n[3/3] Creating local environment files when missing..." -ForegroundColor Yellow
$backendEnv = Join-Path $root "backend\.env"
$backendExample = Join-Path $root "backend\.env.example"
if (-not (Test-Path $backendEnv)) {
    Copy-Item $backendExample $backendEnv
    Write-Host "Created backend/.env from .env.example"
}
else {
    Write-Host "Kept existing backend/.env"
}

$frontendEnv = Join-Path $root "frontend\.env.local"
$frontendExample = Join-Path $root "frontend\.env.example"
if (-not (Test-Path $frontendEnv)) {
    Copy-Item $frontendExample $frontendEnv
    Write-Host "Created frontend/.env.local from .env.example"
}
else {
    Write-Host "Kept existing frontend/.env.local"
}

Write-Host "`nSetup complete." -ForegroundColor Green
Write-Host "Backend:  .\scripts\run-backend.ps1"
Write-Host "Frontend: .\scripts\run-frontend.ps1"
Write-Host "Checks:   .\scripts\verify.ps1"
