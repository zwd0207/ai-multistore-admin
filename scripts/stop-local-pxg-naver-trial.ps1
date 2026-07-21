$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$processFile = Join-Path $root "backend\.local-trial\processes.json"
if (-not (Test-Path -LiteralPath $processFile)) { return }
$trialProcesses = Get-Content -LiteralPath $processFile -Encoding UTF8 | ConvertFrom-Json
foreach ($processId in @($trialProcesses.backend_pid, $trialProcesses.frontend_pid)) {
  $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
  if ($process) { Stop-Process -Id $processId -Force }
}
Remove-Item -LiteralPath $processFile -Force
