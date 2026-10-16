# build.ps1 - build hwmon_ui.exe with the .NET Framework 4 csc.exe (no SDK, no install). Refuses to overwrite a running exe unless -Force (then it asks the widget to exit first).
param([switch]$Force)
$d = Split-Path $MyInvocation.MyCommand.Path; Set-Location $d
$run = Get-Process hwmon_ui -ErrorAction SilentlyContinue
if ($run) { if (-not $Force) { Write-Host "hwmon_ui is running - close it first (hwmon_ui_toggle.ps1) or use -Force"; exit 1 }
  try { $ev = [Threading.EventWaitHandle]::OpenExisting('Local\HwMonUI_Exit'); [void]$ev.Set() } catch {}; $run | % { [void]$_.WaitForExit(5000) } }
$csc = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $csc /nologo /target:winexe /platform:anycpu /optimize+ /out:hwmon_ui.exe /reference:System.dll,System.Core.dll,System.Drawing.dll,System.Windows.Forms.dll,System.Management.dll hwmon_ui.cs
if ($LASTEXITCODE) { Write-Host "BUILD FAILED"; exit 1 }
Write-Host "built $d\hwmon_ui.exe ($((Get-Item hwmon_ui.exe).Length) bytes)"
