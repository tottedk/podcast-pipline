<#  render7b.ps1 (template v1.3, 2026-10-15) - DEFAULT TTS+QC driver: VibeVoice-7B Q8 GGUF (audio.cpp, Vulkan) -> QC after every take -> best take -> final QC -> post_segment.ps1.
Per segment: vv7b_generate.py (seed 42) -> qc_vv.py -> qc_takes.py record -> retry flagged chunks with the next seed (up to -QcRetries; f0_drift and noise are SOFT and never retry alone (v1.7)) -> qc_takes pick -> re-QC if best take != last -> post_segment.ps1.
Run DETACHED (Start-Process ... -WindowStyle Hidden) and poll <Dir>\STATUS.txt - foreground runs die when the tool session is interrupted. Segments that already have a finished mp3 are skipped (-Resume, default).
Usage: .\render7b.ps1 -Dir ui1 [-Segs 00,01,...] [-HostVoice Carter] [-GuestVoice X -Guest2Voice Y]  (guests default to <Dir>\cast.json written by pick_cast.py / run_episode.ps1; there is NO default cast) [-Tempo 0.93] [-ChunkWords 275] [-QcRetries 2]   (inputs: <Dir>\segNN.json)  #>
param([string]$Dir, [string[]]$Segs = @(), [string]$HostVoice = "Carter", [string]$GuestVoice = "", [string]$Guest2Voice = "",
  [double]$Tempo = 0.93, [int]$ChunkWords = 275, [int]$QcRetries = 2, [int[]]$Seeds = @(42,1988,3042,4096), [string]$Glossary = "",
  [double]$Cfg = 1.3, [int]$Steps = 10, [double]$AfftdnNr = 0, [switch]$NoResume, [string]$Root = "C:\grok\podcast")
$ErrorActionPreference = 'Continue'; (Get-Process -Id $PID).PriorityClass = 'Idle'
cd $Root; $W = if ([IO.Path]::IsPathRooted($Dir)) { $Dir } else { Join-Path $Root $Dir }
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$hl = 'C:\grok\hwmon\hwmon_lib.ps1'; if (-not (Test-Path $hl)) { $hl = "$Root\hwmon_lib.ps1" }  # v1.3: own LibreHardwareMonitor monitor, falls back to HWiNFO
. $hl; $hw = Start-HwMonitor ("render7b_" + (Split-Path $W -Leaf))
$py_w = "$Root\venv_whisper\Scripts\python.exe"; $py_t = "$Root\venv_vv\Scripts\python.exe"
if (-not $GuestVoice -and (Test-Path "$W\cast.json")) { $cj = gc "$W\cast.json" -Raw | ConvertFrom-Json; $HostVoice = $cj.host; $GuestVoice = $cj.guest; $Guest2Voice = $cj.guest2 }   # v1.3: cast from pick_cast.py
if (-not $GuestVoice) { throw "No cast: pass -GuestVoice [-Guest2Voice] or create $W\cast.json with pick_cast.py (no default cast in v1.3)" }
if (-not $Glossary) { $Glossary = "$Root\empty_glossary.json" }     # v1.3: no respellings by default
$tpl = Split-Path $MyInvocation.MyCommand.Path
$gen = "`"$py_t`" `"$(if (Test-Path "$Root\vv7b_generate.py") { "$Root\vv7b_generate.py" } else { "$tpl\vv7b_generate.py" })`""
if (-not $Segs.Count) { $Segs = (gci "$W\seg??.json" | % { $_.BaseName.Substring(3) } | sort) }
function St($m) { Set-Content "$W\STATUS.txt" "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $m" }
try {
foreach ($s in $Segs) {
  $json = "$W\seg$s.json"; $wav = "$W\seg$s.raw.wav"; $Out = "$W\seg$s.mp3"; $chunks = "$wav.chunks"; $qcj = "$W\seg$s.qc.json"
  if (-not $NoResume -and (Test-Path $Out) -and (Test-Path $qcj)) { "=== seg$s already done, skipped"; continue }
  $t0 = Get-Date; "=== seg$s $(Get-Date -f HH:mm:ss)"; St "step=TTS seg$s of $($Segs[0])-$($Segs[-1])"
  while (((Invoke-RestMethod http://localhost:11434/api/ps -EA SilentlyContinue).models).Count -gt 0) { "ollama busy, waiting"; St "waiting for Ollama to be empty"; Start-Sleep 15 }
  $g2 = if ($Guest2Voice) { " --guest2 $Guest2Voice" } else { "" }
  $ga = "--host $HostVoice --guest $GuestVoice$g2 --cfg $Cfg --steps $Steps --chunk_words $ChunkWords --glossary `"$Glossary`""
  cmd /c "$gen `"$json`" `"$wav`" $ga --seed $($Seeds[0]) 2>&1" | % { "$_" }
  if (-not (Test-Path $wav)) { "GENFAIL seg$s"; continue }
  $qa = "--chunks `"$chunks`" --host $HostVoice --guest $GuestVoice$g2 --glossary `"$Glossary`""
  if (Test-Path "$chunks\takes") { Remove-Item -Recurse -Force "$chunks\takes" }
  for ($r = 0; $r -le $QcRetries; $r++) {
    $q = cmd /c "`"$py_w`" `"$Root\qc_vv.py`" `"$wav`" `"$json`" $qa --json `"$qcj`" 2>&1" | % { "$_" }
    $q | ? { $_ -match '^chunk \d+ seed' }
    cmd /c "`"$py_t`" `"$Root\qc_takes.py`" record `"$chunks`" `"$qcj`" $r 2>&1" | % { "$_" } | ? { $_ -match 'recorded|Error|Traceback' }
    $redo = ($q | ? { $_ -match '^REDO' } | select -Last 1) -replace '^REDO\s*', ''
    if (-not $redo) { "[QC] pass $r ok"; break }
    if ($r -eq $QcRetries) { "[QC] pass $r still flagged: $redo (retries exhausted)"; break }
    $spec = ($redo -split ',' | % { "${_}:$($Seeds[$r+1])" }) -join ','
    "[QC] pass $r flagged chunk(s) $redo -> regenerate $spec"; St "step=TTS seg$s retry $spec"
    cmd /c "$gen `"$json`" `"$wav`" $ga --redo $spec 2>&1" | % { "$_" }
  }
  $pick = cmd /c "`"$py_t`" `"$Root\qc_takes.py`" pick `"$chunks`" `"$wav`" 2>&1" | % { "$_" }; $pick
  if ($pick | ? { $_ -match '^CHANGED' }) { $q = cmd /c "`"$py_w`" `"$Root\qc_vv.py`" `"$wav`" `"$json`" $qa --json `"$qcj`" 2>&1" | % { "$_" }; $q | ? { $_ -match '^chunk \d+ seed' } | % { "final $_" } }
  $fin = gc $qcj -Raw | ConvertFrom-Json; $fin | Add-Member -NotePropertyName final -NotePropertyValue $true -Force; $fin | ConvertTo-Json -Depth 8 | Set-Content -Encoding ascii $qcj
  if ($fin.redo) { "[QC] WARNING shipped chunk(s) still flagged (hard flags): $($fin.redo -join ',')" } else { "[QC] final: no hard flags" }
  St "step=post seg$s"
  & "$tpl\post_segment.ps1" -Raw $wav -Script $json -Out $Out -Tempo $Tempo -AfftdnNr $AfftdnNr -Root $Root
  "SEGDONE seg$s dur $(ffprobe -v error -show_entries format=duration -of csv=p=0 $Out) s in $([int]((Get-Date)-$t0).TotalSeconds) s"
}
} finally { if ($hw) { Stop-HwMonitor $hw } }
"ALLDONE $(Get-Date -f HH:mm:ss)"

