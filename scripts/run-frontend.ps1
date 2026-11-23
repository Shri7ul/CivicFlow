# Start the CivicFlow Next.js frontend
[CmdletBinding()]
param(
    [int]$Port = 3000,
    [string]$ApiBaseUrl = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    throw "frontend/node_modules is missing. Run .\scripts\setup.ps1 first."
}

if ($ApiBaseUrl) {
    $env:NEXT_PUBLIC_API_BASE_URL = $ApiBaseUrl
    Write-Host "Using NEXT_PUBLIC_API_BASE_URL=$ApiBaseUrl" -ForegroundColor Yellow
}

Push-Location $frontend
try {
    npm run dev -- --port $Port
}
finally {
    Pop-Location
}
