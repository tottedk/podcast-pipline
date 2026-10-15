# last_before.ps1 - after a crash/BSOD: show the last N samples before a time (default: last boot's end / given -At) from the continuous log.
# Usage: .\last_before.ps1 [-At "2026-10-15 14:03:00"] [-Minutes 10] [-Full]   (without -At: the last sample of the previous day/session before the current boot)
param([string]$At = "", [int]$Minutes = 10, [switch]$Full)
$pat = if ($Full) { 'hwmon_full_*.csv' } else { 'hwmon_cont_*.csv' }
$files = gci C:\grok\podcast\hwlogs\$pat | sort Name
$rows = foreach ($f in $files) { Import-Csv $f.FullName }
if (-not $rows) { "no rows"; return }
if ($At) { $t = [datetime]$At } else { $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; $t = ($rows | ? { [datetime]$_.Time -lt $boot } | select -Last 1).Time; $t = [datetime]$t; "(last sample before boot $boot) = $t" }
$rows | ? { ([datetime]$_.Time) -le $t -and ([datetime]$_.Time) -ge $t.AddMinutes(-$Minutes) } | Format-Table -AutoSize | Out-String -Width 400
