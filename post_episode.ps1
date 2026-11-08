<#  post_episode.ps1 (template v1.3, 2026-10-15; v1.12 2026-10-21: BLOCKING mix QC - qc_mix.py --gate (every speaker 145-175 wpm; v1.14 2026-11-07: host 145-190, no intra-line pause > 1.5 s) fails -> STOP exit 7 BEFORE video / copy to -OutDir / registry (nothing published; -NoMixGate only by Thomas' decision); v1.11 2026-10-20: segments = the segNN.json list (every one needs its mp3, else ABORT exit 5 - v1.10 counted mp3s and mixed "0 s" after a GENFAIL), -OutDir (default episodes; never-overwrite guard + all outputs there), -EngineName for the notes (v1.10 hardcoded "VibeVoice-7B Q8"); v1.8 2026-10-16: window 38-48 min, naming convention + episodes registry) - segment mp3s -> mix -> duration gate -> align -> qc_mix -> make_video -> 64k mp3 -> credits. CPU only (+ffmpeg). Never overwrites existing episodes\<Ep>.* (aborts).
Mix (same as das Man v2 / UI ep1): intro (vol 0.6) + seg mp3s (+SegGap s pad) + sting (vol 0.35; +StingPad s silence before/after; none after the last segment) + outro (0.6) -> concat -> loudnorm I=-16 -> 128k mono.
Duration gate (v1.8): <MinDur,MaxDur> (default 2280-2880 s = 38-48 min) -> exit 3 BEFORE align/video if outside. Do NOT slow the tempo for length (0.93 stays); only if the mix is < 38 min use -SegGap 1.2 -StingPad 0.6 (see technical_v1.8.md).
Naming (v1.8, episodes_index.py): -Series "<Series>" -Multi = series with several episodes -> title/corner label "<Series> #<n>"; default / -OneOff = one-off -> title = -Title (subject; a trailing ", Episode 1" is stripped), corner label = date. "Episode 1" is never printed. The episode is appended to <Root>\episodes_index.json (+ .md) when the post finishes.
Voice credits: every cast voice with a "credit" in voices.json (CC BY voices_extra: Clara, Isla, Marcus, Declan) is appended to episodes\<Ep>.notes.md and the end of <Ep>.chapters.txt.
Cast: read from <Dir>\cast.json (pick_cast.py) unless -GuestVoice/-Guest2Voice are given; the cast, pick mode and pick seed are written into the notes.
Usage: .\post_episode.ps1 -Dir ui1 -Ep uploaded_intelligence_ep1 -Bg bg_ui1\backgrounds.json -FrameSuffix _ui1 -Series "Uploaded Intelligence" -Multi -Title "Mind uploading and personal identity"  #>
param([Parameter(Mandatory)][string]$Dir, [Parameter(Mandatory)][string]$Ep, [Parameter(Mandatory)][string]$Bg, [string]$FrameSuffix = "_ep",
  [string]$HostVoice = "Carter", [string]$GuestVoice = "", [string]$Guest2Voice = "", [string]$Title = "", [string]$Chapters = "", [string]$SegSuffix = "",
  [double]$SegGap = 0.4, [double]$StingPad = 0, [int]$MinDur = 2280, [int]$MaxDur = 2880, [string]$Series = "", [switch]$Multi, [switch]$OneOff, [string]$Root = "C:\grok\podcast", [switch]$NoVideo,
  [string]$OutDir = "episodes", [string]$EngineName = "", [switch]$NoMixGate, [double]$WpmLo = 145, [double]$WpmHi = 175, [double]$WpmHiHost = 190, [double]$MaxLinePause = 1.5)
$ErrorActionPreference = 'Continue'; (Get-Process -Id $PID).PriorityClass = 'Idle'; cd $Root
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$W = if ([IO.Path]::IsPathRooted($Dir)) { $Dir } else { Join-Path $Root $Dir }; $P = "$W\post.log"
function Prog($m) { Add-Content $P "- $(Get-Date -f 'HH:mm:ss') $m"; Set-Content "$W\STATUS.txt" "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') post: $m" }
$OD = if ([IO.Path]::IsPathRooted($OutDir)) { $OutDir } else { Join-Path $Root $OutDir }; New-Item -ItemType Directory -Force $OD | Out-Null
foreach ($f in "$OD\$Ep.mp3","$OD\$Ep.mp4","$OD\$Ep.srt","$OD\$Ep.json") { if (Test-Path $f) { Prog "ABORT $f exists (never overwrite)"; exit 2 } }
if (-not $Chapters) { $Chapters = "$W\$Ep.chapters.in.json" }
$castnote = ""
if (Test-Path "$W\cast.json") { $cj = gc "$W\cast.json" -Raw | ConvertFrom-Json; if (-not $GuestVoice) { $HostVoice = $cj.host; $GuestVoice = $cj.guest; $Guest2Voice = $cj.guest2 }
  $sd = if ($cj.seed) { "$($cj.seed)" } else { "n/a (explicit override)" }
  $castnote = "Cast pick: mode=$($cj.mode), seed=$sd, genders required: $(($cj.genders_required | ConvertTo-Json -Compress)), F0 gaps (Hz): $(($cj.f0_gaps_hz | ConvertTo-Json -Compress)) - reproduce: $($cj.reproduce)" }
if (-not $GuestVoice) { Prog "ABORT no cast (no -GuestVoice and no $W\cast.json)"; exit 4 }
Prog "cast: host=$HostVoice guest=$GuestVoice guest2=$Guest2Voice $castnote"
# v1.11: the segment list comes from the segment SCRIPTS (segNN.json), never from the mp3 count; every segment must have its mp3
$segIds = @(gci "$W\seg??.json" | ? { $_.Name -match '^seg\d\d\.json$' } | sort Name | % { $_.BaseName.Substring(3) })
if (-not $segIds.Count) { Prog "ABORT no segNN.json in $W"; exit 5 }
$miss = @($segIds | ? { -not (Test-Path ("$W\seg{0}$SegSuffix.mp3" -f $_)) } | % { "seg$_$SegSuffix.mp3" })
if ($miss.Count) { Prog "ABORT missing segment mp3(s): $($miss -join ', ') - refusing to mix an incomplete episode"; exit 5 }
$n = $segIds.Count; Prog "segments: $n ($($segIds -join ',')), all mp3s present"
& venv_vv\Scripts\python.exe -c "import json;L=[];[L.extend(json.load(open(r'$W\seg%s.json'%i,encoding='utf-8-sig'))) for i in '$($segIds -join ',')'.split(',')];json.dump(L,open(r'$W\$Ep.json','w',encoding='utf-8'),indent=1,ensure_ascii=False);print(len(L))"
# mix
$in = @('-i',"$W\intro.wav"); $f = '[0:a]aresample=44100,aformat=channel_layouts=mono,volume=0.6[a0];'; $k = 1; $lab = '[a0]'
foreach ($s in 0..($n-1)) {
  $in += @('-i',("$W\seg{0}$SegSuffix.mp3" -f $segIds[$s])); $f += "[$($k):a]aresample=44100,aformat=channel_layouts=mono,apad=pad_dur=$SegGap[a$k];"; $lab += "[a$k]"; $k++
  if ($s -lt $n-1) { $st = "volume=0.35"; if ($StingPad -gt 0) { $st += ",adelay=$([int]($StingPad*1000)),apad=pad_dur=$StingPad" }
    $in += @('-i',"$W\sting.wav"); $f += "[$($k):a]aresample=44100,aformat=channel_layouts=mono,$st[a$k];"; $lab += "[a$k]"; $k++ }
}
$in += @('-i',"$W\outro.wav"); $f += "[$($k):a]aresample=44100,aformat=channel_layouts=mono,volume=0.6[a$k];"; $lab += "[a$k]"; $k++
$f += "$($lab)concat=n=$($k):v=0:a=1,loudnorm=I=-16:TP=-1.5:LRA=11[out]"
& ffmpeg -y -v error @in -filter_complex $f -map '[out]' -ar 44100 -ac 1 -b:a 128k "$W\$Ep.mp3"
if ($LASTEXITCODE -or -not (Test-Path "$W\$Ep.mp3")) { Prog "ABORT ffmpeg mix failed (exit $LASTEXITCODE)"; exit 5 }
$dur = [double](ffprobe -v error -show_entries format=duration -of csv=p=0 "$W\$Ep.mp3"); Prog "mixed dur $dur s"
if ($dur -lt $MinDur -or $dur -gt $MaxDur) { Prog "DURATION $dur s OUTSIDE $MinDur-$MaxDur - STOP before align/video"; exit 3 }
# v1.8 naming plan + registry (episodes_index.py): multi-episode series "<Series> #<n>", one-offs subject only + date label; never "Episode 1"
$ixa = @('--ep', $Ep); if ($Title) { $ixa += '--title', $Title }; if ($Series) { $ixa += '--series', $Series }; if ($Multi) { $ixa += '--multi' }; if ($OneOff) { $ixa += '--oneoff' }
$plan = $null; try { $plan = (& venv_vv\Scripts\python.exe episodes_index.py plan @ixa 2>&1 | Out-String) | ConvertFrom-Json } catch { $plan = $null }
if ($plan -and $plan.display_title) { Prog "naming: #$($plan.number) overall, series '$($plan.series)' multi=$($plan.multi) no=$($plan.series_no) -> title '$($plan.display_title)', corner label '$($plan.label)'"; $vtitle = " --title `"$($plan.display_title)`" --label `"$($plan.label)`""; $h1 = $plan.display_title
  $subline = if ($plan.multi -and $plan.subject) { "$($plan.subject)`n" } else { "" }; $subline += "$($plan.date) - podcast #$($plan.number) overall`n`n" }
else { Prog "WARNING naming plan failed - using -Title as is (episodes_index.py plan)"; $vtitle = ""; $h1 = if ($Title) { $Title } else { $Ep }; $subline = "" }
# align + qc_mix
$t = Get-Date; $al = Start-Process venv_whisper\Scripts\python.exe -ArgumentList "align.py $W\$Ep.mp3 $W\$Ep.json --threads 6" -NoNewWindow -PassThru -RedirectStandardOutput "$W\align.out.txt" -RedirectStandardError "$W\align.err.txt"
$al.PriorityClass = 'Idle'; $al.WaitForExit(); Prog "align exit $($al.ExitCode) $([int]((Get-Date)-$t).TotalSeconds) s; $((gc $W\align.out.txt | sls matched) -join ' ')"
& venv_whisper\Scripts\python.exe qc_mix.py "$W\$Ep.mp3" "$W\$Ep.timings.json" --host $HostVoice --guest $GuestVoice $(if ($Guest2Voice) { '--guest2'; $Guest2Voice }) --json "$W\${Ep}_mixqc.json" --gate --wpm_lo $WpmLo --wpm_hi $WpmHi --wpm_hi_host $WpmHiHost --max_pause $MaxLinePause *> "$W\mixqc.txt"; $mq = $LASTEXITCODE; Prog "qc_mix done (exit $mq): $((gc $W\mixqc.txt | ? {$_ -match '^(SILENCE|F0DRIFT|RATE|INTERP|MIXQC|SPKWPM|SPKRATE|PAUSE)'}) -join ' | ')"
if ($mq -eq 2 -and -not $NoMixGate) { Prog "STOP mix QC gate failed: $((gc $W\mixqc.txt | ? {$_ -match '^(SPKRATE|PAUSE)'} | select -First 8) -join ' | ') - nothing published (no video, nothing copied to $OD, no registry); see $W\mixqc.txt"; exit 7 }
if ($mq -ne 0 -and $mq -ne 2) { Prog "STOP qc_mix.py failed (exit $mq) - nothing published"; exit 7 }
if ($mq -eq 2) { Prog "WARNING mix QC gate failed but -NoMixGate was given (Thomas' decision) - continuing" }
if (-not $NoVideo) {
  $t = Get-Date
  $vp = Start-Process venv_video\Scripts\python.exe -ArgumentList "make_video.py $W\$Ep.mp3 $W\$Ep.json `"$OD\$Ep.mp4`" --timings $W\$Ep.timings.json --chapters $Chapters --host $HostVoice --guest $GuestVoice $(if ($Guest2Voice) { "--guest2 $Guest2Voice" }) --fps 20 --backgrounds $Bg --layout speaker --frames-dir video_frames --frame-suffix $FrameSuffix --frame-times 300,1300,2200$vtitle" -NoNewWindow -PassThru -RedirectStandardOutput "$W\video.out.txt" -RedirectStandardError "$W\video.err.txt"
  $vp.PriorityClass = 'Idle'; $vp.WaitForExit(); Prog "make_video exit $($vp.ExitCode), $([int]((Get-Date)-$t).TotalSeconds) s"
}
Copy-Item "$W\$Ep.mp3","$W\$Ep.json" $OD
& ffmpeg -y -v error -i "$OD\$Ep.mp3" -ac 1 -b:a 64k "$OD\${Ep}_64k.mp3"
# credits (CC BY voices)
$reg = gc "$Root\voices.json" -Raw | ConvertFrom-Json
$cr = @(); foreach ($v in @($HostVoice,$GuestVoice,$Guest2Voice)) { if (-not $v) { continue }; $e = $reg.voices.$v; if ($e -and $e.credit) { $cr += $e.credit } }
$ct = "$OD\$Ep.chapters.txt"
if ($cr.Count -and (Test-Path $ct)) { Add-Content -Encoding utf8 $ct ("`n" + ($cr -join "`n")) }
# v1.11: engine name from -EngineName, else from the chunks.json engine field of the first segment (v1.10 hardcoded VibeVoice-7B Q8)
$engNote = $EngineName
if (-not $engNote) { $cjf = "$W\seg$($segIds[0]).raw.wav.chunks\chunks.json"; $en = if (Test-Path $cjf) { (gc $cjf -Raw | ConvertFrom-Json).engine } else { "" }
  $engNote = if ($en -eq 'drama3') { 'Fish Audio Drama 3 (Q4_K_S GGUF) via audio.cpp' } elseif ($en) { "$en via audio.cpp" } else { 'VibeVoice-7B Q8 via audio.cpp' } }
$notes = "# $h1`n`n${subline}Voices: $HostVoice (host), $GuestVoice$(if ($Guest2Voice) { ", $Guest2Voice" }); $engNote.`n$castnote`n`n" + $(if (Test-Path $ct) { (gc $ct -Raw) } else { "" })
Set-Content -Encoding utf8 "$OD\$Ep.notes.md" $notes
$rg = & venv_vv\Scripts\python.exe episodes_index.py add @ixa --dur $dur --cast "$HostVoice, $GuestVoice$(if ($Guest2Voice) { ', ' + $Guest2Voice })" 2>&1 | Out-String; Prog "$($rg.Trim())"
Prog "POST DONE (credits: $($cr.Count))"
