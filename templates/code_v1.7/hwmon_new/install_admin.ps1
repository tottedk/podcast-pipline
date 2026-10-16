# install_admin.ps1 - ONE elevated run: (1) PawnIO driver 2.2.0 (the driver LibreHardwareMonitorLib 0.9.6 uses; verified sha256 + Authenticode),
# (2) Scheduled Task 'HwMon' (at logon, highest privileges, no time limit, restart on failure), (3) start it.
# Run via:  Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File C:\grok\hwmon\install_admin.ps1'
# Options: -SkipPawnIO (task only; CPU/Super I/O sensors then stay unavailable)   Log: C:\grok\hwmon\admin_install.log
param([switch]$SkipPawnIO)
$ErrorActionPreference = 'Continue'
Start-Transcript 'C:\grok\hwmon\admin_install.log' -Force
$elev = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
"Elevated: $elev   User: $env:USERDOMAIN\$env:USERNAME   $(Get-Date)"
if (-not $elev) { "NOT elevated - abort"; Stop-Transcript; exit 2 }
$setup = 'C:\grok\hwmon\dl\PawnIO_setup.exe'; $wantHash = '1F519A22E47187F70A1379A48CA604981C4FCF694F4E65B734AAA74A9FBA3032'
if (-not $SkipPawnIO) {
  if (Get-Service PawnIO -ErrorAction SilentlyContinue) { "PawnIO service already present: " + (Get-Service PawnIO).Status }
  else {
    $h = (Get-FileHash $setup -Algorithm SHA256).Hash; "setup sha256 $h (expected match: $($h -eq $wantHash))"
    $sig = Get-AuthenticodeSignature $setup; "Authenticode: $($sig.Status)  $($sig.SignerCertificate.Subject)"
    if ($h -ne $wantHash -or $sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'namazso') { "VERIFY FAILED - PawnIO NOT installed" }
    else {
      $rj = Start-Job { try { Enable-ComputerRestore -Drive 'C:\' -EA Stop; Checkpoint-Computer -Description 'Pre-PawnIO-hwmon 2026-10-15' -RestorePointType MODIFY_SETTINGS -EA Stop; 'OK' } catch { "$_" } }
      Wait-Job $rj -Timeout 90 | Out-Null
      if ($rj.State -eq 'Running') { Stop-Job $rj; "Restore point TIMED OUT (skipped)" } else { "Restore point: $(Receive-Job $rj)" }
      Remove-Job $rj -Force -EA SilentlyContinue
      $p = Start-Process $setup -ArgumentList '-install','-silent' -Wait -PassThru; "PawnIO_setup -install -silent exit code: $($p.ExitCode)"
      if (-not (Get-Service PawnIO -EA SilentlyContinue)) { $p = Start-Process $setup -ArgumentList '-silent' -Wait -PassThru; "PawnIO_setup -silent exit code: $($p.ExitCode)" }
      Start-Sleep 2; $sv = Get-Service PawnIO -EA SilentlyContinue; "PawnIO service: " + $(if ($sv) { "$($sv.Status) / $($sv.StartType)" } else { 'NOT FOUND' })
    }
  }
}
$user = "$env:USERDOMAIN\$env:USERNAME"
Unregister-ScheduledTask -TaskName HwMon -Confirm:$false -ErrorAction SilentlyContinue
$a = New-ScheduledTaskAction -Execute 'C:\grok\hwmon\hwmon.exe' -WorkingDirectory 'C:\grok\hwmon'
$t = New-ScheduledTaskTrigger -AtLogOn -User $user
$pr = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -StartWhenAvailable -Priority 7
Register-ScheduledTask -TaskName HwMon -Action $a -Trigger $t -Principal $pr -Settings $s -Description 'Own hardware monitor (LibreHardwareMonitorLib 0.9.6, MPL-2.0): logs every 5 s to C:\grok\podcast\hwlogs' | Out-Null
# allow the non-elevated user to start/stop the task (pipeline scripts: schtasks /run /tn HwMon)
try { $sid = ([Security.Principal.WindowsIdentity]::GetCurrent()).User.Value
  $svc = New-Object -ComObject Schedule.Service; $svc.Connect(); $tk = $svc.GetFolder('\').GetTask('HwMon')
  $sd = $tk.GetSecurityDescriptor(0xF); if ($sd -notmatch $sid) { $tk.SetSecurityDescriptor($sd + "(A;;GRGX;;;$sid)", 0); "task ACL: user may read/run" } } catch { "task ACL step failed: $_" }
Start-ScheduledTask -TaskName HwMon; Start-Sleep 12
Get-ScheduledTask HwMon | Get-ScheduledTaskInfo | Select-Object LastRunTime, LastTaskResult | Format-List | Out-String
(Get-ScheduledTask HwMon).Principal | Select-Object UserId, RunLevel, LogonType | Format-List | Out-String
Get-Process hwmon -EA SilentlyContinue | Select-Object Id, PriorityClass | Format-Table | Out-String
"DONE"; Stop-Transcript