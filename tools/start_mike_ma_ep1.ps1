<#  start_mike_ma_ep1.ps1 (2026-10-15) - ONE-CALL launcher for "Mike Ma: Harassment Architecture and Gothic Violence, Episode 1" (code_v1.5/1.6 pipeline).
Start (returns at once; the job runs detached/hidden):
  powershell -NoProfile -ExecutionPolicy Bypass -File C:\grok\podcast\tools\start_mike_ma_ep1.ps1
Poll with short calls:  Get-Content C:\grok\podcast\mm\STATUS.txt ; Get-Content C:\grok\podcast\mm\chain.log -Tail 15
Dry run (checks everything, writes nothing, starts nothing, prints the exact commands):  ... -File ...\start_mike_ma_ep1.ps1 -DryRun
What it does: preflight (aborts on any problem) -> mm\segNN.json from mike_ma_ep1_script.json at the chapter starts (tools\split_segments.py, text untouched) + intro/sting/outro from ui1 ->
  detached wrapper -> run_episode.ps1 (cast Carter/Declan/Isla via -Guests, -Tempo 0.93 (v1.8), -Scheduled = vram_free hook; md_clean italic strip, 7B TTS + QC retries, FLUX backgrounds, post: mix, duration gate, align, qc_mix, video, 64k mp3, credits)
  -> if the duration gate fails SHORT (<2280 s, v1.8) the wrapper re-runs ONLY post with -SegGap 1.2 -StingPad 0.6 (no TTS); anything else outside 2280-2880 s stops with STATUS "STOP ..." for a human decision.
Never overwrites episodes\mike_ma_ep1.* (post aborts). Resumable: run it again (segments with mp3+qc.json are skipped, an existing mm\cast.json is reused).  #>
param([switch]$DryRun, [switch]$NoVramFree, [double]$Tempo = 0.93, [switch]$RescaleBackgrounds, [switch]$Inner, [string]$Root = "C:\grok\podcast")
$ErrorActionPreference = 'Continue'; cd $Root
$Dir = 'mm'; $Ep = 'mike_ma_ep1'; $BgDir = 'bg_mm1'; $Suffix = '_mm1'; $W = "$Root\$Dir"
$Title = 'Mike Ma: Harassment Architecture and Gothic Violence, Episode 1'
$py = "$Root\venv_vv\Scripts\python.exe"
function St($m) { Set-Content "$W\STATUS.txt" "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $m"; Add-Content "$W\chain.log" "$(Get-Date -f 'HH:mm:ss') $m" }
$raArgs = @('-Dir', $Dir, '-Ep', $Ep, '-BgDir', $BgDir, '-FrameSuffix', $Suffix, '-Title', $Title, '-Guests', 'Declan,Isla', '-Tempo', "$Tempo")
if (-not $NoVramFree) { $raArgs += '-Scheduled' }

if ($Inner) {
  St "wrapper started (pid $PID) tempo=$Tempo vram_free=$(-not $NoVramFree)"
  & powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\run_episode.ps1" @raArgs
  $last = (gc "$W\STATUS.txt" -Raw)
  if ($last -match 'ALL DONE \(post exit (\d+)\)') {
    $pe = [int]$matches[1]
    if ($pe -eq 3) {
      $dur = 0; $m = (gc "$W\post.log" -ErrorAction SilentlyContinue | sls 'mixed dur ([\d.]+) s' | select -Last 1); if ($m) { $dur = [double]$m.Matches[0].Groups[1].Value }
      if ($dur -gt 0 -and $dur -lt 2280) {
        St "post exit 3: mix $dur s < 2280 -> re-running POST ONLY with -SegGap 1.2 -StingPad 0.6 (no TTS)"
        & powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\post_episode.ps1" -Dir $W -Ep $Ep -Bg "$BgDir\backgrounds.json" -FrameSuffix $Suffix -Title $Title -SegGap 1.2 -StingPad 0.6 *> "$W\post2.out.txt"
        $pe2 = $LASTEXITCODE
        if ($pe2 -eq 0) { St "ALL DONE (post exit 0 after SegGap 1.2/StingPad 0.6 retry)" } else { St "STOP post retry exit $pe2 (mix still outside 2280-2880 s?): see post.log; next levers: re-post from kept raw wavs with -Tempo 0.93 (v1.8: do not slow down for length) -> stretch pauses (tools\stretch_pauses_repost_ui1.py pattern)" }
      } else { St "STOP duration gate failed (mix $dur s, exit 3): too long or unknown - needs a human decision (see post.log)" }
    } elseif ($pe -ne 0) { St "STOP post failed with exit $pe (see post.out.txt / post.log)" }
  } else { St "STOP run_episode ended without ALL DONE (see chain.log / render.log)" }
  exit 0
}

# ---------------- preflight ----------------
$bad = @(); $ok = @()
function Chk($c, $m) { if ($c) { $script:ok += $m } else { $script:bad += $m } }
foreach ($f in 'mike_ma_ep1_script.json', 'mm\mike_ma_ep1.chapters.in.json', 'bg_mm1\prompts.json', 'bg_mm1\backgrounds.json', 'learn\mike_ma_ep1_details_meta.md', 'run_episode.ps1', 'render7b.ps1', 'post_episode.ps1', 'post_segment.ps1', 'podcast.ps1', 'vram_free.ps1', 'vram_free.json', 'md_clean.py', 'pick_cast.py', 'voices.json', 'voice_f0.json', 'qc_vv.py', 'qc_takes.py', 'qc_mix.py', 'align.py', 'make_video.py', 'hwrun.ps1', 'gen_backgrounds_flux.py', 'vv7b_generate.py', 'tools\split_segments.py', 'ui1\intro.wav', 'ui1\sting.wav', 'ui1\outro.wav', 'tests\vv7b_cpp\bin\audiocpp_cli.exe', 'tests\vv7b_cpp\models\vibevoice-7b-q8_0.gguf', 'venv_vv\Scripts\python.exe', 'venv_whisper\Scripts\python.exe', 'venv_sd\Scripts\python.exe', 'venv_video\Scripts\python.exe', 'voices_extra\en-Declan_man.wav', 'voices_extra\en-Isla_woman.wav') { Chk (Test-Path "$Root\$f") "exists $f" }
Chk (Test-Path 'C:\Users\TJ\.cache\huggingface\hub\models--unsloth--FLUX.1-schnell\snapshots\9df3faa7ae3b6ddf0b2b69bb78616372897cc65c\model_index.json') 'FLUX.1-schnell snapshot'
foreach ($f in 'run_episode.ps1', 'render7b.ps1', 'post_episode.ps1', 'post_segment.ps1', 'vram_free.ps1', 'podcast.ps1') { $e = $null; [void][Management.Automation.Language.Parser]::ParseFile("$Root\$f", [ref]$null, [ref]$e); Chk ($e.Count -eq 0) "PowerShell parse $f" }
Chk ((gc "$Root\post_episode.ps1" -Raw) -notmatch '\\n  \$castnote') 'post_episode.ps1 has no literal \n bug'
Chk ((gc "$Root\run_episode.ps1" -Raw) -match 'PODCAST_SCHEDULED' -and (gc "$Root\run_episode.ps1" -Raw) -match 'md_clean.py') 'run_episode.ps1 has the vram_free hook + md_clean step'
$S = gc "$Root\mike_ma_ep1_script.json" -Raw | ConvertFrom-Json; $wc = 0; $S | % { $wc += ($_.text -split '\s+' | ? { $_ }).Count }
Chk ($S.Count -eq 207) "script lines = $($S.Count) (expect 207)"; Chk ($wc -eq 6191) "script words = $wc (expect 6191)"
$P = gc "$Root\bg_mm1\prompts.json" -Raw | ConvertFrom-Json; Chk ($P.images.Count -eq 22) "prompts = $($P.images.Count) (expect 22)"
$B = gc "$Root\bg_mm1\backgrounds.json" -Raw | ConvertFrom-Json; Chk ($B.Count -eq 22) "backgrounds.json entries = $($B.Count)"
$maxl = ($B.line | measure -Maximum).Maximum; $stale = ($maxl -lt 190)
$vo = gc "$Root\voices.json" -Raw | ConvertFrom-Json; Chk ([bool]($vo.voices.Declan.credit -and $vo.voices.Isla.credit)) 'CC BY credit lines for Declan + Isla in voices.json'
$cast = & $py "$Root\pick_cast.py" --out "$env:TEMP\mm_cast_check.json" --host Carter --roles 'Guest,Guest2' --guests 'Declan,Isla' --force 2>&1 | Out-String; Chk ($cast -match 'guest=Declan guest2=Isla') "pick_cast override ok: $($cast.Trim())"; Remove-Item "$env:TEMP\mm_cast_check.json" -ea 0
foreach ($x in 'mp3', 'mp4', 'srt', 'json') { Chk (-not (Test-Path "$Root\episodes\$Ep.$x")) "episodes\$Ep.$x does not exist yet" }
$free = [math]::Round((Get-PSDrive C).Free / 1GB); Chk ($free -ge 60) "disk free C: $free GB (need >= 60)"
try { $om = @((Invoke-RestMethod http://localhost:11434/api/ps -TimeoutSec 3).models).Count } catch { $om = 0 }; if ($om) { Write-Host "NOTE: Ollama has $om model(s) loaded; run_episode waits until it is empty (does not unload it)" }
$busy = @(Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'run_episode\.ps1|render7b\.ps1|post_episode\.ps1|vv7b_generate|gen_backgrounds|make_video\.py|start_mike_ma_ep1\.ps1 .*-Inner' -and $_.ProcessId -ne $PID -and $_.Name -match 'powershell|python|audiocpp' }); Chk ($busy.Count -eq 0) "no pipeline job running ($($busy.Count))"
if (Test-Path "$W\STATUS.txt") { Write-Host "NOTE: existing $W\STATUS.txt: $(gc "$W\STATUS.txt" -Raw)".Trim() }
Write-Host "--- preflight OK items: $($ok.Count)"; if ($DryRun) { $ok | % { Write-Host "  ok  $_" } }
if ($stale) { Write-Host "WARNING: bg_mm1\backgrounds.json lines end at $maxl but the script has 207 lines (made for the 165-line v2.1): the last image would stay up for the last quarter of the episode. Use -RescaleBackgrounds (x207/165, backup kept) or have the backgrounds regenerated." }
if ($bad.Count) { $bad | % { Write-Host "  FAIL $_" }; Write-Host "ABORT: $($bad.Count) preflight problem(s), nothing started"; exit 1 }
& $py "$Root\tools\split_segments.py" "$Root\mike_ma_ep1_script.json" "$W\mike_ma_ep1.chapters.in.json" $W --expect_lines 207 --expect_words 6191 $(if ($DryRun) { '--dry' })
if ($LASTEXITCODE) { Write-Host "ABORT: split failed"; exit 1 }
if ($RescaleBackgrounds) { & $py "$Root\tools\split_segments.py" --rescale_bg "$Root\bg_mm1\backgrounds.json" --from_lines 165 --to_lines 207 $(if ($DryRun) { '--dry' }) }
$cmd = "powershell -NoProfile -ExecutionPolicy Bypass -File $Root\run_episode.ps1 " + (($raArgs | % { if ($_ -match '\s') { "'$_'" } else { $_ } }) -join ' ')
if ($DryRun) { Write-Host "DRY RUN: nothing written/started. The wrapper would run:`n  $cmd`n  (then the post-only retry with -SegGap 1.2 -StingPad 0.6 if the mix is < 2280 s)"; exit 0 }
foreach ($f in 'intro.wav', 'sting.wav', 'outro.wav') { if (-not (Test-Path "$W\$f")) { Copy-Item "$Root\ui1\$f" "$W\$f" } }
Remove-Item "$W\STATUS.txt" -ea 0; St 'launching detached wrapper'
$a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$Root\tools\start_mike_ma_ep1.ps1", '-Inner', '-Tempo', "$Tempo"); if ($NoVramFree) { $a += '-NoVramFree' }
$p = Start-Process powershell -ArgumentList $a -WindowStyle Hidden -PassThru
Write-Host "STARTED detached wrapper pid $($p.Id) at $(Get-Date -f 'HH:mm:ss'). Poll: Get-Content $W\STATUS.txt ; Get-Content $W\chain.log -Tail 15"
