<#  podcast.ps1 - notes.txt -> Gemma script -> VibeVoice-1.5B -> auto-QC/redo -> pause gate -> highpass/afftdn -> tempo -> loudnorm -> mp3
Usage: .\podcast.ps1 notes.txt episode.mp3 -Topic "..." [-Lines 14] [-HostVoice Carter] [-GuestVoice Frank] [-Tempo 0.93] [-Pace sentence] [-Cfg 1.3] [-Script existing.json]
#>
param(
  [Parameter(Mandatory)][string]$Notes,
  [Parameter(Mandatory)][string]$Out,
  [string]$Topic = "",
  [int]$Lines = 14,
  [string]$HostVoice = "Carter",
  [string]$GuestVoice = "Frank",
  [double]$Tempo = 0.93,
  [ValidateSet("none","sentence","all")][string]$Pace = "sentence",
  [double]$Cfg = 1.3,
  [int]$Seed = 42,
  [string]$Script = "",
  [int]$ChunkWords = 700,
  [int]$Steps = 10,
  [int]$QcRetries = 2,          # auto-QC: regenerate flagged chunks with a new seed up to N times
  [switch]$NoQc,
  [switch]$NoHwMonitor         # skip the HWiNFO/VSB hardware logger (hwlogs\)
)
$ErrorActionPreference = "Continue"   # native stderr (warnings) must not abort
$root = $PSScriptRoot
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$sw = [Diagnostics.Stopwatch]::StartNew()
$Out = [IO.Path]::GetFullPath((Join-Path (Get-Location) $Out))
$base = [IO.Path]::ChangeExtension($Out, $null).TrimEnd('.')
$json = if ($Script) { $Script } else { "$base.script.json" }
$wav = "$base.raw.wav"
. "$root\hwmon_lib.ps1"; $hw = $null
if (-not $NoHwMonitor) { $hw = Start-HwMonitor ("podcast_" + [IO.Path]::GetFileNameWithoutExtension($Out)) }
try {

if (-not $Script) {
  Write-Host "[1/3] Script via Gemma ($Lines turns)..."
  $ctx = if ($Lines -gt 40) { 32768 } else { 8192 }
  cmd /c "`"$root\venv\Scripts\python.exe`" `"$root\write_script.py`" `"$Notes`" `"$json`" --lines $Lines --topic `"$Topic`" --ctx $ctx 2>&1"
  if ($LASTEXITCODE) { throw "write_script failed" }
  # Make sure Ollama has released VRAM (keep_alive 0) before VibeVoice loads
  for ($i=0; $i -lt 30; $i++) { try { $ps = Invoke-RestMethod http://localhost:11434/api/ps; if (-not $ps.models) { break } } catch { break }; Start-Sleep 1 }
}
Write-Host "[2/3] VibeVoice ($HostVoice / $GuestVoice)..."
$env:HIP_VISIBLE_DEVICES = "1"   # device 0 = iGPU, crashes
cmd /c "`"$root\venv_vv\Scripts\python.exe`" `"$root\vv_generate.py`" `"$json`" `"$wav`" --host $HostVoice --guest $GuestVoice --cfg $Cfg --seed $Seed --pace $Pace --chunk_words $ChunkWords --steps $Steps 2>&1" |
  ForEach-Object { "$_" } | Where-Object { $_ -match 'words|chunk|DONE|loaded|Error|Traceback' } | Write-Host
if (-not (Test-Path $wav)) { throw "VibeVoice failed" }

$py_w = "$root\venv_whisper\Scripts\python.exe"; $chunks = "$wav.chunks"; $qcj = "$base.qc.json"
if (-not $NoQc) {
  # Auto-QC (qc_vv.py): per chunk whisper large-v3-turbo -> dropped/garbled line (<75% recognised), chunk WER > 8%,
  # octave pitch jump on a low-confidence word, or excessive non-speech energy -> regenerate that chunk with another seed
  for ($r = 1; $r -le $QcRetries; $r++) {
    $q = cmd /c "`"$py_w`" `"$root\qc_vv.py`" `"$wav`" `"$json`" --chunks `"$chunks`" --json `"$qcj`" 2>&1" | ForEach-Object { "$_" }
    $redo = ($q | Where-Object { $_ -match '^REDO' } | Select-Object -Last 1) -replace '^REDO\s*',''
    if (-not $redo) { Write-Host "[QC] pass $r ok"; break }
    $spec = ($redo -split ',' | ForEach-Object { "${_}:$($Seed + 1000*$r)" }) -join ','
    Write-Host "[QC] pass $r flagged chunk(s) $redo -> regenerate $spec"
    cmd /c "`"$root\venv_vv\Scripts\python.exe`" `"$root\vv_generate.py`" `"$json`" `"$wav`" --host $HostVoice --guest $GuestVoice --cfg $Cfg --pace $Pace --chunk_words $ChunkWords --steps $Steps --redo $spec 2>&1" |
      ForEach-Object { "$_" } | Where-Object { $_ -match 'chunk|DONE|Error|Traceback' } | Write-Host
  }
}
# Pause gate: VibeVoice emits a noise/ambience burst at turn and sentence onsets (A/B 2026-10-13: 2 s, 47 s);
# fade everything outside whisper words (onset-refined) to -60 dB, then highpass + light afftdn, tempo, loudnorm LAST
$gated = "$base.gated.wav"
cmd /c "`"$py_w`" `"$root\qc_vv.py`" `"$wav`" `"$json`" --gate `"$gated`" 2>&1" | Out-Null
if (-not (Test-Path $gated)) { Write-Host "[gate] failed, using raw"; $gated = $wav }
Write-Host "[3/3] highpass/afftdn + tempo $Tempo + loudnorm -> mp3..."
$af = if ($Tempo -ne 1) { "atempo=$Tempo," } else { "" }
ffmpeg -hide_banner -loglevel error -y -i $gated -af "highpass=f=70,afftdn=nf=-45:nr=10:tn=1,${af}loudnorm=I=-16:TP=-1.5:LRA=11" -ar 44100 -ac 1 -b:a 128k $Out
if ($LASTEXITCODE) { throw "ffmpeg failed" }
if ($gated -ne $wav) { Remove-Item $gated }
# raw wav + per-chunk wavs are kept (<out>.raw.wav, .raw.wav.chunks\) so glitches can be diagnosed / single chunks redone
$dur = [double](ffprobe -v error -show_entries format=duration -of csv=p=0 $Out)
$words = (Get-Content $json -Raw | ConvertFrom-Json | ForEach-Object { ($_.text -split '\s+' | ? {$_}).Count } | Measure-Object -Sum).Sum
$t = $sw.Elapsed.TotalSeconds
"DONE {0}  audio {1:n1} min, {2} words, {3:n0} wpm, total {4:n1} min ({5:n2} min per audio-min)" -f $Out, ($dur/60), $words, ($words/($dur/60)), ($t/60), ($t/$dur)
} finally { Stop-HwMonitor $hw }
