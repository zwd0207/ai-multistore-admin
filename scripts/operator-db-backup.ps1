$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$backend = Resolve-Path (Join-Path $root "codex1\backend")
$python = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  $python = "python"
}

Push-Location $backend
try {
  & $python "scripts\create_local_backup.py" `
    --phase "Core-ERP-Operator-Ready-1" `
    --operation-type "operator_trial_manual_checkpoint" `
    --actor-label "operator_handoff" `
    --retention-class "manual_checkpoint" `
    --retention-reason "Before operator trial handoff"
  if ($LASTEXITCODE -ne 0) {
    throw "Backup script failed with exit code $LASTEXITCODE"
  }
} finally {
  Pop-Location
}
