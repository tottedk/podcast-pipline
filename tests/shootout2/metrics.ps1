param([string]$Raw,[string]$Name,[string]$Dir)
$ErrorActionPreference='Continue'; (Get-Process -Id $PID).PriorityClass='Idle'
$env:Path=[Environment]::GetEnvironmentVariable('Path','Machine')+';'+[Environment]::GetEnvironmentVariable('Path','User')
$py="C:\grok\podcast\venv_whisper\Scripts\python.exe"; $S='C:\grok\podcast\tests\shootout2'; $md="$Dir\metrics"; New-Item -ItemType Directory -Force "$md\x.raw.wav.chunks" | Out-Null
$tmp="$md\chain.mp3"; ffmpeg -v error -y -i $Raw -af 'highpass=f=70,atempo=0.93,loudnorm=I=-16:TP=-1.5:LRA=11' -ar 44100 -ac 1 -b:a 128k $tmp
$I=[double]((ffmpeg -hide_banner -i $tmp -af ebur128 -f null - 2>&1 | sls '^\s+I:' | select -Last 1).Line -replace '[^\d\.\-]',''); $g=[math]::Round(-16-$I,2)
$out="$S\ab\$Name.mp3"; ffmpeg -v error -y -i $tmp -af "volume=${g}dB,alimiter=limit=0.89" -ar 44100 -ac 1 -b:a 128k $out
"LOUD $Name gain $g -> " + ((ffmpeg -hide_banner -i $out -af ebur128=peak=true -f null - 2>&1 | sls '^\s+(I|Peak):' | select -Last 2 | % {$_.Line.Trim()}) -join ' ') + " dur $(ffprobe -v error -show_entries format=duration -of csv=p=0 $out)"
Copy-Item $out "$md\x.mp3"; Copy-Item "$S\excerpt.json" "$md\x.json"; Copy-Item $Raw "$md\x.raw.wav"; Copy-Item $Raw "$md\x.raw.wav.chunks\c001.wav"
$L=gc "$S\excerpt.json" -Raw|ConvertFrom-Json; $cj=@{chunks=@(@{i=1;seed=42;first_line=0;n_lines=$L.Count;text=(($L|%{$_.text}) -join ' ');lines=@($L|%{$_.text});speakers=@($L|%{$_.speaker});tts_lines=@($L|%{$_.text})})}
$cj | ConvertTo-Json -Depth 6 | Out-File -Encoding ascii "$md\x.raw.wav.chunks\chunks.json"
& $py C:\grok\podcast\align.py "$md\x.mp3" "$md\x.json" --threads 4 2>&1 | sls 'matched' | % { "ALIGN $($_.Line)" }
& $py C:\grok\podcast\tests\three_speaker\spk_check.py "$md\x.mp3" "$md\x.timings.json" --host Carter --guest Frank --guest2 Samuel --json "$md\spk.json" 2>&1 | % { "SPK $_" }
& $py C:\grok\podcast\qc_vv.py "$md\x.raw.wav" "$md\x.json" --chunks "$md\x.raw.wav.chunks" --host Carter --guest Frank --guest2 Samuel --glossary C:\grok\podcast\ab_dm\empty_glossary.json --json "$md\qc.json" 2>&1 | sls '^chunk' | % { "QC $($_.Line)" }
$j=gc "$md\qc.json" -Raw|ConvertFrom-Json; $c=$j.chunks[0]
"QCSUM WER $($j.wer) pitch_ev $($j.pitch_events) lowprob $($j.lowprob_words.Count) noise $($j.noise_events) nonspeech_s $($j.nonspeech_s) gap_db $($j.gap_db) unrec $($j.unrecognised.Count) bad_lines $(($c.bad_lines|ConvertTo-Json -Compress)) line_wer $(($c.line_wer|ConvertTo-Json -Compress)) glossary_missing $(($c.glossary_missing|ConvertTo-Json -Compress)) f0_drift $(($c.f0_drift|ConvertTo-Json -Compress)) rate_bad $(($c.rate_bad|ConvertTo-Json -Compress)) ref $(($j.f0_ref_used|ConvertTo-Json -Compress))"
$c.lines | % { "LINE k$($_.k) $($_.speaker) n$($_.n) f0 $($_.f0) rate $($_.rate) wer $($_.wer) cov $($_.cov)" }
