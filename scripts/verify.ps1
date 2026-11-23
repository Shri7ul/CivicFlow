# Run the automated backend and frontend verification checks
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "backend/.venv is missing. Run .\scripts\setup.ps1 first."
}

Write-Host "`n=== Backend tests ===" -ForegroundColor Cyan
Push-Location (Join-Path $root "backend")
try {
    & $python -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }
}
finally {
    Pop-Location
}

Write-Host "`n=== Frontend typecheck ===" -ForegroundColor Cyan
Push-Location (Join-Path $root "frontend")
try {
    npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw "TypeScript check failed." }

    Write-Host "`n=== Frontend lint ===" -ForegroundColor Cyan
    npm run lint
    if ($LASTEXITCODE -ne 0) { throw "ESLint failed." }

    Write-Host "`n=== Frontend tests ===" -ForegroundColor Cyan
    npm test
    if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed." }

    Write-Host "`n=== Frontend production build ===" -ForegroundColor Cyan
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Production build failed." }
}
finally {
    Pop-Location
}

Write-Host "`nAll automated checks passed." -ForegroundColor Green
