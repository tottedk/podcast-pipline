<#  render_drama3.ps1 (template v1.12, 2026-10-21; was v1.11/v1.9/v1.10) - TTS+QC driver: Fish Audio Drama 3 Q4_K_S GGUF (audio.cpp v0.9.2-drama3-base-small, Vulkan) -> QC + VOICE-MATCH GATE after every take -> best take -> final QC -> post_segment.ps1.
Same interface and outputs as render7b.ps1 (segNN.raw.wav + .chunks\cNNN.wav/chunks.json at 24 kHz, segNN.qc.json, segNN.mp3, STATUS.txt, SEGDONE/ALLDONE lines).
v1.11 (Fault Lines #1 root causes, fl1\analysis\ANALYSIS.md):
  - drama3_generate.py --mode turn: ONE speaker (one reference) per Drama 3 request (multi-reference requests voiced 54/83 non-first-reference lines with reference 0).
  - default -Tempo 0.90 (Drama 3 speaks ~172 wpm raw; 0.90 -> ~155 wpm; 1.05 gave 181 wpm / 35:17), default -ChunkWords 100 (seg07 runaway/OOM at 150).
  - runaway guard in the generator (max_frames 512 per text chunk; crashed/limit-hit/implausible chunks regenerated with another seed, -GenRetries 2).
  - VOICE-MATCH GATE (spk_check.py, ECAPA, venv_spk): after every QC pass; wrong-voice chunks are regenerated (-SpkRetries 2, next seeds) and get score +1000
    so the best-take pick never ships them; if a wrong voice survives the retries -> SPKFAIL, STATUS 'STOP voice mismatch', exit 5 (nothing shipped).
  - GENFAIL (no audio) -> STATUS 'STOP GENFAIL', exit 4 immediately (no further segments; run_episode stops before FLUX/post).
  - qc_vv.py v2.3: hard flag end_missing (cut-off line ending) -> retry; gate never mutes speech-level audio. post_segment.ps1 v1.11 checks raw vs gated (GATECUT).
v1.12 (fl1b\analysis\TEMPO_PAUSES.md): PER-SPEAKER TEMPO applied per chunk inside drama3_generate.py (-TempoCfg drama3_tempo.json: fixed map by
  reference name + auto-calibration to target_wpm for unmapped refs, clamp 0.85-1.10, locked per run in <Dir>\drama3_tempo_lock.json) -> post_segment.ps1
  runs with -Tempo 1. -Tempo = fallback tempo for refs the config cannot place. -GlobalTempo = v1.11 behaviour (one atempo for the whole segment in post).
  Pause clamp v2: silence = -SilRelDb (20) dB below the chunk speech level, internal pauses > -MaxPause 0.4 s -> -KeepPause 0.4 s (final-tempo seconds).
  -RefMap drama3_ref_map.json (voice -> versioned reference, e.g. Elliot -> Elliot_v2) is passed to drama3_refs.py, the generator and spk_check.py.
GPU hygiene: waits until Ollama is empty AND no other audiocpp_cli runs before each TTS call; the CLI exits after each call (model unloaded); leftovers killed in finally.
Usage: .\render_drama3.ps1 -Dir ui1 [-Segs 00,01,...] [-Tempo 0.90] [-TempoCfg f.json] [-RefMap f.json] [-GlobalTempo] [-MaxPause 0.4] [-ChunkWords 100] [-QcRetries 1] [-SpkRetries 2] [-Mode turn|multi] [-NoSpkCheck] [-D3Home C:\grok\drama3]  #>
param([string]$Dir, [string[]]$Segs = @(), [string]$HostVoice = "Carter", [string]$GuestVoice = "", [string]$Guest2Voice = "",
  [double]$Tempo = 0.90, [int]$ChunkWords = 100, [int]$QcRetries = 1, [int]$SpkRetries = 2, [int]$GenRetries = 2, [int[]]$Seeds = @(42,1988,3042,4096), [string]$Glossary = "",
  [ValidateSet("turn","multi")][string]$Mode = "turn", [switch]$NoSpkCheck,
  [double]$Cfg = 1.3, [int]$Steps = 10, [double]$AfftdnNr = 0, [switch]$NoResume, [string]$Root = "C:\grok\podcast",
  [string]$D3Home = "C:\grok\drama3", [int]$CacheSize = 8, [int]$CtxLen = 4096,
  [string]$TempoCfg = "", [string]$RefMap = "", [switch]$GlobalTempo, [double]$MaxPause = 0.4, [double]$KeepPause = 0.4, [double]$SilRelDb = 20)
$ErrorActionPreference = 'Continue'; (Get-Process -Id $PID).PriorityClass = 'Idle'
cd $Root; $W = if ([IO.Path]::IsPathRooted($Dir)) { $Dir } else { Join-Path $Root $Dir }
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$hl = 'C:\grok\hwmon\hwmon_lib.ps1'; if (-not (Test-Path $hl)) { $hl = "$Root\hwmon_lib.ps1" }
. $hl; $hw = Start-HwMonitor ("render_drama3_" + (Split-Path $W -Leaf))
$py_w = "$Root\venv_whisper\Scripts\python.exe"; $py_t = "$Root\venv_vv\Scripts\python.exe"; $py_s = "$Root\venv_spk\Scripts\python.exe"
if (-not $GuestVoice -and (Test-Path "$W\cast.json")) { $cj = gc "$W\cast.json" -Raw | ConvertFrom-Json; $HostVoice = $cj.host; $GuestVoice = $cj.guest; $Guest2Voice = $cj.guest2 }
if (-not $GuestVoice) { throw "No cast: pass -GuestVoice [-Guest2Voice] or create $W\cast.json with pick_cast.py (no default cast in v1.3)" }
if (-not $Glossary) { $Glossary = "$Root\empty_glossary.json" }
if (-not $NoSpkCheck -and -not (Test-Path $py_s)) { throw "voice-match gate needs $py_s (venv_spk with speechbrain); use -NoSpkCheck only for experiments" }
$tpl = Split-Path $MyInvocation.MyCommand.Path
function Tool($n) { if (Test-Path "$Root\$n") { "$Root\$n" } else { "$tpl\$n" } }
$gen = "`"$py_t`" `"$(Tool 'drama3_generate.py')`""
if (-not $TempoCfg) { $TempoCfg = Tool 'drama3_tempo.json' }; if (-not $RefMap) { $RefMap = Tool 'drama3_ref_map.json' }
$tmx = if ($GlobalTempo) { " --tempo_mode off --tempo $Tempo" } else { " --tempo_mode cfg --tempo_cfg `"$TempoCfg`" --tempo $Tempo" }
$postTempo = if ($GlobalTempo) { $Tempo } else { 1 }   # v1.12: the generator already stretched every chunk to its speaker's tempo
"v1.12 tempo: $(if ($GlobalTempo) { "GLOBAL $Tempo in post (v1.11 mode)" } else { "per speaker ($TempoCfg), fallback $Tempo, post -Tempo 1" }); refmap $RefMap; clamp >$MaxPause s -> $KeepPause s at -$SilRelDb dB"
$d3x = " --ref_map `"$RefMap`" --max_pause $MaxPause --keep_pause $KeepPause --sil_rel_db $SilRelDb$tmx --cli `"$D3Home\bin\audiocpp_cli.exe`" --model `"$D3Home\models\drama-3-backbone-8bit-experts-Q4_K_S.gguf`" --cache_size $CacheSize --ctx $CtxLen --mode $Mode --gen_retries $GenRetries"
function St($m) { Set-Content "$W\STATUS.txt" "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $m" }
function WaitGpu { while ($true) { $om = ((Invoke-RestMethod http://localhost:11434/api/ps -EA SilentlyContinue).models); $ac = Get-Process audiocpp_cli, audiocpp_server -EA 0
    if (-not $om.Count -and -not $ac) { break }; "GPU busy (ollama=$($om.Count) audiocpp=$(@($ac).Count)), waiting"; St "waiting for Ollama/audiocpp to be idle"; Start-Sleep 15 } }
if (-not $Segs.Count) { $Segs = (gci "$W\seg??.json" | % { $_.BaseName.Substring(3) } | sort) }
$castArg = "Host=$HostVoice,Guest=$GuestVoice" + $(if ($Guest2Voice) { ",Guest2=$Guest2Voice" } else { "" })
function SpkCheck($chunks, $qcj, $tag) {   # v1.11 voice-match gate: merges into qc json (flag 'voice', score +1000, redo); returns failing chunk list
  if ($NoSpkCheck) { return @() }
  $o = cmd /c "`"$py_s`" `"$(Tool 'spk_check.py')`" --chunks `"$chunks`" --cast $castArg --ref_map `"$RefMap`" --qc `"$qcj`" --root `"$Root`" --json `"$chunks\spk_$tag.json`" 2>&1" | % { "$_" }
  $o | ? { $_ -match '^SPK .*FAIL|^SPKSUMMARY|Error|Traceback' } | % { Write-Host "[VOICE] $_" }   # Write-Host: the function's output is its return value
  if (-not ($o | ? { $_ -match '^SPKSUMMARY' })) { Write-Host "[VOICE] spk_check.py failed: $(($o | select -Last 3) -join ' / ')"; return @(-1) }
  $r = (($o | ? { $_ -match '^SPKREDO' } | select -Last 1) -replace '^SPKREDO\s*', '').Trim()
  if ($r) { return @($r -split ',' | % { [int]$_ }) } else { return @() } }
$rc = 0
try {
$rv = (@($HostVoice, $GuestVoice, $Guest2Voice) | ? { $_ }) -join ','
$ro = cmd /c "`"$py_w`" `"$(Tool 'drama3_refs.py')`" --voices $rv --root `"$Root`" --ref_map `"$RefMap`" 2>&1" | % { "$_" }; $ro | ? { $_ -match '^REF|Error' }
if ($LASTEXITCODE) { throw "drama3_refs.py failed: $($ro -join ' / ')" }
foreach ($s in $Segs) {
  $json = "$W\seg$s.json"; $wav = "$W\seg$s.raw.wav"; $Out = "$W\seg$s.mp3"; $chunks = "$wav.chunks"; $qcj = "$W\seg$s.qc.json"
  if (-not $NoResume -and (Test-Path $Out) -and (Test-Path $qcj)) { "=== seg$s already done, skipped"; continue }
  $t0 = Get-Date; "=== seg$s $(Get-Date -f HH:mm:ss)"; St "step=TTS seg$s of $($Segs[0])-$($Segs[-1])"
  WaitGpu
  $g2 = if ($Guest2Voice) { " --guest2 $Guest2Voice" } else { "" }
  $ga = "--host $HostVoice --guest $GuestVoice$g2 --chunk_words $ChunkWords --glossary `"$Glossary`"$d3x"
  if (Test-Path $wav) { Remove-Item $wav -Force }
  cmd /c "$gen `"$json`" `"$wav`" $ga --seed $($Seeds[0]) 2>&1" | % { "$_" }
  if (-not (Test-Path $wav)) { "GENFAIL seg$s"; St "STOP GENFAIL seg$s (no audio after generator retries) - chain must stop, nothing shipped"; $rc = 4; break }
  $qa = "--chunks `"$chunks`" --host $HostVoice --guest $GuestVoice$g2 --glossary `"$Glossary`""
  if (Test-Path "$chunks\takes") { Remove-Item -Recurse -Force "$chunks\takes" }
  $maxPass = [Math]::Max($QcRetries, $SpkRetries)
  for ($r = 0; $r -le $maxPass; $r++) {
    $q = cmd /c "`"$py_w`" `"$(Tool 'qc_vv.py')`" `"$wav`" `"$json`" $qa --json `"$qcj`" 2>&1" | % { "$_" }
    $q | ? { $_ -match '^chunk \d+ seed' }
    $qredo = @((($q | ? { $_ -match '^REDO' } | select -Last 1) -replace '^REDO\s*', '').Trim() -split ',' | ? { $_ } | % { [int]$_ })
    $vredo = @(SpkCheck $chunks $qcj "p$r")
    if ($vredo -contains -1) { "SPKFAIL seg$s (voice gate could not run)"; St "STOP voice gate error seg$s (spk_check.py) - nothing shipped"; $rc = 5; break }
    cmd /c "`"$py_t`" `"$(Tool 'qc_takes.py')`" record `"$chunks`" `"$qcj`" $r 2>&1" | % { "$_" } | ? { $_ -match 'recorded|Error|Traceback' }
    $redo = @(); if ($r -lt $QcRetries) { $redo += $qredo }; if ($r -lt $SpkRetries) { $redo += $vredo }
    $redo = @($redo | sort -Unique)
    if (-not $qredo.Count -and -not $vredo.Count) { "[QC] pass $r ok (voices ok)"; break }
    if (-not $redo.Count) { "[QC] pass $r still flagged: qc=$($qredo -join ',') voice=$($vredo -join ',') (retries exhausted)"; break }
    if ($r + 1 -ge $Seeds.Count) { "[QC] no more seeds"; break }
    $spec = ($redo | % { "${_}:$($Seeds[$r+1])" }) -join ','
    "[QC] pass $r flagged qc=$($qredo -join ',') voice=$($vredo -join ',') -> regenerate $spec"; St "step=TTS seg$s retry $spec"
    WaitGpu; cmd /c "$gen `"$json`" `"$wav`" $ga --redo $spec 2>&1" | % { "$_" }
    if ($LASTEXITCODE) { "GENFAIL seg$s (retry $spec)"; St "STOP GENFAIL seg$s retry $spec - nothing shipped"; $rc = 4; break }
  }
  if ($rc) { break }
  $pick = cmd /c "`"$py_t`" `"$(Tool 'qc_takes.py')`" pick `"$chunks`" `"$wav`" 2>&1" | % { "$_" }; $pick
  if ($pick | ? { $_ -match '^CHANGED \d' }) { $q = cmd /c "`"$py_w`" `"$(Tool 'qc_vv.py')`" `"$wav`" `"$json`" $qa --json `"$qcj`" 2>&1" | % { "$_" }; $q | ? { $_ -match '^chunk \d+ seed' } | % { "final $_" }
    $null = SpkCheck $chunks $qcj "final" }
  $fin = gc $qcj -Raw | ConvertFrom-Json; $fin | Add-Member -NotePropertyName final -NotePropertyValue $true -Force; $fin | ConvertTo-Json -Depth 10 | Set-Content -Encoding ascii $qcj
  if ($fin.redo) { "[QC] WARNING shipped chunk(s) still flagged (hard flags): $($fin.redo -join ',')" } else { "[QC] final: no hard flags" }
  $vr = @($fin.voice_redo | ? { $_ -ne $null })
  if (-not $NoSpkCheck -and $vr.Count) { "SPKFAIL seg$s chunk(s) $($vr -join ',') still in the wrong voice after $SpkRetries retries"
    St "STOP voice mismatch seg$s chunk(s) $($vr -join ',') after $SpkRetries retries - nothing shipped (see seg$s.qc.json voice)"; $rc = 5; break }
  St "step=post seg$s"
  & "$(Split-Path (Tool 'post_segment.ps1'))\post_segment.ps1" -Raw $wav -Script $json -Out $Out -Tempo $postTempo -AfftdnNr $AfftdnNr -Root $Root
  if (-not (Test-Path $Out)) { "POSTFAIL seg$s"; St "STOP post_segment failed seg$s"; $rc = 6; break }
  "SEGDONE seg$s dur $(ffprobe -v error -show_entries format=duration -of csv=p=0 $Out) s in $([int]((Get-Date)-$t0).TotalSeconds) s"
}
} finally { if ($hw) { Stop-HwMonitor $hw }
  Get-Process audiocpp_cli -EA 0 | ? { $_.Path -like "$D3Home*" } | % { "killing leftover Drama 3 audiocpp_cli pid $($_.Id)"; Stop-Process -Id $_.Id -Force } }
if ($rc) { "STOPPED rc=$rc $(Get-Date -f HH:mm:ss)"; exit $rc }
"ALLDONE $(Get-Date -f HH:mm:ss)"
