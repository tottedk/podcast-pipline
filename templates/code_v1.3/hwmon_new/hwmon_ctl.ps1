# hwmon_ctl.ps1 - status | start | stop | restart of the HwMon daemon (scheduled task 'HwMon'); start/stop of the task works without UAC after install_admin.ps1
param([ValidateSet('status','start','stop','restart')][string]$Cmd = 'status')
function St { $hb = 'C:\grok\hwmon\heartbeat.txt'
  if (Test-Path $hb) { $age = [int]((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds; "heartbeat age ${age}s"; Get-Content $hb } else { "no heartbeat" }
  (schtasks /query /tn HwMon /fo list 2>&1 | select -First 5) }
switch ($Cmd) {
  'status'  { St }
  'start'   { schtasks /run /tn HwMon; Start-Sleep 8; St }
  'stop'    { schtasks /end /tn HwMon; Start-Sleep 3; St }
  'restart' { schtasks /end /tn HwMon | Out-Null; Start-Sleep 4; schtasks /run /tn HwMon; Start-Sleep 8; St }
}
