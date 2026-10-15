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
Output: episode.mp4 (1920x1080, 2 fps, H.264 + AAC 160k, burned subtitles + soft mov_text track, mp4 chapter markers), episode.srt, episode.chapters.json (titles + aligned times), episode.chapters.txt (YouTube "00:00 Title" list), 3 PNG frames.
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
- `hwmon_lib.ps1`: Start-HwMonitor / Stop-HwMonitor helpers (dot-sourced by both).
- Sensors come from HWiNFO > Sensors > Settings > HWiNFO Gadget tab ("Report value in Gadget"); all enabled as of 2026-10-13.
