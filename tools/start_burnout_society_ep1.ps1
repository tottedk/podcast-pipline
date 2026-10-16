<#  start_burnout_society_ep1.ps1 (2026-10-16, template v1.8 pipeline) - ONE-CALL launcher for "Why Are We So Tired? Byung-Chul Han's The Burnout Society" (one-off by default; naming via episodes_index.py: no "Episode N" anywhere).
Start (returns at once; the job runs detached/hidden):
  powershell -NoProfile -ExecutionPolicy Bypass -File C:\grok\podcast\tools\start_burnout_society_ep1.ps1
Poll with short calls:  Get-Content C:\grok\podcast\bb\STATUS.txt ; Get-Content C:\grok\podcast\bb\chain.log -Tail 15
Dry run (checks everything, writes nothing, starts nothing, prints the exact commands):  ... -File ...\start_burnout_society_ep1.ps1 -DryRun
Cast (Thomas, final 2026-10-16): Host Carter, Guest CLARA, Guest2 Marcus (-Guests Clara,Marcus; both are in the random pool: no exclusion warning). Not Maya (excluded, sounds artificial): the dialogue was changed Maya -> Clara in 16 lines (backup burnout_society_ep1_script_pre_clara.json).
What it does: preflight (aborts on any problem) -> bb\segNN.json at the chapter starts (tools\split_segments.py, text untouched) + intro/sting/outro from ui1 -> detached wrapper -> run_episode.ps1 (-Tempo 0.93, -QcRetries 1, -Scheduled = vram_free hook, md_clean strip, 7B TTS + QC, FLUX backgrounds bb01-bb22, post: mix, duration gate 38-48 min, align, qc_mix, video, 64k mp3, CC BY credits for Clara + Marcus, registry entry)
  -> if the duration gate fails SHORT (< 2280 s) the wrapper re-runs ONLY post with -SegGap 1.2 -StingPad 0.6 (no TTS); anything else outside 2280-2880 s stops with STATUS "STOP ..." for a human decision (never slow the tempo for length).
Naming: default = one-off (title = subject, video corner label = date). -Multi = treat as series "Burnout Society" (title/label "Burnout Society #<n>").
Backgrounds: bg_bb1\backgrounds.json is checked against the script length; if stale use -RescaleBackgrounds -FromLines <old line count> (keeps .bak_pre_rescale), only when needed.
Never overwrites episodes\burnout_society_ep1.* (post aborts). Resumable: run it again (segments with mp3+qc.json are skipped, an existing bb\cast.json is reused).  #>
param([switch]$DryRun, [switch]$NoVramFree, [double]$Tempo = 0.93, [int]$QcRetries = 1, [string]$Guests = 'Clara,Marcus', [switch]$Multi, [switch]$RescaleBackgrounds, [int]$FromLines = 0, [switch]$Inner, [string]$Root = "C:\grok\podcast")
$ErrorActionPreference = 'Continue'; cd $Root
$Dir = 'bb'; $Ep = 'burnout_society_ep1'; $BgDir = 'bg_bb1'; $Suffix = '_bb1'; $W = "$Root\$Dir"
$Title = "Why Are We So Tired? Byung-Chul Han's The Burnout Society"
$ScriptSrc = "$Root\burnout_society_ep1_script.json"; $ExpLines = 232; $ExpWords = 6129
$py = "$Root\venv_vv\Scripts\python.exe"
function St($m) { Set-Content "$W\STATUS.txt" "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $m"; Add-Content "$W\chain.log" "$(Get-Date -f 'HH:mm:ss') $m" }
$raArgs = @('-Dir', $Dir, '-Ep', $Ep, '-BgDir', $BgDir, '-FrameSuffix', $Suffix, '-Title', $Title, '-Guests', $Guests, '-Tempo', "$Tempo", '-QcRetries', "$QcRetries")
if ($Multi) { $raArgs += @('-Series', 'Burnout Society', '-Multi') } else { $raArgs += '-OneOff' }
if (-not $NoVramFree) { $raArgs += '-Scheduled' }

if ($Inner) {
  St "wrapper started (pid $PID) guests=$Guests tempo=$Tempo qcretries=$QcRetries vram_free=$(-not $NoVramFree) multi=$Multi"
  & powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\run_episode.ps1" @raArgs
  $last = (gc "$W\STATUS.txt" -Raw)
  if ($last -match 'ALL DONE \(post exit (\d+)\)') {
    $pe = [int]$matches[1]
    if ($pe -eq 3) {
      $dur = 0; $m = (gc "$W\post.log" -ErrorAction SilentlyContinue | sls 'mixed dur ([\d.]+) s' | select -Last 1); if ($m) { $dur = [double]$m.Matches[0].Groups[1].Value }
      if ($dur -gt 0 -and $dur -lt 2280) {
        St "post exit 3: mix $dur s < 2280 -> re-running POST ONLY with -SegGap 1.2 -StingPad 0.6 (no TTS)"
        $nm = if ($Multi) { @('-Series', 'Burnout Society', '-Multi') } else { @('-OneOff') }
        & powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\post_episode.ps1" -Dir $W -Ep $Ep -Bg "$BgDir\backgrounds.json" -FrameSuffix $Suffix -Title $Title -SegGap 1.2 -StingPad 0.6 @nm *> "$W\post2.out.txt"
        $pe2 = $LASTEXITCODE
        if ($pe2 -eq 0) { St "ALL DONE (post exit 0 after SegGap 1.2/StingPad 0.6 retry)" } else { St "STOP post retry exit $pe2 (mix still outside 2280-2880 s?): see post.log" }
      } else { St "STOP duration gate failed (mix $dur s, exit 3): too long or unknown - needs a human decision (see post.log); do not slow the tempo for length" }
    } elseif ($pe -ne 0) { St "STOP post failed with exit $pe (see post.out.txt / post.log)" }
  } else { St "STOP run_episode ended without ALL DONE (see chain.log / render.log)" }
  exit 0
}

# ---------------- preflight ----------------
$bad = @(); $ok = @()
function Chk($c, $m) { if ($c) { $script:ok += $m } else { $script:bad += $m } }
$gv = @($Guests -split ',' | % { $_.Trim() } | ? { $_ }); Chk ($gv.Count -eq 2) "-Guests has two names ($Guests)"
foreach ($f in 'burnout_society_ep1_script.json', 'bb\burnout_society_ep1.chapters.in.json', 'bg_bb1\prompts.json', 'bg_bb1\backgrounds.json', 'learn\burnout_society_ep1_details_meta.md', 'run_episode.ps1', 'render7b.ps1', 'post_episode.ps1', 'post_segment.ps1', 'podcast.ps1', 'vram_free.ps1', 'vram_free.json', 'md_clean.py', 'pick_cast.py', 'episodes_index.py', 'episodes_index.json', 'voices.json', 'voice_f0.json', 'qc_vv.py', 'qc_takes.py', 'qc_mix.py', 'align.py', 'make_video.py', 'hwrun.ps1', 'gen_backgrounds_flux.py', 'vv7b_generate.py', 'tools\split_segments.py', 'ui1\intro.wav', 'ui1\sting.wav', 'ui1\outro.wav', 'tests\vv7b_cpp\bin\audiocpp_cli.exe', 'tests\vv7b_cpp\models\vibevoice-7b-q8_0.gguf', 'venv_vv\Scripts\python.exe', 'venv_whisper\Scripts\python.exe', 'venv_sd\Scripts\python.exe', 'venv_video\Scripts\python.exe', 'VibeVoice-main\demo\voices\en-Carter_man.wav') { Chk (Test-Path "$Root\$f") "exists $f" }
$vo = gc "$Root\voices.json" -Raw | ConvertFrom-Json
foreach ($g in $gv) { $e = $vo.voices.$g; Chk ($e -and (Test-Path "$Root\$($e.file)")) "voice $g exists ($($e.file))" }
Chk ((Test-Path "$Root\voices_extra\LICENSES.md")) 'voices_extra\LICENSES.md exists'
Chk (Test-Path 'C:\Users\TJ\.cache\huggingface\hub\models--unsloth--FLUX.1-schnell\snapshots\9df3faa7ae3b6ddf0b2b69bb78616372897cc65c\model_index.json') 'FLUX.1-schnell snapshot'
foreach ($f in 'run_episode.ps1', 'render7b.ps1', 'post_episode.ps1', 'post_segment.ps1', 'vram_free.ps1', 'podcast.ps1') { $e = $null; [void][Management.Automation.Language.Parser]::ParseFile("$Root\$f", [ref]$null, [ref]$e); Chk ($e.Count -eq 0) "PowerShell parse $f" }
$re = gc "$Root\run_episode.ps1" -Raw; $pe_ = gc "$Root\post_episode.ps1" -Raw; $r7 = gc "$Root\render7b.ps1" -Raw
Chk ($re -match 'PODCAST_SCHEDULED' -and $re -match 'md_clean.py') 'run_episode.ps1 has the vram_free hook + md_clean step'
Chk ($re -match '\[int\]\$QcRetries = 1' -and $r7 -match '\[int\]\$QcRetries = 1') 'v1.8: QcRetries default 1 (run_episode, render7b)'
Chk ($pe_ -match '\$MinDur = 2280' -and $pe_ -match '\$MaxDur = 2880') 'v1.8: duration window 2280-2880 s in post_episode.ps1'
Chk ($pe_ -match 'episodes_index.py' -and $re -match '-OneOff') 'v1.8: naming/registry hooks present'
Chk ($r7 -match '\[double\]\$Tempo = 0.93') 'render7b default tempo 0.93'
$S = gc $ScriptSrc -Raw -Encoding UTF8 | ConvertFrom-Json; $wc = 0; $S | % { $wc += ($_.text -split '\s+' | ? { $_ }).Count }
Chk ($S.Count -eq $ExpLines) "script lines = $($S.Count) (expect $ExpLines)"; Chk ($wc -eq $ExpWords) "script words = $wc (expect $ExpWords)"
Chk ((@($S | ? { $_.speaker -notin 'Host','Guest','Guest2' })).Count -eq 0) 'speakers are Host/Guest/Guest2 only'
$C = gc "$Root\bb\burnout_society_ep1.chapters.in.json" -Raw | ConvertFrom-Json; $starts = @($C.sections | % { $_.start }); Chk ($C.sections.Count -eq 10 -and $starts[0] -eq 0 -and ($starts | measure -Maximum).Maximum -lt $S.Count) "chapters: $($C.sections.Count) sections, last start $($starts[-1])"
$P = gc "$Root\bg_bb1\prompts.json" -Raw | ConvertFrom-Json; Chk ($P.images.Count -eq 22) "prompts = $($P.images.Count) (expect 22)"
$B = gc "$Root\bg_bb1\backgrounds.json" -Raw | ConvertFrom-Json; Chk ($B.Count -eq 22) "backgrounds.json entries = $($B.Count)"
$maxl = ($B.line | measure -Maximum).Maximum; $stale = ($maxl -lt [int]($S.Count * 0.8)); Chk (-not $stale -or $RescaleBackgrounds) "backgrounds fit the script (last image at line $maxl of $($S.Count))"
Chk ((@($P.images.id) -join ',') -eq ((@($B.image) | % { $_ -replace '\.png$', '' }) -join ',')) 'prompt ids match backgrounds.json images'
Chk ([bool]($vo.voices.Clara.credit -and $vo.voices.Marcus.credit)) 'CC BY credit lines for Clara + Marcus in voices.json (post_episode appends them to notes + chapters)'
Chk (-not ($S | ? { $_.text -match '\bMaya\b' })) 'dialogue no longer names Maya (cast is Clara)'
Chk ((@($vo.pool.guests) -contains 'Clara') -and (@($vo.pool.guests) -contains 'Marcus')) 'Clara and Marcus are in the random pool (no exclusion warning)'
$cast = & $py "$Root\pick_cast.py" --out "$env:TEMP\bb_cast_check.json" --host Carter --roles 'Guest,Guest2' --guests $Guests --force 2>&1 | Out-String
$castWarnOk = ($cast -notmatch 'WARN') ; Chk ($cast -match "guest=$($gv[0]) guest2=$($gv[1])" -and $castWarnOk) "pick_cast override ok (no warnings expected): $($cast.Trim())"; Remove-Item "$env:TEMP\bb_cast_check.json" -ea 0
foreach ($x in 'mp3', 'mp4', 'srt', 'json') { Chk (-not (Test-Path "$Root\episodes\$Ep.$x")) "episodes\$Ep.$x does not exist yet" }
$plan = & $py "$Root\episodes_index.py" plan --ep $Ep --title $Title $(if ($Multi) { '--series'; 'Burnout Society'; '--multi' } else { '--oneoff' }) 2>&1 | Out-String | ConvertFrom-Json
Chk ($plan.display_title -and $plan.display_title -notmatch 'Episode') "naming plan: #$($plan.number) overall, title '$($plan.display_title)', corner label '$($plan.label)'"
$free = [math]::Round((Get-PSDrive C).Free / 1GB); Chk ($free -ge 60) "disk free C: $free GB (need >= 60)"
$lo = [int]($wc * 0.37 + 60); $mid = [int]($wc * 0.384 + 60); $hi = [int]($wc * 0.39 + 60); Write-Host ("Expected mix at tempo {0}: {1:N0}-{2:N0} s (centre {3:N0} s = {4}:{5:00}); window 2280-2880 s" -f $Tempo, $lo, $hi, $mid, [int][math]::Floor($mid / 60), ($mid % 60))
try { $om = @((Invoke-RestMethod http://localhost:11434/api/ps -TimeoutSec 3).models).Count } catch { $om = 0 }; if ($om) { Write-Host "NOTE: Ollama has $om model(s) loaded; run_episode waits until it is empty (does not unload it)" } else { $ok += 'Ollama is empty' }
$busy = @(Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'run_episode\.ps1|render7b\.ps1|post_episode\.ps1|vv7b_generate|gen_backgrounds|make_video\.py|start_(mike_ma|burnout_society)_ep1\.ps1 .*-Inner' -and $_.ProcessId -ne $PID -and $_.Name -match 'powershell|python|audiocpp' }); Chk ($busy.Count -eq 0) "no pipeline job running ($($busy.Count))"
if (Test-Path "$W\STATUS.txt") { Write-Host "NOTE: existing $W\STATUS.txt: $(gc "$W\STATUS.txt" -Raw)".Trim() }
Write-Host "--- preflight OK items: $($ok.Count)"; if ($DryRun) { $ok | % { Write-Host "  ok  $_" } }
if ($stale -and -not $RescaleBackgrounds) { Write-Host "WARNING: bg_bb1\backgrounds.json lines end at $maxl but the script has $($S.Count) lines: use -RescaleBackgrounds -FromLines <old line count> (backup kept)." }
if ($RescaleBackgrounds -and $FromLines -le 0) { $bad += '-RescaleBackgrounds needs -FromLines <old line count>' }
if ($bad.Count) { $bad | % { Write-Host "  FAIL $_" }; Write-Host "ABORT: $($bad.Count) preflight problem(s), nothing started"; exit 1 }
& $py "$Root\tools\split_segments.py" $ScriptSrc "$W\burnout_society_ep1.chapters.in.json" $W --expect_lines $ExpLines --expect_words $ExpWords $(if ($DryRun) { '--dry' })
if ($LASTEXITCODE) { Write-Host "ABORT: split failed"; exit 1 }
if ($RescaleBackgrounds) { & $py "$Root\tools\split_segments.py" --rescale_bg "$Root\bg_bb1\backgrounds.json" --from_lines $FromLines --to_lines $ExpLines $(if ($DryRun) { '--dry' }) }
$cmd = "powershell -NoProfile -ExecutionPolicy Bypass -File $Root\run_episode.ps1 " + (($raArgs | % { if ($_ -match '[\s?'']') { "'" + ($_ -replace "'", "''") + "'" } else { $_ } }) -join ' ')
if ($DryRun) { Write-Host "DRY RUN: nothing written/started. The wrapper would run:`n  $cmd`n  (then the post-only retry with -SegGap 1.2 -StingPad 0.6 if the mix is < 2280 s)"; exit 0 }
foreach ($f in 'intro.wav', 'sting.wav', 'outro.wav') { if (-not (Test-Path "$W\$f")) { Copy-Item "$Root\ui1\$f" "$W\$f" } }
Remove-Item "$W\STATUS.txt" -ea 0; St 'launching detached wrapper'
$a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$Root\tools\start_burnout_society_ep1.ps1", '-Inner', '-Tempo', "$Tempo", '-QcRetries', "$QcRetries", '-Guests', $Guests); if ($NoVramFree) { $a += '-NoVramFree' }; if ($Multi) { $a += '-Multi' }
$p = Start-Process powershell -ArgumentList $a -WindowStyle Hidden -PassThru
Write-Host "STARTED detached wrapper pid $($p.Id) at $(Get-Date -f 'HH:mm:ss'). Poll: Get-Content $W\STATUS.txt ; Get-Content $W\chain.log -Tail 15"