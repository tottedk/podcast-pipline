<#  run_episode.ps1 (template v1.3, 2026-10-15; v1.12 2026-10-21: drama3 PER-SPEAKER tempo per chunk (drama3_tempo.json map + auto-calibration to 160 wpm, -GlobalTempo = v1.11 mode, -TempoCfg), voice->reference map drama3_ref_map.json (Elliot -> Elliot_v2), pause clamp v2 (-20 dB, cap 0.4 s), leading guest [sighs] stripped (md_clean), BLOCKING mix QC in post (per-speaker wpm 145-175, intra-line pause <= 1.5 s; post exit 7 = nothing published; -NoMixGate only by Thomas' decision); v1.11 2026-10-20: drama3 tempo 0.90 (~155 wpm measured), -ChunkWords (drama3 default 100), STOP on GENFAIL/SPKFAIL/missing segment BEFORE FLUX/post (exit 6), -OutDir passthrough, engine name to post_episode, final unload + ollama ps log; v1.8: -QcRetries 1 default, -Series/-Multi/-OneOff naming passthrough; v1.9: -Engine 7b|drama3; v1.10: default drama3, per-engine tempo drama3 1.05 / 7b 0.93, -DryRun) - DETACHED orchestrator: CAST PICK (pick_cast.py -> <Dir>\cast.json) -> render7b -> unload check -> FLUX backgrounds (only missing images) -> post_episode. Writes <Dir>\STATUS.txt + chain.log.
Start it detached and poll STATUS.txt with short calls:
  Start-Process powershell -ArgumentList '-ExecutionPolicy','Bypass','-File','C:\grok\podcast\run_episode.ps1','-Dir','ui1','-Ep','uploaded_intelligence_ep1','-BgDir','bg_ui1','-FrameSuffix','_ui1','-Guest2Voice','Maya' -WindowStyle Hidden
Cast: NO default cast; host = Carter unless -HostVoice. Guests are picked at random from the pool (pick_cast.py; seed logged to cast.json, STATUS.txt and the notes). -GuestGenders "M,F" = script wants Guest male, Guest2 female. -Guests "Marcus,Isla" overrides. -CastSeed N reproduces a pick. An existing <Dir>\cast.json is reused (resume).
Engine (v1.11): -Engine drama3 (DEFAULT, render_drama3.ps1 = Fish Audio Drama 3 Q4_K_S, tempo 0.90 ~155 wpm, 100 words per request, one speaker per request, voice-match gate) or -Engine 7b (fallback, render7b.ps1 = VibeVoice-7B Q8, tempo 0.93). -Tempo 0 (default) = engine default; an explicit -Tempo overrides. -DryRun prints the resolved engine/script/tempo and exits (nothing written/started).
Needs in <Dir>: segNN.json, intro.wav, sting.wav, outro.wav, <Ep>.chapters.in.json; in <BgDir>: prompts.json + backgrounds.json.  #>
param([Parameter(Mandatory)][string]$Dir, [Parameter(Mandatory)][string]$Ep, [Parameter(Mandatory)][string]$BgDir, [string]$FrameSuffix = "_ep", [string]$Title = "",
  [string]$HostVoice = "Carter", [string]$Guests = "", [string]$GuestGenders = "", [int]$CastSeed = 0, [double]$Tempo = 0, [double]$SegGap = 0.4, [double]$StingPad = 0, [int]$QcRetries = 1, [ValidateSet("7b","drama3")][string]$Engine = "drama3", [int]$ChunkWords = 0, [string]$OutDir = "episodes", [string]$Series = "", [switch]$Multi, [switch]$OneOff, [string]$Root = "C:\grok\podcast", [switch]$Scheduled, [switch]$DryRun, [string]$TempoCfg = "", [switch]$GlobalTempo, [switch]$NoMixGate)
$ErrorActionPreference = 'Continue'; (Get-Process -Id $PID).PriorityClass = 'Idle'; cd $Root
if ($Tempo -le 0) { $Tempo = if ($Engine -eq 'drama3') { 0.90 } else { 0.93 } }   # v1.11: per-engine default tempo (drama3 0.90 = ~155 wpm: Drama 3 raw pace 172 wpm measured on Fault Lines #1; 1.05 gave 181 wpm), 7b 0.93; an explicit -Tempo overrides
if ($ChunkWords -le 0) { $ChunkWords = if ($Engine -eq 'drama3') { 100 } else { 150 } }   # v1.11: drama3 100 words per request (runaway/OOM at 150)
if ($DryRun) { $rsD = if ($Engine -eq 'drama3') { 'render_drama3.ps1' } else { 'render7b.ps1' }; $tcD = if ($TempoCfg) { $TempoCfg } else { "$Root\drama3_tempo.json" }; $tcj = gc $tcD -Raw -EA 0 | ConvertFrom-Json
  $tvD = (@($tcj.voices.PSObject.Properties | % { "$($_.Name)=$($_.Value)" })) -join ','
  $tmD = if ($Engine -ne 'drama3') { "global $Tempo (post)" } elseif ($GlobalTempo) { "GLOBAL $Tempo (post, v1.11 mode)" } else { "per-speaker cfg=$tcD fallback=$Tempo [$tvD; unmapped refs auto -> $($tcj.target_wpm) wpm, $($tcj.min_tempo)-$($tcj.max_tempo)]" }
  $rmD = ((gc "$Root\drama3_ref_map.json" -Raw -EA 0 | ConvertFrom-Json).map.PSObject.Properties | % { "$($_.Name)->$($_.Value)" }) -join ','
  Write-Output "DRYRUN engine=$Engine script=$rsD tempo=$tmD refmap=$rmD mixgate=$(if ($NoMixGate) { 'OFF' } else { 'on (145-175 wpm, pause<=1.5s)' }) chunkwords=$ChunkWords qcretries=$QcRetries dir=$Dir outdir=$OutDir stop_on_genfail=yes voice_gate=$(if ($Engine -eq 'drama3') { 'spk_check.py' } else { 'n/a' })"; exit 0 }   # v1.10: nothing written/started
$W = if ([IO.Path]::IsPathRooted($Dir)) { $Dir } else { Join-Path $Root $Dir }; $tpl = Split-Path $MyInvocation.MyCommand.Path
function Tool($n) { if (Test-Path "$Root\$n") { "$Root\$n" } else { "$tpl\$n" } }
function St($m) { Set-Content "$W\STATUS.txt" "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') $m"; Add-Content "$W\chain.log" "$(Get-Date -f 'HH:mm:ss') $m" }
St 'step=start'
# --- cast: random pick unless <Dir>\cast.json exists (resume) ---
if (-not (Test-Path "$W\cast.json")) {
  $g2 = (gci "$W\seg??.json" | % { gc $_ -Raw } | sls '"speaker"\s*:\s*"Guest2"' -Quiet)
  $pa = @("$Root\venv_vv\Scripts\python.exe", (Tool 'pick_cast.py'), '--out', "$W\cast.json", '--host', $HostVoice, '--roles', $(if ($g2) { 'Guest,Guest2' } else { 'Guest' }))
  if ($GuestGenders) { $pa += '--genders', $GuestGenders }; if ($Guests) { $pa += '--guests', $Guests }; if ($CastSeed) { $pa += '--seed', $CastSeed }
  $pl = & $pa[0] $pa[1..($pa.Count-1)] 2>&1 | Out-String; Add-Content "$W\chain.log" $pl
}
if (-not (Test-Path "$W\cast.json")) { St 'ABORT cast pick failed (see chain.log)'; exit 4 }
$cj = gc "$W\cast.json" -Raw | ConvertFrom-Json; $HostVoice = $cj.host; $GuestVoice = $cj.guest; $Guest2Voice = $cj.guest2
St "cast: host=$HostVoice guest=$GuestVoice guest2=$Guest2Voice mode=$($cj.mode) pick_seed=$($cj.seed) warnings=$($cj.warnings -join '; ')"
# --- v1.4: strip markdown marks (*x*, **x**, _x_, `x`, leading #/-/>) from the segment scripts BEFORE TTS (in place; <seg>.pre_md.json saved only if something changed; speaker field untouched)
foreach ($sj in (gci "$W\seg??.json")) { $mo = & "$Root\venv_vv\Scripts\python.exe" (Tool 'md_clean.py') $sj.FullName 2>&1 | Out-String; Add-Content "$W\chain.log" $mo.Trim() }
# --- v1.5: nightly/scheduled runs only (-Scheduled or env PODCAST_SCHEDULED=1): free GPU VRAM by closing configured GPU-hungry apps GRACEFULLY (C:\grok\vram\vram_free.ps1 -Free -Scheduled; guarded: user idle, foreground, audio, fullscreen; never kills; log in hwlogs\vram_free_<date>.log). Manual runs while Thomas is at the PC do nothing here.
if ($Scheduled -or $env:PODCAST_SCHEDULED -eq '1') { $vf = 'C:\grok\vram\vram_free.ps1'; if (Test-Path $vf) { $vo = & powershell -NoProfile -ExecutionPolicy Bypass -File $vf -Free -Scheduled 2>&1 | Out-String; Add-Content "$W\chain.log" $vo.Trim() } }
while (((Invoke-RestMethod http://localhost:11434/api/ps -EA SilentlyContinue).models).Count -gt 0) { St 'waiting for Ollama to be empty'; Start-Sleep 15 }
$rs = if ($Engine -eq 'drama3') { 'render_drama3.ps1' } else { 'render7b.ps1' }   # v1.9: TTS engine switch (v1.10: default drama3)
St "step=TTS engine=$Engine ($rs) tempo=$Tempo"
$rsx = @(); if ($Engine -eq 'drama3') { $rsx += '-ChunkWords', $ChunkWords; if ($TempoCfg) { $rsx += '-TempoCfg', $TempoCfg }; if ($GlobalTempo) { $rsx += '-GlobalTempo' } }
& powershell -ExecutionPolicy Bypass -File (Tool $rs) -Dir $W -HostVoice $HostVoice -Tempo $Tempo -QcRetries $QcRetries @rsx *> "$W\render.log"
$rrc = $LASTEXITCODE
while (Get-Process audiocpp_cli -EA 0) { Start-Sleep 5 }
# v1.11: STOP before FLUX/post on any GENFAIL / SPKFAIL / missing or unfinished segment (v1.10 went on to FLUX + post after a GENFAIL)
$rl = gc "$W\render.log" -EA 0; $bad = @()
foreach ($sj in (gci "$W\seg??.json" | sort Name)) { $b = $sj.BaseName
  if (-not (Test-Path "$W\$b.mp3")) { $bad += "$b.mp3 missing" }
  elseif (-not (Test-Path "$W\$b.qc.json")) { $bad += "$b.qc.json missing" }
  else { $qj = gc "$W\$b.qc.json" -Raw | ConvertFrom-Json; if (-not $qj.final) { $bad += "$b not final" }; if (@($qj.voice_redo | ? { $_ -ne $null }).Count) { $bad += "$b wrong voice in chunk(s) $($qj.voice_redo -join ',')" } } }
$gf = @($rl | sls '^(GENFAIL|SPKFAIL|POSTFAIL)' | % { $_.Line })
if ($rrc -or $gf.Count -or $bad.Count) {
  St "STOP TTS incomplete (render exit $rrc): $((@($gf) + $bad) -join ' | ') - no FLUX, no post, nothing shipped"
  Invoke-RestMethod http://localhost:11434/api/ps -EA SilentlyContinue | % { $_.models } | % { Invoke-RestMethod http://localhost:11434/api/generate -Method Post -Body (@{model=$_.name;keep_alive=0}|ConvertTo-Json) }
  exit 6 }
St "step=TTS done engine=$Engine $((gc $W\render.log | sls SEGDONE).Count) segs (all segments present, voices ok)"
$imgs = (gc -Raw "$BgDir\prompts.json" | ConvertFrom-Json).images.id | ? { -not (Test-Path "$BgDir\$_.png") }
if ($imgs) { $env:HIP_VISIBLE_DEVICES = '1'; St "step=FLUX $($imgs.Count) images"; $t = Get-Date
  $fluxSnap = if ($env:FLUX_SNAPSHOT) { $env:FLUX_SNAPSHOT } else { Join-Path $env:USERPROFILE '.cache\huggingface\hub\models--unsloth--FLUX.1-schnell\snapshots\9df3faa7ae3b6ddf0b2b69bb78616372897cc65c' }
  & powershell -ExecutionPolicy Bypass -File .\hwrun.ps1 -Name "flux_$Ep" venv_sd\Scripts\python.exe gen_backgrounds_flux.py "$BgDir\prompts.json" $BgDir --model "$fluxSnap" --offload staged --fp8 1 *> "$W\flux.log"
  St "step=FLUX done exit $LASTEXITCODE in $([int]((Get-Date)-$t).TotalSeconds) s" }
$nm = @(); if ($NoMixGate) { $nm += '-NoMixGate' }; if ($Series) { $nm += '-Series', $Series }; if ($Multi) { $nm += '-Multi' }; if ($OneOff) { $nm += '-OneOff' }   # v1.8 naming (post_episode.ps1 / episodes_index.py)
$engName = if ($Engine -eq 'drama3') { 'Fish Audio Drama 3 (Q4_K_S GGUF) via audio.cpp' } else { 'VibeVoice-7B Q8 via audio.cpp' }
& powershell -ExecutionPolicy Bypass -File (Tool 'post_episode.ps1') -Dir $W -Ep $Ep -Bg "$BgDir\backgrounds.json" -FrameSuffix $FrameSuffix -Title $Title -HostVoice $HostVoice -SegGap $SegGap -StingPad $StingPad -OutDir $OutDir -EngineName $engName @nm *> "$W\post.out.txt"
$pe = $LASTEXITCODE
Invoke-RestMethod http://localhost:11434/api/ps -EA SilentlyContinue | % { $_.models } | % { Invoke-RestMethod http://localhost:11434/api/generate -Method Post -Body (@{model=$_.name;keep_alive=0}|ConvertTo-Json) }
Start-Sleep 2; Add-Content "$W\chain.log" "ollama ps after run_episode: $((& ollama ps 2>&1 | Out-String).Trim())"
St "step=ALL DONE (post exit $pe)"
