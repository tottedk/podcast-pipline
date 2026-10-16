# hwmon_ui_toggle.ps1 - start the HwMon UI widget if it is not running, otherwise ask it to exit (graceful, via named event).
# Usage: hwmon_ui_toggle.ps1 [-Mode toggle|start|stop|status]
param([ValidateSet('toggle','start','stop','status')][string]$Mode = 'toggle')
$d = Split-Path $MyInvocation.MyCommand.Path
$exe = Join-Path $d 'hwmon_ui.exe'
$run = Get-Process hwmon_ui -ErrorAction SilentlyContinue
function Stop-Ui {
  try { $ev = [Threading.EventWaitHandle]::OpenExisting('Local\HwMonUI_Exit'); [void]$ev.Set() } catch {}
  $run | ForEach-Object { if (-not $_.WaitForExit(6000)) { Write-Host 'did not exit gracefully; stopping hwmon_ui only'; Stop-Process -Id $_.Id } }
  Write-Host 'HwMon UI: stopped'
}
function Start-Ui {
  if (-not (Test-Path $exe)) { Write-Host "missing $exe - run build.ps1"; exit 1 }
  Start-Process -FilePath $exe -WorkingDirectory $d; Write-Host 'HwMon UI: started'
}
switch ($Mode) {
  'status' { if ($run) { Write-Host "running (pid $($run.Id))" } else { Write-Host 'not running' } }
  'start'  { if ($run) { Write-Host 'already running' } else { Start-Ui } }
  'stop'   { if ($run) { Stop-Ui } else { Write-Host 'not running' } }
  default  { if ($run) { Stop-Ui } else { Start-Ui } }
}
