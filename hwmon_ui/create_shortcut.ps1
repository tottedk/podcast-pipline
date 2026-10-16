# create_shortcut.ps1 - creates "HwMon UI toggle" on the Desktop (runs hwmon_ui_toggle.ps1 hidden).
$d = Split-Path $MyInvocation.MyCommand.Path
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'HwMon UI toggle.lnk'
$w = New-Object -ComObject WScript.Shell; $s = $w.CreateShortcut($lnk)
$s.TargetPath = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$s.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $d 'hwmon_ui_toggle.ps1') + '"'
$s.WorkingDirectory = $d; $s.IconLocation = (Join-Path $d 'hwmon_ui.exe') + ',0'; $s.Description = 'Start/stop the HwMon UI widget'; $s.WindowStyle = 7
$s.Save(); Write-Host "created $lnk"
