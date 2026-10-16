<#  run_episode.ps1 (template v1.3, 2026-10-15; v1.8: -QcRetries 1 default, -Series/-Multi/-OneOff naming passthrough) - DETACHED orchestrator: CAST PICK (pick_cast.py -> <Dir>\cast.json) -> render7b -> unload check -> FLUX backgrounds (only missing images) -> post_episode. Writes <Dir>\STATUS.txt + chain.log.
Start it detached and poll STATUS.txt with short calls:
  Start-Process powershell -ArgumentList '-ExecutionPolicy','Bypass','-File','C:\grok\podcast\run_episode.ps1','-Dir','ui1','-Ep','uploaded_intelligence_ep1','-BgDir','bg_ui1','-FrameSuffix','_ui1','-Guest2Voice','Maya' -WindowStyle Hidden
Cast: NO default cast; host = Carter unless -HostVoice. Guests are picked at random from the pool (pick_cast.py; seed logged to cast.json, STATUS.txt and the notes). -GuestGenders "M,F" = script wants Guest male, Guest2 female. -Guests "Marcus,Isla" overrides. -CastSeed N reproduces a pick. An existing <Dir>\cast.json is reused (resume).
Needs in <Dir>: segNN.json, intro.wav, sting.wav, outro.wav, <Ep>.chapters.in.json; in <BgDir>: prompts.json + backgrounds.json.  #>
param([Parameter(Mandatory)][string]$Dir, [Parameter(Mandatory)][string]$Ep, [Parameter(Mandatory)][string]$BgDir, [string]$FrameSuffix = "_ep", [string]$Title = "",
  [string]$HostVoice = "Carter", [string]$Guests = "", [string]$GuestGenders = "", [int]$CastSeed = 0, [double]$Tempo = 0.93, [double]$SegGap = 0.4, [double]$StingPad = 0, [int]$QcRetries = 1, [string]$Series = "", [switch]$Multi, [switch]$OneOff, [string]$Root = "C:\grok\podcast", [switch]$Scheduled)
$ErrorActionPreference = 'Continue'; (Get-Process -Id $PID).PriorityClass = 'Idle'; cd $Root
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
# --- v1.5: nightly/scheduled runs only (-Scheduled or env PODCAST_SCHEDULED=1): free GPU VRAM by closing configured GPU-hungry apps GRACEFULLY (vram_free.ps1 -Free -Scheduled; guarded: user idle, foreground, audio, fullscreen; never kills; log in hwlogs\vram_free_<date>.log). Manual runs while Thomas is at the PC do nothing here.
if ($Scheduled -or $env:PODCAST_SCHEDULED -eq '1') { $vf = Tool 'vram_free.ps1'; if (Test-Path $vf) { $vo = & powershell -NoProfile -ExecutionPolicy Bypass -File $vf -Free -Scheduled 2>&1 | Out-String; Add-Content "$W\chain.log" $vo.Trim() } }
while (((Invoke-RestMethod http://localhost:11434/api/ps -EA SilentlyContinue).models).Count -gt 0) { St 'waiting for Ollama to be empty'; Start-Sleep 15 }
& powershell -ExecutionPolicy Bypass -File (Tool 'render7b.ps1') -Dir $W -HostVoice $HostVoice -Tempo $Tempo -QcRetries $QcRetries *> "$W\render.log"
St "step=TTS done $((gc $W\render.log | sls SEGDONE).Count) segs"
while (Get-Process audiocpp_cli -EA 0) { Start-Sleep 5 }
$imgs = (gc -Raw "$BgDir\prompts.json" | ConvertFrom-Json).images.id | ? { -not (Test-Path "$BgDir\$_.png") }
if ($imgs) { $env:HIP_VISIBLE_DEVICES = '1'; St "step=FLUX $($imgs.Count) images"; $t = Get-Date
  & powershell -ExecutionPolicy Bypass -File .\hwrun.ps1 -Name "flux_$Ep" venv_sd\Scripts\python.exe gen_backgrounds_flux.py "$BgDir\prompts.json" $BgDir --model C:\Users\TJ\.cache\huggingface\hub\models--unsloth--FLUX.1-schnell\snapshots\9df3faa7ae3b6ddf0b2b69bb78616372897cc65c --offload staged --fp8 1 *> "$W\flux.log"
  St "step=FLUX done exit $LASTEXITCODE in $([int]((Get-Date)-$t).TotalSeconds) s" }
$nm = @(); if ($Series) { $nm += '-Series', $Series }; if ($Multi) { $nm += '-Multi' }; if ($OneOff) { $nm += '-OneOff' }   # v1.8 naming (post_episode.ps1 / episodes_index.py)
& powershell -ExecutionPolicy Bypass -File (Tool 'post_episode.ps1') -Dir $W -Ep $Ep -Bg "$BgDir\backgrounds.json" -FrameSuffix $FrameSuffix -Title $Title -HostVoice $HostVoice -SegGap $SegGap -StingPad $StingPad @nm *> "$W\post.out.txt"
$pe = $LASTEXITCODE
Invoke-RestMethod http://localhost:11434/api/ps -EA SilentlyContinue | % { $_.models } | % { Invoke-RestMethod http://localhost:11434/api/generate -Method Post -Body (@{model=$_.name;keep_alive=0}|ConvertTo-Json) }
St "step=ALL DONE (post exit $pe)"
