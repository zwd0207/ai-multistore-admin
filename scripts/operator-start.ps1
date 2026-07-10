$ErrorActionPreference = "Stop"

$phase = "Core-ERP-Operator-Ready-1"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backend = Resolve-Path (Join-Path $root "codex1\backend")
$backendEnv = Join-Path $backend ".env"
$frontendEnv = Join-Path $root ".env.local"
$backendPort = 8012
$frontendPort = 5180

function Assert-ContainsLine($path, $expected, $message) {
  if (-not (Test-Path -LiteralPath $path)) {
    throw "${message}: missing $path"
  }
  $content = Get-Content -LiteralPath $path -Raw
  if ($content -notmatch [regex]::Escape($expected)) {
    throw "${message}: expected $expected"
  }
}

function Stop-LocalPort($port, $expectedNames) {
  $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($pidValue in $listeners) {
    $proc = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if (-not $proc) { continue }
    if ($expectedNames -contains $proc.ProcessName) {
      Stop-Process -Id $pidValue -Force
      Write-Host "Stopped $($proc.ProcessName) on port $port (pid $pidValue)"
    } else {
      throw "Port $port is used by $($proc.ProcessName). Stop it manually before running $phase."
    }
  }
}

function Wait-HttpOk($url, $label) {
  for ($i = 0; $i -lt 40; $i++) {
    try {
      $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
      if ($response.StatusCode -eq 200) {
        Write-Host "$label ready: $url"
        return
      }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  throw "$label did not become ready: $url"
}

Write-Host "Starting $phase"
Assert-ContainsLine $backendEnv "REAL_API_WRITE_ENABLED=false" "Generic platform writes must remain closed"
# Controlled Naver platform writes stay on operation gates:
# shipment dispatch and customer inquiry replies require explicit operator confirmation.
Assert-ContainsLine $frontendEnv "VITE_DATA_SOURCE=backend" "Operator trial must use backend data source"

Stop-LocalPort $backendPort @("python", "python3")
Stop-LocalPort $frontendPort @("node")

$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  $python = "python"
}
$backendOut = Join-Path $backend "operator-ready-8012.out.log"
$backendErr = Join-Path $backend "operator-ready-8012.err.log"
$frontendOut = Join-Path $root "operator-ready-5180.out.log"
$frontendErr = Join-Path $root "operator-ready-5180.err.log"

Start-Process -FilePath $python `
  -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$backendPort") `
  -WorkingDirectory $backend `
  -RedirectStandardOutput $backendOut `
  -RedirectStandardError $backendErr `
  -WindowStyle Hidden

Start-Process -FilePath "npm.cmd" `
  -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$frontendPort") `
  -WorkingDirectory $root `
  -RedirectStandardOutput $frontendOut `
  -RedirectStandardError $frontendErr `
  -WindowStyle Hidden

Wait-HttpOk "http://127.0.0.1:$backendPort/api/v1/health" "Backend health"
Wait-HttpOk "http://127.0.0.1:$backendPort/api/v1/dashboard/store-overview?include_inactive=false" "Store overview"
Wait-HttpOk "http://127.0.0.1:$frontendPort/" "Frontend"
# scripts/operator-readiness-check.mjs uses a non-writing OPTIONS probe for /sync/manual-batch/all.

Push-Location $root
try {
  $env:VITE_API_BASE_URL = "http://127.0.0.1:$backendPort/api/v1"
  node "scripts\operator-readiness-check.mjs"
  if ($LASTEXITCODE -ne 0) {
    throw "Operator readiness check failed with exit code $LASTEXITCODE"
  }
} finally {
  Pop-Location
}

Write-Host "Operator trial URL: http://127.0.0.1:$frontendPort/"
