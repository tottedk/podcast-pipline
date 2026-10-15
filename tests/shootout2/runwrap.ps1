param([string]$Name,[string]$Job,[string]$OutDir)
$ctr='\GPU Adapter Memory(luid_0x00000000_0x000111ea_phys_0)\Dedicated Usage'; $base=(Get-Counter $ctr).CounterSamples[0].CookedValue
$t0=Get-Date; $p=Start-Process powershell -ArgumentList '-ExecutionPolicy','Bypass','-File',$Job -RedirectStandardOutput "$OutDir\$Name.log" -RedirectStandardError "$OutDir\$Name.err" -WindowStyle Hidden -PassThru
Start-Sleep 1; try{$p.PriorityClass='Idle'}catch{}; $peak=0
while(-not $p.HasExited){ $v=(Get-Counter $ctr -ea 0).CounterSamples[0].CookedValue; if($v -gt $peak){$peak=$v}; Start-Sleep 2 }
$w=((Get-Date)-$t0).TotalSeconds
"{`"name`":`"$Name`",`"wall_s`":$([math]::Round($w,1)),`"vram_base_gb`":$([math]::Round($base/1GB,2)),`"vram_peak_gb`":$([math]::Round($peak/1GB,2)),`"exit`":`"$($p.ExitCode)`"}" | Out-File -Encoding ascii "$OutDir\$Name.stats.json"

