# job.ps1 [-List models.txt] - detached shootout: per model, hwmon session + run.py (BelowNormal), cool-down between models. Progress -> STATUS.txt
param([string]$List = "$PSScriptRoot\models.txt")
$ErrorActionPreference = 'Continue'; $d = $PSScriptRoot; $py = 'C:\grok\podcast\venv\Scripts\python.exe'; $st = "$d\STATUS.txt"
(Get-Process -Id $PID).PriorityClass = 'BelowNormal'
function S($m) { "$(Get-Date -f 'HH:mm:ss') $m" | Add-Content $st }
. 'C:\grok\hwmon\hwmon_lib.ps1'
function HotNow { try { $c = 'C:\grok\hwmon\sessions'; $f = (Get-ChildItem 'C:\grok\podcast\hwlogs\hwmon_full_*.csv' | Sort-Object LastWriteTime | Select-Object -Last 1).FullName
  $h = (Get-Content $f -TotalCount 1).Split(','); $i = [array]::IndexOf($h, 'AMD Radeon RX 7900 XT / GPU Hot Spot [Temperature]'); [double]((Get-Content $f -Tail 1).Split(',')[$i]) } catch { 0 } }
S "JOB START pid $PID"
foreach ($m in (Get-Content $List | Where-Object { $_.Trim() -and -not $_.StartsWith('#') })) {
  $m = $m.Trim(); $safe = $m -replace '[^\w\.\-]', '_'
  if (Test-Path "$d\results\$safe.hw.json") { S "SKIP $m (done)"; continue }
  if ((Invoke-RestMethod http://localhost:11434/api/ps).models) { S "ABORT: Ollama has a model loaded, not touching"; break }
  if (Get-Process audiocpp_cli, ffmpeg -ErrorAction SilentlyContinue) { S "WAIT: other GPU/podcast job running"; while (Get-Process audiocpp_cli -ErrorAction SilentlyContinue) { Start-Sleep 20 } }
  for ($i = 0; $i -lt 30 -and (HotNow) -gt 70; $i++) { if ($i -eq 0) { S "cooldown (hotspot $(HotNow) C)" }; Start-Sleep 10 }
  S "START $m (hotspot $(HotNow) C)"
  $h = Start-HwMonitor ("shootout_" + $safe); $csv = (Get-Content "C:\grok\hwmon\sessions\shootout_$safe.state")[0]; Start-Sleep 12
  $t0 = Get-Date
  $p = Start-Process $py -ArgumentList "`"$d\run.py`"", $m -NoNewWindow -PassThru -RedirectStandardOutput "$d\results\$safe.out" -RedirectStandardError "$d\results\$safe.err"
  try { $p.PriorityClass = 'BelowNormal' } catch {}
  $dl = (Get-Date).AddMinutes(40); while (-not $p.HasExited) { Start-Sleep 5; if ((Get-Date) -gt $dl) { S "TIMEOUT $m -> kill"; $p.Kill(); break } ; $hn = HotNow; if ($hn -ge 104) { S "HOTSPOT $hn C >= 104: aborting $m"; $p.Kill(); break } }
  try { Invoke-RestMethod http://localhost:11434/api/generate -Method Post -Body (@{ model = $m; prompt = ''; keep_alive = 0 } | ConvertTo-Json) -TimeoutSec 60 | Out-Null } catch {}
  Start-Sleep 12; $t1 = Get-Date; Stop-HwMonitor $h | Out-Null
  & $py "$d\analyze_hw.py" $csv $safe ($t0.ToString('yyyy-MM-dd HH:mm:ss')) ($t1.ToString('yyyy-MM-dd HH:mm:ss')) 2>&1 | Add-Content $st
  S "END $m exit $($p.ExitCode) ($([int](($t1 - $t0).TotalSeconds)) s) ollama_ps_empty=$(-not (Invoke-RestMethod http://localhost:11434/api/ps).models)"
}
S "JOB DONE"
