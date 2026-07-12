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
& $python (Join-Path $backend "scripts\provision_local_config_admin.py")
if ($LASTEXITCODE -ne 0) { throw "Local PXG configuration administrator provisioning failed." }
$backendPort = Find-OpenPort @(8013, 8014, 8015, 8016)
$frontendPort = Find-OpenPort @(5181, 5182, 5183, 5184)
$env:CORS_ALLOWED_ORIGINS = "[`"http://127.0.0.1:$frontendPort`"]"
$env:VITE_API_BASE_URL = "http://127.0.0.1:$backendPort/api/v1"
$env:VITE_DATA_SOURCE = "backend"

$processFile = Join-Path $trialDir "processes.json"
if (Test-Path -LiteralPath $processFile) {
  & (Join-Path $PSScriptRoot "stop-local-pxg-naver-trial.ps1")
}
$backendOut = Join-Path $trialDir "backend.out.log"
$backendErr = Join-Path $trialDir "backend.err.log"
$frontendOut = Join-Path $trialDir "frontend.out.log"
$frontendErr = Join-Path $trialDir "frontend.err.log"
$backendLauncher = Start-Process -FilePath $python -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$backendPort") -WorkingDirectory $backend -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -WindowStyle Hidden -PassThru
$frontendLauncher = Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$frontendPort") -WorkingDirectory $root -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -WindowStyle Hidden -PassThru
$backendConnection = $null
$frontendConnection = $null
for ($attempt = 0; $attempt -lt 40; $attempt++) {
  $backendConnection = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  $frontendConnection = Get-NetTCPConnection -LocalPort $frontendPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($backendConnection -and $frontendConnection) { break }
  Start-Sleep -Milliseconds 250
}
if (-not $backendConnection -or -not $frontendConnection) {
  foreach ($launcher in @($backendLauncher, $frontendLauncher)) {
    if ($launcher -and -not $launcher.HasExited) { Stop-Process -Id $launcher.Id -Force }
  }
  throw "Local PXG trial services did not start. Check the local trial logs."
}
@{
  backend_pid = $backendConnection.OwningProcess
  frontend_pid = $frontendConnection.OwningProcess
  backend_port = $backendPort
  frontend_port = $frontendPort
} | ConvertTo-Json | Set-Content -LiteralPath $processFile -Encoding UTF8
Write-Output "http://127.0.0.1:$frontendPort/"
