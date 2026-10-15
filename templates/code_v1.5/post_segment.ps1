<#  post_segment.ps1 (template v1.3, 2026-10-15) - raw wav -> safe pause gate -> lighter post chain -> 128k mono mp3. CPU/ffmpeg only (qc_vv.py --gate runs whisper on CPU).
Chain v1.3: highpass 70 -> [afftdn only if -AfftdnNr > 0] -> presence bell +1.5 dB @ 3 kHz (2-4 kHz) -> de-esser (i=0.4) -> atempo -> loudnorm I=-16 TP=-1.5 LRA=11
v1.0-1.2 chain was: highpass 70, afftdn nf=-45 nr=10 tn=1, atempo 0.93, loudnorm.   -Old reproduces it exactly.
Usage: .\post_segment.ps1 -Raw dm_v2\seg02.raw.wav -Script dm_v2\seg02.json -Out dm_v2\seg02.mp3 [-Tempo 0.93] [-Gated already_gated.wav] [-Old]  #>
param([Parameter(Mandatory)][string]$Raw, [Parameter(Mandatory)][string]$Script, [Parameter(Mandatory)][string]$Out,
  [double]$Tempo = 0.93,        # length rule: 0.93 default; 0.90-0.97 allowed (see technical_v1.3.md)
  [double]$DeEss = 0.4,         # ffmpeg deesser intensity; 0 = off (values <= 0.3 do nothing measurable)
  [double]$Presence = 1.5,      # dB, bell at 3 kHz (width 2 octaves ~ 2-4 kHz); 0 = off
  [double]$AfftdnNr = 0,        # v1.3: OFF by default; 4 = soft; old chain used 10
  [string]$Gated = "", [switch]$Old, [string]$Root = "C:\grok\podcast")
$ErrorActionPreference = 'Continue'
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$own = $false
if (-not $Gated) {
  $Gated = [IO.Path]::ChangeExtension($Out, $null).TrimEnd('.') + ".gated.wav"; $own = $true
  $gq = cmd /c "`"$Root\venv_whisper\Scripts\python.exe`" `"$Root\qc_vv.py`" `"$Raw`" `"$Script`" --gate `"$Gated`" 2>&1" | % { "$_" }
  $gq | ? { $_ -match 'gate_kept' } | select -Last 1
  if (-not (Test-Path $Gated)) { Write-Host "[gate] failed, using raw"; $Gated = $Raw; $own = $false }
}
$f = @('highpass=f=70')
if ($Old) { $f += 'afftdn=nf=-45:nr=10:tn=1' } else {
  if ($AfftdnNr -gt 0) { $f += "afftdn=nf=-45:nr=${AfftdnNr}:tn=1" }
  if ($Presence -ne 0) { $f += "equalizer=f=3000:t=o:w=2:g=$Presence" }
  if ($DeEss -gt 0) { $f += "deesser=i=${DeEss}:m=0.5:f=0.5" }
}
if ($Tempo -ne 1) { $f += "atempo=$Tempo" }
$f += 'loudnorm=I=-16:TP=-1.5:LRA=11'
$af = $f -join ','
ffmpeg -hide_banner -loglevel error -y -i $Gated -af $af -ar 44100 -ac 1 -b:a 128k $Out
if ($LASTEXITCODE) { throw "ffmpeg failed: $af" }
if ($own) { Remove-Item $Gated }
"POST $Out  [$af]  dur $(ffprobe -v error -show_entries format=duration -of csv=p=0 $Out) s"
