# Technical template
**Version 1.12 - 2026-10-21** = v1.11 + fixes after Thomas's feedback on the Fault Lines #1 re-render (v1.11, 43:13): the speakers talk too slowly, and Elliot is monotone with long pauses. Analysis: `fl1b\analysis\TEMPO_PAUSES.md`. These changes apply to the NEXT episode. Fault Lines #1 audio and episode files were not re-rendered or touched; only its registry entry was updated. Everything not listed here is as in `technical_v1.11.md`, which follows below for reference. v1.11 and older files stay unedited.

## v1.12 changes
1. **Pause clamp v2 (relative silence)** in `d3_pace.clamp`, called by `drama3_generate.py`.
   - **Cause in v1.11:** an internal silence had to be 32 dB below the speech level. Elliot's reference has a noise floor only about 35-41 dB below speech, so his generated pauses carry breath and noise at -20..-32 dB. The clamp found 0 pauses of 0.9 s or more in any Fault Lines #1 chunk. A -20 dB rule finds 69 for Elliot, 1 for Carter and 1 for Clara.
   - **v1.12 behaviour:** an internal silence is any stretch more than `--sil_rel_db` **20 dB** below that chunk's speech level (the median of the active frames). Any intra-line pause longer than `--max_pause` **0.4 s** is cut to `--keep_pause` **0.4 s**. The cut removes the middle of the pause and keeps the edges.
   - **Final-tempo terms:** the clamp runs AFTER the tempo stretch, so 0.4 s is what you hear.
   - **Leading and trailing silence:** these still use the conservative 32 dB rule, cut to 0.05 s and 0.12 s.
   - **`[whispers]` chunks:** these keep the 32 dB rule, so soft speech is never treated as silence.
   - **Records:** pre-tempo audio is kept in `<chunks>\_pretempo\`. Each chunk's `clamp` field in chunks.json records speech_db, floor_db and the list of cuts.
2. **Per-speaker tempo, applied per chunk** in `drama3_generate.py`.
   - **Where it is set:** `drama3_tempo.json` (passed with `--tempo_cfg`; `render_drama3.ps1 -TempoCfg`, and `run_episode.ps1 -TempoCfg`, which defaults to the root file). The map is keyed by **reference name**: Carter 0.90, Clara 0.95, Elliot 1.00 (the old Elliot.wav).
   - **Auto-calibration:** a reference that is not in the map (or every reference, with `"auto_all": true`) gets the tempo target_wpm (**160**) / its measured raw wpm, clamped to **0.85-1.10**.
     - **Raw wpm:** words / pre-tempo chunk seconds after a provisional clamp.
     - **When it is set:** the tempo becomes provisional at 15 words and is locked at 60 words in `<Dir>\drama3_tempo_lock.json`, so later segments of the episode reuse the same tempo. `--redo` keeps the segment's tempo.
     - **Fallback:** a reference with fewer than 15 words gets the fallback `--tempo` (0.90).
   - **Post stage:** `post_segment.ps1` now runs at `-Tempo 1`.
   - **v1.11 mode:** `-GlobalTempo` restores the single post atempo. `--mode multi` always uses the global tempo.
   - **Log lines:** `TEMPO <role>=<ref>:<t>(map|auto|auto-provisional|locked|fallback, raw N wpm)` in render.log. Each chunk records `tempo`/`tempo_src`/`dur_s`.
   - The 38-48 min duration gate is unchanged.
3. **New Elliot reference `drama3_refs\Elliot_v2.wav` + `.txt` (+ `.json` provenance)**, built by `tools\make_ref_v2.ps1`. `drama3_ref_map.json` (`{"map":{"Elliot":"Elliot_v2"}}`) points the cast name Elliot at it. `drama3_generate.py`, `spk_check.py` and `drama3_refs.py` take `--ref_map`.
   - **Original untouched:** `drama3_refs\Elliot.wav` is not overwritten. A run with an empty map (`-RefMap <file with {"map":{}}>`) uses the old reference.
   - **Source:** Drama 3's own Elliot output of Fault Lines #1, `fl1b\seg01.raw.wav.chunks\c006.wav`.
     - **Why this source:** the only original recordings of this voice are short VCTK p227 read sentences. The VibeVoice sample has a 1.64 s pause and no exact transcript. This chunk is continuous conversational speech with an exact punctuated transcript (the script text), and it keeps the voice identity the gate accepts.
     - **Numbers:** 19.8 s, 57 words, raw 173 wpm, longest pause 0.65 s, no tags. It was the best of the 50 Elliot chunks on wpm, pitch variation and pauses at about 20 s.
   - **Processing:** highpass 70 Hz, afftdn (nr 12, nf -42), and lead/tail trim, saved as 24 kHz mono. The noise floor goes from -35.0 to -39.7 dB relative to speech.
   - **Credit:** CSTR VCTK p227, CC BY 4.0, the same as Elliot in voices.json. Never a clone of Thomas.
4. **Script prep: a guest line never opens with `[sighs]`.** `md_clean.strip_lead_sighs` removes a leading `[sighs]` tag from Guest/Guest2 lines.
   - **Where it runs:** in `md_clean.py` (CLI) and again in `drama3_generate.py`, so it also covers old scripts.
   - **What stays:** a line that is only `[sighs]` and any mid-line tag. Host lines are unchanged.
5. **Blocking mix QC** in `qc_mix.py --gate`, called by `post_episode.ps1` (`-WpmLo 145 -WpmHi 175 -MaxLinePause 1.5`).
   - **Speaker rate:** per-speaker wpm = spoken words / the summed first-to-last word span of each line (speakers with 150 words or more). Any speaker outside 145-175 wpm fails.
   - **Pauses:** any intra-line pause longer than 1.5 s fails. A pause is a stretch of 20 ms frames more than 30 dB below the line's p70 level.
   - **On a fail:** `MIXQC GATE FAIL` gives exit 2, and post STOPs with **exit 7** before the video, the copy to -OutDir and the registry. Nothing is published, and launchers do not swap (they only swap on post exit 0). `-NoMixGate` (on run_episode and post) only warns, and is used only when Thomas decides.
   - **Regression check:** the gate was run on the published Fault Lines #1 mix and fails it, as it should: Elliot 135.6 wpm and 15 pauses longer than 1.5 s, the first at 12:25 (1.8 s).
6. **Episode index:**
   - `episodes_index.py` now has an `if __name__ == "__main__"` guard. Importing it no longer runs argparse.
   - New `update` subcommand (`--dur --date --note --cast [--dry]`).
   - New `tools\launcher_lib.ps1`:
     - `Update-EpisodeIndex` calls the CLI, using `update` for a known ep and `add` otherwise.
     - `Get-PostExitText` (7 = mix QC).
   - **Fault Lines #1 launcher fix:** `tools\start_faultlines_01b.ps1` failed with "the following arguments are required: cmd" because it imported the module in an inline `python -c`. It now uses the lib. Future launchers must dot-source `launcher_lib.ps1` and never import episodes_index inline.
   - **Registry fix for Fault Lines #1** (2026-10-21): `update --ep faultlines_01 --dur 2593.4378 --date 2026-10-21 --note "re-render v1.11 (...)"`. The index now shows #11 Fault Lines #1, 2026-10-21, **43:13**.
7. **Tests:**
   - `tests\test_v112.py` (17 unit tests: clamp v2 vs the 32 dB rule, the whispers guard, plan_tempo map/auto/lock/clip/fallback/auto_all, strip_lead_sighs, the import guard, and `update` on a temp index).
   - `tools\test_v112.ps1` (Elliot reference A/B and a short v1.12 render into `tests\v112_ab\` only).
   - The `-Segs` ids are quoted inside `powershell -Command`, because a bare `00,01` binds as the integers 0,1.
8. Code snapshot `code_v1.12\` = the code_v1.11 file list from live files, plus d3_pace.py, drama3_tempo.json, drama3_ref_map.json, tools\launcher_lib.ps1, tools\make_ref_v2.ps1, tools\test_v112.ps1 and tests\test_v112.py. SHA256SUMS.txt was regenerated. Tracked in git.

## Validation (2026-10-21, UTC+2)
- **Static checks:**
  - PowerShell parse check of all changed .ps1: 0 errors.
  - py_compile: OK.
  - `tests\test_v112.py`: 17/17 pass.
  - `tests\test_md_clean.py`: 9 tests OK.
  - `run_episode.ps1 -DryRun` prints the per-speaker cfg, `refmap=Elliot->Elliot_v2` and `mixgate=on`, and writes nothing.
- **A/B render, 18:55-19:08** (`tools\test_v112.ps1`): the same 4 Elliot lines of Fault Lines #1 (script lines 63, 103, 114, 132; 134 words), rendered with v1.12 settings.

| Elliot, 4 lines | old ref Elliot.wav (map 1.00) | new ref Elliot_v2 (auto 0.885) |
|---|---|---|
| raw wpm (pre-tempo) | 164.3 | 180.7 |
| wpm in the mix (whisper span) | 164.9 | 162.0 |
| longest pause | 1.49 s | 0.39 s |
| pauses > 0.5 s / > 1.0 s | 1 / 1 | 0 / 0 |
| clamp cuts | 20 | 9 |
| F0 std, mp3 (P5-95) | 2.29 st (6.5) | 1.97 st (6.3) |
| F0 std, chunk wavs (P5-95) | 3.29 st (12.3) | 2.50 st (7.5) |

- **Voice identity:** the new-ref chunks scored against the ORIGINAL refs: SPKSUMMARY ok=2 fail=0, margins +0.64 and +0.71.
- **Second short segment, seg01** (Fault Lines #1 lines 13-18, Carter/Elliot/Clara, 268 words): mix wpm 164.1, longest pause 0.49 s, voice gate ok=6 fail=0.

| seg01 | Carter (map 0.90) | Elliot_v2 (locked 0.885) | Clara (map 0.95) |
|---|---|---|---|
| raw wpm | 200.8 | 167.9 | 183.2 |
| chunk wpm | 181.6 | 150.3 | 174.1 |
| F0 std | 4.38 st | 2.70 st | 2.98 st |

- **Result:**
  - **Fixed:** pace and pauses (the longest pause drops from 1.49 s to 0.39 s at about 160 wpm).
  - **NOT fixed:** pitch variation. The target was 3.3 st or more, and the new reference is flatter on these lines.
  - **Rate gate risk:** in this small sample Carter's lines run fast (181.6 chunk wpm, above the 175 gate). See Open.
- **A/B files:** `C:\Users\TJ\agent-tools\v112_ab\` (elliot_AB_old_ref_Elliot.mp3, elliot_AB_new_ref_Elliot_v2.mp3, v112_seg01_mixed_Carter_Elliot_Clara.mp3, RESULT.txt).

## Open (Thomas)
- **Elliot's monotone is not solved by Elliot_v2.** It fixes the pace and pauses, but pitch std is 2.0-2.7 st against a target of 3.3 or more.
  - **Options:**
    - keep Elliot_v2 for the next episode;
    - try another reference (fl1b seg07 c007; or the VibeVoice sample, std 4.8 but with a 1.64 s pause);
    - or keep Elliot out of the cast.
  - **To return to the old reference:** set `drama3_ref_map.json` to `{"map":{}}`.
- **Carter at 0.90 may now exceed the 175 wpm gate,** because the shorter pauses raise his rate.
  - **Options:**
    - set `"auto_all": true` (Carter would get about 0.86, slower);
    - or lower Carter's map value to about 0.86.
  - The full-episode mix QC will block publishing if he ends up above 175.
- The tempo target is 160 wpm (earlier 155) and the gate band is 145-175. Both can be changed in `drama3_tempo.json` and in the post parameters.
- `-NoMixGate` overrides the blocking gate. Use it only when Thomas decides.

---

# Technical template
**Version 1.11 - 2026-10-20** = v1.10 + fixes after Thomas rejected the Fault Lines #1 render (v1.10, 35:17 at tempo 1.05): the wrong voices (54 of 164 lines in another cast member's voice), a cut word at 0:53, long pauses at 1:49 and 3:33, and the seg07 GENFAIL that the chain ignored. Root-cause analysis: `fl1\analysis\ANALYSIS.md`. Everything not listed here is as in `technical_v1.10.md`, which follows below for reference. v1.10 and older files stay unedited.

## v1.11 changes
1. **Voice mismatch fix: one speaker per Drama 3 request** (`drama3_generate.py --mode turn`, the default).
   - **Cause in v1.10:** each request held up to 150 words from several speakers, with clone references numbered `<|speaker:0..2|>`. Drama 3 Q4_K_S often voiced speaker:1/2 lines with the speaker:0 reference. In Fault Lines #1, 54 of the 83 lines that were not reference 0 came out in the wrong voice. All 81 lines that were reference 0 came out right.
   - **v1.11 behaviour:** every request now carries one speaker's text and only that speaker's reference, as `<|speaker:0|>`. Chunks also break at every speaker change; the old mode is still available as `--mode multi` (not recommended). Turns are joined with the normal 0.35 s gap.
   - **Trade-off:** less cross-speaker prosody context, and more requests per segment (test: RTF 1.6-1.9 after load, the same as v1.10).
2. **Automatic voice-match gate**: new `spk_check.py`, run in `venv_spk` (CPU torch and SpeechBrain ECAPA `spkrec-ecapa-voxceleb`, model in `models\spkrec-ecapa-voxceleb`).
   - **How it scores:** it embeds every chunk (or every line, for multi-speaker chunks, using the qc line times) and compares it with the cast's clone refs and with the segment's own centroids. Margin = similarity to the own voice minus the best other cast voice.
   - **What fails:** a unit of 1.5 s or more with margin < 0; a unit of 0.8-1.5 s with margin < -0.10; or any 3 s window with margin < -0.15. Units under 0.8 s are not judged.
   - **What happens on a fail:** `render_drama3.ps1` re-renders the failing chunks with the next seeds (`-SpkRetries 2`). If a chunk still fails after the retries, the render STOPs with STATUS `STOP voice mismatch ...` and exit 5, and nothing is shipped. The result is written into `segNN.qc.json` (`voice`, `voice_summary`, `voice_redo`) and logged as `[VOICE] SPKSUMMARY ok=.. fail=..` in render.log. Use `-NoSpkCheck` only for debugging.
3. **Cut-word fix: `qc_vv.py` v2.3**.
   - **Cause in v1.10:** the v2.2 pause gate (`--gate`, used for every engine since v1.3) muted everything outside the whisper word times ±0.04 s. Word tails that whisper timed too short were muted to -84..-115 dB, for example the end of "assassination" at 0:53. Fault Lines #1 had 71 such cuts (7.5 s); earlier episodes have them too (see ANALYSIS.md).
   - **v2.3 behaviour:** the gate restores every frame louder than speech level -24 dB (±30 ms) before it applies the mask. It also adds a new HARD QC flag, `end_missing`: the last word of a line (3+ words) is missing at the end, which forces a regeneration.
   - **Cut-word gate:** new `gate_cut_check.py`, run by `post_segment.ps1` on raw vs gated audio. If any speech-level stretch of 40 ms or more was muted (`GATECUT n>0`), the segment falls back to the ungated audio. Results are in `segNN.gatecut.json`.
4. **Long-pause fix: pause clamp in `drama3_generate.py`**.
   - **Cause in v1.10:** the long pauses at 1:47, 2:04 and 3:33 (3.5-4.1 s) were silences that the model generated inside multi-speaker requests, after short sentences and at handoffs. The gate cannot shorten silences.
   - **v1.11 behaviour:** each generated chunk is clamped. Leading silence is cut to 0.05 s and trailing silence to 0.12 s (silence = 32 dB below the speech level). Any internal silence over 0.9 s becomes 0.6 s. The unclamped audio stays in `_d3out`, and the per-chunk `clamp` is recorded in chunks.json.
5. **Runaway protection**:
   - `-ChunkWords` default **100** (was 150).
   - `options.max_tokens` 512 frames per text chunk, about 24 s (`--max_frames`).
   - **Generator retry (`--gen_retries 2`):** a chunk is regenerated in a new CLI process with a new seed if it hits `reached_limit`, produces no output (CLI crash or Vulkan OOM, like seg07: `ErrorOutOfDeviceMemory`), or has an implausible length. Implausible means more than 2.3 × expected + 4 s, or less than 0.4 × expected - 1 s, with expected = words × 60/172 s.
6. **Chain stops on missing audio**:
   - `render_drama3.ps1`: GENFAIL now STOPs the render at once, with STATUS `STOP GENFAIL segNN` and exit 4.
   - `run_episode.ps1`: after TTS it checks that every `segNN.json` has its mp3, a final qc.json, no open voice redo, and no GENFAIL/SPKFAIL/POSTFAIL line in render.log. If any check fails, STATUS is `STOP TTS incomplete ...`, Ollama is unloaded, the exit code is 6, and FLUX/post do not run.
   - `post_episode.ps1`: the segment list comes from `seg??.json`, not from counting mp3s. A missing mp3 gives `ABORT missing segment mp3(s)` and exit 5.
   - **Why:** in v1.10, seg07 failed, the chain still ran FLUX for 9 minutes, and post mixed "0 s".
7. **Drama 3 tempo 0.90 by default** (`run_episode.ps1 -Tempo 0` resolves to drama3 0.90, `render_drama3.ps1 -Tempo 0.90`; was 1.05).
   - **Calibration:** Fault Lines #1 had 6,198 words and 2,161 s of raw speech = 172 wpm raw. At 1.05 that became 181 wpm and 35:17. For the target of 155 wpm, 155/172 = 0.90 (0.88 after the pause clamp).
   - **Prediction for Fault Lines #1:** about 40-42 min.
   - The 7B engine stays at 0.93.
8. **Other changes**:
   - **Engine name in the notes:** `post_episode.ps1 -EngineName`, or the engine field in chunks.json (the v1.10 notes always said VibeVoice).
   - **Output dir:** `post_episode.ps1 -OutDir` (staging dir, with the same never-overwrite guard), passed through by `run_episode.ps1 -OutDir`.
   - **Chain log:** at the end, `run_episode.ps1` logs `ollama ps` to chain.log.
   - **Fault Lines #1 launcher:** `tools\start_faultlines_01b.ps1` (re-render into `fl1b\`, reusing the bg_fl1 FLUX images, staged output, final gates, swap with the rejected v1.10 files moved to `episodes\_rejected\faultlines_01_v110\`).
   - **Test tools:** `tools\test_fl1_v111.ps1` (short test) and `tools\verify_words.py`.
   - **Old launcher:** `tools\start_faultlines_01.ps1` (v1.10) is left unchanged; its preflight still expects tempo 1.05, so do not use it any more.
9. Code snapshot `code_v1.11\` = code_v1.10 + the changed/new files; SHA256SUMS.txt regenerated. Tracked in git (tottedk/podcast-pipline, main).

## v1.11 test render (2026-10-20 17:26-17:39 UTC+2, `tools\test_fl1_v111.ps1`, output `tests\fl1_v111\`)

**Input:** the exact Fault Lines #1 lines around Thomas's spots, with the script text unchanged.
- seg00 = script lines 0-4: the cold open and the 0:53 "assassination" line.
- seg01 = script lines 13-18: the 3:33 pause, Elliot at 3:40 and Clara at 4:20.

The render used 449 words, Host Carter, Guest Elliot and Guest2 Clara, in turn mode at tempo 0.90 with ChunkWords 100.

**Voice gate:** 11 of 11 turn chunks pass, with margins +0.61 to +0.84.
- `SPKSUMMARY ok=5 fail=0` (seg00) and `ok=6 fail=0` (seg01), confirmed by an independent re-run.
- In v1.10 the same lines had margins of about -0.6 (lines 0, 2, 14, 17 and others).
- The gate fired once during the render, on the first retake of seg00 c005 (Carter): a 3 s window at the start leaned toward Elliot (-0.175). The automatic re-render with seed 3042 passed (+0.73).

**Cut word:**
- `GATECUT 0` for both segments, in post_segment and in the independent raw-vs-mp3 check.
- Whisper finds "assassination," intact (0.70 s, p=1.00).
- 11 of 11 line endings are found in order.

**Pauses:**
- The longest pause is 0.94 s, compared with 3.5-4.1 s in v1.10.
- The pause clamp did not have to act (0 internal pauses > 0.9 s in raw).

**Pace:** 150 wpm including pauses (seg00 146, seg01 153). The target is 155.

**Runaway check:**
- No `reached_limit`.
- No GENFAIL.
- RTF 1.6-1.9 after load.
- VRAM peak 10.7 GB.

**QC:**
- seg01 passed with no hard flags.
- seg00 c002 shipped with a `wer` flag after the retry; all its line endings were present.

**Afterwards:** no Ollama model loaded, 0 audiocpp processes, 0 TTS python jobs.

## Open (Thomas)
- Listen to the re-render `fl1b` (scheduled 2026-10-21 01:00). If the voice gate STOPs, decide whether to loosen the thresholds or ship that segment.

---
_v1.10 base text (unchanged, for reference; where it differs, the v1.11 text above overrides):_

# Technical template
**Version 1.10 - 2026-10-19** = v1.9 + **Fish Audio Drama 3 is the DEFAULT TTS engine** (Thomas decided after the v1.9 test render). VibeVoice-7B Q8 stays as the selectable fallback (`run_episode.ps1 -Engine 7b`). Everything not listed here is as in `technical_v1.9.md` (its text follows below for reference); v1.9 and older files stay unedited.

## v1.10 changes
1. **`run_episode.ps1`**: `-Engine` default **`drama3`** (was `7b`). `-Tempo` default `0` = per-engine default: **drama3 1.05** (target 2.6 w/s = 155 wpm; v1.9 test: 0.93 -> 139 wpm, 1.0 -> ~149 wpm, 1.05 -> ~155 wpm), **7b 0.93** (unchanged). An explicit `-Tempo` still overrides for either engine. Engine + resolved tempo are logged (`step=TTS engine=... (script) tempo=...` in STATUS.txt / chain.log).
2. **`run_episode.ps1 -DryRun`** (new): prints `DRYRUN engine=... script=... tempo=... qcretries=... dir=...` and exits before anything is written or started (no cast pick, no models). Example: `run_episode.ps1 -Dir x -Ep x -BgDir x -DryRun` -> `engine=drama3 script=render_drama3.ps1 tempo=1.05`; with `-Engine 7b` -> `render7b.ps1 tempo=0.93`.
3. **`render_drama3.ps1`**: default `-Tempo 1.05` (was 0.93), so direct calls (e.g. `tools\test_drama3_pipeline.ps1`) match run_episode. `render7b.ps1` keeps `-Tempo 0.93` (header comment now says fallback). `post_segment.ps1` / `podcast.ps1` (1.5B backup) keep 0.93; the render drivers always pass `-Tempo` to post_segment explicitly.
4. **Launchers** `tools\start_mike_ma_ep1.ps1`, `tools\start_burnout_society_ep1.ps1`, `tools\start_agentic_ai_ep1.ps1`: new `-Engine 7b|drama3` (default `drama3`), `-Tempo` default `0` (= engine default); both are passed to run_episode. Use `-Engine 7b` to reproduce the original 7B renders of those episodes.
5. **Duration gate unchanged and engine-independent**: `post_episode.ps1 -MinDur 2280 -MaxDur 2880` (38-48 min) on the final mix; still do not change the tempo for length. Drama 3 at 1.05 targets the same spoken pace as 7B at 0.93 (~155 wpm), so the v1.8 word-count rule of thumb (~5,900-7,400 script words = 38-48 min) applies; verify on the first full Drama 3 episode.
6. **QC caveat (not changed)**: `qc_vv.py` f0_drift uses `voice_f0.json`, calibrated on the 7B voices. With Drama 3 expect soft f0_drift flags (soft = no retry, as in the v1.9 test). Recalibrating voice_f0 for Drama 3 is a later task.
7. `tools\test_drama3_pipeline.ps1`: the "tempo for 2.6 w/s" hint now assumes the 1.05 default.
8. Code snapshot `code_v1.10\` = code_v1.9 + the live versions of the changed files that are part of the snapshot; SHA256SUMS.txt regenerated. Tracked in git (tottedk/podcast-pipline, main), no `_backup` copies.

---
_v1.9 base text (unchanged, for reference; where it says the default stays 7b, v1.10 above overrides):_

**Version 1.9 - 2026-10-19** = v1.8 + a second, EXPERIMENTAL TTS engine: Fish Audio Drama 3 (Thomas approved: "Lad os implementere det i podcast"). **The default engine stays VibeVoice-7B Q8 (`-Engine 7b`)**; switching the default to Drama 3 only after Thomas has listened to the test render. Everything not listed here is as in `technical_v1.8.md` (and v1.7 ... v1.3), which stay unedited.

## v1.9 changes (inherited from technical_v1.9.md)
1. **`run_episode.ps1 -Engine 7b|drama3`** (default `7b`): picks `render7b.ps1` or the new `render_drama3.ps1`; the engine is written to STATUS.txt / chain.log. Nothing else in the chain changes (FLUX, post_episode, align, video).
2. **`render_drama3.ps1`** = `render7b.ps1` with the Drama 3 generator: same parameters (-Dir -Segs -HostVoice -GuestVoice -Guest2Voice -Tempo -ChunkWords -QcRetries -Seeds -Glossary -NoResume; -Cfg/-Steps accepted and ignored) and the same outputs (`segNN.raw.wav`, `segNN.raw.wav.chunks\cNNN.wav` 24 kHz mono + `chunks.json`, `segNN.qc.json`, `segNN.mp3`, STATUS.txt, SEGDONE/ALLDONE), so qc_vv.py v2.2 (lenient, max 1 retry per chunk), qc_takes.py, post_segment.ps1, post_episode.ps1 and align.py run unchanged. Extra: -D3Home (C:\grok\drama3), -CacheSize 8, -CtxLen 4096; -ChunkWords default 150 (three clone refs + text must fit context 4096).
3. **`drama3_generate.py`** (drop-in for vv7b_generate.py, incl. `--redo i:seed`): audio.cpp v0.9.2-drama3-base-small Windows Vulkan, model `drama-3-backbone-8bit-experts-Q4_K_S.gguf` (full Drama 3, 22.9 GiB), device 0 = RX 7900 XT. Session options as PR #927 / #929: `disk_experts=true`, `expert_cache_size=8`, `cpu_expert_layers=0`, `context_length=4096`, `codec_encoder_f32_accumulation=true` (Vulkan cloning fix). **No pin_experts / -Pin** (needs ~17 GB extra RAM). All chunks of a segment run as one `--request-sequence` session (model loaded once), IDLE priority; the process exits when the segment is done (model unloaded). Guards: refuses to start with < 6 GB free RAM, kills audiocpp if free RAM < 1.2 GB. Per-run metrics (CLI rtf per chunk, wall, VRAM peak via typeperf, commit/RSS peak, min free RAM, reached_limit) in `<chunks>\drama3_metrics.json` and a `D3RUN` line in render.log.
   - Speakers: per chunk the speakers present are numbered `<|speaker:0|>`, `<|speaker:1|>`, ... (Host, Guest, Guest2 order) and passed as `options.references` (clone refs).
   - **Emotion/event tags** `[sighs]`, `[laughs]`, `[whispers]` etc. are kept in the text sent to Drama 3 (performed, not read aloud) and stripped from the QC texts in chunks.json, so QC does not expect them as words. (The 7B engine does not strip them - do not put tags in scripts rendered with `-Engine 7b`.)
4. **`drama3_refs.py`** (venv_whisper): clone references come from the existing voice registry (`voices.json` files, the same refs VibeVoice uses: Carter = VibeVoice-main\demo\voices\en-Carter_man.wav, Clara/Lachlan = voices_extra\en-*.wav), cut at a word boundary to <= 20 s, transcribed with faster-whisper large-v3-turbo; cached in `C:\grok\podcast\drama3_refs\<Name>.wav/.txt`. Blocked for cloning: **Thomas (never), Maya, Declan, Alice, Mary**.
5. **GPU hygiene**: before every TTS call render_drama3 waits until Ollama has no model loaded AND no other audiocpp_cli/audiocpp_server runs (one GPU model at a time); a leftover Drama 3 audiocpp_cli is killed in `finally`. No -Scheduled / app closing, no reboot.
6. **`tools\test_drama3_pipeline.ps1`**: one short test (first 10 lines of chapter 9 "The surprise call" of agentic_ai_ep1, Host Carter, Guest Clara, Guest2 Lachlan, one `[laughs]` tag added) into `tests\drama3_pipeline\` only (never episodes\ or ag\) -> QC -> post -> align -> RESULT.txt.
7. Code snapshot `code_v1.9\` = code_v1.8 + the files above (render_drama3.ps1, drama3_generate.py, drama3_refs.py, tools\test_drama3_pipeline.ps1) + live run_episode.ps1; SHA256SUMS.txt regenerated. Changes are tracked in git (repo tottedk/podcast-pipline, branch main), no `_backup` copies.

## Drama 3 reference numbers (Tech Bro test, C:\grok\drama3, 2026-10-19)
VRAM peak 11.3 GB total (~9.4 GB net of desktop), RAM private peak 12 GB, RTF ~1.8-2.1 generation-only (2.0-2.6 incl. model load) -> a 40 min episode needs about 1.5 h of TTS (plus QC). Tags not read aloud. Carter/Clara dialogue ran slightly fast.

## Open (Thomas)
- Listen to the test render; decide default engine and tempo for Drama 3 (see test results below).

---

# Technical template
**Version 1.8 - 2026-10-16** = v1.7 + four changes approved by Thomas. Everything not listed here is as in `technical_v1.7.md` (and v1.6 ... v1.3), which stay unedited.

## v1.8 changes
1. **QcRetries default 1** (was 2): `render7b.ps1`, `run_episode.ps1` (new `-QcRetries`, passed to render7b) and `podcast.ps1` (1.5B backup engine). A flagged chunk gets at most one regeneration (seed 1988), then the best take ships. With v1.7's soft `noise` this is rarely needed (v1.7 validation: 142 takes -> 86 on the three reference episodes).
2. **Length window 38-48 min** (was 40-45) in the `post_episode.ps1` gate: `-MinDur 2280 -MaxDur 2880` (exit 3 before align/video if the mix is outside). **Tempo stays at the normal 0.93** (`render7b`, `run_episode`, `post_segment`, `podcast` defaults) - do NOT slow down for length any more (this supersedes lever 2 "-Tempo 0.90" of the v1.3 length rule). The fallback levers `-SegGap 1.2 -StingPad 0.6` (post only, no TTS) are for a mix that is **< 38 min** only. The episode-specific launcher `tools\start_mike_ma_ep1.ps1` was aligned (tempo 0.93, 2280/2880).
   - **Word-count rule of thumb at tempo 0.93:** `mix seconds ~= words x 0.37..0.39 + 60` -> **about 5,900-7,400 script words = 38-48 min** (0.38 s/word centre; 6,300-7,000 words is the comfortable middle). Examples: UI ep1 6,040 words = 2,446 s with tempo 0.90 (2,243 s speech at 0.93); Mike Ma ep1 6,191 words, tempo 0.90 -> 2,520 s (an 0.93 render would be ~2,440 s = 40:40).
3. **Episode naming + registry.**
   - Convention: every episode gets a **running number across all podcasts created so far** (`number`; a re-render `<ep>_v2` keeps the number of the original and shows "(v2)" in the title). A series with **several episodes** is titled **`<Series> #<n>`** (n = number inside the series); the video's top-right corner label is the same text. **One-offs (the default)** are titled with the subject only (a trailing ", Episode 1" / "- Episode 1" / "(v2)" is stripped) and the corner label is the **date** (YYYY-MM-DD). The words "Episode 1" appear nowhere (video title card + corner, title metadata, notes heading, chapters).
   - A series counts as multi-episode when `-Multi` is given (`run_episode.ps1 -Series "Uploaded Intelligence" -Multi`, or `post_episode.ps1 -Series ... -Multi`) or when it is already marked `multi` in the registry; otherwise it is a one-off (`-OneOff` forces it). Default series name = the `-Ep` name without `_epN` / `_vN`, title-cased.
   - `make_video.py`: new `--label` (top-right text; default = the title) and `--dry-label` (prints the resolved title/label/topic as JSON, renders nothing); the hard-coded fallback "Fanged Noumena - Episode N" is gone (fallback = the file name without `_epN`); `no_ep()` strips "Episode N" from titles and labels that come from `--title`, `--label` or the chapters json (this is where the "episode 1" corner text of a one-off came from: `ctx["title"]` was drawn top-right and the chapters json title was "..., Episode 1").
   - `episodes_index.py` (new; stdlib): `plan` (dry run, prints the naming JSON), `add` (register; no-op if already registered), `backfill`, `show`. Registry = `episodes_index.json` (+ generated `episodes_index.md`) in the live root (state, git-tracked, not part of the template). `post_episode.ps1` computes the plan after the duration gate (passes `--title/--label` to make_video, writes the notes heading and a "date - podcast #n overall" line) and appends the episode with its duration and cast when the post finishes (`registry: ...` line in post.log).
   - Backfill (9 files from `episodes\*.mp3`, oldest first): #1-#3 Fanged Noumena #1-#3 (multi), #4 Patchwork, #5 The Dark Enlightenment, #6 das Man in the modern world (+ its v2 re-render, same number), #7 Uploaded Intelligence #1 (multi), #8 Mike Ma: Harassment Architecture and Gothic Violence (one-off). Already rendered files/videos/notes were NOT touched (their titles still say "Episode 1"; only new renders use the convention). Edit `series.<name>.multi` in the json to change a series' mode.
4. **Declan removed from the random guest pool** (Thomas: voice sounds too machine-like): moved from `pool.guests` to `pool.excluded` in `voices.json` (entry, F0 and credit kept; `pick_cast.py --guests Declan,...` still works but prints the exclusion warning, as for Maya). Pool now: Frank, Clara, Isla, Marcus, Willa, Zara, Imogen, Elliot, Hugh, Lachlan + Samuel (weight 0.25); excluded: Maya, Declan. With host Carter (132 Hz) Frank, Samuel (and Hugh) drop out through the >= 12 Hz F0-gap rule, so male guests are Marcus / Elliot / Lachlan.
   - Test (`tools\pick_cast_test.py`, 150 seeds each, host Carter): genders M,F -> Guest from Lachlan 54 / Elliot 53 / Marcus 43, Guest2 from Willa, Imogen, Isla, Zara, Clara; none -> any of Lachlan, Elliot, Isla, Zara, Willa, Imogen, Clara, Marcus. Declan 0, Maya 0, Hugh 0 (gap rule), Frank 0, Samuel 0; 0 F0-gap violations (min gap 12.6 Hz), 0 runs with warnings. Override `--guests Declan,Isla` -> picked with the warning.

## Tests (no render, no GPU)
- PowerShell parse check of post_episode, run_episode, render7b, podcast, post_segment, vram_free, start_mike_ma_ep1: 0 errors; `make_video.py` / `episodes_index.py` / `pick_cast.py` compile.
- `make_video.py --dry-label` on the real Mike Ma / UI / das Man v2 files: legacy chapters titles ", Episode 1" are stripped; one-off -> title = subject, label = date; multi -> "Uploaded Intelligence #1" both.
- The naming block of `post_episode.ps1` executed standalone for: new one-off, next episode of a registered multi series (-> "#2"), new multi series, re-render `_v2`, already registered: titles/labels/notes line as designed; registry unchanged by `plan`; `add` tested on a temp index (idempotent).
## v1.9 test render (2026-10-19 13:49-13:58, tools\test_drama3_pipeline.ps1)
- Input: agentic_ai_ep1 chapter 9 "The surprise call", script lines 181-190 (225 words), Host Carter / Guest Clara / Guest2 Lachlan, one [laughs] tag added. Output: tests\drama3_pipeline\seg00.mp3 (97.5 s), seg00.raw.wav (90.7 s).
- Refs: Carter 20.1 s, Clara 19.8 s, Lachlan 20.2 s (cut at word boundaries). 2 chunks (150 words).
- TTS: 88.2 s audio in 197 s wall (RTF 2.23 incl. load; gen 2.25 / 1.89); QC retry of chunk 1 (seed 1988, 57.4 s in 132 s, RTF 2.3). VRAM peak 10.0 GB total (base 1.9 GB), commit peak 10.9 GB, RSS 17.2 GB (mostly mapped GGUF), min free RAM 6.9 GB. Whole render+QC+post 496 s; no audiocpp process and no Ollama model left afterwards.
- QC v2.2: final no hard flags; WER 2.2 % / 1.1 %; only soft f0_drift (voice_f0.json is calibrated on the 7B voices). Align OK (20 s).
- Pace: raw 2.48 w/s; after post tempo 0.93 = 2.31 w/s (139 wpm) vs target 2.6 w/s (155 wpm). Drama 3 is NOT too fast in the pipeline; tempo 1.0 would give ~2.48 w/s (149 wpm), ~1.05 hits 2.6. Tempo for -Engine drama3 not changed yet (decision for Thomas after listening).
