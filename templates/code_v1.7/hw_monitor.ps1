<# hw_monitor.ps1 - lightweight sampler of HWiNFO VSB registry values (HKCU\Software\HWiNFO64\VSB)
Usage: hw_monitor.ps1 -Run <name> [-ParentPid <pid>] [-Interval 5] [-StopFlag <file>]
Writes C:\grok\podcast\hwlogs\<run>_<yyyyMMdd_HHmmss>.csv and .summary.txt; stops on stop-flag or parent exit. #>
param([string]$Run = "run", [int]$ParentPid = 0, [int]$Interval = 5, [string]$StopFlag = "", [int]$MaxHours = 24)
$ErrorActionPreference = "SilentlyContinue"
try { [Diagnostics.Process]::GetCurrentProcess().PriorityClass = 'BelowNormal' } catch {}
$dir = "C:\grok\podcast\hwlogs"; New-Item -ItemType Directory -Force $dir | Out-Null
# retention: 30 days
Get-ChildItem $dir -File | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force
$Run = $Run -replace '[^\w\-\.]', '_'
$csv = Join-Path $dir ("{0}_{1}.csv" -f $Run, (Get-Date -f 'yyyyMMdd_HHmmss'))
$sum = [IO.Path]::ChangeExtension($csv, '.summary.txt')
if (-not $StopFlag) { $StopFlag = "$csv.stop" }
# column -> exact VSB label; FIRST occurrence wins (7900 XT before iGPU, first RAM/drive)
$map = [ordered]@{
  GpuTemp_C      = 'GPU Temperature'
  GpuHotspot_C   = 'GPU Hot Spot Temperature'
  GpuMemJunc_C   = 'GPU Memory Junction Temperature'
  GpuPower_W     = 'Total Board Power (TBP)'
  GpuLoad_pct    = 'GPU Utilization'
  GpuVram_MB     = 'GPU D3D Memory Dedicated'
  GpuFan_RPM     = 'GPU Fan'
  GpuHotLimit_pct= 'GPU Hotspot Thermal Limit'
  CpuTemp_C      = 'CPU (Tctl/Tdie)'
  CpuPower_W     = 'CPU Package Power'
  CpuLoad_pct    = 'Total CPU Usage'
  CpuHTC         = 'Thermal Throttling (HTC)'
  RamUsed_MB     = 'Physical Memory Used'
}
$vsbPath = 'HKCU:\Software\HWiNFO64\VSB'
$want = @{}; foreach ($c in $map.Keys) { $want[$map[$c]] = $c }
function Read-Vsb { $k = Get-ItemProperty $vsbPath; $h = @{}
  if ($k) { $k.PSObject.Properties | Where-Object Name -like 'Label*' | Sort-Object { [int]$_.Name.Substring(5) } | ForEach-Object {
    $c = $want[$_.Value]; if ($c -and -not $h.Contains($c)) { $h[$c] = $k.('Value' + $_.Name.Substring(5)) } } }; $h }
function Num($s) { if ($null -eq $s) { return $null }; $s = "$s"
  if ($s -match '^\s*(Yes|No)\b') { return [int]($Matches[1] -eq 'Yes') }
  $m = [regex]::Match(($s -replace ',', ''), '-?\d+(\.\d+)?'); if ($m.Success) { [double]::Parse($m.Value, [Globalization.CultureInfo]::InvariantCulture) } }
$vsb = Read-Vsb; $lab = @{}; foreach ($c in $map.Keys) { $lab[$c] = $vsb.Contains($c) }
$missing = @($map.Keys | Where-Object { -not $lab[$_] })
$totMB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1MB)
(@('Time') + $map.Keys) -join ',' | Out-File $csv -Encoding utf8
$rows = New-Object System.Collections.Generic.List[object]; $start = Get-Date; $last = $start; $eG = 0.0; $eC = 0.0
while ($true) {
  $vsb = Read-Vsb; $r = [ordered]@{}
  foreach ($c in $map.Keys) { $r[$c] = if ($lab[$c]) { Num $vsb[$c] } else { $null } }
  if ($null -eq $r.CpuLoad_pct) { $r.CpuLoad_pct = [double](Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'").PercentProcessorTime }
  if ($null -eq $r.RamUsed_MB) { $os = Get-CimInstance Win32_OperatingSystem -Property FreePhysicalMemory; $r.RamUsed_MB = [math]::Round($totMB - $os.FreePhysicalMemory / 1KB) }
  $now = Get-Date; $dt = ($now - $last).TotalSeconds; $last = $now
  if ($r.GpuPower_W) { $eG += $r.GpuPower_W * $dt }; if ($r.CpuPower_W) { $eC += $r.CpuPower_W * $dt }
  $rows.Add([pscustomobject]$r)
  ((@($now.ToString('yyyy-MM-dd HH:mm:ss')) + @($r.Values | ForEach-Object { "$_" })) -join ',') | Add-Content $csv
  if (Test-Path $StopFlag) { break }
  if ($ParentPid -and -not (Get-Process -Id $ParentPid)) { break }
  if (($now - $start).TotalHours -ge $MaxHours) { break }
  for ($i = 0; $i -lt $Interval * 2; $i++) { Start-Sleep -Milliseconds 500; if (Test-Path $StopFlag) { break } }
}
Remove-Item $StopFlag -Force
$o = @("Run: $Run", "Start: $($start.ToString('yyyy-MM-dd HH:mm:ss'))  End: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))  Duration: $([math]::Round(((Get-Date)-$start).TotalMinutes,1)) min  Samples: $($rows.Count)", "")
$o += "{0,-14}{1,10}{2,10}" -f 'Sensor', 'Max', 'Avg'
foreach ($c in $map.Keys) { $m = $rows | Where-Object { $null -ne $_.$c } | Measure-Object $c -Max -Average
  $o += if ($m.Count) { "{0,-14}{1,10:n1}{2,10:n1}" -f $c, $m.Maximum, $m.Average } else { "{0,-14}{1,10}{2,10}" -f $c, 'n/a', 'n/a' } }
$o += ""
$o += "HTC throttling samples: " + $(if ($lab.CpuHTC) { @($rows | Where-Object { $_.CpuHTC -eq 1 }).Count } else { 'n/a' })
$o += "Hotspot >95 C samples: " + $(if ($lab.GpuHotspot_C) { @($rows | Where-Object { $_.GpuHotspot_C -gt 95 }).Count } else { 'n/a (sensor missing)' })
$o += "Energy GPU: " + $(if ($lab.GpuPower_W) { "{0:n4} kWh" -f ($eG / 3.6e6) } else { 'n/a' }) + "   CPU: " + $(if ($lab.CpuPower_W) { "{0:n4} kWh" -f ($eC / 3.6e6) } else { 'n/a' }) + "   Total: {0:n4} kWh" -f (($eG + $eC) / 3.6e6)
$fb = @('CpuLoad_pct', 'RamUsed_MB')
if ($missing) { $o += "Missing in HWiNFO VSB (enable in Sensor settings > HWiNFO Gadget): " + (($missing | ForEach-Object { if ($fb -contains $_) { "$_ (CIM fallback used)" } else { $_ } }) -join ', ') }
$o | Out-File $sum -Encoding utf8
