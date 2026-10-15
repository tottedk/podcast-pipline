# compare_hwinfo.ps1 - samples HWiNFO VSB registry values and the HwMon full CSV every 5 s, writes compare_<ts>.csv + prints mean/min/max side by side
param([int]$Samples = 24, [int]$Interval = 5)
$map = [ordered]@{
 'GPU Temp'      = @('GPU Temperature',0,                     'AMD Radeon RX 7900 XT / GPU Core [Temperature]')
 'GPU Hotspot'   = @('GPU Hot Spot Temperature',0,            'AMD Radeon RX 7900 XT / GPU Hot Spot [Temperature]')
 'GPU MemJunc'   = @('GPU Memory Junction Temperature',0,     'AMD Radeon RX 7900 XT / GPU Memory [Temperature]')
 'GPU Fan RPM'   = @('GPU Fan',0,                             'AMD Radeon RX 7900 XT / GPU Fan [Fan]')
 'GPU Power W (HWiNFO TBP)' = @('Total Board Power (TBP)',0,  'AMD Radeon RX 7900 XT / GPU Package [Power]')
 'GPU Load %'    = @('GPU Utilization',0,                     'AMD Radeon RX 7900 XT / GPU Core [Load]')
 'GPU VRAM MB'   = @('GPU D3D Memory Dedicated',0,            'AMD Radeon RX 7900 XT / D3D Dedicated Memory Used [SmallData]')
 'CPU Tctl C'    = @('CPU (Tctl/Tdie)',0,                     'AMD Ryzen 5 7600X / Core (Tctl/Tdie) [Temperature]')
 'CPU CCD1 C'    = @('CPU CCD1 (Tdie)',0,                     'AMD Ryzen 5 7600X / CCD1 (Tdie) [Temperature]')
 'CPU Pkg Power W' = @('CPU Package Power',0,                 'AMD Ryzen 5 7600X / Package [Power]')
 'CPU Load %'    = @('Total CPU Usage',0,                     'AMD Ryzen 5 7600X / CPU Total [Load]')
 'Mobo Temp C'   = @('Motherboard',0,                         'Nuvoton NCT6799D / Motherboard [Temperature]')
 '+12V'          = @('+12V',0,                                'Nuvoton NCT6799D / +12V [Voltage]')
 '+5V'           = @('+5V',0,                                 'Nuvoton NCT6799D / +5V [Voltage]')
 'Vcore (SuperIO)' = @('Vcore',0,                             'Nuvoton NCT6799D / Vcore [Voltage]')
 'Fan: HWiNFO Chassis1 vs LHM Fan #1' = @('Chassis1',0,       'Nuvoton NCT6799D / Fan #1 [Fan]')
 'Fan: HWiNFO CPU fan vs LHM Fan #2'  = @('CPU',1,            'Nuvoton NCT6799D / Fan #2 [Fan]')
 'Drive 1 temp C'  = @('Drive Temperature',0,                 'Samsung SSD 980 PRO with Heatsink 1TB / Composite Temperature [Temperature]')
 'RAM used MB'   = @('Physical Memory Used',0,                'Total Memory / Memory Used [Data]')
}
function Num($s) { $m = [regex]::Match(($s -replace ',', ''), '-?\d+(\.\d+)?'); if ($m.Success) { [double]::Parse($m.Value, [Globalization.CultureInfo]::InvariantCulture) } }
function Hw { $k = Get-ItemProperty HKCU:\Software\HWiNFO64\VSB; $l = @{}
  $k.PSObject.Properties | ? Name -like 'Label*' | sort { [int]$_.Name.Substring(5) } | % { $i = $_.Name.Substring(5); if (-not $l.ContainsKey($_.Value)) { $l[$_.Value] = @() }; $l[$_.Value] += $k.("Value$i") }; $l }
$full = (gci C:\grok\podcast\hwlogs\hwmon_full_*.csv | sort LastWriteTime | select -Last 1).FullName
$hdr = (Get-Content $full -TotalCount 1) | ConvertFrom-Csv -Header (1..1) 2>$null
$cols = [Text.RegularExpressions.Regex]::Split((Get-Content $full -TotalCount 1), ',(?=(?:[^"]*"[^"]*")*[^"]*$)') | % { $_.Trim('"') }
$rows = @()
for ($n = 0; $n -lt $Samples; $n++) {
  $h = Hw
  $fs = New-Object IO.FileStream($full, 'Open', 'Read', 'ReadWrite'); $sr = New-Object IO.StreamReader($fs); $all = $sr.ReadToEnd(); $sr.Dispose()
  $last = ($all -split "`r?`n" | ? { $_ } | select -Last 1) -split ','
  $r = [ordered]@{ Time = (Get-Date -f 'HH:mm:ss') }
  foreach ($k in $map.Keys) { $m = $map[$k]; $hv = $null; if ($h.ContainsKey($m[0])) { $hv = Num $h[$m[0]][$m[1]] }
    $ix = [array]::IndexOf($cols, $m[2]); $lv = if ($ix -ge 0 -and $last[$ix] -ne '') { [double]::Parse($last[$ix], [Globalization.CultureInfo]::InvariantCulture) } else { $null }
    if ($k -match 'RAM used') { $lv = $lv * 1024 }
    $r["$k | HWiNFO"] = $hv; $r["$k | LHM"] = $lv }
  $rows += [pscustomobject]$r; Start-Sleep $Interval
}
$out = "C:\grok\hwmon\compare_$(Get-Date -f yyyyMMdd_HHmmss).csv"; $rows | Export-Csv $out -NoTypeInformation -Encoding utf8
"{0,-38}{1,22}{2,22}{3,10}" -f 'Sensor', 'HWiNFO mean (min-max)', 'LHM mean (min-max)', 'diff'
foreach ($k in $map.Keys) { $a = @($rows | % { $_."$k | HWiNFO" } | ? { $null -ne $_ }); $b = @($rows | % { $_."$k | LHM" } | ? { $null -ne $_ })
  if ($a.Count -and $b.Count) { $ma = ($a | measure -Average).Average; $mb = ($b | measure -Average).Average
    "{0,-38}{1,22}{2,22}{3,10:n2}" -f $k, ("{0:n1} ({1:n1}-{2:n1})" -f $ma, ($a | measure -Min).Minimum, ($a | measure -Max).Maximum), ("{0:n1} ({1:n1}-{2:n1})" -f $mb, ($b | measure -Min).Minimum, ($b | measure -Max).Maximum), ($mb - $ma) }
  else { "{0,-38}{1,22}{2,22}" -f $k, "n=$($a.Count)", "n=$($b.Count)" } }
"csv: $out"