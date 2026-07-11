$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backend = Join-Path $root "codex1\backend"
$trialDir = Join-Path $backend ".local-trial"
$runtimeEnv = Join-Path $trialDir "runtime.env"
$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }

function Import-LocalEnv($Path) {
  Get-Content -LiteralPath $Path -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') { Set-Item -Path "Env:$($matches[1].Trim())" -Value $matches[2].Trim() }
  }
}

function Find-OpenPort($Ports) {
  foreach ($port in $Ports) {
    if (-not (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)) { return $port }
  }
  throw "No local trial port is available."
}

& $python (Join-Path $backend "scripts\provision_local_pxg_naver_trial.py")
if ($LASTEXITCODE -ne 0) { throw "Local PXG trial provisioning failed." }
Import-LocalEnv $runtimeEnv
$backendPort = Find-OpenPort @(8013, 8014, 8015, 8016)
$frontendPort = Find-OpenPort @(5181, 5182, 5183, 5184)
$env:CORS_ALLOWED_ORIGINS = "[`"http://127.0.0.1:$frontendPort`"]"
$env:VITE_API_BASE_URL = "http://127.0.0.1:$backendPort/api/v1"

$backendOut = Join-Path $trialDir "backend.out.log"
$backendErr = Join-Path $trialDir "backend.err.log"
$frontendOut = Join-Path $trialDir "frontend.out.log"
$frontendErr = Join-Path $trialDir "frontend.err.log"
Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$backendPort") -WorkingDirectory $backend -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -WindowStyle Hidden
Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$frontendPort") -WorkingDirectory $root -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -WindowStyle Hidden
Write-Output "http://127.0.0.1:$frontendPort/"
