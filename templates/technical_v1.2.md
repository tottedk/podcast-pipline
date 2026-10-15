# Technical template
**Version 1.2 - 2026-10-14** (v1.1 + 3-speaker support, make_video 2nd-guest colour + .srt-only subtitles, qc_takes venv fix; 3-speaker GPU test done, not yet used for an episode). Never edit; copy to v1.3+. Code snapshot: `code_v1.2\` (+ `SHA256SUMS.txt`).

## Hardware / platform
- Windows 11 PC "DESKTOP-5B87DR9", AMD Radeon RX 7900 XT 20 GB (ROCm/HIP torch on Windows), plus an AMD iGPU = device 0.
- **`HIP_VISIBLE_DEVICES=1` is required** (device 0 = iGPU, crashes). podcast.ps1 and the FLUX/SDXL runs set it.
- CPU/RAM: unknown model; RAM peak ~31.9 GB used during FLUX (hwlogs). HWiNFO64 sensors via VSB registry (hw_monitor.ps1); `Documents\hwinfo.CSV` logging was NOT active during DE (last written 2026-10-13 21:35).

## Pipeline (DE ep1, step by step)
1. Source EPUB/PDF -> read once -> `notes\<book>.md` (Grok Bot cloud).
2. Script from the note (Grok Bot cloud; Gemma `write_script.py` optional/legacy) -> `de\<ep>.json` `[{speaker: Host|Guest, text}]`; split into section files `de\segNN.json` (11 for DE).
3. Fact-check -> `learn\factcheck_<ep>.md`, fix the script.
4. Music: `pw\synth.py` -> `de\intro.wav`, `sting.wav`, `outro.wav`.
5. TTS per segment: run `prep_script.py` on the full script BEFORE chapters/backgrounds (merges <=2-word lines), then loop `podcast.ps1 x segNN.mp3 -Script segNN.json -HostVoice Carter -GuestVoice <guest> -Seed 42` (defaults now -ChunkWords 175, -QcRetries 3). Inside: vv_generate.py (VibeVoice, glossary respelling on TTS text only) -> qc_vv.py v2 QC after EVERY pass, qc_takes.py records takes, best take per chunk ships, final qc.json (final=true) -> qc_vv.py --gate (safe pause cleanup, keeps unrecognised speech) -> ffmpeg `highpass=f=70,afftdn=nf=-45:nr=10:tn=1,atempo=0.93,loudnorm=I=-16:TP=-1.5:LRA=11` -> 128k mono mp3.
6. Mix: `de\mix.ps1`: intro (vol 0.6) + seg mp3s (0.4 s apad each) + sting (vol 0.35) between sections (not after seg09 takeaways) + outro (0.6) -> concat -> loudnorm I=-16 -> `<ep>.mp3` 128k mono.
6b. NEW: after align (step 7) run `qc_mix.py <ep>.mp3 <ep>.timings.json --json logs\<ep>_mixqc.json` and review SILENCE/F0DRIFT/RATE/INTERP lines before the video.
7. Align: `align.py <ep>.mp3 <ep>.json --threads 6` (faster-whisper large-v3-turbo, CPU int8) -> `.whisper.json`, `.timings.json` (DE: 97.2% match).
8. Chapters: hand-written `de\<ep>.chapters.in.json` (start = script line index).
9. Backgrounds: `bg_de1\prompts.json` (20 images) -> `gen_backgrounds_flux.py` (FLUX.1 schnell unsloth snapshot, fp8, `--offload staged`, 4 steps, 1344x768) run under `hwrun.ps1` -> `bg_de1\backgrounds.json`.
10. Video: `make_video.py <ep>.mp3 <ep>.json episodes\<ep>.mp4 --timings --chapters --host Carter --guest Frank --fps 20 --backgrounds bg_de1\backgrounds.json --layout speaker --frames-dir video_frames --frame-suffix _dark --frame-times 300,1300,2200` -> mp4 (v1.2: no subs in video; add `--burn-subs` for the old burned + mov_text), .srt, .chapters.txt/.json, PNG frames.
11. `ffmpeg -ac 1 -b:a 64k` -> `_64k.mp3`; stage in `C:\Users\TJ\Downloads\<x>_stage` for CopyToBox; unload Ollama models (keep_alive 0).
Orchestration for steps 6-11 in DE: `logs\dark_post.ps1` (sequential, waits for render ALLDONE, waits for empty Ollama /api/ps and no VibeVoice before FLUX), progress in `logs\dark_progress.md`.

## Models and roles
| Model | Role | Notes |
|---|---|---|
| Gemma `gemma4:26b-a4b-it-qat` via Ollama | optional script drafting (`write_script.py`) | keep_alive 0; often short turns / HTTP 500; not used for DE |
| microsoft/VibeVoice-1.5B | TTS, 2-3 speakers (Host/Guest/Guest2; tested 3 in one chunk) | bf16, SDPA, 10 diffusion steps, cfg 1.3, seed 42 (reset per chunk), `--pace sentence`; peak 6.35 GB VRAM. **Do not change settings.** |
| faster-whisper large-v3-turbo (CPU int8) | align.py and qc_vv.py | medium.en/small.en available |
| SDXL base 1.0 fp16 (`gen_backgrounds.py`) | older backgrounds (ep3, Patchwork) | ~10 s/image at 30 steps, 9.05 GB peak |
| FLUX.1 schnell, unsloth snapshot, fp8 layerwise cast (`gen_backgrounds_flux.py`) | backgrounds since DE | 4 steps, `--offload staged`, peak 18.82 GB |
| synth.py (numpy) | intro/stings/outro | no model |
Tested, not used: Dia-1.6B, Higgs Audio v2 3B, Kokoro-82M (test_dia*.py, test_higgs.py).

## Programs / libraries
ffmpeg/ffprobe (PATH from registry); PowerShell 5.1 (no `$ErrorActionPreference=Stop` with native cmds; UTF-8 without BOM for JSON read by make_video.py); venvs: `venv` (stdlib, write_script), `venv_vv` (VibeVoice fork, transformers 4.51.3, ROCm torch), `venv_whisper` (faster-whisper, numpy only - no librosa/scipy), `venv_video` (Pillow), `venv_sd` (diffusers/transformers/accelerate, torch reused from `venv_rocm` via .pth), `venv_higgs`.

## Code inventory (snapshot code_v1.2)
| File | Purpose / key args |
|---|---|
| podcast.ps1 | TTS episode driver. `notes out.mp3 -Script json -HostVoice -GuestVoice -Guest2Voice -Tempo 0.93 -Pace sentence -Cfg 1.3 -Seed 42 -ChunkWords 175 -Steps 10 -QcRetries 3 -NoQc -NoMerge -Glossary file -NoHwMonitor` |
| prep_script.py | merge <=2-word interjections into the same speaker's next line (`script.json [out.json] [--min_words 2]`) |
| qc_takes.py | `record <chunks> <qc.json> <pass>` / `pick <chunks> <raw.wav>`: best-take bookkeeping |
| qc_mix.py | final QC of the mixed mp3 using align timings (`--json --host --guest --f0_tol`) |
| glossary.json / voice_f0.json | hard-term respellings / calibrated generated-speech F0 per voice (Carter 131.1, Frank 127.5 Hz; others unknown) |
| vv_generate.py | VibeVoice generation, chunked on turn boundaries; `--guest2 --chunk_words 175 --glossary --pause 0.35 --pace --clean_refs --redo i:seed,...`; keeps `<out>.chunks\cNNN.wav` + chunks.json (lines, tts_lines, speakers) |
| qc_vv.py (v2) | v1 checks + per-line WER >0.25, glossary misses, F0 drift +/-15% (voice_f0.json ref), rate (>=12-word lines outside 2.1-5.0 w/s), unrecognised speech-level audio >=1 s; score; `--rescore`; `--gate` keeps long speech-level gaps |
| align.py | script-to-audio word alignment (difflib), `--model --threads --words` |
| make_video.py | video render; `--timings --chapters --backgrounds --layout speaker|quote --fps --frame-times --frames-dir --frame-suffix --host --guest --guest2 --burn-subs --keep-tmp`; default since v1.2: no subtitles in the mp4, separate .srt only |
| gen_backgrounds.py / gen_backgrounds_flux.py | SDXL / FLUX images from prompts.json; `--steps --w --h --seed --only`, FLUX `--model --offload staged|model|seq|none --fp8` |
| write_script.py | Gemma script drafting (`--lines --topic --ctx`) |
| tests\three_speaker\spk_check.py | 3-speaker test: per-line F0 + log-mel voice-ID vs voice prompts and leave-one-out speaker centroids (`audio timings.json --host --guest --guest2 --json`) |
| check_sync.py | subtitle/audio sync check by episode stem |
| hw_monitor.ps1 / hwmon_lib.ps1 / hwrun.ps1 | HWiNFO VSB sensor logging to hwlogs\ |
| mk_style.py | FLUX style A/B/C comparison prompts |
| pw\synth.py | music synthesis (drone, saw, plucks) |
| de\render.ps1, de\mix.ps1, pw\render.ps1, logs\dark_post.ps1 | per-episode render/mix/post helpers |

| Snapshot file (code_v1.2) | Bytes | SHA256 (16) |
|---|---|---|
| `align.py` | 5422 | `C35424A88224E48F` |
| `check_sync.py` | 1502 | `FAAF64A759948D35` |
| `gen_backgrounds.py` | 2433 | `47F17D1C66E5EACA` |
| `gen_backgrounds_flux.py` | 3940 | `7F5E02B8821DA4C9` |
| `glossary.json` | 764 | `A19F6937469517A9` |
| `hw_monitor.ps1` | 5188 | `30B65AB14D7C24E5` |
| `hwmon_lib.ps1` | 955 | `F90957DA655BEE5C` |
| `hwrun.ps1` | 788 | `ED99A045BC92AA5C` |
| `make_video.py` (changed) | 30140 | `B701A58C23DF05D6` |
| `mk_style.py` | 1729 | `237B6B02CDA40D71` |
| `podcast.ps1` (changed) | 7775 | `8767E8569F82003B` |
| `prep_script.py` | 1630 | `E3F10F4DE90187BB` |
| `qc_mix.py` (changed) | 4238 | `19184255EC8012CD` |
| `qc_takes.py` | 2391 | `5C0546FB1D80C3DB` |
| `qc_vv.py` (changed) | 15365 | `B9DB86158A67E492` |
| `README.md` (changed) | 15376 | `0ACCD910CE6251AA` |
| `voice_f0.json` | 296 | `9A1616A0AC276A3F` |
| `vv_generate.py` (changed) | 7441 | `4EC88ED3C5FF084E` |
| `write_script.py` | 3016 | `DFE47AAAB423995C` |
| `de\mix.ps1` | 891 | `88FFAC3133A1A074` |
| `de\render.ps1` | 404 | `4B9DB16A0C40954D` |
| `logs\dark_post.ps1` | 2809 | `B3CE72163733359F` |
| `pw\render.ps1` | 401 | `CFD1BD41D4EA2225` |
| `pw\synth.py` | 1811 | `4885A18E092790E6` |
| `tests\spk_check.py` (changed) | 4325 | `9E7B930314797A13` |

## GPU rules
One GPU model at a time; check for stale python/GPU processes first; Ollama keep_alive 0 and wait for empty `/api/ps` before VibeVoice/FLUX; unload everything at the end (Thomas games). Do not touch VibeVoice model settings. Whisper runs on CPU.

## Model test log
- **SDXL vs FLUX:** SDXL ~10 s/image (30 steps), weaker composition. FLUX schnell fp8: ~140 s/image with offload in early tests; **DE run 46-63 s/image (1317.5 s for 20)**, peak 18.82 GB torch / ~19.7 GB VRAM; GPU hotspot max 91 C in DE (avg 84.7), 91-102 C reported in earlier tests; no throttling in DE (HTC 0, hotspot limit max 80.5%).
- **FLUX styles** (`bg_flux_style\A|B|C`): A = matte painting, amber lamplight; B = cinematic photograph, cold teal/blue; **C = concept art, semi-realistic, amber/teal -> chosen**, then strengthened (visible brush strokes, rich warm amber glow, film grain, "no text").
- **VibeVoice issues:** garbled words (hard terms, one-word lines after silence), voice/pitch drift within long chunks (DE seg01 c2 host F0 173 Hz vs ~130), random BGM-like music + slow voice (DE seg04 c1), onset noise bursts; Mary voice has background music (never use). cfg 1.5/1.8, 20 steps, clean refs did not help (A/B 2026-10-13).
- **Whisper:** large-v3-turbo default since 2026-10-13 (ab_test\README_ab.txt).

## Scripting: local LLM vs cloud
Gemma (local) gave too short/few turns for 150+ turn scripts and HTTP 500s; Grok Bot cloud does note, script, fact-check and orchestration. Token use: Patchwork ep1 ~500k, DE ep1 ~130k (rough).

## Known bugs / DE diagnosis
See `logs\dark_bug_diagnosis.md`. Root causes: no QC after the final redo, 350-word chunks, no F0/rate/silence/music checks, the gate muting real speech, hard terms. **Status in v1.1: fixes APPLIED (approved 2026-10-14)**: QC after every pass + best take + final qc.json, QcRetries 3, ChunkWords 175 + prep_script.py merging, F0 drift / rate / unrecognised-audio (silence/music/babble) checks, per-line WER + glossary, safe gate, respelling (TTS only), qc_mix.py.

### CPU test of QC v2 on the existing DE files (no re-render, 2026-10-14; logs\qc2_*.json, qc2_test.log, qc2_mix.log)
| Bug | Chunk | v2 flags | Caught |
|---|---|---|---|
| 1 5:16 host pitch up | seg01 c2 | f0_drift (host lines 188/188/168 Hz vs 131) | yes |
| 2 7:40 Sisyphean, 3 7:57 neocameralism | seg02 c1 | glossary (both terms), f0_drift | yes |
| 4 9:46 noise+pitch | seg02 c2 | f0_drift | yes |
| 5 17:28 babble/music/slow | seg04 c1 | noise, rate (2.05 w/s) | yes |
| 6 21:31 glitch+pitch | seg05 c1 | noise | yes |
| 7 26:39 noise in words | seg05 c3 | none (score 2.9) | **no** - in-word noise not detectable with current metrics (spectral flatness/HF tried, no outlier) |
| 8 30:27 silence | seg06 c2 | unrecognised 14.2 s, wer, bad_lines, line_wer, noise | yes; new gate keeps 131.96-146.7 s (gated wav -23..-26 dB there; old: -73 dB) |
| extra: seg08 c2 host drift | seg08 c2 | f0_drift (172/188/160 Hz), glossary (Sandifer) | yes |
Chunks with no flags: seg01 c1/c3, seg04 c2, seg05 c2/c3, seg06 c1. Also flagged: seg08 c1 (noise + host lines 177/154 Hz; not reported by Thomas, likely real).
qc_mix.py on the final mp3: SILENCE 30:26 15.9 s (line 141) and 17:30; F0DRIFT 5:06, 13:45, 38:18 (host); RATE 17:17 (1.88 w/s); minor 2-2.7 s silences and fast-rate lines are probably false positives (35:45 line 167 includes a sting boundary).
Remaining limits: in-word noise (bug 7) is not detected; the F0 reference for voices other than Carter and Frank is unknown (falls back to the segment median); thresholds are tuned on one episode.

## 3-speaker test (v1.2, 2026-10-14) - `tests\three_speaker\`
Script `three_speaker.json`: 10 lines, 168 words (1 chunk at -ChunkWords 175): Carter (Host, 4 lines), Alice (Guest, 3), Samuel (Guest2, 3), including Guest->Guest2 handovers with no host line between them, and a short 8-word line. Mary not used. Command (Idle priority, Ollama /api/ps empty before; nothing on the GPU afterwards):
`podcast.ps1 x three_speaker.mp3 -Script three_speaker.json -HostVoice Carter -GuestVoice Alice -Guest2Voice Samuel -Seed 42` (defaults cfg 1.3, 10 steps, pace sentence, QcRetries 3).
- run1\ = first run (qc_takes bug: last take p3/s3042 shipped); run2\ = after the fix, same seeds, bit-identical takes (deterministic), best take p2/s2042 shipped. Per take: VibeVoice ~53-61 s for ~56-68 s audio (~1x realtime), model load 4-6 s, peak VRAM 6.78 GB (2 speakers: 6.35 GB). Total 7.0 min wall for 1.0 min audio (4 generations + 5 QC passes). GPU max 69 C, hotspot 82 C.
- QC v2 per take: p0/s42 score 23.0 [f0_drift]; p1/s1042 33.5 [noise, f0_drift]; p2/s2042 22.68 [f0_drift]; p3/s3042 25.59 [f0_drift]. Shipped p2: WER 1.2%, 0 bad lines, 0 line-WER, 0 pitch glitches, 0 low-prob words, 3 noise events, no rate/unrecognised flags; f0_drift lines 2 (Guest2 119.4 vs 101.3 Hz) and 6 (Host 109.2 vs 131.1 Hz). Gate kept 1 speech-level region (50.1-51.4 s).
- align.py on the final mp3: 98.8% match. qc_mix.py: 1 F0DRIFT (Host from 0:18, 107 Hz vs 131.7 prompt ref; < 6 lines per speaker, so the prompt F0 is the reference), no silence/rate/interp.
- **Speaker mix-ups: none.** spk_check.py on all 4 takes (40 lines): every line is nearest to its own speaker by log-mel similarity, to both the voice prompt and the leave-one-out speaker centroid. Alice is clearly separated (sim ~0.85-0.90 to the men vs 0.975-0.995 to herself; F0 195-262 Hz). Carter vs Samuel is the narrow pair: own centroid 0.97-0.995 vs other man 0.92-0.977, so the margin is only 0.01-0.05. **F0 cannot separate them**: Host median 114.7 Hz vs Samuel 114.3 Hz in the shipped take. This is an objective proxy, not a listening test.
- **Pitch stability:** Samuel stable (100-119 Hz, prompt 101). Alice is moderately variable (195-262 Hz). **Carter is unstable across and within takes**: shipped take 107-123 Hz, p0 120-158 Hz, p1 111-162 Hz (calibrated 131 Hz). In 3-speaker scripts Carter mostly sits LOWER than his 2-speaker register (median 115-120 vs 131), which brings him toward Samuel's range. Every take was flagged f0_drift, so with Carter + a male Guest2 QC will usually exhaust its retries. Options (not done): calibrate per-cast refs in voice_f0.json after a listening check, or use a female + male guest pair (or a host/guest pair with a larger F0 gap).
- **Verdict:** 3 speakers work in VibeVoice-1.5B with no code change to model settings: no speaker swaps and no garbles (WER 1.2%), and the voices stay recognisable. Weak point: Carter's pitch register drifts (the same known 1.5B issue, more visible here). For episodes, prefer clearly different voices (e.g. Carter + Alice/Maya + Frank/Samuel), have Thomas listen to `run2\three_speaker.mp3`, and treat f0_drift on Host as soft until the refs are recalibrated.
- Video test (CPU): `video\three_speaker_test.mp4` (fps 10, 2 FLUX DE backgrounds, 15 s render, no subtitle stream, .srt next to it, Samuel plate/meter crimson) and `video\three_speaker_burn.mp4` (`--burn-subs`, fps 2, subtitle burned + mov_text). Frames in `video\frames\`. Chapters intact. (The ffprobe "Referenced QT chapter track not found" warning also appears on old episodes; it is harmless.)

## Timings per stage (DE ep1)
| Stage | Time |
|---|---|
| TTS + QC, 11 segments (41.9 min audio) | 22:09-23:54 = 105 min (1.3-3.0 min per audio-min; QC redo passes dominate) |
| Mix | ~20 s |
| Align (large-v3-turbo, 6 threads) | 489 s |
| FLUX 20 images | 1317.5 s (22 min) |
| make_video (20 fps, bg 331 s) | ~12.8 min, 209 MB |
| 64k mp3 + staging | <1 min |

## Changelog
- 1.0 (2026-10-14): first template, state of DE ep1.
- 1.1 (2026-10-14): QC v2 audio fixes applied (podcast.ps1, qc_vv.py v2, vv_generate.py glossary/175 words/speakers, new qc_takes.py, qc_mix.py, prep_script.py, glossary.json, voice_f0.json); CPU test on DE files: 7/8 bugs + seg08 c2 flagged, the 30:27 mute is fixed by the new gate. Backups *_backup_pre_qc2.*. Not yet tested in a GPU render.
- 1.2 (2026-10-14): **3 speakers**: script speaker `Guest2`; vv_generate.py `--guest2` (Host=Speaker 1, Guest=2, Guest2=3, renumbered per chunk; aborts if Guest2 lines but no voice; cfg 1.3 / 10 steps / seed 42 unchanged); qc_vv.py and qc_mix.py `--guest2` (F0 reference per Guest2 voice); podcast.ps1 `-Guest2Voice`. **make_video.py**: `--guest2 <name>`, third colour crimson (220,50,70) for plate + level meter (host amber, guest blue), title card "with X (host), Y and Z (guests)"; subtitles NOT burned in by default and no mov_text stream, only `<out>.srt`; `--burn-subs` = old behaviour. **Bug fix**: podcast.ps1 ran qc_takes.py with venv_whisper python, which has no `soundfile` -> `record` and `pick` crashed silently (Out-Null) in v1.1, so the best-take logic never ran and the last take shipped; now venv_vv python, `record` output shown. New `tests\three_speaker\spk_check.py`. Backups `*_backup_pre_3spk.*`. Old episodes not re-rendered.
