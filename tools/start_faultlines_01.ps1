<#  start_faultlines_01.ps1 (2026-10-19, template v1.10 pipeline; copy-adapted from tools\start_agentic_ai_ep1.ps1) - ONE-CALL launcher for "Fault Lines #1 - Left vs Right: Is It Becoming a War?" (series "Fault Lines", #n naming via episodes_index.py).
Start now (returns at once; the job runs detached/hidden):  powershell -NoProfile -ExecutionPolicy Bypass -File C:\grok\podcast\tools\start_faultlines_01.ps1
Scheduled (armed for 20 Oct 2026 01:00 as the per-user task PodcastFaultlines01):  ... -File ...\start_faultlines_01.ps1 -FromTask   (logs to logs\faultlines_01_task.log; deletes the task 30 s later, so it runs once)
Poll:  Get-Content C:\grok\podcast\fl1\STATUS.txt ; Get-Content C:\grok\podcast\fl1\chain.log -Tail 15      Dry run: add -DryRun (writes/starts nothing in the project).
Cast: FIXED Host Carter, Guest Elliot (far right), Guest2 Clara (far left) = episodes\faultlines_01\cast.json (pick seed 548870699), copied to fl1\cast.json (run_episode reuses it).
Script: episodes\faultlines_01\faultlines_01_script.json AS IS (164 lines / 6198 words; no prep_script merge in this chain). Chapters: episodes\faultlines_01\faultlines_01.chapters.in.json.
Line indices: segments are cut at the chapter starts (tools\split_segments.py, text untouched). Before TTS the wrapper runs tools\fl1_sync_lines.py: if the segment files no longer match the
  script line-for-line (e.g. someone ran prep_script.py on them), chapter starts are rebuilt from the segment lengths and bg_fl1\backgrounds.json lines are remapped by ORIGINAL line index
  (from bg_fl1\backgrounds.src.json). Unchanged segments = files copied as is.
Pipeline: preflight -> fl1\segNN.json + intro/sting/outro from ui1 -> detached wrapper -> run_episode.ps1 (-Engine drama3, engine tempo 1.05, -QcRetries 1, -Series 'Fault Lines' -Multi,
  -Scheduled = graceful vram_free hook unless -NoVramFree) -> Drama 3 TTS + QC, FLUX bg_fl1 (fl01-fl21), post (duration gate 38-48 min, align, qc_mix, video, srt, 64k mp3, CC BY credits).
  Short mix (< 2280 s) -> post-only retry with -SegGap 1.2 -StingPad 0.6. Cleanup at the end: every loaded Ollama model stopped, leftover audiocpp/python GPU jobs of this run stopped, ollama ps logged.
  Never reboots, never changes power settings. Never overwrites episodes\faultlines_01.* (preflight + post abort). Resumable (segments with mp3+qc.json are skipped).  #>
param([switch]$DryRun, [switch]$NoVramFree, [double]$Tempo = 0, [ValidateSet('7b','drama3')][string]$Engine = 'drama3', [int]$QcRetries = 1, [string]$Guests = 'Elliot,Clara', [switch]$OneOff, [switch]$Inner, [switch]$FromTask, [string]$Root = "C:\grok\podcast")
$ErrorActionPreference = 'Continue'; cd $Root
$Dir = 'fl1'; $Ep = 'faultlines_01'; $BgDir = 'bg_fl1'; $Suffix = '_fl1'; $W = "$Root\$Dir"; $TaskName = 'PodcastFaultlines01'
$Title = "Left vs Right: Is It Becoming a War?"; $Series = 'Fault Lines'
$EpSrc = "$Root\episodes\faultlines_01"; $ScriptSrc = "$EpSrc\faultlines_01_script.json"; $ChapSrc = "$EpSrc\faultlines_01.chapters.in.json"; $CastSrc = "$EpSrc\cast.json"
$ExpLines = 164; $ExpWords = 6198
$py = "$Root\venv_vv\Scripts\python.exe"
function St($m) { if (Test-Path $W) { Set-Content "$W\STATUS.txt" "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $m"; Add-Content "$W\chain.log" "$(Get-Date -f 'HH:mm:ss') $m" } else { Write-Host $m } }
function OllamaModels { try { @((Invoke-RestMethod http://localhost:11434/api/ps -TimeoutSec 5).models | % { $_.name }) } catch { @() } }
$raArgs = @('-Dir', $Dir, '-Ep', $Ep, '-BgDir', $BgDir, '-FrameSuffix', $Suffix, '-Title', $Title, '-Guests', $Guests, '-Tempo', "$Tempo", '-Engine', $Engine, '-QcRetries', "$QcRetries")
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
      if ($pe -eq 0) { $res = "ALL DONE (post exit 0)" }
      elseif ($pe -eq 3) {
        $dur = 0; $m = (gc "$W\post.log" -ErrorAction SilentlyContinue | sls 'mixed dur ([\d.]+) s' | select -Last 1); if ($m) { $dur = [double]$m.Matches[0].Groups[1].Value }
        if ($dur -gt 0 -and $dur -lt 2280) {
          St "post exit 3: mix $dur s < 2280 -> re-running POST ONLY with -SegGap 1.2 -StingPad 0.6 (no TTS)"
          $nm = if ($OneOff) { @('-OneOff') } else { @('-Series', $Series, '-Multi') }
          & powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\post_episode.ps1" -Dir $W -Ep $Ep -Bg "$BgDir\backgrounds.json" -FrameSuffix $Suffix -Title $Title -SegGap 1.2 -StingPad 0.6 @nm *> "$W\post2.out.txt"
          $pe2 = $LASTEXITCODE
          $res = if ($pe2 -eq 0) { "ALL DONE (post exit 0 after SegGap 1.2/StingPad 0.6 retry)" } else { "STOP post retry exit $pe2 (mix still outside 2280-2880 s?): see post.log" }
        } else { $res = "STOP duration gate failed (mix $dur s, exit 3): too long or unknown - needs a human decision (see post.log); do not slow the tempo for length" }
      } else { $res = "STOP post failed with exit $pe (see post.out.txt / post.log)" }
    } else { $res = "STOP run_episode ended without ALL DONE (see chain.log / render.log)" }
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
  New-Item -ItemType Directory "$Root\logs" -Force | Out-Null; Start-Transcript -Path "$Root\logs\faultlines_01_task.log" -Append | Out-Null
  # run once: delete the scheduled task after this action has returned (deleting is safe; the detached wrapper is a separate process)
  Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', "Start-Sleep 30; schtasks /delete /tn $TaskName /f *> '$Root\logs\faultlines_01_taskdel.log'"
}
$bad = @(); $ok = @()
function Chk($c, $m) { if ($c) { $script:ok += $m } else { $script:bad += $m } }
$gv = @($Guests -split ',' | % { $_.Trim() } | ? { $_ }); Chk ($gv.Count -eq 2) "-Guests has two names ($Guests)"
$need = @('episodes\faultlines_01\faultlines_01_script.json', 'episodes\faultlines_01\faultlines_01.chapters.in.json', 'episodes\faultlines_01\cast.json', 'bg_fl1\prompts.json', 'bg_fl1\backgrounds.src.json', 'bg_fl1\backgrounds.json',
  'run_episode.ps1', 'post_episode.ps1', 'post_segment.ps1', 'md_clean.py', 'pick_cast.py', 'episodes_index.py', 'episodes_index.json', 'voices.json', 'voice_f0.json', 'qc_vv.py', 'qc_takes.py', 'qc_mix.py', 'align.py', 'make_video.py',
  'hwrun.ps1', 'gen_backgrounds_flux.py', 'tools\split_segments.py', 'tools\fl1_sync_lines.py', 'ui1\intro.wav', 'ui1\sting.wav', 'ui1\outro.wav', 'empty_glossary.json',
  'venv_vv\Scripts\python.exe', 'venv_whisper\Scripts\python.exe', 'venv_sd\Scripts\python.exe', 'venv_video\Scripts\python.exe', 'VibeVoice-main\demo\voices\en-Carter_man.wav')
if ($Engine -eq 'drama3') { $need += 'render_drama3.ps1', 'drama3_generate.py', 'drama3_refs.py' } else { $need += 'render7b.ps1', 'vv7b_generate.py', 'tests\vv7b_cpp\bin\audiocpp_cli.exe', 'tests\vv7b_cpp\models\vibevoice-7b-q8_0.gguf' }
foreach ($f in $need) { Chk (Test-Path "$Root\$f") "exists $f" }
if ($Engine -eq 'drama3') { foreach ($f in 'bin\audiocpp_cli.exe', 'models\drama-3-backbone-8bit-experts-Q4_K_S.gguf') { Chk (Test-Path "C:\grok\drama3\$f") "exists C:\grok\drama3\$f (read-only check)" } }
Chk ((Test-Path 'C:\grok\hwmon\hwmon_lib.ps1') -or (Test-Path "$Root\hwmon_lib.ps1")) 'hwmon_lib.ps1 available'
Chk ([bool](Get-Command ffmpeg -EA 0) -and [bool](Get-Command ffprobe -EA 0)) 'ffmpeg + ffprobe on PATH'; Chk ([bool](Get-Command ollama -EA 0)) 'ollama on PATH'
$vo = gc "$Root\voices.json" -Raw | ConvertFrom-Json
foreach ($g in $gv) { $e = $vo.voices.$g; Chk ($e -and (Test-Path "$Root\$($e.file)")) "voice $g exists ($($e.file))"; Chk ($g -notin 'Maya','Declan','Alice','Mary','Hugh') "guest $g allowed with Carter" }
Chk ([bool]($vo.voices.Elliot.credit -and $vo.voices.Clara.credit)) 'CC BY credit lines for Elliot + Clara in voices.json'
Chk (Test-Path (Join-Path $(if ($env:FLUX_SNAPSHOT) { $env:FLUX_SNAPSHOT } else { Join-Path $env:USERPROFILE '.cache\huggingface\hub\models--unsloth--FLUX.1-schnell\snapshots\9df3faa7ae3b6ddf0b2b69bb78616372897cc65c' }) 'model_index.json')) 'FLUX.1-schnell snapshot'
foreach ($f in 'run_episode.ps1', 'render_drama3.ps1', 'post_episode.ps1', 'post_segment.ps1', 'tools\start_faultlines_01.ps1') { $e = $null; [void][Management.Automation.Language.Parser]::ParseFile("$Root\$f", [ref]$null, [ref]$e); Chk ($e.Count -eq 0) "PowerShell parse $f" }
if (-not $NoVramFree) { Chk (Test-Path 'C:\grok\vram\vram_free.ps1') 'vram_free.ps1 exists (graceful, guarded hook)' }
$re = gc "$Root\run_episode.ps1" -Raw; $pe_ = gc "$Root\post_episode.ps1" -Raw
Chk ($re -match "\[string\]\`$Engine = `"drama3`"" -and $re -match "1\.05") 'run_episode v1.10: default engine drama3, tempo 1.05'
Chk ($pe_ -match '\$MinDur = 2280' -and $pe_ -match '\$MaxDur = 2880') 'duration window 2280-2880 s (38-48 min) in post_episode.ps1'
Chk ($pe_ -match 'never overwrite') 'post_episode never-overwrite guard present'
Chk ($re -notmatch 'prep_script') 'run_episode does not call prep_script.py (no line merging in this chain)'
$S = gc $ScriptSrc -Raw -Encoding UTF8 | ConvertFrom-Json; $wc = 0; $S | % { $wc += ($_.text -split '\s+' | ? { $_ }).Count }
Chk ($S.Count -eq $ExpLines) "script lines = $($S.Count) (expect $ExpLines)"; Chk ($wc -eq $ExpWords) "script words = $wc (expect $ExpWords)"
Chk ((@($S | ? { $_.speaker -notin 'Host','Guest','Guest2' })).Count -eq 0) 'speakers are Host/Guest/Guest2 only'
Chk ((@($S | ? { $_.text -match '\[(?!sighs\]|laughs\]|whispers\])[A-Za-z][A-Za-z'' -]{0,30}\]' })).Count -eq 0) 'only [sighs]/[laughs]/[whispers] tags'
$C = gc $ChapSrc -Raw | ConvertFrom-Json; $starts = @($C.sections | % { $_.start }); Chk ($C.sections.Count -eq 10 -and $starts[0] -eq 0 -and ($starts | measure -Maximum).Maximum -lt $S.Count) "chapters: $($C.sections.Count) sections, starts $($starts -join ',')"
$cj = gc $CastSrc -Raw | ConvertFrom-Json; Chk ($cj.host -eq 'Carter' -and $cj.guest -eq $gv[0] -and $cj.guest2 -eq $gv[1]) "cast.json: host=$($cj.host) guest=$($cj.guest) guest2=$($cj.guest2) seed=$($cj.seed)"
if (Test-Path "$W\cast.json") { $wc_ = gc "$W\cast.json" -Raw | ConvertFrom-Json; Chk ($wc_.guest -eq $gv[0] -and $wc_.guest2 -eq $gv[1]) "existing fl1\cast.json matches ($($wc_.guest)/$($wc_.guest2))" }
$P = gc "$Root\$BgDir\prompts.json" -Raw | ConvertFrom-Json; $B = gc "$Root\$BgDir\backgrounds.src.json" -Raw | ConvertFrom-Json
Chk ($P.images.Count -eq 21 -and $B.Count -eq 21) "bg prompts = $($P.images.Count), backgrounds.src.json = $($B.Count) (expect 21)"
Chk ((@($P.images.id) -join ',') -eq ((@($B.image) | % { $_ -replace '\.png$', '' }) -join ',')) 'prompt ids match backgrounds images'
Chk (($B.line | measure -Maximum).Maximum -lt $S.Count -and $B[0].line -eq 0) "background lines 0..$(($B.line | measure -Maximum).Maximum) within script"
foreach ($x in 'mp3', 'mp4', 'srt', 'json', 'notes.md', 'chapters.txt', 'chapters.json') { Chk (-not (Test-Path "$Root\episodes\$Ep.$x")) "episodes\$Ep.$x does not exist yet" }; Chk (-not (Test-Path "$Root\episodes\${Ep}_64k.mp3")) "episodes\${Ep}_64k.mp3 does not exist yet"
$pa = @('plan', '--ep', $Ep, '--title', $Title); if ($OneOff) { $pa += '--oneoff' } else { $pa += '--series', $Series, '--multi' }
try { $plan = & $py "$Root\episodes_index.py" @pa 2>&1 | Out-String | ConvertFrom-Json } catch { $plan = $null }
Chk ($plan.display_title -and $plan.display_title -notmatch 'Episode') "naming plan: #$($plan.number) overall, title '$($plan.display_title)', corner label '$($plan.label)'"
$free = [math]::Round((Get-PSDrive C).Free / 1GB); Chk ($free -ge 60) "disk free C: $free GB (need >= 60)"
$sp = [int]($wc / 155 * 60); Write-Host ("Expected speech at ~155 wpm (drama3 tempo 1.05): ~{0} s = {1}:{2:00} min + intro/9 stings/outro/gaps; gate 2280-2880 s" -f $sp, [int][math]::Floor($sp / 60), ($sp % 60))
$om = (OllamaModels).Count; if ($om) { Write-Host "NOTE: Ollama has $om model(s) loaded; the wrapper waits up to 20 min, then stops them" } else { $ok += 'Ollama is empty' }
$busy = @(Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'run_episode\.ps1|render7b\.ps1|render_drama3\.ps1|post_episode\.ps1|vv7b_generate|drama3_generate|gen_backgrounds|make_video\.py|start_\w+\.ps1 .*-Inner' -and $_.ProcessId -ne $PID -and $_.Name -match 'powershell|python|audiocpp' }); Chk ($busy.Count -eq 0) "no pipeline job running ($($busy.Count))"
if (Test-Path "$W\STATUS.txt") { Write-Host "NOTE: existing $W\STATUS.txt: $(gc "$W\STATUS.txt" -Raw)".Trim() }
Write-Host "--- preflight OK items: $($ok.Count)"; if ($DryRun) { $ok | % { Write-Host "  ok  $_" } }
if ($bad.Count) { $bad | % { Write-Host "  FAIL $_" }; Write-Host "ABORT: $($bad.Count) preflight problem(s), nothing started"; if ($FromTask) { New-Item -ItemType Directory $W -Force | Out-Null; St "ABORT preflight at task start: $($bad -join ' | ')"; Stop-Transcript | Out-Null }; exit 1 }
if ($DryRun) {
  $tmp = "$env:TEMP\fl1_dryrun"; Remove-Item -Recurse -Force $tmp -EA 0; New-Item -ItemType Directory $tmp | Out-Null
  & $py "$Root\tools\split_segments.py" $ScriptSrc $ChapSrc $tmp --expect_lines $ExpLines --expect_words $ExpWords
  if ($LASTEXITCODE) { Write-Host "ABORT: split failed"; exit 1 }
  & $py "$Root\tools\fl1_sync_lines.py" $ScriptSrc $ChapSrc "$Root\$BgDir\backgrounds.src.json" $tmp "$tmp\c.json" "$tmp\b.json" --dry
  & powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\run_episode.ps1" @raArgs -DryRun
  Remove-Item -Recurse -Force $tmp -EA 0
  $cmd = "powershell -NoProfile -ExecutionPolicy Bypass -File $Root\run_episode.ps1 " + (($raArgs | % { if ($_ -match '[\s?'':]') { "'" + ($_ -replace "'", "''") + "'" } else { $_ } }) -join ' ')
  Write-Host "DRY RUN: nothing written/started in the project (split/sync tested in $tmp, removed). The wrapper would run:`n  $cmd`n  (then the post-only retry with -SegGap 1.2 -StingPad 0.6 if the mix is < 2280 s, then cleanup)"; exit 0 }
New-Item -ItemType Directory $W -Force | Out-Null
& $py "$Root\tools\split_segments.py" $ScriptSrc $ChapSrc $W --expect_lines $ExpLines --expect_words $ExpWords
if ($LASTEXITCODE) { St "ABORT: split failed"; if ($FromTask) { Stop-Transcript | Out-Null }; exit 1 }
if (-not (Test-Path "$W\cast.json")) { Copy-Item $CastSrc "$W\cast.json" }
foreach ($f in 'intro.wav', 'sting.wav', 'outro.wav') { if (-not (Test-Path "$W\$f")) { Copy-Item "$Root\ui1\$f" "$W\$f" } }
Remove-Item "$W\STATUS.txt" -ea 0; St 'launching detached wrapper'
$a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$Root\tools\start_faultlines_01.ps1", '-Inner', '-Tempo', "$Tempo", '-Engine', $Engine, '-QcRetries', "$QcRetries", '-Guests', $Guests); if ($NoVramFree) { $a += '-NoVramFree' }; if ($OneOff) { $a += '-OneOff' }; if ($FromTask) { $a += '-FromTask' }
$p = Start-Process powershell -ArgumentList $a -WindowStyle Hidden -PassThru
Write-Host "STARTED detached wrapper pid $($p.Id) at $(Get-Date -f 'HH:mm:ss'). Poll: Get-Content $W\STATUS.txt ; Get-Content $W\chain.log -Tail 15"
if ($FromTask) { Stop-Transcript | Out-Null }
