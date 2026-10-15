<#  post_episode.ps1 (template v1.3, 2026-10-15) - segment mp3s -> mix -> duration gate -> align -> qc_mix -> make_video -> 64k mp3 -> credits. CPU only (+ffmpeg). Never overwrites existing episodes\<Ep>.* (aborts).
Mix (same as das Man v2 / UI ep1): intro (vol 0.6) + seg mp3s (+SegGap s pad) + sting (vol 0.35; +StingPad s silence before/after; none after the last segment) + outro (0.6) -> concat -> loudnorm I=-16 -> 128k mono.
Duration gate: <MinDur,MaxDur> (default 2400-2700 s = 40-45 min) -> exit 3 BEFORE align/video if outside (fix with -Tempo / -SegGap / -StingPad, see the length rule in technical_v1.3.md).
Voice credits: every cast voice with a "credit" in voices.json (CC BY voices_extra: Clara, Isla, Marcus, Declan) is appended to episodes\<Ep>.notes.md and the end of <Ep>.chapters.txt.
Cast: read from <Dir>\cast.json (pick_cast.py) unless -GuestVoice/-Guest2Voice are given; the cast, pick mode and pick seed are written into the notes.
Usage: .\post_episode.ps1 -Dir ui1 -Ep uploaded_intelligence_ep1 -Bg bg_ui1\backgrounds.json -FrameSuffix _ui1 -Title "Uploaded Intelligence, Episode 1"  #>
param([Parameter(Mandatory)][string]$Dir, [Parameter(Mandatory)][string]$Ep, [Parameter(Mandatory)][string]$Bg, [string]$FrameSuffix = "_ep",
  [string]$HostVoice = "Carter", [string]$GuestVoice = "", [string]$Guest2Voice = "", [string]$Title = "", [string]$Chapters = "", [string]$SegSuffix = "",
  [double]$SegGap = 0.4, [double]$StingPad = 0, [int]$MinDur = 2400, [int]$MaxDur = 2700, [string]$Root = "C:\grok\podcast", [switch]$NoVideo)
$ErrorActionPreference = 'Continue'; (Get-Process -Id $PID).PriorityClass = 'Idle'; cd $Root
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$W = if ([IO.Path]::IsPathRooted($Dir)) { $Dir } else { Join-Path $Root $Dir }; $P = "$W\post.log"
function Prog($m) { Add-Content $P "- $(Get-Date -f 'HH:mm:ss') $m"; Set-Content "$W\STATUS.txt" "$(Get-Date -f 'yyyy-MM-dd HH:mm:ss') post: $m" }
foreach ($f in "episodes\$Ep.mp3","episodes\$Ep.mp4","episodes\$Ep.srt","episodes\$Ep.json") { if (Test-Path $f) { Prog "ABORT $f exists (never overwrite)"; exit 2 } }
if (-not $Chapters) { $Chapters = "$W\$Ep.chapters.in.json" }
$castnote = ""
if (Test-Path "$W\cast.json") { $cj = gc "$W\cast.json" -Raw | ConvertFrom-Json; if (-not $GuestVoice) { $HostVoice = $cj.host; $GuestVoice = $cj.guest; $Guest2Voice = $cj.guest2 }
  $sd = if ($cj.seed) { "$($cj.seed)" } else { "n/a (explicit override)" }
  $castnote = "Cast pick: mode=$($cj.mode), seed=$sd, genders required: $(($cj.genders_required | ConvertTo-Json -Compress)), F0 gaps (Hz): $(($cj.f0_gaps_hz | ConvertTo-Json -Compress)) - reproduce: $($cj.reproduce)" }
if (-not $GuestVoice) { Prog "ABORT no cast (no -GuestVoice and no $W\cast.json)"; exit 4 }
Prog "cast: host=$HostVoice guest=$GuestVoice guest2=$Guest2Voice $castnote"
$n = (gci "$W\seg??$SegSuffix.mp3").Count
& venv_vv\Scripts\python.exe -c "import json;L=[];[L.extend(json.load(open(r'$W\seg%02d.json'%i,encoding='utf-8-sig'))) for i in range($n)];json.dump(L,open(r'$W\$Ep.json','w',encoding='utf-8'),indent=1,ensure_ascii=False);print(len(L))"
# mix
$in = @('-i',"$W\intro.wav"); $f = '[0:a]aresample=44100,aformat=channel_layouts=mono,volume=0.6[a0];'; $k = 1; $lab = '[a0]'
foreach ($s in 0..($n-1)) {
  $in += @('-i',("$W\seg{0:D2}$SegSuffix.mp3" -f $s)); $f += "[$($k):a]aresample=44100,aformat=channel_layouts=mono,apad=pad_dur=$SegGap[a$k];"; $lab += "[a$k]"; $k++
  if ($s -lt $n-1) { $st = "volume=0.35"; if ($StingPad -gt 0) { $st += ",adelay=$([int]($StingPad*1000)),apad=pad_dur=$StingPad" }
    $in += @('-i',"$W\sting.wav"); $f += "[$($k):a]aresample=44100,aformat=channel_layouts=mono,$st[a$k];"; $lab += "[a$k]"; $k++ }
}
$in += @('-i',"$W\outro.wav"); $f += "[$($k):a]aresample=44100,aformat=channel_layouts=mono,volume=0.6[a$k];"; $lab += "[a$k]"; $k++
$f += "$($lab)concat=n=$($k):v=0:a=1,loudnorm=I=-16:TP=-1.5:LRA=11[out]"
& ffmpeg -y -v error @in -filter_complex $f -map '[out]' -ar 44100 -ac 1 -b:a 128k "$W\$Ep.mp3"
$dur = [double](ffprobe -v error -show_entries format=duration -of csv=p=0 "$W\$Ep.mp3"); Prog "mixed dur $dur s"
if ($dur -lt $MinDur -or $dur -gt $MaxDur) { Prog "DURATION $dur s OUTSIDE $MinDur-$MaxDur - STOP before align/video"; exit 3 }
# align + qc_mix
$t = Get-Date; $al = Start-Process venv_whisper\Scripts\python.exe -ArgumentList "align.py $W\$Ep.mp3 $W\$Ep.json --threads 6" -NoNewWindow -PassThru -RedirectStandardOutput "$W\align.out.txt" -RedirectStandardError "$W\align.err.txt"
$al.PriorityClass = 'Idle'; $al.WaitForExit(); Prog "align exit $($al.ExitCode) $([int]((Get-Date)-$t).TotalSeconds) s; $((gc $W\align.out.txt | sls matched) -join ' ')"
& venv_whisper\Scripts\python.exe qc_mix.py "$W\$Ep.mp3" "$W\$Ep.timings.json" --host $HostVoice --guest $GuestVoice $(if ($Guest2Voice) { "--guest2 $Guest2Voice" }) --json "$W\${Ep}_mixqc.json" *> "$W\mixqc.txt"; Prog "qc_mix done: $((gc $W\mixqc.txt | ? {$_ -match '^(SILENCE|F0DRIFT|RATE|INTERP|MIXQC)'}) -join ' | ')"
if (-not $NoVideo) {
  $t = Get-Date
  $p = Start-Process venv_video\Scripts\python.exe -ArgumentList "make_video.py $W\$Ep.mp3 $W\$Ep.json episodes\$Ep.mp4 --timings $W\$Ep.timings.json --chapters $Chapters --host $HostVoice --guest $GuestVoice $(if ($Guest2Voice) { "--guest2 $Guest2Voice" }) --fps 20 --backgrounds $Bg --layout speaker --frames-dir video_frames --frame-suffix $FrameSuffix --frame-times 300,1300,2200" -NoNewWindow -PassThru -RedirectStandardOutput "$W\video.out.txt" -RedirectStandardError "$W\video.err.txt"
  $p.PriorityClass = 'Idle'; $p.WaitForExit(); Prog "make_video exit $($p.ExitCode), $([int]((Get-Date)-$t).TotalSeconds) s"
}
Copy-Item "$W\$Ep.mp3","$W\$Ep.json" episodes\
& ffmpeg -y -v error -i "episodes\$Ep.mp3" -ac 1 -b:a 64k "episodes\${Ep}_64k.mp3"
# credits (CC BY voices)
$reg = gc "$Root\voices.json" -Raw | ConvertFrom-Json
$cr = @(); foreach ($v in @($HostVoice,$GuestVoice,$Guest2Voice)) { if (-not $v) { continue }; $e = $reg.voices.$v; if ($e -and $e.credit) { $cr += $e.credit } }
$ct = "episodes\$Ep.chapters.txt"
if ($cr.Count -and (Test-Path $ct)) { Add-Content -Encoding utf8 $ct ("`n" + ($cr -join "`n")) }
$notes = "# $(if ($Title) { $Title } else { $Ep })`n`nVoices: $HostVoice (host), $GuestVoice$(if ($Guest2Voice) { ", $Guest2Voice" }); VibeVoice-7B Q8 via audio.cpp.`n$castnote`n`n" + $(if (Test-Path $ct) { (gc $ct -Raw) } else { "" })
Set-Content -Encoding utf8 "episodes\$Ep.notes.md" $notes
Prog "POST DONE (credits: $($cr.Count))"
