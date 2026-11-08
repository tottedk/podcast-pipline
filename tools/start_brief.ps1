<#  tools\start_brief.ps1 (v1.14 2026-11-07: preflight checks Carter fixed 0.86 + host mix limit 190 + drama3_directions.json + content_style_v2.6.md; 2026-10-25, technical template v1.12 pipeline, content template v2.3; modelled on tools\start_fd1.ps1 + tools\launcher_lib.ps1) - Episode desk launcher.
Maps one desk brief (briefs\brief_<slug>_<stamp>.json, schema_version 1 or 2; v2 = topic first + optional books, see templates\technical_v1.13.md) onto the real pipeline and renders ONE new episode unattended.
Called by the Episode desk (config.json launcher_cmd):  & 'C:\grok\podcast\tools\start_brief.ps1' -BriefPath {brief_path}
By hand:   powershell -NoProfile -ExecutionPolicy Bypass -File C:\grok\podcast\tools\start_brief.ps1 -BriefPath <brief.json> [-DryRun]
Modes:  (default) = validate brief + archive the previous run folder + register a self-deleting ONE-TIME per-user task PodcastDesk_<stamp> (Interactive, ~40 s from now)
        -FromTask = (the task) preflight, then start the detached -Inner wrapper; the task deletes itself 30 s after start (survives the desk / shell closing)
        -Inner    = the run: brief_gen.py (gemma4: sources -> verified notes -> plan -> script by parts -> fact-check -> PRE-TTS LENGTH GATE -> learn + FLUX prompts)
                    -> split_segments -> cast (pick_cast -Guests) -> md_clean -> vram_free (-Scheduled) -> Drama 3 TTS (render_drama3.ps1, voice-match gate, per-speaker tempo)
                    -> STOP on GENFAIL/SPKFAIL/missing seg -> FLUX -> post_episode.ps1 with the DURATION WINDOW SCALED TO THE BRIEF (40: 2280-2880, 30: 1680-2160, 20: 1080-1440 s)
                    + blocking mix gate 145-175 wpm (host 145-190, v1.14) / pause <= 1.5 s -> final gates -> swap staging into episodes\ (never overwrite) + learn\ / notes\ files + episodes_index (one-off)
                    Any failure: staged files -> episodes\_rejected\<ep>_<stamp>\, nothing published. Cleanup ALWAYS (finally): Ollama models stopped, leftover audiocpp / pipeline python stopped.
        -DryRun   = validate brief + preflight + brief_gen --dry; registers / writes / starts nothing.
Run folder: C:\grok\podcast\deskr\ (STATUS.txt = the desk's status_file, chain.log, gen\). The previous deskr\ is archived to desk_runs\<stamp>_<ep>\ when the next brief starts.
Why the orchestration is inline and not run_episode.ps1: run_episode v1.12 does not pass -MinDur/-MaxDur to post_episode (fixed 38-48 min); v1.13 candidate. Same steps, same order.
Never reboots, no admin, C:\grok\drama3 read-only, banned voices Maya/Declan/Alice/Mary, never Hugh with Carter, Carter always host, never regenerates a finished episode.  #>
param([string]$BriefPath = '', [switch]$DryRun, [switch]$FromTask, [switch]$Inner, [switch]$NoVramFree, [int]$QcRetries = 1, [string]$Root = "C:\grok\podcast")
$ErrorActionPreference = 'Continue'; cd $Root
. "$Root\tools\launcher_lib.ps1"   # Update-EpisodeIndex / Get-PostExitText
$W = "$Root\deskr"; $RejBase = "$Root\episodes\_rejected"; $Arch = "$Root\desk_runs"; $py = "$Root\venv_vv\Scripts\python.exe"; $Engine = 'drama3'
$Flux = if ($env:FLUX_SNAPSHOT) { $env:FLUX_SNAPSHOT } else { Join-Path $env:USERPROFILE '.cache\huggingface\hub\models--unsloth--FLUX.1-schnell\snapshots\9df3faa7ae3b6ddf0b2b69bb78616372897cc65c' }
function St($m) { if (Test-Path $W) { Set-Content "$W\STATUS.txt" "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $m"; Add-Content "$W\chain.log" "$(Get-Date -f 'HH:mm:ss') $m" } else { Write-Host $m } }
function Log($m) { if (Test-Path $W) { Add-Content "$W\chain.log" "$(Get-Date -f 'HH:mm:ss') $m" } else { Write-Host $m } }
function OllamaModels { try { @((Invoke-RestMethod http://localhost:11434/api/ps -TimeoutSec 5).models | % { $_.name }) } catch { @() } }
function Busy { @(Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'run_episode\.ps1|render7b\.ps1|render_drama3\.ps1|post_episode\.ps1|vv7b_generate|drama3_generate|gen_backgrounds|make_video\.py|brief_gen\.py|start_\w+\.ps1 .*-Inner' -and $_.ProcessId -ne $PID -and $_.Name -match 'powershell|python|audiocpp' }) }
function Cleanup($since) {
  foreach ($m in (OllamaModels)) { Log "cleanup: ollama stop $m"; & ollama stop $m 2>&1 | Out-Null }
  Get-Process audiocpp_cli, audiocpp_server -EA 0 | ? { -not $since -or $_.StartTime -ge $since } | % { Log "cleanup: stopping leftover $($_.Name) pid $($_.Id)"; Stop-Process -Id $_.Id -Force -EA 0 }
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.ExecutablePath -like "$Root\venv*" -and (-not $since -or $_.CreationDate -ge $since) } | % { Log "cleanup: stopping leftover python pid $($_.ProcessId) $($_.CommandLine)"; Stop-Process -Id $_.ProcessId -Force -EA 0 }
  Start-Sleep 3; foreach ($m in (OllamaModels)) { & ollama stop $m 2>&1 | Out-Null }
  $ps = (& ollama ps 2>&1 | Out-String).Trim(); Log "cleanup: ollama ps -> $ps"
  "ollama models=$((OllamaModels).Count), audiocpp=$(@(Get-Process audiocpp_cli, audiocpp_server -EA 0).Count), podcast python=$(@(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.ExecutablePath -like "$Root\venv*" }).Count)"
}
function Reject($why, $Stage, $Ep) {
  $sd = "$Root\$Stage"; $files = @(gci $sd -File -EA 0)
  if ($Stage -and $files.Count) { $rd = "$RejBase\${Ep}_$(Get-Date -f yyyyMMdd_HHmm)"; New-Item -ItemType Directory -Force $rd | Out-Null; $files | % { Move-Item $_.FullName $rd -Force }; Log "reject: moved $($files.Count) staged file(s) to $rd"; return "$why - staged files moved to $rd, nothing published" }
  return "$why - nothing staged, nothing published"
}
if (-not $BriefPath -or -not (Test-Path $BriefPath)) { Write-Host "ABORT: -BriefPath missing or not found ($BriefPath)"; exit 2 }
$BriefPath = (Resolve-Path $BriefPath).Path

# ======================= INNER: the run =======================
if ($Inner) {
  $t0 = Get-Date; $res = 'STOP wrapper ended unexpectedly'; $Ep = ''; $Stage = ''
  try {
    (Get-Process -Id $PID).PriorityClass = 'BelowNormal'
    St "wrapper started (pid $PID) brief=$(Split-Path $BriefPath -Leaf) engine=$Engine qcretries=$QcRetries vram_free=$(-not $NoVramFree)"
    for ($i = 0; $i -lt 80 -and (OllamaModels).Count; $i++) { if ($i -eq 0) { St "Ollama busy ($((OllamaModels) -join ',')), waiting up to 20 min" }; Start-Sleep 15 }
    foreach ($m in (OllamaModels)) { St "stopping leftover Ollama model $m"; & ollama stop $m 2>&1 | Out-Null }
    # ---- 1 script + learn materials (gemma4, unloads itself)
    St "step=gen starting brief_gen.py (gemma4:26b-a4b-it-qat)"
    & $py "$Root\tools\brief_gen.py" --brief $BriefPath --work $W --root $Root --books_dir 'C:\grok\books' --books_text "$Root\books_text" *> "$W\gen.log"
    $gx = $LASTEXITCODE; foreach ($m in (OllamaModels)) { & ollama stop $m 2>&1 | Out-Null }
    if ($gx -ne 0) { $why = (gc "$W\STATUS.txt" -Raw -EA 0).Trim(); throw "brief_gen exit $gx ($why) - no TTS" }
    $R = gc "$W\gen\result.json" -Raw -Encoding UTF8 | ConvertFrom-Json
    $Ep = $R.ep; $Title = $R.title; $BgDir = $R.bg_dir; $Suffix = $R.suffix; $Guests = $R.guests; $Cast = $R.cast; $MinDur = [int]$R.min_dur; $MaxDur = [int]$R.max_dur
    $Stage = "episodes\_staging_$Ep"
    if (@(gci "$Root\episodes" -File -EA 0 | ? { $_.Name -like "$Ep.*" }).Count) { throw "episodes\$Ep.* already exists (never regenerate)" }
    $pred = [double]$R.predicted_s; if ($pred -lt $MinDur -or $pred -gt $MaxDur) { throw "pre-TTS length gate: predicted $pred s outside $MinDur-$MaxDur" }
    St "step=gen done: '$Title' ep=$Ep $($R.lines) lines $($R.words) words predicted $([math]::Round($pred/60,1)) min (gate $MinDur-$MaxDur s), $($R.quotes) verified quotes, $($R.factcheck_fixes) fact-check fixes, $($R.gen_minutes) min"
    # ---- 2 split + inputs
    $so = & $py "$Root\tools\split_segments.py" "$W\${Ep}_script.json" "$W\$Ep.chapters.in.json" $W --expect_lines $R.lines --expect_words $R.words 2>&1 | Out-String
    if ($LASTEXITCODE) { throw "split failed: $($so.Trim())" }
    foreach ($f in 'intro.wav', 'sting.wav', 'outro.wav') { Copy-Item "$Root\fd1\$f" "$W\$f" -Force }
    St "split: $(($so.Trim() -split "`n" | select -Last 1))"
    # ---- 3 the v1.12 run_episode chain, inline (identical steps; post_episode gets the scaled duration window)
    $pa = @("$Root\pick_cast.py", '--out', "$W\cast.json", '--host', 'Carter', '--roles', $(if ($Guests -match ',') { 'Guest,Guest2' } else { 'Guest' }), '--guests', $Guests)
    $pl = & $py @pa 2>&1 | Out-String; Add-Content "$W\chain.log" $pl
    if (-not (Test-Path "$W\cast.json")) { throw 'cast pick failed (see chain.log)' }
    $cj = gc "$W\cast.json" -Raw | ConvertFrom-Json
    if ($cj.host -ne 'Carter' -or (@($cj.guest, $cj.guest2) | ? { $_ -in 'Maya','Declan','Alice','Mary','Hugh' })) { throw "cast not allowed: host=$($cj.host) guest=$($cj.guest) guest2=$($cj.guest2)" }
    St "cast: host=$($cj.host) guest=$($cj.guest) guest2=$($cj.guest2) mode=$($cj.mode) warnings=$($cj.warnings -join '; ')"
    foreach ($sj in (gci "$W\seg??.json")) { $mo = & $py "$Root\md_clean.py" $sj.FullName 2>&1 | Out-String; Add-Content "$W\chain.log" $mo.Trim() }
    # pre-TTS script QC (deterministic, no model): strip labels / stage directions / markdown (backup seg??.pre_epqc.json), fail on anything left (e.g. duplicated lines) before any TTS
    $QcNames = (@('Carter') + @($Guests -split ',') + @($cj.guest, $cj.guest2) | ? { $_ -and $_.Trim() } | % { $_.Trim() } | select -Unique) -join ','
    $qo = & $py "$Root\tools\episode_qc.py" pre $W --names $QcNames --fix 2>&1 | Out-String; Add-Content "$W\chain.log" $qo.Trim()
    if ($LASTEXITCODE) { throw "pre-TTS script QC failed (see $W\epqc_pre.json): $(($qo.Trim() -split "`n" | ? { $_ -match '^EPQC' } | select -Last 1))" }
    St "script QC: $(($qo.Trim() -split "`n" | ? { $_ -match '^EPQC' } | select -Last 1))"
    if (-not $NoVramFree) { $vf = 'C:\grok\vram\vram_free.ps1'; if (Test-Path $vf) { $vo = & powershell -NoProfile -ExecutionPolicy Bypass -File $vf -Free -Scheduled 2>&1 | Out-String; Add-Content "$W\chain.log" $vo.Trim() } }
    for ($i = 0; (OllamaModels).Count -and $i -lt 80; $i++) { St 'waiting for Ollama to be empty'; Start-Sleep 15 }
    foreach ($m in (OllamaModels)) { & ollama stop $m 2>&1 | Out-Null }
    St "step=TTS engine=$Engine (render_drama3.ps1) tempo=per-speaker drama3_tempo.json"
    & powershell -ExecutionPolicy Bypass -File "$Root\render_drama3.ps1" -Dir $W -HostVoice Carter -Tempo 0.90 -QcRetries $QcRetries -ChunkWords 100 *> "$W\render.log"
    $rrc = $LASTEXITCODE
    while (Get-Process audiocpp_cli -EA 0) { Start-Sleep 5 }
    $rl = gc "$W\render.log" -EA 0; $bad = @()
    foreach ($sj in (gci "$W\seg??.json" | ? { $_.Name -match '^seg\d\d\.json$' } | sort Name)) { $b = $sj.BaseName
      if (-not (Test-Path "$W\$b.mp3")) { $bad += "$b.mp3 missing" }
      elseif (-not (Test-Path "$W\$b.qc.json")) { $bad += "$b.qc.json missing" }
      else { $qj = gc "$W\$b.qc.json" -Raw | ConvertFrom-Json; if (-not $qj.final) { $bad += "$b not final" }; if (@($qj.voice_redo | ? { $_ -ne $null }).Count) { $bad += "$b wrong voice in chunk(s) $($qj.voice_redo -join ',')" } } }
    $gf = @($rl | sls '^(GENFAIL|SPKFAIL|POSTFAIL)' | % { $_.Line })
    if ($rrc -or $gf.Count -or $bad.Count) { throw "TTS incomplete (render exit $rrc): $((@($gf) + $bad) -join ' | ') - no FLUX, no post" }
    St "step=TTS done $((gc $W\render.log | sls SEGDONE).Count) segs (all segments present, voices ok)"
    $imgs = (gc -Raw "$Root\$BgDir\prompts.json" | ConvertFrom-Json).images.id | ? { -not (Test-Path "$Root\$BgDir\$_.png") }
    if ($imgs) { $env:HIP_VISIBLE_DEVICES = '1'; St "step=FLUX $(@($imgs).Count) images"; $t = Get-Date
      & powershell -ExecutionPolicy Bypass -File "$Root\hwrun.ps1" -Name "flux_$Ep" venv_sd\Scripts\python.exe gen_backgrounds_flux.py "$BgDir\prompts.json" $BgDir --model $Flux --offload staged --fp8 1 *> "$W\flux.log"
      St "step=FLUX done exit $LASTEXITCODE in $([int]((Get-Date)-$t).TotalSeconds) s"; Remove-Item Env:HIP_VISIBLE_DEVICES -EA 0 }
    St "step=post (duration gate $MinDur-$MaxDur s, mix gate on)"
    & powershell -ExecutionPolicy Bypass -File "$Root\post_episode.ps1" -Dir $W -Ep $Ep -Bg "$BgDir\backgrounds.json" -FrameSuffix $Suffix -Title $Title -HostVoice Carter -SegGap 0.4 -StingPad 0 -MinDur $MinDur -MaxDur $MaxDur -OutDir $Stage -OneOff -EngineName 'Fish Audio Drama 3 (Q4_K_S GGUF) via audio.cpp' *> "$W\post.out.txt"
    $pe = $LASTEXITCODE
    foreach ($m in (OllamaModels)) { & ollama stop $m 2>&1 | Out-Null }
    St "step=post exit $pe"
    # ---- 4 final gates + swap
    $dur = 0; $m = (gc "$W\post.log" -EA 0 | sls 'mixed dur ([\d.]+) s' | select -Last 1); if ($m) { $dur = [double]$m.Matches[0].Groups[1].Value }
    if ($pe -eq 0) {
      $g = @()
      if ($dur -lt $MinDur -or $dur -gt $MaxDur) { $g += "duration $dur s outside $MinDur-$MaxDur" }
      foreach ($sj in (gci "$W\seg??.json" | ? { $_.Name -match '^seg\d\d\.json$' })) { $b = $sj.BaseName
        if (-not (Test-Path "$W\$b.mp3")) { $g += "$b.mp3 missing" } else { $qj = gc "$W\$b.qc.json" -Raw | ConvertFrom-Json; if (@($qj.voice_redo | ? { $_ -ne $null }).Count) { $g += "$b voice" }; if (-not $qj.voice_summary) { $g += "$b no voice check" } } }
      if (@(gc "$W\render.log" -EA 0 | sls '^(GENFAIL|SPKFAIL|POSTFAIL)').Count) { $g += 'GENFAIL/SPKFAIL/POSTFAIL in render.log' }
      $gcut = @(gc "$W\render.log" -EA 0 | sls 'GATECUT [1-9]'); if ($gcut.Count) { Log "note: $($gcut.Count) segment(s) fell back to ungated raw audio (GATECUT) - no cut words shipped" }
      # post-TTS episode QC: heard words vs script (repeats >= 15 s, dropped lines, truncated end, extra speech, spoken labels) + script/srt labels; plan per segment in epqc_post.json
      $qp = & $py "$Root\tools\episode_qc.py" post $W --ep $Ep --srt "$Root\$Stage\$Ep.srt" --names $QcNames 2>&1 | Out-String; $qx = $LASTEXITCODE; Add-Content "$W\chain.log" $qp.Trim()
      $ql = ($qp.Trim() -split "`n" | ? { $_ -match '^EPQC' } | select -Last 1)
      if ($qx) { $g += "episode QC (exit $qx, see $W\epqc_post.json): $ql" } else { Log "episode QC: $ql" }
      if (Test-Path "$W\mixqc.txt") { Log "mixqc: $((gc "$W\mixqc.txt" -EA 0 | select -Last 4) -join ' / ')" } else { $g += 'mixqc.txt missing (mix gate not run)' }
      foreach ($x in 'mp3', 'mp4', 'srt', 'json', 'notes.md', 'chapters.txt', 'chapters.json') { if (-not (Test-Path "$Root\$Stage\$Ep.$x")) { $g += "staged $Ep.$x missing" } }
      foreach ($f in @(gci "$Root\$Stage" -File -EA 0)) { if (Test-Path "$Root\episodes\$($f.Name)") { $g += "episodes\$($f.Name) already exists (never overwrite)" } }
      if ($g.Count) { $res = Reject "STOP final gates failed: $($g -join ' | ')" $Stage $Ep }
      else {
        $moved = @(); foreach ($f in @(gci "$Root\$Stage" -File)) { Move-Item $f.FullName "$Root\episodes\"; $moved += $f.Name }
        Log "swap: moved into episodes\: $($moved -join ', ')"; Remove-Item "$Root\$Stage" -EA 0
        $lc = @(); foreach ($f in @(gci "$W\learn" -File -EA 0)) { if (Test-Path "$Root\learn\$($f.Name)") { Log "learn: $($f.Name) exists, kept the old one" } else { Copy-Item $f.FullName "$Root\learn\"; $lc += $f.Name } }
        foreach ($f in @(gci "$W\notes" -File -EA 0)) { if (Test-Path "$Root\notes\$($f.Name)") { Log "notes: $($f.Name) exists, kept the old one" } else { Copy-Item $f.FullName "$Root\notes\"; $lc += "notes\$($f.Name)" } }
        Log "learn/notes copied: $($lc -join ', ')"
        $ro = Update-EpisodeIndex -Py $py -Root $Root -Ep $Ep -Dur $dur -Date (Get-Date -f yyyy-MM-dd) -Cast $Cast -Title $Title -OneOff
        Log "index: $($ro.Trim())"
        $res = "ALL DONE '$Title' ($Ep): post exit 0, mix $([math]::Round($dur/60,1)) min, all gates passed, swapped into episodes\, index: $($ro.Trim())" }
    }
    elseif ($pe -eq 3) { $res = Reject "STOP duration gate failed (mix $dur s, outside $MinDur-$MaxDur s): needs Thomas' decision (see $W\post.log)" $Stage $Ep }
    else { $res = Reject "STOP $(Get-PostExitText $pe) (exit $pe, see post.out.txt / post.log / mixqc.txt)" $Stage $Ep }
  } catch { $res = Reject "STOP $($_.Exception.Message)" $Stage $Ep }
  finally {
    $cl = Cleanup $t0
    St "$res | cleanup: $cl, total $([int]((Get-Date)-$t0).TotalMinutes) min"
  }
  exit 0
}

# ======================= preflight (DryRun + FromTask) =======================
function Preflight {
  $script:bad = @(); $script:ok = @()
  function Chk($c, $m) { if ($c) { $script:ok += $m } else { $script:bad += $m } }
  $need = @('pick_cast.py', 'md_clean.py', 'render_drama3.ps1', 'drama3_generate.py', 'drama3_refs.py', 'post_episode.ps1', 'post_segment.ps1', 'spk_check.py', 'gate_cut_check.py', 'venv_spk\Scripts\python.exe',
    'models\spkrec-ecapa-voxceleb\hyperparams.yaml', 'drama3_tempo.json', 'drama3_ref_map.json', 'drama3_directions.json', 'd3_pace.py', 'episodes_index.py', 'episodes_index.json', 'voices.json', 'voice_f0.json', 'qc_vv.py', 'qc_takes.py', 'qc_mix.py', 'align.py', 'make_video.py',
    'hwrun.ps1', 'gen_backgrounds_flux.py', 'tools\split_segments.py', 'tools\launcher_lib.ps1', 'tools\brief_gen.py', 'tools\research.py', 'templates\cast_bible_v1.json', 'templates\content_style_v2.6.md', 'tools\episode_qc.py', 'fd1\intro.wav', 'fd1\sting.wav', 'fd1\outro.wav', 'empty_glossary.json',
    'venv_vv\Scripts\python.exe', 'venv_whisper\Scripts\python.exe', 'venv_sd\Scripts\python.exe', 'venv_video\Scripts\python.exe', 'drama3_refs\Carter.wav')
  foreach ($f in $need) { Chk (Test-Path "$Root\$f") "exists $f" }
  foreach ($f in 'bin\audiocpp_cli.exe', 'models\drama-3-backbone-8bit-experts-Q4_K_S.gguf') { Chk (Test-Path "C:\grok\drama3\$f") "exists C:\grok\drama3\$f (read-only check)" }
  Chk ((Test-Path 'C:\grok\hwmon\hwmon_lib.ps1') -or (Test-Path "$Root\hwmon_lib.ps1")) 'hwmon_lib.ps1 available'
  Chk ([bool](Get-Command ffmpeg -EA 0) -and [bool](Get-Command ffprobe -EA 0)) 'ffmpeg + ffprobe on PATH'; Chk ([bool](Get-Command ollama -EA 0)) 'ollama on PATH'
  Chk (Test-Path "$Flux\model_index.json") 'FLUX.1-schnell snapshot'
  Chk ((& ollama list 2>&1 | Out-String) -match 'gemma4:26b-a4b-it-qat') 'gemma4:26b-a4b-it-qat installed'
  foreach ($f in 'render_drama3.ps1', 'post_episode.ps1', 'post_segment.ps1', 'tools\launcher_lib.ps1', 'tools\start_brief.ps1') { $e = $null; [void][Management.Automation.Language.Parser]::ParseFile("$Root\$f", [ref]$null, [ref]$e); Chk ($e.Count -eq 0) "PowerShell parse $f" }
  if (-not $NoVramFree) { Chk (Test-Path 'C:\grok\vram\vram_free.ps1') 'vram_free.ps1 exists' }
  $rd = gc "$Root\render_drama3.ps1" -Raw; $pe_ = gc "$Root\post_episode.ps1" -Raw
  Chk ($rd -match 'SpkCheck' -and $rd -match 'SPKFAIL') 'render_drama3: voice-match gate + SPKFAIL stop'
  Chk ($pe_ -match '\[int\]\$MinDur' -and $pe_ -match '\[int\]\$MaxDur' -and $pe_ -match 'never overwrite' -and $pe_ -match 'NoMixGate') 'post_episode: -MinDur/-MaxDur params, never-overwrite guard, mix gate'
  $tc = gc "$Root\drama3_tempo.json" -Raw | ConvertFrom-Json; Chk ($tc.voices.Carter -eq 0.86 -and $tc.min_tempo -eq 0.85 -and $tc.auto) "drama3_tempo: Carter=$($tc.voices.Carter) min=$($tc.min_tempo) auto=$($tc.auto)"
  $qm = gc "$Root\qc_mix.py" -Raw; $pe2 = gc "$Root\post_episode.ps1" -Raw; Chk ($qm -match 'wpm_hi_host' -and $pe2 -match 'WpmHiHost = 190') 'mix gate: host 145-190, guests 145-175 (v1.14, Thomas t62u)'
  $free = [math]::Round((Get-PSDrive C).Free / 1GB); Chk ($free -ge 60) "disk free C: $free GB (need >= 60)"
  $b = Busy; Chk ($b.Count -eq 0) "no pipeline job running ($($b.Count))"
  $o = & $py "$Root\tools\brief_gen.py" --brief $BriefPath --work "$env:TEMP\deskr_dry" --root $Root --books_dir 'C:\grok\books' --books_text "$Root\books_text" --dry 2>&1 | Out-String
  Chk ($LASTEXITCODE -eq 0) "brief valid + sources readable (brief_gen --dry): $(($o -split "`n" | ? { $_ -match 'sources:|ABORT' }) -join ' ')".Trim()
  Remove-Item -Recurse -Force "$env:TEMP\deskr_dry" -EA 0
  return $o
}

# ======================= FROM TASK: preflight + detached inner =======================
if ($FromTask) {
  New-Item -ItemType Directory "$Root\logs", $W -Force | Out-Null; Start-Transcript -Path "$Root\logs\desk_task_$(Get-Date -f yyyyMMdd_HHmmss).log" -Append | Out-Null
  $tn = (gc "$W\task.txt" -EA 0 | select -First 1)
  if ($tn) { Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', "Start-Sleep 30; Unregister-ScheduledTask -TaskName '$tn' -Confirm:`$false *> '$Root\logs\desk_taskdel.log'" }
  St "task $tn started: preflight"
  $null = Preflight
  if ($bad.Count) { St "ABORT preflight at task start: $($bad -join ' | ') | cleanup: $(Cleanup $null)"; Stop-Transcript | Out-Null; exit 1 }
  St "preflight ok ($($ok.Count) checks) | launching detached wrapper"
  $al = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$Root\tools\start_brief.ps1`"", '-Inner', '-BriefPath', "`"$BriefPath`"", '-QcRetries', "$QcRetries"); if ($NoVramFree) { $al += '-NoVramFree' }
  $p = $null; try { $p = Start-Process powershell -ArgumentList $al -WorkingDirectory $Root -WindowStyle Hidden -PassThru -ErrorAction Stop } catch { St "ABORT could not start the wrapper: $($_.Exception.Message)"; Stop-Transcript | Out-Null; exit 1 }
  Log "STARTED detached wrapper pid $($p.Id)"; Stop-Transcript | Out-Null; exit 0
}

# ======================= DEFAULT (the desk): validate + register the one-time task =======================
New-Item -ItemType Directory "$Root\logs" -Force | Out-Null
$lg = "$Root\logs\desk_launch_$(Get-Date -f yyyyMMdd_HHmmss).log"
function L($m) { Add-Content $lg "$(Get-Date -f 'HH:mm:ss') $m"; Write-Host $m }
L "brief: $BriefPath dryrun=$DryRun"
if ($DryRun) {
  $o = Preflight; L ($o.Trim())
  $bad | % { L "  FAIL $_" }; L "--- preflight OK items: $($ok.Count), problems: $($bad.Count)"
  L "DRY RUN: would archive $W (if present), register a one-time task PodcastDesk_<stamp> and render. Nothing registered, written or started."; exit ([int]($bad.Count -gt 0))
}
$b = Busy; if ($b.Count) { L "ABORT: a pipeline job is running ($($b.Count)): $(($b | % { $_.ProcessId }) -join ',')"; if (Test-Path $W) { Add-Content "$W\chain.log" "$(Get-Date -f 'HH:mm:ss') desk brief $(Split-Path $BriefPath -Leaf) REFUSED: pipeline busy" }; exit 3 }
$o = & $py "$Root\tools\brief_gen.py" --brief $BriefPath --work "$env:TEMP\deskr_chk" --root $Root --books_dir 'C:\grok\books' --books_text "$Root\books_text" --dry 2>&1 | Out-String; $bx = $LASTEXITCODE
Remove-Item -Recurse -Force "$env:TEMP\deskr_chk" -EA 0
if ($bx) { L "ABORT brief check: $($o.Trim())"; exit 2 }
if (Test-Path $W) { $old = 'run'; try { $old = (gc "$W\gen\result.json" -Raw | ConvertFrom-Json).ep } catch {}
  $dst = "$Arch\$((gi $W).LastWriteTime.ToString('yyyyMMdd_HHmm'))_$old"; New-Item -ItemType Directory $Arch -Force | Out-Null; Move-Item $W $dst; L "archived previous run folder -> $dst" }
New-Item -ItemType Directory $W -Force | Out-Null
$tn = "PodcastDesk_$(Get-Date -f yyyyMMdd_HHmmss)"; Set-Content "$W\task.txt" $tn; Copy-Item $BriefPath "$W\brief.json"
$arg = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Root\tools\start_brief.ps1`" -BriefPath `"$BriefPath`" -FromTask"
try {
  $act = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arg -WorkingDirectory $Root
  $trg = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(40)
  $pr = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
  $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
  Register-ScheduledTask -TaskName $tn -Action $act -Trigger $trg -Principal $pr -Settings $set -Description "Episode desk one-time run for $(Split-Path $BriefPath -Leaf); deletes itself 30 s after start" -ErrorAction Stop | Out-Null
  St "queued: brief $(Split-Path $BriefPath -Leaf), one-time task $tn starts at $((Get-Date).AddSeconds(40).ToString('HH:mm:ss'))"; L "registered $tn"
} catch { St "ABORT could not register task $tn : $($_.Exception.Message)"; L "ABORT register: $($_.Exception.Message)"; exit 4 }
exit 0
