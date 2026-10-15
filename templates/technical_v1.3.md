# Technical template
**Version 1.3 - 2026-10-15** (v1.2 + 7B audio.cpp default engine, Carter host + random guests (no default cast), no glossary, soft f0_drift + per-voice F0 calibration, 275-word chunks, lighter post chain, voices_extra + credits, length rule; own LibreHardwareMonitor hardware logger replaces HWiNFO logging, 15 Oct). Never edit; copy to v1.4+. Code snapshot: `code_v1.3\` (+ `SHA256SUMS.txt`). Content style unchanged (`content_style_v2.0.md`).

## v1.3 defaults (supersede the v1.2 text below wherever they differ)
| Item | v1.2 | **v1.3 default** |
|---|---|---|
| TTS engine | VibeVoice-1.5B (`podcast.ps1`, torch/ROCm) | **VibeVoice-7B Q8_0 GGUF via audio.cpp v0.9.1, Vulkan, Idle priority**: `render7b.ps1` + `vv7b_generate.py` (`tests\vv7b_cpp\bin\audiocpp_cli.exe`, `models\vibevoice-7b-q8_0.gguf`). Backups: VV-1.5B (`podcast.ps1`), SoulX-Podcast-1.7B (`tests\soulx\run_soulx.py`, test script only) |
| Cast | Carter + Frank (+ Alice/Samuel tests) | **No default cast.** Host = Carter; Guest/Guest2 random per episode from Frank, Clara, Maya, Isla, Marcus, Declan (Samuel low priority), gender-aware, F0 gap >= 12 Hz (section 2a). Never Alice, Mary (music in the clip), Thomas |
| Glossary | respellings (`glossary.json`) | **OFF**: `empty_glossary.json`; write hard terms normally in the script. `glossary.json` stays available (`-Glossary`) |
| Chunk size | 175 words (1.5B); 350 in dm_v2/UI | **275 words, always ending on turn boundaries** (a single longer line is its own chunk) |
| QC | retries 3, every flag hard | **QcRetries 2** (seeds 42, 1988, 3042), QC after every take, **best take ships**; **f0_drift = soft flag** (reported, scored 3 instead of 10, never retries alone) |
| F0 reference | Carter 131.1, Frank 127.5 | `voice_f0.json` per voice (table below) |
| Post chain | `highpass 70, afftdn nf=-45 nr=10 tn=1, atempo 0.93, loudnorm -16/-1.5/11` | `highpass 70, equalizer f=3000 t=o w=2 g=+1.5, deesser i=0.4 m=0.5 f=0.5, atempo 0.93, loudnorm -16/-1.5/11` (**afftdn off**; `-AfftdnNr 4` = soft; `-Old` reproduces the v1.2 chain bit-exactly) |
| Length | - | rule below; duration gate 40-45 min in `post_episode.ps1` |
| Orchestration | per-episode ad-hoc scripts | `run_episode.ps1` (detached, `<Dir>\STATUS.txt`, resumable) -> `render7b.ps1` -> FLUX -> `post_episode.ps1` |

### 1) Engine: 7B audio.cpp default (data from shootout2 2026-10-14 and the two 7B episodes)
- shootout2 (443-word das Man excerpt, Carter/Frank/Samuel, seed 42, no glossary): WER 3.38% (1.5B) / 1.58% (SoulX) / **1.58% (7B)**; align 96.8 / 98.9 / 98.6%; **RTF 0.82 / 1.44 / 0.44**; VRAM adapter +7.6 / +8.8 / +12.0 GB; no speaker mix-ups in any. Files: `tests\shootout2\results.md`, `ab\*.mp3`.
- Episode use: das Man ep1 v2 (23 chunks of ~350 words, TTS+QC 90 min for 40:37 audio) and Uploaded Intelligence ep1 (23 chunks, 84 min for 38:22 raw / 40:46 final). Generation runs ~0.5x realtime (e.g. 111 s audio in 57 s); most wall time is whisper QC on the CPU. Peak VRAM 17.7-18.1 GB adapter (desktop baseline 4.6-4.9 GB). Heat (hwlogs): GPU core max 70-71 C, hotspot max 90 C, memory junction max 96-97 C (avg 84-85), 311 W max, no throttling, no hotspot sample > 95 C.
- **7B behaviour to expect:** hallucinated/garbled openings and noise bursts at turn starts still happen (QC catches them: dm_v2 seg00 c1 unrecognised speech + noise; UI seg04 c3 WER/bad_lines/rate). First-take results over 23 chunks each: **dm_v2 15 clean / 3 fixed by a retry / 5 shipped with a remaining `noise` flag; UI ep1 11 clean / 8 fixed / 4 shipped still flagged** (noise or f0_drift or lowprob; max shipped chunk WER 4.4% (dm_v2) / 6.3% (UI)).
- Backups: **VV-1.5B** = `podcast.ps1` (v1.3 defaults applied, same post chain). **SoulX-Podcast-1.7B** = `tests\soulx\run_soulx.py` in `venv_soulx` (torch borrowed from `venv_rocm`), RTF 1.44, more noise events (16 vs 10) in shootout2, F0 closest to the prompts for Carter; it is a test script bound to `three_speaker.json`, not wired into the pipeline (needs a driver like `vv7b_generate.py` if it is ever used).
- audio.cpp CLI recipe (what `vv7b_generate.py` runs per chunk): `audiocpp_cli.exe --task tts --family vibevoice --model <gguf> --backend vulkan --device 0 --threads 6 --seed S --guidance-scale 1.3 --num-inference-steps 10 --request-option voice_samples=a.wav,b.wav,c.wav --text "Speaker 1: ...\nSpeaker 2: ..." --out c001.wav --log-file c001.cli.log`. Reference prompts are capped at 10 s internally (linear resample, libsoxr missing). `Speaker 1/2/3` = Host/Guest/Guest2 renumbered per chunk.

### 2) Cast and voices (see 2a for the random pick) (`voices.json`, `voices_extra\LICENSES.md`)
| Voice | Gender / accent | Source | Licence | Credit needed | Note |
|---|---|---|---|---|---|
| Carter, Frank | M, US | VibeVoice demo voices | not verified | no | Carter = default Host; Frank = pool guest (not next to Carter: F0 gap 1.6 Hz) |
| **Clara** | F, US (presumed) | LibriTTS-R speaker 84 | CC BY 4.0 | **yes** | pool guest; used in das Man ep1 v2 |
| Maya | F, US | VibeVoice demo voice | not verified | no | other shows; 7B test WER 0, F0 +3.8%; used in UI ep1 |
| Isla | F, Scottish (West Dumfries) | VCTK p234 | CC BY 4.0 | yes | passed 7B test (WER 0, no noise, F0 +8.8%) |
| Marcus | M, US (presumed) | LibriTTS-R speaker 2086 | CC BY 4.0 | yes | passed test (F0 +10.5%) |
| Declan | M, Irish (Dublin) | VCTK p245 | CC BY 4.0 | yes | passed test (F0 +5.9%, deep ~95 Hz) |
| Samuel | M, Indian English | demo voice | - | no | not a default; usable |
| Alice / Mary | - | demo | - | - | **never** (blocked in `vv7b_generate.py`; Mary has background music) |
Credits: `post_episode.ps1` reads `voices.json` and appends the credit line of every cast voice that has one to `episodes\<ep>.notes.md` and the end of `<ep>.chapters.txt` (Clara: "Voice credit: the voice of Clara is synthesized from a reference recording of LibriTTS-R speaker 84 (Y. Koizumi et al., ..., Interspeech 2023; CC BY 4.0, https://www.openslr.org/141/), derived from public-domain LibriVox recordings."; VCTK voices: Yamagishi, Veaux, MacDonald, Univ. of Edinburgh 2019, CC BY 4.0, doi 10.7488/ds/2645). The suggested one-line general credit in LICENSES.md is an alternative. The earlier das Man ep1 v2 notes carry the Clara line already.

### 2a) Cast selection (v1.3, no default cast) - `pick_cast.py`
**Correction (15 Oct, Thomas): there is NO default cast.** An earlier v1.3 text said "default cast Carter + Frank + Clara"; that is withdrawn. Only the Host is fixed (Carter, unless Thomas says otherwise); guests are picked at random per episode.

- **Host** = Carter (`voices.json` `host_default`; `-HostVoice` overrides). **Guest / Guest2** are picked at random per episode from `voices.json` `pool`: **Frank, Clara, Maya, Isla, Marcus, Declan**; **Samuel** is allowed at low priority (weight 0.25 vs 1.0). **Never Alice, Mary, Thomas** (blocked, also rejected on override).
- **Gender**: if the script says so, the pick respects it. `run_episode.ps1 -GuestGenders "M,F"` = Guest male, Guest2 female (or `<Dir>\cast_request.json`). Without it any gender is allowed.
- **F0 gap rule**: every pair in the cast (Host-Guest, Host-Guest2, Guest-Guest2) must differ by **>= 12 Hz** in `voice_f0.json` (7B, 3-speaker). Carter 132.2 and Frank 130.6 (gap 1.6 Hz) are indistinguishable, so **Frank is never picked next to Carter while any other voice qualifies; Samuel (132.2, provisional) likewise.** With host Carter the male guests are therefore **Marcus (gap 20 Hz) or Declan (37 Hz)**; female: Clara, Maya, Isla (Maya + Isla never together: 202.5 vs 200.0). Frank and Samuel become eligible with a host far from 131 Hz (e.g. host Declan). If no pair satisfies the rule the pick takes the largest minimum gap and writes a warning to cast.json / STATUS / notes.
- **Algorithm**: enumerate all valid (Guest, Guest2) permutations (gender + gap + not blocked), draw one with `random.Random(seed).choices(weights)` over a deterministically sorted list. The seed is `--seed` / `-CastSeed` or a fresh `SystemRandom` seed; it is stored.
- **Where it runs**: `run_episode.ps1` (step 0, only if `<Dir>\cast.json` is missing, so a resumed run keeps the same cast; Guest2 is auto-detected from `seg*.json`). Then `render7b.ps1` and `post_episode.ps1` read `<Dir>\cast.json`; neither has a default guest any more and both abort if there is no cast. `podcast.ps1` (1.5B) picks when `-GuestVoice` is empty (`<out>.cast.json`). Manual: `python pick_cast.py --out <Dir>\cast.json --host Carter --roles Guest,Guest2 [--genders M,F] [--seed N]`.
- **Override**: `-Guests "Marcus,Isla"` (run_episode) / `--guests A,B` (pick_cast): validated (pool/blocked), F0 and gender conflicts are only warnings. Reproduce a random pick with `-CastSeed <seed>` (+ same `-GuestGenders`).
- **Logging**: `cast.json` (host, guest, guest2, mode random|override, seed, genders required, F0 gaps, warnings, reproduce command); `STATUS.txt` + `chain.log` line `cast: host= guest= guest2= mode= pick_seed= warnings=`; `post_episode.ps1` adds "Cast pick: mode, seed, genders required, F0 gaps, reproduce" to `episodes\<ep>.notes.md` and the Prog log.
- **Credits**: unchanged: `post_episode.ps1` adds the CC BY credit line of every voice in the final cast that has one (Clara, Marcus, Isla, Declan) to the notes and chapters.txt.
- Tests (CPU only, `tests\v13_check\cast\`): host Carter, genders M,F, 150 seeds: male guest only Marcus/Declan, female Clara/Maya/Isla, never Frank/Samuel, never Maya+Isla; host Declan: Frank and Samuel can appear.

- **Pool update (15 Oct 2026, Thomas):** random guest pool is now Frank, Clara, Isla, Marcus, Declan, with Samuel at low weight (0.25); **Maya excluded** (sounds artificial; entry and F0 kept in oices.json, usable only via explicit -Guests override, pick_cast.py warns). With host Carter and genders M,F the female guest is only Clara or Isla (150-seed test).
- **Pool update 2 (15 Oct 2026, Thomas):** Willa, Zara, Imogen, Elliot, Hugh and Lachlan (VCTK, CC BY 4.0, credit auto-added; provisional F0 165/178/219/110/144/83) added to the random guest pool, which is now Frank, Clara, Isla, Marcus, Declan, Willa, Zara, Imogen, Elliot, Hugh, Lachlan, with Samuel at low weight and Maya excluded; with host Carter Hugh (144 Hz) is 11.8 Hz away, so the 12 Hz gap rule never picks him next to Carter (200-seed test, 0 violations).

### 3) Glossary OFF
Respellings (v1.1/1.2) are not applied: `empty_glossary.json` is passed to `vv7b_generate.py`, `vv_generate.py` and `qc_vv.py` (so the glossary QC check has nothing to look for). Write terms normally in the script (das Man v2 and UI ep1 were rendered this way).

### 4) Softer QC + F0 calibration (`voice_f0.json`)
- `qc_vv.py` v2.1: `--soft f0_drift` (default). A chunk is retried only if it has a hard flag (wer, bad_lines, pitch_glitch, lowprob, noise, line_wer, glossary, rate, unrecognised). Score = 10 x hard flags + 3 x soft flags + the old terms, so best-take still prefers less drift. On the real takes of the two 7B episodes this would have avoided **3 of 36 generations in dm_v2 and 3 of 40 in UI ep1** (`tests\retries_from_takes.py`); the shipped takes would not change (rescoring the final qc.json files: only UI seg03 c1 loses its retry flag).
- **Measured generated-speech F0 per voice (Hz)** - median over lines >= 5 words in the final qc.json (qc_vv f0_track), 7B, 3-speaker context:
| Voice | median F0 | lines | observed p10-p90 | source |
|---|---|---|---|---|
| Carter | **132.2** | 81 | 117-146 | dm_v2 40 lines (132.2) + UI 41 (131.1) |
| Frank | **130.6** | 80 | 117-149 | dm_v2 42 (132.2) + UI 38 (127.5) |
| Clara | **228.6** | 35 | 208-246 | dm_v2 (voice eval single line 225.4, prompt 222.2) |
| Maya | **202.5** | 39 | 190-216 | UI ep1 (eval 205.1, prompt 197.5) |
| Isla | 200.0 *provisional* | 0 (1 test line) | - | 7B test line, prompt 183.9 |
| Marcus | 152.4 *provisional* | 0 (1 test line) | - | 7B test line, prompt 137.9 |
| Declan | 95.2 *provisional* | 0 (1 test line) | - | 7B test line, prompt 89.9 |
  The three provisional values come from one 41-word single-speaker test line each (same qc f0 method); replace them with episode medians after first use (`tests\f0_episode_stats.py`). Old 1.5B 2-speaker values were Carter 131.1 / Frank 127.5. **Carter and Frank are indistinguishable by F0** (132 vs 131 Hz); speaker-ID needs `tests\spk_check.py`. The +/-15% tolerance still fits (p10-p90 spread is about -11%/+12%).

### 5) Chunking
`--chunk_words 275` (was 175 for the 1.5B; 350 used for the 7B episodes). Chunks always end on turn boundaries; only whole lines are packed. Untested in a render (no TTS was run for v1.3): more chunks means more chunk openings (where 7B hallucinations/noise bursts cluster) but less in-chunk drift; check the first episode's first-take clean rate against the 15/23 and 11/23 above.

### 6) Post chain A/B (CPU, `dm_v2\seg02.raw.wav` gated, whole segment 242.7 s, same atempo 0.93 + loudnorm in both chains)
Metrics are speech-frame means (frames > -40 dBFS), 44.1 kHz decode of the 128k mp3 (`tests\spectral_ab.py`; the 24 kHz source has no content above 12 kHz, so "air" = 10-12 kHz):
| | raw gated | **old chain** | **new chain** | new - old |
|---|---|---|---|---|
| spectral centroid, mean spectrum | 621 Hz | 605 Hz | **622 Hz** | +17 Hz |
| spectral centroid, median per frame | 399 Hz | 413 Hz | **438 Hz** | +25 Hz (+6%) |
| presence 2-4 kHz (dB of total) | -15.03 | -15.20 | **-14.25** | +0.95 dB |
| sibilance 5-9 kHz, sibilant frames (dB) | -9.68 | -9.61 | **-10.24** | -0.63 dB |
| air 10-12 kHz (dB of total) | -30.33 | -29.85 | **-31.73** | -1.88 dB |
| noise floor p5 frame level | -67.1 | -63.0 | -61.0 | +2.0 dB (gate floor is -60 dB) |
| integrated loudness / LRA | -25.8 / 6.2 | -17.3 / 5.4 | -17.4 / 5.5 | ~equal |
- afftdn nr=10 (old) vs none: air band, sibilance and centroid unchanged within 0.1 dB / 6 Hz on this gated segment - it only lowered the quiet floor by about 2 dB. So it was dropped (no measurable benefit, risk of "watery" artefacts); `-AfftdnNr 4` available.
- Presence bell alone: +47 Hz mean centroid, +1.1 dB presence. De-esser (i=0.4): -1.0 dB sibilance (5-9 kHz) but **also -1.9 dB at 10-12 kHz** (broad action); i <= 0.3 had no measurable effect (nonlinear threshold). If the voices sound too dull, use `-DeEss 0` (air back to the old level, presence/centroid gain kept).
- Listening pair (same loudness, -16.4 / -16.5 LUFS after matching): first 75 s of seg02 (Carter, Clara, Frank), old chain then new chain: box `/workspace/template13/` (`A_old_chain.mp3`, `B_new_chain.mp3`, `AB_pair_old_then_new.mp3` = 1 beep + A, 2 beeps + B). **Objective metrics only - needs Thomas' ears.**
- `post_segment.ps1 -Old` output on seg02 decodes bit-identically to the original `dm_v2\seg02.mp3`, so the old chain is reproducible.

### 7) Length rule (HARD 40-45 min = 2400-2700 s mix)
Measured with the 7B at tempo 0.93: speech = **0.37-0.39 s per script word** (das Man v2: 6,106 words -> 2375 s = 0.389 s/word, 154 wpm; Uploaded Intelligence: 6,040 words -> 2244 s = 0.3715 s/word, 161 wpm - depends on the cast/script). Mix overhead (intro 9 s + outro 14 s + stings 3.5 s each + 0.4 s gap per segment) = **58-62 s** for 10-11 segments.
`mix seconds ~= words x 0.37..0.39 + 60` -> **script length 6,300-6,800 words** lands inside 40-45 min with the default tempo (6,000 words is the very edge; UI ep1 with 6,040 words gave 38:22 and failed the gate).
Levers, in this order:
1. Write 6,300-6,800 words (preferred; do not stretch audio to rescue a short script).
2. `-Tempo` 0.90-0.97 (duration ~ 1/tempo; 0.93 -> 0.90 = +3.3%, ~+77 s on 2244 s). 0.90 is the lowest allowed value (Thomas' range 0.90-0.97). Re-run `post_segment.ps1 -Raw segNN.raw.wav ... -Tempo 0.90` from the kept raw wavs (no TTS; gate = CPU whisper), rather than re-tempoing finished mp3s (double loudnorm).
3. `post_episode.ps1 -SegGap 1.2 -StingPad 0.6` (UI ep1: segment gap 0.4 -> 1.2 s, 0.6 s silence either side of each sting: about +19 s).
4. Stretch intra-segment pauses (`tools\stretch_pauses_repost_ui1.py`, reference only: +0.145 s on each of 344 pauses >= 0.45 s = about +50 s).
UI ep1 final = 2243.8 x 0.93/0.90 + 50 + 19 + 58 = 2445.7 s (40:46). `post_episode.ps1` stops with exit 3 *before align/video* if the mix is outside `-MinDur 2400 -MaxDur 2700`.

### 8) Running it (reliability)
Foreground tool calls die when the session is interrupted (happened 4 times in dm_v2/UI). Always start `run_episode.ps1` detached (`Start-Process ... -WindowStyle Hidden`), poll `<Dir>\STATUS.txt` / `chain.log` with calls under ~20 s. `render7b.ps1` skips segments that already have a finished mp3 + qc.json, so a restart resumes. GPU rules unchanged: Ollama `/api/ps` empty first, one GPU model at a time (TTS finishes before FLUX), Idle priority, nothing left running, no reboot.

---
## v1.2 text (still valid except where v1.3 above differs)

## Hardware / platform
- Windows 11 PC "DESKTOP-5B87DR9", AMD Radeon RX 7900 XT 20 GB (ROCm/HIP torch on Windows), plus an AMD iGPU = device 0.
- **`HIP_VISIBLE_DEVICES=1` is required** (device 0 = iGPU, crashes). podcast.ps1 and the FLUX/SDXL runs set it.
- CPU/RAM: unknown model; RAM peak ~31.9 GB used during FLUX (hwlogs). HWiNFO64 sensors via VSB registry (hw_monitor.ps1); `Documents\hwinfo.CSV` logging was NOT active during DE (last written 2026-10-13 21:35).

## Pipeline (DE ep1, step by step)
1. Source EPUB/PDF -> read once -> `notes\<book>.md` (Grok Bot cloud).
2. Script from the note (Grok Bot cloud; Gemma `write_script.py` optional/legacy) -> `de\<ep>.json` `[{speaker: Host|Guest, text}]`; split into section files `de\segNN.json` (11 for DE).
3. Fact-check -> `learn\factcheck_<ep>.md`, fix the script.
4. Music: `pw\synth.py` -> `de\intro.wav`, `sting.wav`, `outro.wav`.
5. (v1.3: use `render7b.ps1 -Dir <dir>` / `run_episode.ps1` instead - 7B audio.cpp, 275-word chunks, no glossary, QcRetries 2, soft f0_drift, new post chain; the 1.5B text follows.) TTS per segment: run `prep_script.py` on the full script BEFORE chapters/backgrounds (merges <=2-word lines), then loop `podcast.ps1 x segNN.mp3 -Script segNN.json -HostVoice Carter -GuestVoice <guest> -Seed 42` (defaults now -ChunkWords 175, -QcRetries 3). Inside: vv_generate.py (VibeVoice, glossary respelling on TTS text only) -> qc_vv.py v2 QC after EVERY pass, qc_takes.py records takes, best take per chunk ships, final qc.json (final=true) -> qc_vv.py --gate (safe pause cleanup, keeps unrecognised speech) -> ffmpeg `highpass=f=70,afftdn=nf=-45:nr=10:tn=1,atempo=0.93,loudnorm=I=-16:TP=-1.5:LRA=11` -> 128k mono mp3.
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
| VibeVoice-7B Q8_0 GGUF via audio.cpp v0.9.1 (Vulkan) | **DEFAULT TTS (v1.3)**, 3 speakers via `voice_samples=a,b,c`; seed/cfg 1.3/10 steps | 10.6 GB gguf, adapter +12 GB, RTF ~0.44-0.5, Idle priority; `tests\vv7b_cpp\` |
| SoulX-Podcast-1.7B (`venv_soulx`) | backup TTS (test script only) | RTF 1.44, `tests\soulx\` |
| microsoft/VibeVoice-1.5B | BACKUP TTS (v1.3), 2-3 speakers (Host/Guest/Guest2; tested 3 in one chunk) | bf16, SDPA, 10 diffusion steps, cfg 1.3, seed 42 (reset per chunk), `--pace sentence`; peak 6.35 GB VRAM. **Do not change settings.** |
| faster-whisper large-v3-turbo (CPU int8) | align.py and qc_vv.py | medium.en/small.en available |
| SDXL base 1.0 fp16 (`gen_backgrounds.py`) | older backgrounds (ep3, Patchwork) | ~10 s/image at 30 steps, 9.05 GB peak |
| FLUX.1 schnell, unsloth snapshot, fp8 layerwise cast (`gen_backgrounds_flux.py`) | backgrounds since DE | 4 steps, `--offload staged`, peak 18.82 GB |
| synth.py (numpy) | intro/stings/outro | no model |
Tested, not used: Dia-1.6B, Higgs Audio v2 3B, Kokoro-82M (test_dia*.py, test_higgs.py).

## Programs / libraries
ffmpeg/ffprobe (PATH from registry); PowerShell 5.1 (no `$ErrorActionPreference=Stop` with native cmds; UTF-8 without BOM for JSON read by make_video.py); venvs: `venv` (stdlib, write_script), `venv_vv` (VibeVoice fork, transformers 4.51.3, ROCm torch), `venv_whisper` (faster-whisper, numpy only - no librosa/scipy), `venv_video` (Pillow), `venv_sd` (diffusers/transformers/accelerate, torch reused from `venv_rocm` via .pth), `venv_higgs`.

## Code inventory (snapshot code_v1.3; v1.3 additions: vv7b_generate.py, render7b.ps1, post_segment.ps1, post_episode.ps1, run_episode.ps1, voices.json, empty_glossary.json, tests\spectral_ab.py, retries_from_takes.py, f0_voice_eval.py, f0_episode_stats.py, tools\stretch_pauses_repost_ui1.py; changed: qc_vv.py v2.1, qc_mix.py, voice_f0.json, podcast.ps1, vv_generate.py, README.md)
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
| hw_monitor.ps1 / hwmon_lib.ps1 / hwrun.ps1 | HWiNFO VSB sensor logging to hwlogs\ (old, now the fallback). **v1.3: primary = `C:\grok\hwmon\hwmon.exe` + `hwmon_lib.ps1` (section 9); hwrun.ps1 / podcast.ps1 / render7b.ps1 use it** |
| mk_style.py | FLUX style A/B/C comparison prompts |
| pw\synth.py | music synthesis (drone, saw, plucks) |
| de\render.ps1, de\mix.ps1, pw\render.ps1, logs\dark_post.ps1 | per-episode render/mix/post helpers |

| Snapshot file (code_v1.3) | Bytes | SHA256 (16) |
|---|---|---|
| `README.md` (changed) | 20368 | `B6AAB2BF2D827A00` |
| `align.py` | 5422 | `C35424A88224E48F` |
| `check_sync.py` | 1502 | `FAAF64A759948D35` |
| `empty_glossary.json` (new) | 191 | `21C17DB893BF3D11` |
| `gen_backgrounds.py` | 2433 | `47F17D1C66E5EACA` |
| `gen_backgrounds_flux.py` | 3940 | `7F5E02B8821DA4C9` |
| `glossary.json` | 764 | `A19F6937469517A9` |
| `hw_monitor.ps1` | 5188 | `30B65AB14D7C24E5` |
| `hwmon_lib.ps1` | 955 | `F90957DA655BEE5C` |
| `hwrun.ps1` (changed) | 926 | `9E5D25F19A7E0EFE` |
| `make_video.py` | 30140 | `B701A58C23DF05D6` |
| `mk_style.py` | 1729 | `237B6B02CDA40D71` |
| `pick_cast.py` (new) | 6508 | `9D81C76073690659` |
| `podcast.ps1` (changed) | 9780 | `78D7728256C833DB` |
| `post_episode.ps1` (new) | 6569 | `0663EB41791DFE6A` |
| `post_segment.ps1` (new) | 2403 | `A709BE8CF6ABE8F9` |
| `prep_script.py` | 1630 | `E3F10F4DE90187BB` |
| `qc_mix.py` (changed) | 4423 | `6365CFF11D3C91A2` |
| `qc_takes.py` | 2391 | `5C0546FB1D80C3DB` |
| `qc_vv.py` (changed) | 16176 | `4F7726BAC6E84815` |
| `render7b.ps1` (new) | 5581 | `1E9468A4B6B36125` |
| `run_episode.ps1` (new) | 4345 | `7A6FCB5803C7263A` |
| `voice_f0.json` (changed) | 1710 | `B4B61482FA42B3CB` |
| `voices.json` (new) | 7785 | `5D77C6785D5580D7` |
| `vv7b_generate.py` (new) | 7563 | `F7E38062C814E7FC` |
| `vv_generate.py` (changed) | 7646 | `F4001FE4428AD368` |
| `write_script.py` | 3016 | `DFE47AAAB423995C` |
| `hwmon_new\compare_hwinfo.ps1` (new, own monitor snapshot) | 4650 | `D390611C0D0192BF` |
| `hwmon_new\hwmon.cs` (new, own monitor snapshot) | 18301 | `0C3AF9B930244F49` |
| `hwmon_new\hwmon.exe.config` (new, own monitor snapshot) | 605 | `7AFD3C46EF805B39` |
| `hwmon_new\hwmon_ctl.ps1` (new, own monitor snapshot) | 783 | `47B2E15FFBF3D424` |
| `hwmon_new\hwmon_lib.ps1` (new, own monitor snapshot) | 3160 | `5ADC660E3EE6C3F6` |
| `hwmon_new\install_admin.ps1` (new, own monitor snapshot) | 4237 | `E10B5597F64BD112` |
| `hwmon_new\last_before.ps1` (new, own monitor snapshot) | 964 | `7EA77A45E9729E49` |
| `hwmon_new\README.md` (new, own monitor snapshot) | 5161 | `19E3365CEF21D12B` |
| `de\mix.ps1` | 891 | `88FFAC3133A1A074` |
| `de\render.ps1` | 404 | `4B9DB16A0C40954D` |
| `logs\dark_post.ps1` | 2809 | `B3CE72163733359F` |
| `pw\render.ps1` | 401 | `CFD1BD41D4EA2225` |
| `pw\synth.py` | 1811 | `4885A18E092790E6` |
| `tests\f0_episode_stats.py` (new) | 873 | `19B929879D65124B` |
| `tests\f0_voice_eval.py` (new) | 1186 | `4E394B9CF524C970` |
| `tests\retries_from_takes.py` (new) | 667 | `CD57D41621745D83` |
| `tests\spectral_ab.py` (new) | 1674 | `CBFFF7C83C0A7B66` |
| `tests\spk_check.py` | 4325 | `9E7B930314797A13` |
| `tools\stretch_pauses_repost_ui1.py` (new) | 1079 | `02DE4CF92CFD8E63` |

## GPU rules
(v1.3: also applies to audio.cpp/Vulkan runs - Idle priority, ~12-18 GB adapter VRAM.) One GPU model at a time; check for stale python/GPU processes first; Ollama keep_alive 0 and wait for empty `/api/ps` before VibeVoice/FLUX; unload everything at the end (Thomas games). Do not touch VibeVoice model settings. Whisper runs on CPU.

## Model test log
- **SDXL vs FLUX:** SDXL ~10 s/image (30 steps), weaker composition. FLUX schnell fp8: ~140 s/image with offload in early tests; **DE run 46-63 s/image (1317.5 s for 20)**, peak 18.82 GB torch / ~19.7 GB VRAM; GPU hotspot max 91 C in DE (avg 84.7), 91-102 C reported in earlier tests; no throttling in DE (HTC 0, hotspot limit max 80.5%).
- **FLUX styles** (`bg_flux_style\A|B|C`): A = matte painting, amber lamplight; B = cinematic photograph, cold teal/blue; **C = concept art, semi-realistic, amber/teal -> chosen**, then strengthened (visible brush strokes, rich warm amber glow, film grain, "no text").
- **VibeVoice issues:** garbled words (hard terms, one-word lines after silence), voice/pitch drift within long chunks (DE seg01 c2 host F0 173 Hz vs ~130), random BGM-like music + slow voice (DE seg04 c1), onset noise bursts; Mary voice has background music (never use). cfg 1.5/1.8, 20 steps, clean refs did not help (A/B 2026-10-13).
- **Whisper:** large-v3-turbo default since 2026-10-13 (ab_test\README_ab.txt).

## Scripting: local LLM vs cloud
Gemma (local) gave too short/few turns for 150+ turn scripts and HTTP 500s; Grok Bot cloud does note, script, fact-check and orchestration. Token use: Patchwork ep1 ~500k, DE ep1 ~130k (rough).

## Known bugs / DE diagnosis
See `logs\dark_bug_diagnosis.md`. Root causes: no QC after the final redo, 350-word chunks, no F0/rate/silence/music checks, the gate muting real speech, hard terms. **Status in v1.1: fixes APPLIED (approved 2026-10-14)**: QC after every pass + best take + final qc.json, QcRetries 3, ChunkWords 175 + prep_script.py merging, F0 drift / rate / unrecognised-audio (silence/music/babble) checks, per-line WER + glossary, safe gate, respelling (TTS only), qc_mix.py.


### 9) Hardware monitor: own LibreHardwareMonitor logger (added 15 Oct 2026, replaces HWiNFO logging)
HWiNFO free stops sharing sensors after 12 h, so the pipeline now logs with **`C:\grok\hwmon\hwmon.exe`** (LibreHardwareMonitorLib 0.9.6, MPL-2.0; C#, no SDK needed), run by the Scheduled Task **HwMon** (at logon, highest privileges, no time limit). Driver: PawnIO 2.2.0 (LHM 0.9.6 has no WinRing0). Docs: `C:\grok\hwmon\README.md` (copy in `code_v1.3\hwmon_new\`).
- **Pipeline switch**: `podcast.ps1`, `render7b.ps1` and `hwrun.ps1` (live + `code_v1.3`) now dot-source `C:\grok\hwmon\hwmon_lib.ps1` (falls back to `<root>\hwmon_lib.ps1`, the old HWiNFO lib, if the new file is missing). `run_episode.ps1` gets it through `render7b.ps1`. `Start-HwMonitor "<name>"` / `Stop-HwMonitor $h` keep their API; the daemon writes the session log; if the daemon is not alive the lib runs `schtasks /run /tn HwMon`, and if that fails it starts the old `hw_monitor.ps1` (HWiNFO VSB). The old `hw_monitor.ps1`, `hwmon_lib.ps1` and HWiNFO stay in place as the fallback.
- **Logs** (`hwlogs\`): session `<run>_<ts>.csv` (same 14 columns as before; `GpuHotLimit_pct` and `CpuHTC` blank) + `.summary.txt` (same max/avg, energy, hotspot>95 format) + `.summary_full.txt` (min/max/avg of all ~257 sensors); continuous `hwmon_cont_<day>.csv` (same columns) and `hwmon_full_<day>.csv` (all sensors), rotated daily.
- **Limits** (LHM, see the hwmon README): Vcore (Super I/O) reads ~1.8x high and Core VID is wrong; no SVI3 VRM telemetry, per-core temps, PPT/TDC/EDC limits, HTC/PROCHOT, GPU VRM/memory-chip temps. Old backups: `*_backup_pre_newhwmon.ps1` (live root), `code_v1.3\_backup_pre_hwmon\`, `technical_v1.3_backup_pre_hwmonswitch.md`.

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
- 1.3 (2026-10-15): **new defaults approved by Thomas**: (1) 7B Q8 audio.cpp is the default engine (`render7b.ps1`, `vv7b_generate.py`, `post_segment.ps1`, `post_episode.ps1`, `run_episode.ps1`), VV-1.5B and SoulX documented as backups; (2) **no default cast** (Thomas, 15 Oct: only the Host is fixed; guests random per episode from the pool, gender-aware, F0 gap >= 12 Hz, seed logged; earlier "Carter + Frank + Clara" statement withdrawn; `pick_cast.py`, `cast.json`), `voices_extra` (Clara, Isla, Marcus, Declan; CC BY 4.0) with `voices.json` registry and automatic credit lines; (3) glossary respellings OFF (`empty_glossary.json`); (4) QcRetries 2, `f0_drift` soft (`qc_vv.py` v2.1 `--soft`), `voice_f0.json` recalibrated per voice from das Man v2 / UI ep1 / voice eval; (5) ChunkWords 275 on turn boundaries; (6) post chain: afftdn off, +1.5 dB presence bell, de-esser, atempo 0.93, loudnorm -16 (A/B above); length rule + duration gate; detached-run reliability pattern. Live files backed up as `*_backup_pre_v13.*` (qc_vv.py, qc_mix.py, voice_f0.json, podcast.ps1, vv_generate.py, templates\README.md). No episode re-rendered, no TTS run for this version (CPU/ffmpeg tests only: `tests\v13_check\`).
- 1.3 addendum (2026-10-15): hardware logging moved from HWiNFO (12 h sharing limit) to the own LibreHardwareMonitor monitor `C:\grok\hwmon` (task HwMon, PawnIO driver); `podcast.ps1`, `render7b.ps1`, `hwrun.ps1` dot-source the new lib with fallback to the old HWiNFO monitor; snapshot copy in `code_v1.3\hwmon_new\`. Section 9.
