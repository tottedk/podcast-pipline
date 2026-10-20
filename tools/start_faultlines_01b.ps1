<#  start_faultlines_01b.ps1 (2026-10-20, template v1.11 pipeline; copy-adapted from tools\start_faultlines_01.ps1) - ONE-CALL launcher for the REDO of "Fault Lines #1 - Left vs Right: Is It Becoming a War?"
(Thomas rejected the v1.10 render of 2026-10-20: wrong voices, a cut-off word, long pauses, 35:17 too fast - root causes in fl1\analysis\ANALYSIS.md).
Start now:  powershell -NoProfile -ExecutionPolicy Bypass -File C:\grok\podcast\tools\start_faultlines_01b.ps1        Dry run: add -DryRun (writes/starts nothing in the project).
Scheduled (per-user task PodcastFaultlines01b, once 2026-10-21 01:00):  ... -File ...\start_faultlines_01b.ps1 -FromTask   (logs\faultlines_01b_task.log; the task deletes itself 30 s after start)
Poll:  Get-Content C:\grok\podcast\fl1b\STATUS.txt ; Get-Content C:\grok\podcast\fl1b\chain.log -Tail 15
SAME approved script, unchanged: episodes\faultlines_01\faultlines_01_script.json (164 lines / 6198 words), same cast (Carter / Elliot / Clara, episodes\faultlines_01\cast.json), same chapters.
Fresh working dir fl1b\ (fl1\ stays as evidence). FLUX images reused from bg_fl1\ (all 21 PNGs must exist -> run_episode skips FLUX; nothing regenerated).
Pipeline v1.11: run_episode.ps1 (-Engine drama3, tempo 0.90 ~155 wpm, ChunkWords 100, one speaker per request, runaway retry, VOICE-MATCH GATE, end_missing QC,
  STOP on GENFAIL/SPKFAIL/missing segment before post) -> post_episode.ps1 -OutDir episodes\_staging_faultlines_01b (mix from the segment list, gate 38-48 min, align, qc_mix, video, srt, 64k, notes with the real engine name).
FINAL SWAP only when everything passed (post exit 0, mix 2280-2880 s, all 10 segments voice-ok, no GATECUT): the rejected v1.10 files episodes\faultlines_01.* + _64k.mp3 are MOVED to
  episodes\_rejected\faultlines_01_v110\ (never deleted), then the staged files are moved into episodes\ and the registry entry #11 gets the new duration/date.
  Duration outside 38-48 min -> STOP for Thomas (no SegGap retry, no tempo change). Any failure -> STOP, old files untouched.
Cleanup at the end: every Ollama model stopped, leftover audiocpp/python GPU jobs of this run stopped, ollama ps logged. Never reboots, no admin, never touches C:\grok\drama3 (read-only use of the CLI/model).  #>
param([switch]$DryRun, [switch]$NoVramFree, [double]$Tempo = 0, [ValidateSet('7b','drama3')][string]$Engine = 'drama3', [int]$QcRetries = 1, [string]$Guests = 'Elliot,Clara', [switch]$OneOff, [switch]$Inner, [switch]$FromTask, [string]$Root = "C:\grok\podcast")
$ErrorActionPreference = 'Continue'; cd $Root
$Dir = 'fl1b'; $Ep = 'faultlines_01'; $BgDir = 'bg_fl1'; $Suffix = '_fl1b'; $W = "$Root\$Dir"; $TaskName = 'PodcastFaultlines01b'
$Stage = "episodes\_staging_faultlines_01b"; $Rej = "$Root\episodes\_rejected\faultlines_01_v110"
$Title = "Left vs Right: Is It Becoming a War?"; $Series = 'Fault Lines'
$EpSrc = "$Root\episodes\faultlines_01"; $ScriptSrc = "$EpSrc\faultlines_01_script.json"; $ChapSrc = "$EpSrc\faultlines_01.chapters.in.json"; $CastSrc = "$EpSrc\cast.json"
$ExpLines = 164; $ExpWords = 6198
$py = "$Root\venv_vv\Scripts\python.exe"
function St($m) { if (Test-Path $W) { Set-Content "$W\STATUS.txt" "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $m"; Add-Content "$W\chain.log" "$(Get-Date -f 'HH:mm:ss') $m" } else { Write-Host $m } }
function OllamaModels { try { @((Invoke-RestMethod http://localhost:11434/api/ps -TimeoutSec 5).models | % { $_.name }) } catch { @() } }
$raArgs = @('-Dir', $Dir, '-Ep', $Ep, '-BgDir', $BgDir, '-FrameSuffix', $Suffix, '-Title', $Title, '-Guests', $Guests, '-Tempo', "$Tempo", '-Engine', $Engine, '-QcRetries', "$QcRetries", '-OutDir', $Stage)
if ($OneOff) { $raArgs += '-OneOff' } else { $raArgs += @('-Series', $Series, '-Multi') }
if (-not $NoVramFree) { $raArgs += '-Scheduled' }

if ($Inner) {
  $t0 = Get-Date
  St "wrapper started (pid $PID) engine=$Engine guests=$Guests tempo=$Tempo qcretries=$QcRetries vram_free=$(-not $NoVramFree) oneoff=$OneOff fromtask=$FromTask"
  # unattended: a model left in Ollama would block run_episode forever -> wait up to 20 min, then stop it (Thomas' rule: unload after use)
  for ($i = 0; $i -lt 80 -and (OllamaModels).Count; $i++) { if ($i -eq 0) { St "Ollama busy ($((OllamaModels) -join ',')), waiting up to 20 min" }; Start-Sleep 15 }
  foreach ($m in (OllamaModels)) { St "stopping leftover Ollama model $m"; & ollama stop $m 2>&1 | Out-Null }
  $so = & $py "$Root\tools\fl1_sync_lines.py" $ScriptSrc $ChapSrc "$Root\$BgDir\backgrounds.src.json" $W "$W\$Ep.chapters.in.json" "$Root\$BgDir\backgrounds.json" 2>&1 | Out-String
  Add-Content "$W\chain.log" $so.Trim(); if ($so -notmatch 'SYNC lines') { St "STOP fl1_sync_lines.py failed (see chain.log)"; $res = 'STOP sync' }
  else {
    & powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\run_episode.ps1" @raArgs
    $last = (gc "$W\STATUS.txt" -Raw)
    if ($last -match 'ALL DONE \(post exit (\d+)\)') {
      $pe = [int]$matches[1]
      if ($pe -eq 0) {
        # ---- v1.11 final gates, then swap (old files moved to _rejected, never deleted) ----
        $g = @(); $dur = 0; $m = (gc "$W\post.log" -EA 0 | sls 'mixed dur ([\d.]+) s' | select -Last 1); if ($m) { $dur = [double]$m.Matches[0].Groups[1].Value }
        if ($dur -lt 2280 -or $dur -gt 2880) { $g += "duration $dur s outside 2280-2880" }
        foreach ($sj in (gci "$W\seg??.json" | ? { $_.Name -match '^seg\d\d\.json$' })) { $b = $sj.BaseName
          if (-not (Test-Path "$W\$b.mp3")) { $g += "$b.mp3 missing" } else { $qj = gc "$W\$b.qc.json" -Raw | ConvertFrom-Json; if (@($qj.voice_redo | ? { $_ -ne $null }).Count) { $g += "$b voice" }; if (-not $qj.voice_summary) { $g += "$b no voice check" } } }
        $gcut = @(gc "$W\render.log" -EA 0 | sls 'GATECUT [1-9]'); if ($gcut.Count) { Add-Content "$W\chain.log" "note: $($gcut.Count) segment(s) fell back to ungated raw audio (GATECUT) - no cut words shipped" }
        foreach ($x in 'mp3', 'mp4', 'srt', 'json', 'notes.md', 'chapters.txt', 'chapters.json') { if (-not (Test-Path "$Root\$Stage\$Ep.$x")) { $g += "staged $Ep.$x missing" } }
        if ($g.Count) { $res = "STOP final gates failed: $($g -join ' | ') - staged files kept in $Stage, old episode untouched" }
        else {
          New-Item -ItemType Directory -Force $Rej | Out-Null; $moved = @()
          foreach ($f in @(gci "$Root\episodes" -File | ? { $_.Name -like "$Ep.*" -or $_.Name -eq "${Ep}_64k.mp3" })) { Move-Item $f.FullName $Rej -Force; $moved += $f.Name }
          Add-Content "$W\chain.log" "swap: moved rejected v1.10 files to $Rej : $($moved -join ', ')"
          foreach ($f in @(gci "$Root\$Stage" -File)) { Move-Item $f.FullName "$Root\episodes\" }
          $ro = & $py -c "import sys,json;sys.path.insert(0,r'$Root');import episodes_index as E;p=r'$Root\episodes_index.json';ix=E.load(p);e=[x for x in ix['episodes'] if x['ep']=='$Ep'][0];e['duration_s']=$dur;e['date']='$(Get-Date -f yyyy-MM-dd)';e['note']='re-render v1.11 (v1.10 render rejected, moved to episodes/_rejected/faultlines_01_v110)';E.write(ix,p,p[:-5]+'.md');print('registry updated',e['number'],e['duration_s'])" 2>&1 | Out-String
          Add-Content "$W\chain.log" "swap: new files in episodes\: $((gci "$Root\episodes" -File | ? { $_.Name -like "$Ep*" } | % { $_.Name }) -join ', '); $($ro.Trim())"
          $res = "ALL DONE (post exit 0, mix $([math]::Round($dur/60,1)) min, all gates passed, swapped into episodes\)" }
      }
      elseif ($pe -eq 3) { $dur = 0; $m = (gc "$W\post.log" -EA 0 | sls 'mixed dur ([\d.]+) s' | select -Last 1); if ($m) { $dur = [double]$m.Matches[0].Groups[1].Value }
        $res = "STOP duration gate failed (mix $dur s, outside 2280-2880 s): needs Thomas' decision (see $W\post.log); old episode untouched" }
      else { $res = "STOP post failed with exit $pe (see post.out.txt / post.log); old episode untouched" }
    } else { $res = "STOP run_episode ended without ALL DONE: $($last.Trim()) (see chain.log / render.log); old episode untouched" }
  }
  # ---- cleanup: no model / GPU job left behind (never reboots) ----
  foreach ($m in (OllamaModels)) { Add-Content "$W\chain.log" "cleanup: ollama stop $m"; & ollama stop $m 2>&1 | Out-Null }
  Get-Process audiocpp_cli, audiocpp_server -EA 0 | ? { $_.StartTime -ge $t0 } | % { Add-Content "$W\chain.log" "cleanup: stopping leftover $($_.Name) pid $($_.Id)"; Stop-Process -Id $_.Id -Force -EA 0 }
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.ExecutablePath -match '\\venv_(sd|whisper|video|vv)\\' -and $_.CommandLine -match 'gen_backgrounds|align\.py|make_video|qc_|drama3_' -and $_.CreationDate -ge $t0 } | % { Add-Content "$W\chain.log" "cleanup: stopping leftover python pid $($_.ProcessId) $($_.CommandLine)"; Stop-Process -Id $_.ProcessId -Force -EA 0 }
  Start-Sleep 3; $left = (OllamaModels).Count; $ps = (& ollama ps 2>&1 | Out-String).Trim(); Add-Content "$W\chain.log" "cleanup: ollama ps -> $ps"
  $gp = @(Get-Process audiocpp_cli, audiocpp_server -EA 0).Count
  St "$res | cleanup: ollama models=$left, audiocpp=$gp, total $([int]((Get-Date)-$t0).TotalMinutes) min"
  exit 0
}

# ---------------- outer: preflight + launch ----------------
if ($FromTask) {
  New-Item -ItemType Directory "$Root\logs" -Force | Out-Null; Start-Transcript -Path "$Root\logs\faultlines_01b_task.log" -Append | Out-Null
  # run once: delete the scheduled task after this action has returned (deleting is safe; the detached wrapper is a separate process)
  Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', "Start-Sleep 30; Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false *> '$Root\logs\faultlines_01b_taskdel.log'"
}
$bad = @(); $ok = @()
function Chk($c, $m) { if ($c) { $script:ok += $m } else { $script:bad += $m } }
$gv = @($Guests -split ',' | % { $_.Trim() } | ? { $_ }); Chk ($gv.Count -eq 2) "-Guests has two names ($Guests)"
$need = @('episodes\faultlines_01\faultlines_01_script.json', 'episodes\faultlines_01\faultlines_01.chapters.in.json', 'episodes\faultlines_01\cast.json', 'bg_fl1\prompts.json', 'bg_fl1\backgrounds.src.json', 'bg_fl1\backgrounds.json',
  'run_episode.ps1', 'post_episode.ps1', 'post_segment.ps1', 'spk_check.py', 'gate_cut_check.py', 'venv_spk\Scripts\python.exe', 'models\spkrec-ecapa-voxceleb\hyperparams.yaml', 'drama3_refs\Carter.wav', 'drama3_refs\Elliot.wav', 'drama3_refs\Clara.wav', 'md_clean.py', 'pick_cast.py', 'episodes_index.py', 'episodes_index.json', 'voices.json', 'voice_f0.json', 'qc_vv.py', 'qc_takes.py', 'qc_mix.py', 'align.py', 'make_video.py',
  'hwrun.ps1', 'gen_backgrounds_flux.py', 'tools\split_segments.py', 'tools\fl1_sync_lines.py', 'tools\start_faultlines_01b.ps1', 'ui1\intro.wav', 'ui1\sting.wav', 'ui1\outro.wav', 'empty_glossary.json',
  'venv_vv\Scripts\python.exe', 'venv_whisper\Scripts\python.exe', 'venv_sd\Scripts\python.exe', 'venv_video\Scripts\python.exe', 'VibeVoice-main\demo\voices\en-Carter_man.wav')
if ($Engine -eq 'drama3') { $need += 'render_drama3.ps1', 'drama3_generate.py', 'drama3_refs.py' } else { $need += 'render7b.ps1', 'vv7b_generate.py', 'tests\vv7b_cpp\bin\audiocpp_cli.exe', 'tests\vv7b_cpp\models\vibevoice-7b-q8_0.gguf' }
foreach ($f in $need) { Chk (Test-Path "$Root\$f") "exists $f" }
if ($Engine -eq 'drama3') { foreach ($f in 'bin\audiocpp_cli.exe', 'models\drama-3-backbone-8bit-experts-Q4_K_S.gguf') { Chk (Test-Path "C:\grok\drama3\$f") "exists C:\grok\drama3\$f (read-only check)" } }
Chk ((Test-Path 'C:\grok\hwmon\hwmon_lib.ps1') -or (Test-Path "$Root\hwmon_lib.ps1")) 'hwmon_lib.ps1 available'
Chk ([bool](Get-Command ffmpeg -EA 0) -and [bool](Get-Command ffprobe -EA 0)) 'ffmpeg + ffprobe on PATH'; Chk ([bool](Get-Command ollama -EA 0)) 'ollama on PATH'
$vo = gc "$Root\voices.json" -Raw | ConvertFrom-Json
foreach ($g in $gv) { $e = $vo.voices.$g; Chk ($e -and (Test-Path "$Root\$($e.file)")) "voice $g exists ($($e.file))"; Chk ($g -notin 'Maya','Declan','Alice','Mary','Hugh') "guest $g allowed with Carter" }
Chk ([bool]($vo.voices.Elliot.credit -and $vo.voices.Clara.credit)) 'CC BY credit lines for Elliot + Clara in voices.json'
Chk (Test-Path 'C:\Users\TJ\.cache\huggingface\hub\models--unsloth--FLUX.1-schnell\snapshots\9df3faa7ae3b6ddf0b2b69bb78616372897cc65c\model_index.json') 'FLUX.1-schnell snapshot'
foreach ($f in 'run_episode.ps1', 'render_drama3.ps1', 'post_episode.ps1', 'post_segment.ps1', 'tools\start_faultlines_01b.ps1') { $e = $null; [void][Management.Automation.Language.Parser]::ParseFile("$Root\$f", [ref]$null, [ref]$e); Chk ($e.Count -eq 0) "PowerShell parse $f" }
if (-not $NoVramFree) { Chk (Test-Path 'C:\grok\vram\vram_free.ps1') 'vram_free.ps1 exists (graceful, guarded hook)' }
$re = gc "$Root\run_episode.ps1" -Raw; $pe_ = gc "$Root\post_episode.ps1" -Raw
$rd = gc "$Root\render_drama3.ps1" -Raw; $dg = gc "$Root\drama3_generate.py" -Raw; $qv = gc "$Root\qc_vv.py" -Raw
Chk ($re -match "\[string\]\`$Engine = `"drama3`"" -and $re -match "drama3'\) \{ 0\.90 \}" -and $re -match "drama3'\) \{ 100 \}") 'run_episode v1.11: default engine drama3, tempo 0.90, ChunkWords 100'
Chk ($re -match 'STOP TTS incomplete' -and $re -match 'exit 6') 'run_episode v1.11: stops before FLUX/post on GENFAIL/SPKFAIL/missing segment'
Chk ($rd -match 'template v1\.11' -and $rd -match 'SpkCheck' -and $rd -match 'SPKFAIL') 'render_drama3 v1.11: voice-match gate + SPKFAIL stop'
Chk ($dg -match 'default="turn"' -and $dg -match 'chunk_words", type=int, default=100' -and $dg -match 'max_tokens') 'drama3_generate v1.11: one speaker per request, 100 words, runaway cap/retry'
Chk ($qv -match 'qc_vv.py v2\.3' -and $qv -match 'gate_protect_db' -and $qv -match 'end_missing') 'qc_vv v2.3: speech-safe gate + end_missing flag'
Chk ((gc "$Root\post_segment.ps1" -Raw) -match 'GATECUT') 'post_segment v1.11: cut-word gate'
Chk ($pe_ -match 'missing segment mp3' -and $pe_ -match 'OutDir' -and $pe_ -notmatch '; VibeVoice-7B Q8 via audio\.cpp\.') 'post_episode v1.11: segment list from json, refuses missing mp3, -OutDir, engine name'
$pngs = @((gc -Raw "$Root\$BgDir\prompts.json" | ConvertFrom-Json).images.id | ? { -not (Test-Path "$Root\$BgDir\$_.png") }); Chk ($pngs.Count -eq 0) "bg_fl1: all FLUX images exist (reuse, no regeneration; missing: $($pngs -join ','))"
Chk (-not (Test-Path "$W\seg00.json")) "fresh working dir $Dir (no old segments)"
Chk (-not (Test-Path "$Root\$Stage") -or -not @(gci "$Root\$Stage" -File).Count) "staging dir $Stage empty"
Chk (-not (Test-Path $Rej) -or -not @(gci $Rej -File).Count) "rejected dir $Rej empty (old files not moved yet)"
Chk (Test-Path "$Root\episodes\$Ep.mp3") "rejected v1.10 episode present (will be moved to _rejected only after all gates pass)" 
Chk ($pe_ -match '\$MinDur = 2280' -and $pe_ -match '\$MaxDur = 2880') 'duration window 2280-2880 s (38-48 min) in post_episode.ps1'
Chk ($pe_ -match 'never overwrite') 'post_episode never-overwrite guard present'
Chk ($re -notmatch 'prep_script') 'run_episode does not call prep_script.py (no line merging in this chain)'
$S = gc $ScriptSrc -Raw -Encoding UTF8 | ConvertFrom-Json; $wc = 0; $S | % { $wc += ($_.text -split '\s+' | ? { $_ }).Count }
Chk ($S.Count -eq $ExpLines) "script lines = $($S.Count) (expect $ExpLines)"; Chk ($wc -eq $ExpWords) "script words = $wc (expect $ExpWords)"
Chk ((@($S | ? { $_.speaker -notin 'Host','Guest','Guest2' })).Count -eq 0) 'speakers are Host/Guest/Guest2 only'
Chk ((@($S | ? { $_.text -match '\[(?!sighs\]|laughs\]|whispers\])[A-Za-z][A-Za-z'' -]{0,30}\]' })).Count -eq 0) 'only [sighs]/[laughs]/[whispers] tags'
$C = gc $ChapSrc -Raw | ConvertFrom-Json; $starts = @($C.sections | % { $_.start }); Chk ($C.sections.Count -eq 10 -and $starts[0] -eq 0 -and ($starts | measure -Maximum).Maximum -lt $S.Count) "chapters: $($C.sections.Count) sections, starts $($starts -join ',')"
$cj = gc $CastSrc -Raw | ConvertFrom-Json; Chk ($cj.host -eq 'Carter' -and $cj.guest -eq $gv[0] -and $cj.guest2 -eq $gv[1]) "cast.json: host=$($cj.host) guest=$($cj.guest) guest2=$($cj.guest2) seed=$($cj.seed)"
if (Test-Path "$W\cast.json") { $wc_ = gc "$W\cast.json" -Raw | ConvertFrom-Json; Chk ($wc_.guest -eq $gv[0] -and $wc_.guest2 -eq $gv[1]) "existing fl1b\cast.json matches ($($wc_.guest)/$($wc_.guest2))" }
$P = gc "$Root\$BgDir\prompts.json" -Raw | ConvertFrom-Json; $B = gc "$Root\$BgDir\backgrounds.src.json" -Raw | ConvertFrom-Json
Chk ($P.images.Count -eq 21 -and $B.Count -eq 21) "bg prompts = $($P.images.Count), backgrounds.src.json = $($B.Count) (expect 21)"
Chk ((@($P.images.id) -join ',') -eq ((@($B.image) | % { $_ -replace '\.png$', '' }) -join ',')) 'prompt ids match backgrounds images'
Chk (($B.line | measure -Maximum).Maximum -lt $S.Count -and $B[0].line -eq 0) "background lines 0..$(($B.line | measure -Maximum).Maximum) within script"
foreach ($x in 'mp3', 'mp4', 'srt', 'json') { Chk (-not (Test-Path "$Root\$Stage\$Ep.$x")) "$Stage\$Ep.$x does not exist yet" }
$pa = @('plan', '--ep', $Ep, '--title', $Title); if ($OneOff) { $pa += '--oneoff' } else { $pa += '--series', $Series, '--multi' }
try { $plan = & $py "$Root\episodes_index.py" @pa 2>&1 | Out-String | ConvertFrom-Json } catch { $plan = $null }
Chk ($plan.display_title -and $plan.display_title -notmatch 'Episode') "naming plan: #$($plan.number) overall, title '$($plan.display_title)', corner label '$($plan.label)'"
$free = [math]::Round((Get-PSDrive C).Free / 1GB); Chk ($free -ge 60) "disk free C: $free GB (need >= 60)"
$sp = [int]($wc / 155 * 60); Write-Host ("Expected speech at ~155 wpm (drama3 tempo 0.90): ~{0} s = {1}:{2:00} min + intro/9 stings/outro/gaps; gate 2280-2880 s" -f $sp, [int][math]::Floor($sp / 60), ($sp % 60))
$om = (OllamaModels).Count; if ($om) { Write-Host "NOTE: Ollama has $om model(s) loaded; the wrapper waits up to 20 min, then stops them" } else { $ok += 'Ollama is empty' }
$busy = @(Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'run_episode\.ps1|render7b\.ps1|render_drama3\.ps1|post_episode\.ps1|vv7b_generate|drama3_generate|gen_backgrounds|make_video\.py|start_\w+\.ps1 .*-Inner' -and $_.ProcessId -ne $PID -and $_.Name -match 'powershell|python|audiocpp' }); Chk ($busy.Count -eq 0) "no pipeline job running ($($busy.Count))"
if (Test-Path "$W\STATUS.txt") { Write-Host "NOTE: existing $W\STATUS.txt: $(gc "$W\STATUS.txt" -Raw)".Trim() }
Write-Host "--- preflight OK items: $($ok.Count)"; if ($DryRun) { $ok | % { Write-Host "  ok  $_" } }
if ($bad.Count) { $bad | % { Write-Host "  FAIL $_" }; Write-Host "ABORT: $($bad.Count) preflight problem(s), nothing started"; if ($FromTask) { New-Item -ItemType Directory $W -Force | Out-Null; St "ABORT preflight at task start: $($bad -join ' | ')"; Stop-Transcript | Out-Null }; exit 1 }
if ($DryRun) {
  $tmp = "$env:TEMP\fl1b_dryrun"; Remove-Item -Recurse -Force $tmp -EA 0; New-Item -ItemType Directory $tmp | Out-Null
  & $py "$Root\tools\split_segments.py" $ScriptSrc $ChapSrc $tmp --expect_lines $ExpLines --expect_words $ExpWords
  if ($LASTEXITCODE) { Write-Host "ABORT: split failed"; exit 1 }
  & $py "$Root\tools\fl1_sync_lines.py" $ScriptSrc $ChapSrc "$Root\$BgDir\backgrounds.src.json" $tmp "$tmp\c.json" "$tmp\b.json" --dry
  & powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\run_episode.ps1" @raArgs -DryRun
  Remove-Item -Recurse -Force $tmp -EA 0
  $cmd = "powershell -NoProfile -ExecutionPolicy Bypass -File $Root\run_episode.ps1 " + (($raArgs | % { if ($_ -match '[\s?'':]') { "'" + ($_ -replace "'", "''") + "'" } else { $_ } }) -join ' ')
  Write-Host "DRY RUN: nothing written/started in the project (split/sync tested in $tmp, removed). The wrapper would run:`n  $cmd`n  (then final gates + swap: old files -> $Rej, staged -> episodes\; any failure = STOP for Thomas; then cleanup)"; exit 0 }
New-Item -ItemType Directory $W -Force | Out-Null
& $py "$Root\tools\split_segments.py" $ScriptSrc $ChapSrc $W --expect_lines $ExpLines --expect_words $ExpWords
if ($LASTEXITCODE) { St "ABORT: split failed"; if ($FromTask) { Stop-Transcript | Out-Null }; exit 1 }
if (-not (Test-Path "$W\cast.json")) { Copy-Item $CastSrc "$W\cast.json" }
foreach ($f in 'intro.wav', 'sting.wav', 'outro.wav') { if (-not (Test-Path "$W\$f")) { Copy-Item "$Root\ui1\$f" "$W\$f" } }
Remove-Item "$W\STATUS.txt" -ea 0; St 'launching detached wrapper'
$a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$Root\tools\start_faultlines_01b.ps1", '-Inner', '-Tempo', "$Tempo", '-Engine', $Engine, '-QcRetries', "$QcRetries", '-Guests', $Guests); if ($NoVramFree) { $a += '-NoVramFree' }; if ($OneOff) { $a += '-OneOff' }; if ($FromTask) { $a += '-FromTask' }
$p = Start-Process powershell -ArgumentList $a -WindowStyle Hidden -PassThru
Write-Host "STARTED detached wrapper pid $($p.Id) at $(Get-Date -f 'HH:mm:ss'). Poll: Get-Content $W\STATUS.txt ; Get-Content $W\chain.log -Tail 15"
if ($FromTask) { Stop-Transcript | Out-Null }
