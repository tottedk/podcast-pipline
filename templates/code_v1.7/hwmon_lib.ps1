# hwmon_lib.ps1 - dot-source; Start-HwMonitor returns a handle, Stop-HwMonitor stops it and waits for the summary
function Start-HwMonitor([string]$Run) {
  $flag = Join-Path $env:TEMP ("hwmon_{0}_{1}.stop" -f $PID, (Get-Random))
  $p = Start-Process powershell -WindowStyle Hidden -PassThru -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',"$PSScriptRoot\hw_monitor.ps1",'-Run',$Run,'-ParentPid',$PID,'-StopFlag',$flag)
  Write-Host "[hwmon] started (pid $($p.Id)) -> C:\grok\podcast\hwlogs\"
  [pscustomobject]@{ Proc = $p; Flag = $flag }
}
function Stop-HwMonitor($h) {
  if (-not $h) { return }
  New-Item -ItemType File -Force $h.Flag | Out-Null
  if (-not $h.Proc.WaitForExit(30000)) { $h.Proc.Kill() }
  Remove-Item $h.Flag -Force -ErrorAction SilentlyContinue
  $s = Get-ChildItem C:\grok\podcast\hwlogs\*.summary.txt | Sort-Object LastWriteTime | Select-Object -Last 1
  if ($s) { Write-Host "[hwmon] summary: $($s.FullName)" }
}
