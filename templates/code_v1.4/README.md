# Podcast pipeline - code snapshot v1.4 (2026-10-15)

**v1.4 = v1.3 + markdown-mark stripping before TTS (Thomas approved, after the LLM shootout showed Gemma leaves *italic* marks in the script).** New: `md_clean.py` (strips *x*, **x**, ***x***, _x_, __x__, ~~x~~, `x`, [t](url), leading #/>/-/* from the TEXT only; keeps words, speaker field, snake_case and math asterisks like 2 * 3), unit tests `tests\test_md_clean.py` (`python tests\test_md_clean.py`). Hooked into `write_script.py` (at write time), `prep_script.py` (`--no_md_clean` to skip), `run_episode.ps1` (segment scripts, in place, `<seg>.pre_md.json` only if changed), `vv7b_generate.py` and `vv_generate.py` (in-memory, before chunking/TTS). Everything else is unchanged from v1.3 (below).

---

# Podcast pipeline - code snapshot v1.3 (2026-10-15)

**v1.3 = v1.2 + new defaults approved by Thomas (2026-10-15). Default engine: VibeVoice-7B Q8 GGUF via audio.cpp (Vulkan). Backups: VibeVoice-1.5B (podcast.ps1) and SoulX-Podcast-1.7B (test script only).** Nothing was re-rendered; episodes keep the version they were made with.

## v1.3 defaults
| | v1.2 | **v1.3** |
|---|---|---|
| Engine | VibeVoice-1.5B (`podcast.ps1`) | **7B Q8 audio.cpp: `render7b.ps1` + `vv7b_generate.py`** (1.5B = backup, SoulX = backup) |
| Cast | Carter + Frank (+Alice/Samuel tests) | **NO default cast**: Host Carter; Guest/Guest2 random per episode from Frank, Clara, Maya, Isla, Marcus, Declan (Samuel low priority); gender-aware; F0 gap >= 12 Hz (so not Frank next to Carter); seed logged; never Alice/Mary/Thomas |
| Glossary | respellings (`glossary.json`) | **OFF** (`empty_glossary.json`); write hard terms normally in the script |
| Chunks | 175 words (1.5B) | **275 words on turn boundaries** |
| QC retries | 3 | **2** (seeds 42, 1988, 3042), best take ships |
| f0_drift | hard flag (retry) | **soft flag**: reported + scored, never triggers a retry alone (`qc_vv.py --soft`) |
| voice_f0.json | Carter 131.1, Frank 127.5 (1.5B) | per voice, 7B 3-speaker, measured (Carter 132.2, Frank 130.6, Clara 228.6, Maya 202.5; Isla/Marcus/Declan provisional) |
| Post chain | highpass 70, afftdn nr 10, atempo 0.93, loudnorm -16 | highpass 70, **no afftdn**, presence +1.5 dB @3 kHz, **de-esser i=0.4**, atempo 0.93, loudnorm -16 |

## Run an episode (detached, poll STATUS.txt with short calls)
    # inputs in <Dir>: segNN.json, intro.wav, sting.wav, outro.wav, <Ep>.chapters.in.json ; <BgDir>: prompts.json + backgrounds.json
    Start-Process powershell -ArgumentList '-ExecutionPolicy','Bypass','-File','C:\grok\podcast\run_episode.ps1','-Dir','ui2','-Ep','my_ep1','-BgDir','bg_ui2','-FrameSuffix','_ui2' -WindowStyle Hidden
run_episode.ps1 = render7b.ps1 (TTS + QC + post per segment, resumable) -> FLUX for missing backgrounds -> post_episode.ps1 (mix, duration gate 40-45 min, align, qc_mix, video, 64k mp3, CC BY credit lines for voices_extra voices).
Single pieces: `render7b.ps1 -Dir x`, `post_segment.ps1 -Raw x.raw.wav -Script x.json -Out x.mp3 [-Tempo 0.93] [-Old]` (CPU only), `post_episode.ps1 ...`.
Copy the scripts + voices.json + empty_glossary.json + voice_f0.json to `C:\grok\podcast\` (already installed live on 2026-10-15).

## Voices
`voices.json` = registry (file, gender, accent, source, licence, credit line). `voices_extra\` (Clara, Isla, Marcus, Declan; CC BY 4.0, LibriTTS-R / VCTK): the credit line is added to the notes and chapters.txt automatically when the voice is in the cast. Blocked in vv7b_generate.py: Alice, Mary, Thomas.

**Cast pick (v1.3): Correction (15 Oct, Thomas): there is NO default cast. An earlier v1.3 text said "default cast Carter + Frank + Clara"; that is withdrawn. Only the Host is fixed (Carter, unless Thomas says otherwise); guests are picked at random per episode.** `pick_cast.py` (called by run_episode.ps1; podcast.ps1 when -GuestVoice is empty) draws guests with a seeded random pick over the pool in voices.json, respects `-GuestGenders "M,F"`, requires an F0 gap >= 12 Hz (voice_f0.json) between host and guests and between guests, Samuel weight 0.25. Writes `<Dir>\cast.json`, STATUS.txt, chain.log and the episode notes (mode, seed, gaps, reproduce). Override: `-Guests "Marcus,Isla"`; reproduce: `-CastSeed N`. Details: technical_v1.3.md section 2a.

## New / changed files in this snapshot
`pick_cast.py` (new), `vv7b_generate.py`, `render7b.ps1`, `post_segment.ps1`, `post_episode.ps1`, `run_episode.ps1`, `voices.json`, `empty_glossary.json`, `voice_f0.json` (new values), `qc_vv.py` (v2.1: --soft, voices_extra lookup), `qc_mix.py` (voices_extra lookup), `podcast.ps1` (new defaults + post chain), `vv_generate.py` (voices_extra, 275, empty glossary), `tests\spectral_ab.py`, `tests\retries_from_takes.py`, `tests\f0_voice_eval.py`, `tests\f0_episode_stats.py`, `tools\stretch_pauses_repost_ui1.py` (reference only: the pause-stretch used to lengthen Uploaded Intelligence ep1).
See `technical_v1.3.md` for the length rule, the A/B numbers and the QC statistics.

---
## (below: v1.2 README, unchanged)
# Podcast pipeline (VibeVoice-1.5B) - default

notes.txt -> write_script.py (Ollama gemma4:26b-a4b-it-qat, keep_alive 0 -> unloads) -> vv_generate.py (VibeVoice-1.5B, chunked) -> ffmpeg atempo + loudnorm -> mp3

## Run (PowerShell, from C:\grok\podcast)
    .\podcast.ps1 notes.txt episode.mp3 -Topic "Hayek's The Road to Serfdom" [-Lines 14]
Options: -HostVoice Carter -GuestVoice Frank -Tempo 0.93 -Pace sentence|all|none -Cfg 1.3 -Seed 42 -Script existing.json (skip Gemma).
If blocked by policy: `powershell -ExecutionPolicy Bypass -File .\podcast.ps1 ...`
Output: episode.mp3 + episode.script.json (raw wav is deleted). Last line prints duration, words, wpm, total time.
Length: ~30 words per turn, ~155 wpm -> -Lines 14 = ~3 min, -Lines 150-200 = ~30-45 min.

## Components
- venv\        : python for write_script.py (stdlib only; needs Ollama on localhost:11434). Output JSON [{speaker:"Host"|"Guest", text}]. Retries 3x.
- venv_vv\     : VibeVoice (vibevoice-community fork in VibeVoice-main\), transformers 4.51.3, ROCm torch. Weights microsoft/VibeVoice-1.5B from HF cache. bf16, SDPA, 10 diffusion steps, seed 42 (reset per chunk), cfg 1.3.
- vv_generate.py script.json out.wav : chunks at ~700 words on turn boundaries, Host is always Speaker 1, Guest Speaker 2, 0.35 s gap between chunks. `--list_voices` lists voices.
- ffmpeg/ffprobe: PATH is reloaded from the registry in podcast.ps1.

## Voices (VibeVoice-main\demo\voices, use the short name)
Carter (m, default Host), Frank (m, default Guest), Alice (f), Maya (f), Mary (f, has background music), Samuel (m, Indian English), Anchen (zh m, bgm), Bowen (zh m), Xinran (zh f). Add your own: drop a 10-30 s clean wav named en-Name_gender.wav there.

## Tempo
VibeVoice has no speed parameter; cfg_scale does not change pace (1.3 -> 197 wpm, 2.0 -> 203 wpm). Native trick used: `--pace sentence` turns ". " into "... " -> natural pauses (~167 wpm). Then atempo 0.93 -> ~155 wpm. (`--pace all` also pauses at commas, ~164 wpm alone but choppier.)

## Pitfalls
- HIP_VISIBLE_DEVICES=1 is REQUIRED (device 0 = iGPU, crashes). podcast.ps1 sets it.
- GPU sharing: Gemma unloads (keep_alive 0) and the script waits until /api/ps is empty before loading VibeVoice. VibeVoice peak ~6.4 GB VRAM.
- Do not use $ErrorActionPreference=Stop with native commands in PS 5.1: python warnings on stderr abort the script (calls are wrapped in cmd /c ... 2>&1).
- Gemma sometimes returns HTTP 500 or a single object instead of a list -> retried automatically.
- Speed: ~1.0x realtime for VibeVoice, ~1.3-1.4 min wall time per audio minute including Gemma.
- Long episodes: Gemma in one call may give fewer/shorter turns than asked for 150+ turns (ctx is raised to 32768 when -Lines > 40); for 30-45 min consider writing per section and concatenating JSONs, then -Script. Chunk boundaries can give a small change in timbre/energy; voices stay the same since each chunk re-uses the voice prompt. Model max context ~64k tokens (~90 min) but single-pass long runs drift, hence chunking.
- Non-ASCII chars are stripped before TTS (English only).

## Video (narrated slideshow) - align.py + make_video.py
Step 1 - exact timings (faster-whisper, CPU int8, low priority):
    start /low /b venv_whisper\Scripts\python.exe align.py episode.mp3 episode.json --threads 6   (default model large-v3-turbo; --model medium.en for the old one)
  -> episode.whisper.json (raw Whisper words, cached; re-runs skip ASR) + episode.timings.json (every script line + word with real start/end).
  Alignment: script words (ground truth) are matched to Whisper words with difflib on normalized tokens; unmatched words are interpolated. Prints match ratio (ep2: see log).
  Default Whisper model is large-v3-turbo (faster-whisper, CPU int8), since 2026-10-13; select the old one with --model medium.en (speed comparison: see ab_test\README_ab.txt).
  medium.en on 6 threads: roughly 0.25-0.4x realtime (~10-15 min for 43 min audio, slower while gaming). small.en is ~2-3x faster, slightly less accurate words (timing is about as good).
Step 2 - chapters: write episode.chapters.in.json by hand: {"title": "...", "sections": [{"start": <script line index>, "title": "..."}]}; first section must be line 0. (Without --chapters: auto TF-IDF sections, clunky.)
Step 3 - render:
    start /low /b venv_video\Scripts\python.exe make_video.py episode.mp3 episode.json episode.mp4 --timings episode.timings.json --chapters episode.chapters.in.json --frames-dir video_frames
Options: --title --topic --host Carter --guest Frank --sections 8 (auto only) --fps 2 --frame-suffix _v2 --keep-tmp.
Output: episode.mp4 (1920x1080, 2 fps, H.264 + AAC 160k, NO subtitles in the video since v1.2 (--burn-subs = old burned + soft mov_text track), mp4 chapter markers), episode.srt, episode.chapters.json (titles + aligned times), episode.chapters.txt (YouTube "00:00 Title" list), 3 PNG frames.
Subtitles (with --timings): script wording, chunks <= 84 chars as max 2 balanced lines of ~42 chars, split at sentence ends/commas, never across speaker turns, shown 1-6 s from first word -0.1 s to last word +0.4 s, never overlapping; gaps show the slide without subtitle. Speaker plate switches at the real line start.
Layout: title card (first ~9 s), section cards (~6 s at each section start), otherwise key-quote card per script line + colored speaker plate (host amber, guest blue) + subtitle bar. Dark abstract generated backgrounds, Segoe UI fonts.
CPU only (Pillow + ffmpeg libx264, 4 threads). 43 min episode = ~2 min render, ~100 MB.
Without --timings the old estimate (chars per chunk scaled to mp3 length) is used; drifts by seconds.
Venvs: venv_video (Pillow), venv_whisper (faster-whisper; audio decoded via ffmpeg pipe because the bundled PyAV rejects metadata_errors).
## Backgrounds (local SDXL, gen_backgrounds.py) + Ken Burns video
Step 2b - prompts: write bg_dir\prompts.json by hand (or with Gemma, then keep_alive 0 and wait for empty /api/ps BEFORE loading SDXL):
    {"style": "<fixed style suffix>", "negative": "text, watermark, letters, logo, real person, ...",
     "images": [{"id": "c01a", "line": <script line where the image starts>, "prompt": "..."}]}
  ~1 image per chapter, 2-3 for chapters > ~6 min (ep3: 20 images, style "dark cyber-gothic, abstract, atmospheric, cinematic lighting, muted teal and amber ... no text, no letters, no faces of real people").
Step 2c - generate (GPU, HIP_VISIBLE_DEVICES=1 set by the script):
    set HIP_VISIBLE_DEVICES=1&& venv_sd\Scripts\python.exe gen_backgrounds.py bg_ep3\prompts.json bg_ep3 [--steps 30 --cfg 6.5 --w 1344 --h 768 --seed 1234]
  -> bg_ep3\<id>.png (1344x768 SDXL, Lanczos to 1920x1080) + gen_log.json. Existing images are skipped: delete/move a bad one and re-run (other --seed) to regenerate only it.
  Model: stabilityai/stable-diffusion-xl-base-1.0 fp16 (HF cache C:\Users\TJ\.cache\huggingface, ~7 GB). 7900 XT: ~10 s/image at 30 steps, load 7 s, torch peak alloc 9.05 GB (first image after a fresh install ~70 s: MIOpen kernel tuning, harmless "Invalid elapsed time" MIOpen errors).
  venv_sd = new venv with diffusers/transformers/accelerate; torch ROCm is reused from venv_rocm via venv_sd\Lib\site-packages\rocm_base.pth (no second torch copy).
  Then make bg_ep3\backgrounds.json: [{"line": 0, "image": "c01a.png"}, ...] (or {"start": <seconds>}); each image lasts until the next one.
Step 3 with backgrounds:
    start /low /b venv_video\Scripts\python.exe make_video.py ep.mp3 ep.json ep.mp4 --timings ep.timings.json --chapters ep.chapters.in.json --guest Alice --fps 20 --backgrounds bg_ep3\backgrounds.json [--frame-times 95,470,1050,1900]
  Background video: per image a zoompan Ken Burns (zoom 1.0<->1.1 alternating in/out, alternating pans, from a 4K-upscaled source to avoid jitter), 1.5 s fade crossfade at each boundary, gblur 3 + slight darken; each segment is its own clip (3 parallel ffmpeg), then concat -c copy (a single 20-input xfade chain crashed ffmpeg).
  Overlay: text frames are rendered as transparent PNGs with a dark top/bottom gradient and dark quote/title panels, overlaid on the bg video; final x264 medium crf 22.
  ep3 (43 min, 20 fps): bg video 6.5 min + overlay/encode ~7 min = ~14.5 min total, 279 MB. Without --backgrounds the old 2-fps slideshow is unchanged.
Files must be UTF-8 without BOM (PowerShell 5.1 Set-Content -Encoding utf8 writes a BOM; gen_backgrounds.py tolerates it, make_video.py does not).
check_sync.py now takes the episode stem: venv_whisper\Scripts\python.exe check_sync.py fanged_ep3

## Artifact fix + auto-QC (2026-10-13)
Problem (ab_test\ab_vv15b.mp3, Carter/Alice): "crowd/hall" noise at ~2 s, garble at ~9 s, strange sound at ~47 s;
Patchwork ep1: pitch break at 4:06 ("He leans" jumps ~100-150 Hz -> 220-260 Hz, whisper hears "notes", p=0.05) and
6:26 (Host line "Voting with your feet." replaced by ~1.7 s of noise/garble; line missing from transcript).
Cause: all are VibeVoice-1.5B generation artifacts at an onset after silence (speaker turn or sentence start) - present
in the raw wav, NOT made by atempo/loudnorm (loudnorm only lifts them ~6 dB together with everything else). None were
at a chunk boundary and there was no clipping. Short interjection lines (<=5 words) are the most vulnerable.
Tested on the excerpt (qc_vv.py metrics): cleaned refs, cfg 1.5/1.8, 20 steps, no '...' -> no improvement (cfg 1.8 and
20 steps gave MORE onset bursts). So generation defaults stay cfg 1.3 / 10 steps / '...' pace / original refs.
Fix (podcast.ps1 now does this automatically):
1. vv_generate.py keeps per-chunk wavs (<out>.raw.wav.chunks\) and supports `--redo chunk:seed,...`.
2. qc_vv.py (whisper large-v3-turbo, CPU; ideas from pw\qc.py) checks every chunk: any script line < 75% recognised,
   chunk WER > 8%, octave pitch jump coinciding with a low-confidence word, or > max(6, dur/15) non-speech bursts ->
   chunk is regenerated with seed+1000*pass (up to -QcRetries 2). Report: <out>.qc.json
3. Pause gate: qc_vv.py --gate fades everything outside whisper words to -60 dB, with onset refinement (a word's
   start is moved to where >3 kHz speech energy begins, because whisper folds the low-band burst into the first word).
4. ffmpeg: highpass=70, afftdn=nf=-45:nr=10, atempo, loudnorm LAST.
Raw wav + chunks are now kept for diagnosis. Options: -NoQc, -QcRetries N, -Steps N; vv_generate --clean_refs 1 --pace none.
Backups: vv_generate_backup_pre_cleanfix.py, podcast_backup_pre_cleanfix.ps1, README_backup_pre_cleanfix.md.

## Hardware monitor (hwlogs)
Logs HWiNFO64 sensor values only while a podcast / AI run is active. Reads the HWiNFO **VSB gadget registry** (`HKCU\Software\HWiNFO64\VSB`); does not touch HWiNFO settings or `Documents\hwinfo.CSV`.
- `hw_monitor.ps1 -Run <name> [-ParentPid <pid>] [-StopFlag <file>] [-Interval 5]` - sampler (BelowNormal priority, every 5 s). Writes `hwlogs\<run>_<yyyyMMdd_HHmmss>.csv`; stops when the stop flag appears or the parent PID exits (24 h safety cap), then writes `<same>.summary.txt` (max/avg per sensor, GPU hotspot >95 C sample count, GPU/CPU energy in kWh). Deletes hwlogs older than 30 days on each start.
- CSV columns (exact VSB labels, FIRST occurrence = 7900 XT, not iGPU): GpuTemp_C (GPU Temperature), GpuHotspot_C (GPU Hot Spot Temperature), GpuMemJunc_C (GPU Memory Junction Temperature), GpuPower_W (Total Board Power (TBP)), GpuLoad_pct (GPU Utilization), GpuVram_MB (GPU D3D Memory Dedicated; "GPU Memory Usage" is bogus, not used), GpuFan_RPM (GPU Fan), GpuHotLimit_pct (GPU Hotspot Thermal Limit), CpuTemp_C (CPU (Tctl/Tdie)), CpuPower_W (CPU Package Power), CpuLoad_pct (Total CPU Usage), CpuHTC (Thermal Throttling (HTC), 1=Yes), RamUsed_MB (Physical Memory Used). Values parsed robustly (thousands commas, mojibake units). CIM fallback only for CPU load/RAM if missing from VSB; missing sensors are listed in the summary. Summary also counts HTC throttling samples.
- `podcast.ps1` starts/stops it automatically (try/finally, also on error). Disable with `-NoHwMonitor`. Backup: `podcast_backup_pre_hwmon.ps1` (old monitor: `hw_monitor_backup_pre_hwmon.ps1`).
- Standalone runs: `.\hwrun.ps1 [-Name label] <command> [args...]`, e.g. `.\hwrun.ps1 venv\Scripts\python.exe gen_backgrounds.py ...` or `.\hwrun.ps1 python make_video.py ...`. Exit code of the command is passed through. Env vars (e.g. `HIP_VISIBLE_DEVICES=1`) are inherited unchanged.
- `hwmon_lib.ps1`: Start-HwMonitor / Stop-HwMonitor helpers (dot-sourced by both) = the OLD HWiNFO lib, now only the fallback.
- **v1.3 (15 Oct): primary monitor = own LibreHardwareMonitor logger** `C:\grok\hwmon\hwmon.exe` (Scheduled Task `HwMon`, PawnIO driver, no 12 h limit). `podcast.ps1`, `render7b.ps1` (so run_episode.ps1 too) and `hwrun.ps1` dot-source `C:\grok\hwmon\hwmon_lib.ps1` (same Start-/Stop-HwMonitor API; falls back to the old HWiNFO monitor if the daemon is not alive, and to `<root>\hwmon_lib.ps1` if the new lib file is missing). Session logs keep the old CSV columns + `.summary.txt` and add `.summary_full.txt`; continuous logs `hwmon_cont_<day>.csv` / `hwmon_full_<day>.csv`. Files: `hwmon_new\` (lib, source, admin installer, ctl, README). Details: technical_v1.3.md section 9.
- Sensors come from HWiNFO > Sensors > Settings > HWiNFO Gadget tab ("Report value in Gadget"); all enabled as of 2026-10-13.

## QC v2 (2026-10-14, approved after the DE ep1 diagnosis, logs\dark_bug_diagnosis.md)
- `prep_script.py script.json [out.json]`: merges <=2-word interjection lines into the same speaker's next line (podcast.ps1 runs it in place unless -NoMerge; backup *.pre_merge.json). Run BEFORE writing chapters/backgrounds (line indices change).
- `glossary.json`: hard-term respellings; vv_generate.py applies them to the TTS text only (chunks.json keeps original `lines` + `tts_lines` + `speakers`); qc_vv.py checks each term was recognised (original or respelling, fuzzy).
- Defaults: -ChunkWords 175 (was 700; DE used 350), -QcRetries 3 (was 2).
- podcast.ps1: QC after EVERY generation pass; qc_takes.py records every take's score; the best take per chunk ships (reassembled raw wav); if the best is not the last take the shipped audio is QCed again; `<out>.qc.json` has `final: true` and lists chunks still flagged.
- qc_vv.py v2 adds per-line WER (>0.25), glossary misses, F0 drift (line median vs voice_f0.json calibrated F0, +/-15%, >=2 lines or chunk median), speech rate (lines >=12 words outside 2.1-5.0 w/s raw), unrecognised speech-level audio >=1 s (dropped speech/babble/music, 'tonal' tag), numeric score; `--rescore qc.json` re-applies thresholds without audio.
- Pause gate: gaps >0.8 s with >40% speech-level frames are NOT muted (gate_kept) - fixes the DE 30:27 mute.
- `qc_mix.py ep.mp3 ep.timings.json`: final QC of the mixed episode (silence >2 s inside lines, F0 drift vs episode median, rate, interpolated lines). Run after align.py.
- Backups: podcast_backup_pre_qc2.ps1, qc_vv_backup_pre_qc2.py, vv_generate_backup_pre_qc2.py, README_backup_pre_qc2.md.

## 3 speakers + subtitles (v1.2, 2026-10-14)
- Script speakers: `Host`, `Guest`, `Guest2`. VibeVoice gets Host = Speaker 1, Guest = 2, Guest2 = 3 (renumbered per chunk if a speaker is absent). Model settings unchanged.
- `podcast.ps1 ... -GuestVoice Alice -Guest2Voice Samuel` (passes `--guest2` to vv_generate.py and qc_vv.py); `qc_mix.py ... --guest2 Samuel`.
- make_video.py: `--guest2 <name>` -> crimson plate/level meter (host amber, guest blue). Subtitles are **no longer burned in by default**: only `<out>.srt` is written next to the mp4 (no subtitle stream in the mp4). `--burn-subs` restores the old behaviour (burned + soft mov_text).
- Fix: podcast.ps1 runs qc_takes.py with venv_vv python (venv_whisper has no soundfile -> in v1.1 take recording + best-take pick failed silently and the LAST take shipped).
- 3-speaker test + speaker-ID check: `tests\three_speaker\` (spk_check.py = per-line F0 + log-mel voice-ID vs prompts/centroids). Results: templates\technical_v1.2.md.
- Backups: *_backup_pre_3spk.* (vv_generate, qc_vv, qc_mix, podcast, make_video, README, align, prep_script, qc_takes).

