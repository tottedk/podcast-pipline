# Podcast pipeline

Local Windows pipeline that drafts a podcast script with Ollama, speaks it with Fish Audio Drama 3, checks the audio, and mixes an episode. Tested on an AMD Radeon RX 7900 XT with about 20 GB of VRAM. This repository is the orchestration and the versioned templates. It does not include model weights, voice samples, or generated episodes.

**Built with Fish Audio.** The default speech engine is Fish Audio Drama 3, run locally through audio.cpp. Drama 3 is used under the [Fish Audio Community License v1.0](https://huggingface.co/fishaudio/drama-3/blob/main/LICENSE). That license is not MIT. See [Licenses](#licenses).

Current templates: technical **v1.14** and content style **v2.6** (2026-11-07). Older template files are kept and are not edited. The version log is `templates/README.md`.

## LLM limits and responsible use

This is an experimental local production tool, not an autonomous publisher. The script model can invent facts, sources, and quotations. Automated research and fact checks can also be wrong. Every episode needs a person to fact-check it and listen to it before publication.

The tested full pipeline uses Ollama `gemma4:26b-a4b-it-qat` for scripts (`write_script.py` and `tools/brief_gen.py`), Fish Audio Drama 3 through audio.cpp for speech, and VibeVoice-7B Q8 as a fallback (`run_episode.ps1 -Engine 7b`). `podcast.ps1` is the older VibeVoice-1.5B path. Models are downloaded separately under their own licenses.

Tested hardware is an AMD Radeon RX 7900 XT with about 20 GB of VRAM. That is the machine this release was run on, not a minimum spec and not a promise that every stage fits in memory at once. The scripts unload Ollama (`keep_alive` 0) before loading a speech or image model. On this PC, `HIP_VISIBLE_DEVICES=1` is required because device 0 is the integrated GPU.

- Context is finite. `tools/brief_gen.py` sends `num_ctx` 16384. `write_script.py` defaults to 8192 (`--ctx`), and `podcast.ps1` raises that to 32768 when `-Lines` is over 40. Long inputs and multi-part scripts can omit details, repeat material, or lose continuity. Chunking and checks reduce those failures. They do not remove them.
- A scripted guest's personal angle is fictional character dialogue, not a real person's testimony or verified lived experience. Everyday analogies are explanatory devices, not evidence.
- Speech synthesis can flatten delivery, change pronunciation, miss words, or vary pace. Pitch and tempo gates are heuristics, not a guarantee of natural speech.
- Technical v1.14 and content v2.6 have passed short tests. A full episode has not yet validated these changes. Earlier episodes that passed do not certify this release.
- Do not clone a real person's voice. Do not supply a real person's voice as a reference. This repository does not distribute voice samples, weights, private books, or generated episodes.

## Install

Windows and PowerShell. Python 3 for the unit tests; the PC runs the pipeline from several virtual environments named below. There is no install script in this repository.

Scripts default to `-Root C:\grok\podcast` and look for Drama 3 at `C:\grok\drama3` (`-D3Home` on `render_drama3.ps1`). Point those parameters at your own directories.

You provide, outside this repo:

- [Ollama](https://ollama.com/) on `localhost:11434`, with `gemma4:26b-a4b-it-qat` pulled.
- `ffmpeg` and `ffprobe` on `PATH`.
- Fish Audio Drama 3 weights and a matching audio.cpp build (`audiocpp_cli.exe`). No weights are committed here. Read the Community License before you download them.
- Python environments the launchers call: `venv_vv` (generator, numpy, soundfile, librosa), `venv_whisper` (faster-whisper), `venv_spk` (speechbrain ECAPA voice check), and, for pictures, `venv_sd` plus `venv_video` (Pillow). `venv_rocm_freeze_pre_librosa.txt` is an old package freeze, not a supported install list.
- Optional fallback: VibeVoice-7B Q8 weights for `-Engine 7b`. The Microsoft VibeVoice software repository is MIT. The license of the exact 7B TTS weights used as this fallback is not verified. Do not treat those weights as MIT. See `NOTICE`.
- Optional backgrounds: a FLUX.1-schnell snapshot. Set `FLUX_SNAPSHOT` to the snapshot directory, or place it in the current user's Hugging Face cache at `%USERPROFILE%\.cache\huggingface\hub\models--unsloth--FLUX.1-schnell\snapshots\9df3faa7ae3b6ddf0b2b69bb78616372897cc65c`.

A brief-to-episode run also expects local assets that are intentionally absent here: `fd1\intro.wav`, `fd1\sting.wav`, `fd1\outro.wav`, voice references, and the files listed under [Known gaps](#known-gaps).

## Usage

Unit tests, from the repository root (no GPU, no audio):

```text
python tests/test_md_clean.py
python tests/test_v112.py
```

Dry run of the orchestrator (PowerShell). This prints the engine and tempo and does not start a render:

```text
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_episode.ps1 -Dir <work-dir> -Ep <episode-id> -BgDir <bg-dir> -DryRun
```

`-Engine drama3` is the default. `-Engine 7b` selects the VibeVoice-7B fallback. `-Tempo 0` keeps the engine default. Drama 3 tempo for mapped voices comes from `drama3_tempo.json` (Carter is fixed at 0.86). Guest upper pace in the mix gate is 175 words per minute; the host upper limit is 190 (`qc_mix.py --wpm_hi_host`, `post_episode.ps1 -WpmHiHost`).

`tools\start_brief.ps1 -BriefPath <brief.json> -DryRun` checks a desk brief and does not register a task. A real run needs the missing v1.13 files below, plus the local models and audio. It refuses host other than Carter, and refuses guests Maya, Declan, Alice, Mary, and Hugh.

`write_script.py` is the shorter notes-to-JSON path. It talks to the same Ollama model and unloads it when the call finishes:

```text
python write_script.py notes.txt script.json --model gemma4:26b-a4b-it-qat
```

Versioned behaviour, QC gates, and per-release file lists live in `templates/technical_v1.14.md` and earlier `templates/technical_v*.md` files.

## Known gaps

`main` did not contain the v1.13 files that v1.14 is built on, and they were not in the PC file drop used to sync this tree. Their contents were not reconstructed. Until you add the copies from the PC, `tools/brief_gen.py` cannot finish a topic-first episode:

- `tools/research.py` (imported by `brief_gen.py`)
- `tools/episode_qc.py` (called by `tools/start_brief.ps1`)
- `tools/qc_eval.py` (the PC regression command; also part of the PC `templates/code_v1.14` snapshot)
- `templates/cast_bible_v1.json` (required for content styles v2.5 and v2.6)
- `templates/content_style_v2.5.md` and `templates/technical_v1.13.md`
- `templates/code_v1.13/`

`templates/code_v1.14/` in this repo hashes only the files that were in the drop. It is not a byte-for-byte copy of the PC snapshot.

The Episode desk (the small local UI that writes a brief) is a separate project. Its files were in the same drop and were not copied into this repository.

## Licenses

The MIT license in `LICENSE` covers original orchestration code in this repository by Thomas Jensen. It does not cover models, weights, voice recordings, or third-party libraries. `NOTICE` lists those boundaries.

**Built with Fish Audio.** Drama 3 is open-weight under the Fish Audio Community License v1.0 (13 October 2026):

- Research and non-commercial use are allowed. Commercial use is allowed only under USD 500,000 combined rolling-12-month gross revenue, including affiliates. At or above that threshold the license requires notice and a commercial license after the stated transition.
- A hosted, self-service text-to-speech, voice-cloning, or inference service needs a separate license regardless of revenue.
- Products and services that use the materials need prominent "Built with Fish Audio" attribution.
- The license forbids unconsented imitation of identifiable people, deceptive impersonation, and watermark removal.
- Drama 3 weights are not in this repository. Do not relicense those weights, or derivatives of them, as MIT.

Microsoft's VibeVoice software repository is MIT (Copyright 2025 Microsoft). This repo does not vendor that source. The exact VibeVoice-7B TTS weights used as the optional fallback were not identifiable from public model cards at review time (the official TTS release was withdrawn, and the current ASR-7B model is a different model). Their license stays unverified. Do not describe those weights as MIT.

Voice credit lines for reference speakers drawn from LibriTTS-R and the CSTR VCTK Corpus are CC BY 4.0 and live in `voices.json`. The recordings themselves are not committed. `hwmon.cs` is original code that calls LibreHardwareMonitorLib 0.9.6 (MPL-2.0). That library is not vendored here.
