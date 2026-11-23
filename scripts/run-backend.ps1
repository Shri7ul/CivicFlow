# Start the CivicFlow FastAPI backend
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$BindHost = "0.0.0.0"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "backend/.venv is missing. Run .\scripts\setup.ps1 first."
}

Push-Location (Join-Path $root "backend")
try {
    & $python -m uvicorn app.main:app --reload --host $BindHost --port $Port
}
finally {
    Pop-Location
}
