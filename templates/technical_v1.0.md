# Technical template
**Version 1.0 - 2026-10-14** (pre-fix state as used for *The Dark Enlightenment* ep1). Never edit; copy to v1.1+. Code snapshot: `code_v1.0\` (+ `SHA256SUMS.txt`).

## Hardware / platform
- Windows 11 PC "DESKTOP-5B87DR9", AMD Radeon RX 7900 XT 20 GB (ROCm/HIP torch on Windows), plus an AMD iGPU = device 0.
- **`HIP_VISIBLE_DEVICES=1` is required** (device 0 = iGPU, crashes). podcast.ps1 and the FLUX/SDXL runs set it.
- CPU/RAM: unknown model; RAM peak ~31.9 GB used during FLUX (hwlogs). HWiNFO64 sensors via VSB registry (hw_monitor.ps1); `Documents\hwinfo.CSV` logging was NOT active during DE (last written 2026-10-13 21:35).

## Pipeline (DE ep1, step by step)
1. Source EPUB/PDF -> read once -> `notes\<book>.md` (Grok Bot cloud).
2. Script from the note (Grok Bot cloud; Gemma `write_script.py` optional/legacy) -> `de\<ep>.json` `[{speaker: Host|Guest, text}]`; split into section files `de\segNN.json` (11 for DE).
3. Fact-check -> `learn\factcheck_<ep>.md`, fix the script.
4. Music: `pw\synth.py` -> `de\intro.wav`, `sting.wav`, `outro.wav`.
5. TTS per segment: `de\render.ps1` loops `podcast.ps1 x de\segNN.mp3 -Script de\segNN.json -HostVoice Carter -GuestVoice Frank -ChunkWords 350 -Seed 42`. Inside: vv_generate.py (VibeVoice) -> qc_vv.py QC + up to 2 redo passes -> qc_vv.py --gate (pause cleanup) -> ffmpeg `highpass=f=70,afftdn=nf=-45:nr=10:tn=1,atempo=0.93,loudnorm=I=-16:TP=-1.5:LRA=11` -> 128k mono mp3.
6. Mix: `de\mix.ps1`: intro (vol 0.6) + seg mp3s (0.4 s apad each) + sting (vol 0.35) between sections (not after seg09 takeaways) + outro (0.6) -> concat -> loudnorm I=-16 -> `<ep>.mp3` 128k mono.
7. Align: `align.py <ep>.mp3 <ep>.json --threads 6` (faster-whisper large-v3-turbo, CPU int8) -> `.whisper.json`, `.timings.json` (DE: 97.2% match).
8. Chapters: hand-written `de\<ep>.chapters.in.json` (start = script line index).
9. Backgrounds: `bg_de1\prompts.json` (20 images) -> `gen_backgrounds_flux.py` (FLUX.1 schnell unsloth snapshot, fp8, `--offload staged`, 4 steps, 1344x768) run under `hwrun.ps1` -> `bg_de1\backgrounds.json`.
10. Video: `make_video.py <ep>.mp3 <ep>.json episodes\<ep>.mp4 --timings --chapters --host Carter --guest Frank --fps 20 --backgrounds bg_de1\backgrounds.json --layout speaker --frames-dir video_frames --frame-suffix _dark --frame-times 300,1300,2200` -> mp4 (burned subs + mov_text), .srt, .chapters.txt/.json, PNG frames.
11. `ffmpeg -ac 1 -b:a 64k` -> `_64k.mp3`; stage in `C:\Users\TJ\Downloads\<x>_stage` for CopyToBox; unload Ollama models (keep_alive 0).
Orchestration for steps 6-11 in DE: `logs\dark_post.ps1` (sequential, waits for render ALLDONE, waits for empty Ollama /api/ps and no VibeVoice before FLUX), progress in `logs\dark_progress.md`.

## Models and roles
| Model | Role | Notes |
|---|---|---|
| Gemma `gemma4:26b-a4b-it-qat` via Ollama | optional script drafting (`write_script.py`) | keep_alive 0; often short turns / HTTP 500; not used for DE |
| microsoft/VibeVoice-1.5B | TTS, 2 speakers | bf16, SDPA, 10 diffusion steps, cfg 1.3, seed 42 (reset per chunk), `--pace sentence`; peak 6.35 GB VRAM. **Do not change settings.** |
| faster-whisper large-v3-turbo (CPU int8) | align.py and qc_vv.py | medium.en/small.en available |
| SDXL base 1.0 fp16 (`gen_backgrounds.py`) | older backgrounds (ep3, Patchwork) | ~10 s/image at 30 steps, 9.05 GB peak |
| FLUX.1 schnell, unsloth snapshot, fp8 layerwise cast (`gen_backgrounds_flux.py`) | backgrounds since DE | 4 steps, `--offload staged`, peak 18.82 GB |
| synth.py (numpy) | intro/stings/outro | no model |
Tested, not used: Dia-1.6B, Higgs Audio v2 3B, Kokoro-82M (test_dia*.py, test_higgs.py).

## Programs / libraries
ffmpeg/ffprobe (PATH from registry); PowerShell 5.1 (no `$ErrorActionPreference=Stop` with native cmds; UTF-8 without BOM for JSON read by make_video.py); venvs: `venv` (stdlib, write_script), `venv_vv` (VibeVoice fork, transformers 4.51.3, ROCm torch), `venv_whisper` (faster-whisper, numpy only - no librosa/scipy), `venv_video` (Pillow), `venv_sd` (diffusers/transformers/accelerate, torch reused from `venv_rocm` via .pth), `venv_higgs`.

## Code inventory (snapshot code_v1.0)
| File | Purpose / key args |
|---|---|
| podcast.ps1 | TTS episode driver. `notes out.mp3 -Script json -HostVoice -GuestVoice -Tempo 0.93 -Pace sentence -Cfg 1.3 -Seed 42 -ChunkWords (default 700; DE used 350) -Steps 10 -QcRetries 2 -NoQc -NoHwMonitor` |
| vv_generate.py | VibeVoice generation, chunked on turn boundaries; `--chunk_words --pause 0.35 --pace --clean_refs --redo i:seed,...`; keeps `<out>.chunks\cNNN.wav` + chunks.json |
| qc_vv.py | Whisper QC per chunk (line coverage <75%, WER >8%, octave pitch jump + low-prob word, >2 low-prob words, noise events > max(6,dur/15)) -> `REDO`; `--gate` fades non-word regions to -60 dB |
| align.py | script-to-audio word alignment (difflib), `--model --threads --words` |
| make_video.py | video render; `--timings --chapters --backgrounds --layout speaker|quote --fps --frame-times --frames-dir --frame-suffix --host --guest --keep-tmp` |
| gen_backgrounds.py / gen_backgrounds_flux.py | SDXL / FLUX images from prompts.json; `--steps --w --h --seed --only`, FLUX `--model --offload staged|model|seq|none --fp8` |
| write_script.py | Gemma script drafting (`--lines --topic --ctx`) |
| check_sync.py | subtitle/audio sync check by episode stem |
| hw_monitor.ps1 / hwmon_lib.ps1 / hwrun.ps1 | HWiNFO VSB sensor logging to hwlogs\ |
| mk_style.py | FLUX style A/B/C comparison prompts |
| pw\synth.py | music synthesis (drone, saw, plucks) |
| de\render.ps1, de\mix.ps1, pw\render.ps1, logs\dark_post.ps1 | per-episode render/mix/post helpers |

| Snapshot file | Bytes | SHA256 (16) |
|---|---|---|
| `align.py` | 5422 | `C35424A88224E48F` |
| `check_sync.py` | 1502 | `FAAF64A759948D35` |
| `gen_backgrounds.py` | 2433 | `47F17D1C66E5EACA` |
| `gen_backgrounds_flux.py` | 3940 | `7F5E02B8821DA4C9` |
| `hwmon_lib.ps1` | 955 | `F90957DA655BEE5C` |
| `hwrun.ps1` | 788 | `ED99A045BC92AA5C` |
| `hw_monitor.ps1` | 5188 | `30B65AB14D7C24E5` |
| `make_video.py` | 29079 | `0C755BEDB8841BCB` |
| `mk_style.py` | 1729 | `237B6B02CDA40D71` |
| `podcast.ps1` | 5238 | `5BC8CDF42BB30412` |
| `qc_vv.py` | 7767 | `D92A73B46C9CD7FE` |
| `README.md` | 12556 | `80BD608E57A3D028` |
| `vv_generate.py` | 6466 | `1B9C7376E164D189` |
| `write_script.py` | 3016 | `DFE47AAAB423995C` |
| `de\mix.ps1` | 891 | `88FFAC3133A1A074` |
| `de\render.ps1` | 404 | `4B9DB16A0C40954D` |
| `logs\dark_post.ps1` | 2809 | `B3CE72163733359F` |
| `pw\render.ps1` | 401 | `CFD1BD41D4EA2225` |
| `pw\synth.py` | 1811 | `4885A18E092790E6` |

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
See `logs\dark_bug_diagnosis.md`. Root causes: no QC after the final redo (9 chunks shipped unverified), 350-word chunks, no F0-drift/rate/silence/music checks, pause gate muting real speech when Whisper drops words (30:27), hard terms. **Proposed fixes (status in v1.0: proposed, not applied):** QC after every redo + best take, QcRetries 3, final qc.json; ChunkWords 150-200 + merge one-word lines; F0 drift / speech rate / silence / music checks; per-line WER + hard-term glossary; gate safety; phonetic respelling; final mixed-mp3 QC.
Other: duplicate post-pipeline launches overlapped mixes (mp3 OK, first align truncated); agent connection drops (PC unaffected).

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