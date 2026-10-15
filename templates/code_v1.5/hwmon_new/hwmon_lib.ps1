# hwmon_lib.ps1 (own LibreHardwareMonitor-based monitor) - dot-source; same API as podcast\hwmon_lib.ps1:
#   $h = Start-HwMonitor "<run>"   ...   Stop-HwMonitor $h
# Sessions are handled by the HwMon daemon (scheduled task 'HwMon', or hwmon.exe running). If no daemon is alive it is started
# (schtasks /run /tn HwMon); if that fails it falls back to the old HWiNFO-based hw_monitor.ps1 (podcast\hwmon_lib.ps1).
$script:HwDir = 'C:\grok\hwmon'
function Test-HwMonDaemon {
  $hb = Join-Path $script:HwDir 'heartbeat.txt'
  if (-not (Test-Path $hb)) { return $false }
  ((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds -lt 20
}
function Start-HwMonitor([string]$Run, [double]$MaxHours = 72, [string]$Dir = 'C:\grok\hwmon') {
  $script:HwDir = $Dir
  $Run = $Run -replace '[^\w\-\.]', '_'
  if (-not (Test-HwMonDaemon)) {
    try { schtasks.exe /run /tn HwMon 2>&1 | Out-Null } catch {}
    for ($i = 0; $i -lt 20 -and -not (Test-HwMonDaemon); $i++) { Start-Sleep -Milliseconds 500 }
  }
  if (-not (Test-HwMonDaemon)) {
    Write-Host "[hwmon] HwMon daemon not running -> fallback to HWiNFO hw_monitor.ps1"
    $flag = Join-Path $env:TEMP ('hwmon_{0}_{1}.stop' -f $PID, (Get-Random))
    $p = Start-Process powershell -WindowStyle Hidden -PassThru -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','C:\grok\podcast\hw_monitor.ps1','-Run',$Run,'-ParentPid',$PID,'-StopFlag',$flag)
    Write-Host "[hwmon] fallback (old HWiNFO monitor) started (pid $($p.Id)) -> C:\grok\podcast\hwlogs\"
    return [pscustomobject]@{ Fallback = $true; Proc = $p; Flag = $flag }
  }
  $sd = Join-Path $Dir 'sessions'
  Remove-Item (Join-Path $sd "$Run.stop"), (Join-Path $sd "$Run.done") -Force -ErrorAction SilentlyContinue
  "parent=$PID`r`nmaxhours=$MaxHours`r`nstarted=$((Get-Date).ToString('o'))" | Set-Content (Join-Path $sd "$Run.session") -Encoding ascii
  $st = Join-Path $sd "$Run.state"; Remove-Item $st -Force -ErrorAction SilentlyContinue
  for ($i = 0; $i -lt 20 -and -not (Test-Path $st); $i++) { Start-Sleep -Milliseconds 250 }
  $csv = if (Test-Path $st) { (Get-Content $st)[0] } else { '(starting)' }
  Write-Host "[hwmon] session '$Run' started -> $csv"
  [pscustomobject]@{ Fallback = $false; Run = $Run; Dir = $Dir }
}
function Stop-HwMonitor($h) {
  if (-not $h) { return }
  if ($h.Fallback) {
    New-Item -ItemType File -Force $h.Flag | Out-Null
    if (-not $h.Proc.WaitForExit(30000)) { $h.Proc.Kill() }
    Remove-Item $h.Flag -Force -ErrorAction SilentlyContinue
    $sm = Get-ChildItem C:\grok\podcast\hwlogs\*.summary.txt | Sort-Object LastWriteTime | Select-Object -Last 1
    if ($sm) { Write-Host "[hwmon] summary: $($sm.FullName)" }
    return
  }
  $sd = Join-Path $h.Dir 'sessions'
  New-Item -ItemType File -Force (Join-Path $sd "$($h.Run).stop") | Out-Null
  $done = Join-Path $sd "$($h.Run).done"
  for ($i = 0; $i -lt 60 -and -not (Test-Path $done); $i++) { Start-Sleep -Milliseconds 500 }
  if (Test-Path $done) { $l = Get-Content $done; Write-Host "[hwmon] summary: $($l[1])"; Remove-Item $done -Force -ErrorAction SilentlyContinue }
  else { Write-Host "[hwmon] no summary confirmation (daemon busy/stopped)" }
}
