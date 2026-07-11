$ErrorActionPreference = "Stop"
foreach ($port in @(8013, 8014, 8015, 8016, 5181, 5182, 5183, 5184)) {
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
    $process = Get-Process -Id $_ -ErrorAction SilentlyContinue
    if ($process -and $process.ProcessName -in @("python", "node")) { Stop-Process -Id $_ -Force }
  }
}
