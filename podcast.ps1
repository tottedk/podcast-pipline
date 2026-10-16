<#  podcast.ps1 (v1.3 2026-10-15: BACKUP engine VibeVoice-1.5B; defaults ChunkWords 275, QcRetries 1 (v1.8; was 2), empty glossary, lighter post chain; DEFAULT engine is now render7b.ps1 = VibeVoice-7B Q8 via audio.cpp) (v2 2026-10-14: merge short lines, glossary respelling, QC every take + best take, final qc.json, safe gate) - notes.txt -> Gemma script -> VibeVoice-1.5B -> auto-QC/redo -> pause gate -> highpass/afftdn -> tempo -> loudnorm -> mp3
Usage: .\podcast.ps1 notes.txt episode.mp3 -Topic "..." [-Lines 14] [-HostVoice Carter] [-GuestVoice X -Guest2Voice Y | none = random pick] [-Tempo 0.93] [-Pace sentence] [-Cfg 1.3] [-Script existing.json]
#>
param(
  [Parameter(Mandatory)][string]$Notes,
  [Parameter(Mandatory)][string]$Out,
  [string]$Topic = "",
  [int]$Lines = 14,
  [string]$HostVoice = "Carter",
  [string]$GuestVoice = "",       # v1.3: NO default cast - empty = random pick (pick_cast.py), logged to <out>.cast.json
  [string]$Guest2Voice = "",     # v1.2: voice for "Guest2" lines (3-speaker scripts); v1.3: picked at random if empty and the script has Guest2 lines
  [double]$Tempo = 0.93,
  [ValidateSet("none","sentence","all")][string]$Pace = "sentence",
  [double]$Cfg = 1.3,
  [int]$Seed = 42,
  [string]$Script = "",
  [int]$ChunkWords = 275,      # v1.3: 275 on turn boundaries (v1.0-1.2: 175 for the 1.5B; 350 drifted in DE ep1)
  [int]$Steps = 10,
  [int]$QcRetries = 1,          # auto-QC: regenerate flagged chunks up to N times; every take is QCed, best take ships
  [switch]$NoQc,
  [switch]$NoMerge,            # skip prep_script.py (merging of <=2-word interjection lines)
  [string]$Glossary = "",      # v1.3: respellings OFF by default (empty_glossary.json); opt in with -Glossary glossary.json
  [double]$AfftdnNr = 0,       # v1.3: afftdn OFF by default (old chain nr=10); 4 = soft
  [double]$DeEss = 0.4, [double]$Presence = 1.5,   # v1.3 post chain: de-esser intensity, 3 kHz bell dB (0 = off)
  [switch]$Scheduled,          # v1.5: nightly run -> vram_free.ps1 -Free -Scheduled first (guarded, graceful; also env PODCAST_SCHEDULED=1)
  [switch]$NoHwMonitor         # skip the hardware logger (hwlogs\; own HwMon / LibreHardwareMonitor, fallback HWiNFO VSB)
)
$ErrorActionPreference = "Continue"   # native stderr (warnings) must not abort
$root = $PSScriptRoot
if (-not $Glossary) { $Glossary = "$root\empty_glossary.json" }   # v1.3
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$sw = [Diagnostics.Stopwatch]::StartNew()
if (($Scheduled -or $env:PODCAST_SCHEDULED -eq '1') -and (Test-Path "$root\vram_free.ps1")) { & powershell -NoProfile -ExecutionPolicy Bypass -File "$root\vram_free.ps1" -Free -Scheduled 2>&1 | Out-String | Write-Host }   # v1.5: free VRAM for scheduled runs only
$Out = [IO.Path]::GetFullPath((Join-Path (Get-Location) $Out))
$base = [IO.Path]::ChangeExtension($Out, $null).TrimEnd('.')
$json = if ($Script) { $Script } else { "$base.script.json" }
$wav = "$base.raw.wav"
# v1.3: no default cast. If no guest was given, pick at random from the pool (pick_cast.py: gender-free here, F0 gap >= 12 Hz), seed + cast logged to <out>.cast.json
$hasG2 = [bool]($Script -and (Test-Path $Script) -and (Select-String -Path $Script -Pattern '"speaker"\s*:\s*"Guest2"' -Quiet))
if (-not $GuestVoice) {
  $pcl = cmd /c "`"$root\venv_vv\Scripts\python.exe`" `"$root\pick_cast.py`" --out `"$base.cast.json`" --host $HostVoice --roles $(if ($hasG2) { 'Guest,Guest2' } else { 'Guest' }) --force 2>&1"; $pcl | Write-Host
  $cj = Get-Content "$base.cast.json" -Raw | ConvertFrom-Json; $GuestVoice = $cj.guest; if ($hasG2) { $Guest2Voice = $cj.guest2 }
} elseif ($hasG2 -and -not $Guest2Voice) { throw "script has Guest2 lines: give -Guest2Voice (or give neither guest to pick both at random)" }
$hl = 'C:\grok\hwmon\hwmon_lib.ps1'; if (-not (Test-Path $hl)) { $hl = "$root\hwmon_lib.ps1" }  # v1.3: own LibreHardwareMonitor monitor (HwMon task); lib falls back to the old HWiNFO monitor itself, old lib if new missing
. $hl; $hw = $null
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
if (-not $NoMerge) { cmd /c "`"$root\venv\Scripts\python.exe`" `"$root\prep_script.py`" `"$json`" 2>&1" | Write-Host }   # merges <=2-word lines in place (backup *.pre_merge.json); use the same json for align/video
$gl = if ($Glossary) { " --glossary `"$Glossary`"" } else { "" }
if ($Guest2Voice) { $gl += " --guest2 $Guest2Voice" }
Write-Host "[2/3] VibeVoice ($HostVoice / $GuestVoice$(if ($Guest2Voice) { " / $Guest2Voice" }))..."
$env:HIP_VISIBLE_DEVICES = "1"   # device 0 = iGPU, crashes
cmd /c "`"$root\venv_vv\Scripts\python.exe`" `"$root\vv_generate.py`" `"$json`" `"$wav`" --host $HostVoice --guest $GuestVoice --cfg $Cfg --seed $Seed --pace $Pace --chunk_words $ChunkWords --steps $Steps$gl 2>&1" |
  ForEach-Object { "$_" } | Where-Object { $_ -match 'words|chunk|DONE|loaded|Error|Traceback' } | Write-Host
if (-not (Test-Path $wav)) { throw "VibeVoice failed" }

$py_w = "$root\venv_whisper\Scripts\python.exe"; $py_t = "$root\venv_vv\Scripts\python.exe"   # v1.2: qc_takes.py needs soundfile (not in venv_whisper -> best-take pick silently failed in v1.1)
$chunks = "$wav.chunks"; $qcj = "$base.qc.json"
if (-not $NoQc) {
  # v2 (2026-10-14): QC after EVERY (re)generation, record each take's score (qc_takes.py), ship the best take per chunk,
  # then a final QC of exactly what ships -> $qcj (final=true). Checks: see qc_vv.py docstring.
  $qa = "--chunks `"$chunks`" --host $HostVoice --guest $GuestVoice" + $(if ($Guest2Voice) { " --guest2 $Guest2Voice" } else { "" }) + $(if ($Glossary) { " --glossary `"$Glossary`"" } else { "" })
  if (Test-Path "$chunks\takes") { Remove-Item -Recurse -Force "$chunks\takes" }
  for ($r = 0; $r -le $QcRetries; $r++) {
    $q = cmd /c "`"$py_w`" `"$root\qc_vv.py`" `"$wav`" `"$json`" $qa --json `"$qcj`" 2>&1" | ForEach-Object { "$_" }
    $q | Where-Object { $_ -match '^chunk \d+ seed' } | Write-Host
    cmd /c "`"$py_t`" `"$root\qc_takes.py`" record `"$chunks`" `"$qcj`" $r 2>&1" | ForEach-Object { "$_" } | Where-Object { $_ -match "recorded|Error|Traceback" } | Write-Host
    $redo = ($q | Where-Object { $_ -match '^REDO' } | Select-Object -Last 1) -replace '^REDO\s*',''
    if (-not $redo) { Write-Host "[QC] pass $r ok"; break }
    if ($r -eq $QcRetries) { Write-Host "[QC] pass $r still flagged: $redo (retries exhausted)"; break }
    $spec = ($redo -split ',' | ForEach-Object { "${_}:$($Seed + 1000*($r+1))" }) -join ','
    Write-Host "[QC] pass $r flagged chunk(s) $redo -> regenerate $spec"
    cmd /c "`"$root\venv_vv\Scripts\python.exe`" `"$root\vv_generate.py`" `"$json`" `"$wav`" --host $HostVoice --guest $GuestVoice --cfg $Cfg --pace $Pace --chunk_words $ChunkWords --steps $Steps --redo $spec$gl 2>&1" |
      ForEach-Object { "$_" } | Where-Object { $_ -match 'chunk|DONE|Error|Traceback' } | Write-Host
  }
  $pick = cmd /c "`"$py_t`" `"$root\qc_takes.py`" pick `"$chunks`" `"$wav`" 2>&1" | ForEach-Object { "$_" }
  $pick | Write-Host
  $changed = ($pick | Where-Object { $_ -match '^CHANGED' }) -replace '^CHANGED\s*',''
  if ($changed) {   # best take differs from the last generated one -> re-QC the shipped audio so qc.json describes it
    $q = cmd /c "`"$py_w`" `"$root\qc_vv.py`" `"$wav`" `"$json`" $qa --json `"$qcj`" 2>&1" | ForEach-Object { "$_" }
  }
  $fin = Get-Content $qcj -Raw | ConvertFrom-Json
  $fin | Add-Member -NotePropertyName final -NotePropertyValue $true -Force
  $fin | ConvertTo-Json -Depth 8 | Set-Content -Encoding ascii $qcj
  if ($fin.redo) { Write-Host "[QC] WARNING shipped chunk(s) still flagged: $($fin.redo -join ',') - see $qcj" } else { Write-Host "[QC] final: all chunks clean" }
}
# Pause gate: VibeVoice emits a noise/ambience burst at turn and sentence onsets (A/B 2026-10-13: 2 s, 47 s);
# fade everything outside whisper words (onset-refined) to -60 dB, then highpass + light afftdn, tempo, loudnorm LAST
$gated = "$base.gated.wav"
$gq = cmd /c "`"$py_w`" `"$root\qc_vv.py`" `"$wav`" `"$json`" --gate `"$gated`" 2>&1" | ForEach-Object { "$_" }
$gk = ($gq | Where-Object { $_ -match 'gate_kept' } | Select-Object -Last 1); if ($gk -match '"gate_kept": \[(\[.+?\])\]') { Write-Host "[gate] kept unrecognised speech-level regions (not muted): $($Matches[1])" }
if (-not (Test-Path $gated)) { Write-Host "[gate] failed, using raw"; $gated = $wav }
Write-Host "[3/3] v1.3 post chain (highpass, presence, de-esser, tempo $Tempo, loudnorm) -> mp3..."
$fl = @("highpass=f=70"); if ($AfftdnNr -gt 0) { $fl += "afftdn=nf=-45:nr=${AfftdnNr}:tn=1" }
if ($Presence -ne 0) { $fl += "equalizer=f=3000:t=o:w=2:g=$Presence" }; if ($DeEss -gt 0) { $fl += "deesser=i=${DeEss}:m=0.5:f=0.5" }
if ($Tempo -ne 1) { $fl += "atempo=$Tempo" }; $fl += "loudnorm=I=-16:TP=-1.5:LRA=11"
ffmpeg -hide_banner -loglevel error -y -i $gated -af ($fl -join ",") -ar 44100 -ac 1 -b:a 128k $Out
if ($LASTEXITCODE) { throw "ffmpeg failed" }
if ($gated -ne $wav) { Remove-Item $gated }
# raw wav + per-chunk wavs are kept (<out>.raw.wav, .raw.wav.chunks\) so glitches can be diagnosed / single chunks redone
$dur = [double](ffprobe -v error -show_entries format=duration -of csv=p=0 $Out)
$words = (Get-Content $json -Raw | ConvertFrom-Json | ForEach-Object { ($_.text -split '\s+' | ? {$_}).Count } | Measure-Object -Sum).Sum
$t = $sw.Elapsed.TotalSeconds
"DONE {0}  audio {1:n1} min, {2} words, {3:n0} wpm, total {4:n1} min ({5:n2} min per audio-min)" -f $Out, ($dur/60), $words, ($words/($dur/60)), ($t/60), ($t/$dur)
} finally { Stop-HwMonitor $hw }
