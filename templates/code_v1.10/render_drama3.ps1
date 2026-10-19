<#  render_drama3.ps1 (template v1.9, 2026-10-19; v1.10: DEFAULT engine, tempo 1.05) - TTS+QC driver: Fish Audio Drama 3 Q4_K_S GGUF (audio.cpp v0.9.2-drama3-base-small, Vulkan) -> QC after every take -> best take -> final QC -> post_segment.ps1.
Same interface and outputs as render7b.ps1 (segNN.raw.wav + .chunks\cNNN.wav/chunks.json at 24 kHz, segNN.qc.json, segNN.mp3, STATUS.txt, SEGDONE/ALLDONE lines), so run_episode.ps1 / post_episode.ps1 / qc_vv.py / qc_takes.py / align.py work unchanged.
DEFAULT engine since v1.10 (run_episode.ps1 -Engine drama3, default tempo 1.05 ~155 wpm; -Engine 7b = VibeVoice-7B fallback, tempo 0.93). Generator = drama3_generate.py; clone refs = drama3_refs.py (voices.json refs, cut <= 20 s, whisper transcript, cached in <Root>\drama3_refs\).
Drama 3 specifics: -ChunkWords default 150 (3 refs + text must fit context 4096); -Cfg/-Steps accepted but ignored; [sighs]/[laughs]/[whispers] tags are performed, not spoken, and are stripped from the QC texts.
GPU hygiene: waits until Ollama is empty AND no other audiocpp_cli runs before each TTS call (one GPU model at a time); the CLI exits after each call (model unloaded); a leftover Drama 3 audiocpp_cli is killed in finally. No -Pin (pin_experts needs ~17 GB extra RAM).
Usage: .\render_drama3.ps1 -Dir ui1 [-Segs 00,01,...] [-HostVoice Carter] [-GuestVoice X -Guest2Voice Y] (default: <Dir>\cast.json) [-Tempo 1.05] [-ChunkWords 150] [-QcRetries 1] [-D3Home C:\grok\drama3]  #>
param([string]$Dir, [string[]]$Segs = @(), [string]$HostVoice = "Carter", [string]$GuestVoice = "", [string]$Guest2Voice = "",
  [double]$Tempo = 1.05, [int]$ChunkWords = 150, [int]$QcRetries = 1, [int[]]$Seeds = @(42,1988,3042,4096), [string]$Glossary = "",
  [double]$Cfg = 1.3, [int]$Steps = 10, [double]$AfftdnNr = 0, [switch]$NoResume, [string]$Root = "C:\grok\podcast",
  [string]$D3Home = "C:\grok\drama3", [int]$CacheSize = 8, [int]$CtxLen = 4096)
$ErrorActionPreference = 'Continue'; (Get-Process -Id $PID).PriorityClass = 'Idle'
cd $Root; $W = if ([IO.Path]::IsPathRooted($Dir)) { $Dir } else { Join-Path $Root $Dir }
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$hl = 'C:\grok\hwmon\hwmon_lib.ps1'; if (-not (Test-Path $hl)) { $hl = "$Root\hwmon_lib.ps1" }  # v1.3: own LibreHardwareMonitor monitor, falls back to HWiNFO
. $hl; $hw = Start-HwMonitor ("render_drama3_" + (Split-Path $W -Leaf))
$py_w = "$Root\venv_whisper\Scripts\python.exe"; $py_t = "$Root\venv_vv\Scripts\python.exe"
if (-not $GuestVoice -and (Test-Path "$W\cast.json")) { $cj = gc "$W\cast.json" -Raw | ConvertFrom-Json; $HostVoice = $cj.host; $GuestVoice = $cj.guest; $Guest2Voice = $cj.guest2 }   # v1.3: cast from pick_cast.py
if (-not $GuestVoice) { throw "No cast: pass -GuestVoice [-Guest2Voice] or create $W\cast.json with pick_cast.py (no default cast in v1.3)" }
if (-not $Glossary) { $Glossary = "$Root\empty_glossary.json" }     # v1.3: no respellings by default
$tpl = Split-Path $MyInvocation.MyCommand.Path
$gen = "`"$py_t`" `"$(if (Test-Path "$Root\drama3_generate.py") { "$Root\drama3_generate.py" } else { "$tpl\drama3_generate.py" })`""
function Tool($n) { if (Test-Path "$Root\$n") { "$Root\$n" } else { "$tpl\$n" } }
$d3x = " --cli `"$D3Home\bin\audiocpp_cli.exe`" --model `"$D3Home\models\drama-3-backbone-8bit-experts-Q4_K_S.gguf`" --cache_size $CacheSize --ctx $CtxLen"
function WaitGpu { while ($true) { $om = ((Invoke-RestMethod http://localhost:11434/api/ps -EA SilentlyContinue).models); $ac = Get-Process audiocpp_cli, audiocpp_server -EA 0
    if (-not $om.Count -and -not $ac) { break }; "GPU busy (ollama=$($om.Count) audiocpp=$(@($ac).Count)), waiting"; St "waiting for Ollama/audiocpp to be idle"; Start-Sleep 15 } }
if (-not $Segs.Count) { $Segs = (gci "$W\seg??.json" | % { $_.BaseName.Substring(3) } | sort) }
function St($m) { Set-Content "$W\STATUS.txt" "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $m" }
try {
$rv = (@($HostVoice, $GuestVoice, $Guest2Voice) | ? { $_ }) -join ','
$ro = cmd /c "`"$py_w`" `"$(Tool 'drama3_refs.py')`" --voices $rv --root `"$Root`" 2>&1" | % { "$_" }; $ro | ? { $_ -match '^REF|Error' }
if ($LASTEXITCODE) { throw "drama3_refs.py failed: $($ro -join ' / ')" }
foreach ($s in $Segs) {
  $json = "$W\seg$s.json"; $wav = "$W\seg$s.raw.wav"; $Out = "$W\seg$s.mp3"; $chunks = "$wav.chunks"; $qcj = "$W\seg$s.qc.json"
  if (-not $NoResume -and (Test-Path $Out) -and (Test-Path $qcj)) { "=== seg$s already done, skipped"; continue }
  $t0 = Get-Date; "=== seg$s $(Get-Date -f HH:mm:ss)"; St "step=TTS seg$s of $($Segs[0])-$($Segs[-1])"
  WaitGpu
  $g2 = if ($Guest2Voice) { " --guest2 $Guest2Voice" } else { "" }
  $ga = "--host $HostVoice --guest $GuestVoice$g2 --chunk_words $ChunkWords --glossary `"$Glossary`"$d3x"
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
    WaitGpu; cmd /c "$gen `"$json`" `"$wav`" $ga --redo $spec 2>&1" | % { "$_" }
  }
  $pick = cmd /c "`"$py_t`" `"$Root\qc_takes.py`" pick `"$chunks`" `"$wav`" 2>&1" | % { "$_" }; $pick
  if ($pick | ? { $_ -match '^CHANGED' }) { $q = cmd /c "`"$py_w`" `"$Root\qc_vv.py`" `"$wav`" `"$json`" $qa --json `"$qcj`" 2>&1" | % { "$_" }; $q | ? { $_ -match '^chunk \d+ seed' } | % { "final $_" } }
  $fin = gc $qcj -Raw | ConvertFrom-Json; $fin | Add-Member -NotePropertyName final -NotePropertyValue $true -Force; $fin | ConvertTo-Json -Depth 8 | Set-Content -Encoding ascii $qcj
  if ($fin.redo) { "[QC] WARNING shipped chunk(s) still flagged (hard flags): $($fin.redo -join ',')" } else { "[QC] final: no hard flags" }
  St "step=post seg$s"
  & "$tpl\post_segment.ps1" -Raw $wav -Script $json -Out $Out -Tempo $Tempo -AfftdnNr $AfftdnNr -Root $Root
  "SEGDONE seg$s dur $(ffprobe -v error -show_entries format=duration -of csv=p=0 $Out) s in $([int]((Get-Date)-$t0).TotalSeconds) s"
}
} finally { if ($hw) { Stop-HwMonitor $hw }
  Get-Process audiocpp_cli -EA 0 | ? { $_.Path -like "$D3Home*" } | % { "killing leftover Drama 3 audiocpp_cli pid $($_.Id)"; Stop-Process -Id $_.Id -Force } }
"ALLDONE $(Get-Date -f HH:mm:ss)"

