# Fault Lines #1 (v1.10 render) - root-cause analysis
2026-10-20, for Thomas. Rejected file: `episodes\faultlines_01.mp3` (35:17, Drama 3, tempo 1.05). Script: `episodes\faultlines_01\faultlines_01_script.json` (164 lines, 6,198 words). Cast: Host Carter, Guest Elliot, Guest2 Clara.

**How the timestamps were mapped:** each timestamp was mapped to a line, segment and chunk using `fl1\timings.json` (final mp3 line times; the intro takes about 8.8 s) together with `fl1\segNN.raw.wav.chunks\chunks.json` and the Drama 3 request json.

**Evidence files**, all in `fl1\analysis\`:
- `voice_mismatch.csv`: the 62 flagged lines.
- `voice_mismatch_all.csv`: all 164 lines.
- `gatecut_sweep.log` and `gatecut_sweep_old.log`.
- `spk_old_seg01.json`.

| Timestamp | Line | Where |
|---|---|---|
| 0:53 | line 3 (Elliot) | seg00 chunk c001, the word "assassination" |
| 1:47 / 2:04 | lines 8-10 | seg00 c003: silences of 4.08 s after "Noted." and 3.54 s before Clara's line 9 |
| 3:33 | end of line 13 | seg01 c001: 3.68 s after "Elliot.", then another 2.04 s |
| 3:40 | line 14 (Elliot; final 3:36.4-) | seg01 c001, speaker:1 |
| 4:20 | line 17 (Clara; final 4:15.4-) | seg01 c002, speaker:2 |

---
## 1. Wrong voices (most important)

**Symptom:** at 3:40 Elliot speaks with Carter's voice, and at 4:20 Clara does.

**Evidence: the whole episode was scanned.** Every line was embedded with SpeechBrain ECAPA (`spkrec-ecapa-voxceleb`) and compared with the three clone refs and the per-segment voice centroids. Margin = similarity to the expected voice minus the best other voice.

- **54 lines are MISMATCH and 8 are UNCERTAIN.** That makes **62 lines not OK out of 164**; 102 are OK. The mismatched lines cover 791 s of the 2,019 s of speech (39 %).
- **By speaker:**
  - Clara: 32 wrong and 2 uncertain, of 53 lines.
  - Elliot: 22 wrong and 2 uncertain, of 50.
  - Carter: 0 wrong and 4 uncertain, of 61. The uncertain ones are very short lines such as "Sorry?" and "Go on.".
- **By segment** (wrong/total): seg00 2/13, seg01 8/12, seg02 5/15, seg03 8/21, seg04 3/12, seg05 6/15, seg06 8/18, seg07 5/23, seg08 8/26, seg09 1/9.
- **The pattern is deterministic:**
  - Lines whose speaker was reference index 0 in their request: 81, of which **0 were wrong** (77 OK, 4 uncertain).
  - Lines whose speaker was reference 1 or 2: 83, of which **54 were wrong** (25 OK, 4 uncertain).
  - **52 of the 54 wrong lines sound like that request's speaker:0 voice.**
  - Single-speaker chunks: 0 wrong lines. Multi-speaker chunks: 43 of 56.
- **Thomas's examples:**
  - Line 14 (Elliot) has margin -0.62 and sounds like Carter.
  - Line 17 (Clara) has margin -0.69 and sounds like Carter.
  - Seg01 came out almost entirely in Carter's voice: 8 of 12 lines were wrong.
- **Not noticed before:** the cold open (seg00 c001, refs Elliot then Clara) has Clara's lines 0 and 2 in Elliot's voice (margin -0.67 / -0.68).
- **The margins separate cleanly:**
  - Wrong lines: median margin -0.55, max +0.06.
  - Right lines: medians +0.24 (Clara) to +0.71 (Carter), minimum +0.06.

**Root cause:** `drama3_generate.py` (v1.9/v1.10) packs up to `-ChunkWords` 150 words of consecutive lines from different speakers into **one** Drama 3 request. The speakers present are numbered `<|speaker:0|>`, `<|speaker:1|>`, ... in Host/Guest/Guest2 order, and the clone refs go in `options.references`.

The request json is correct: every line has the right tag, and the refs are in the right order. The model (Drama 3 Q4_K_S in audio.cpp) still often renders speaker:1/2 text with the speaker:0 timbre, so the tag is not reliably followed in multi-reference cloning.

Other causes were ruled out:
- **The script:** the speaker field is correct.
- **Chunk splitting:** lines are never split.
- **QC retries:** seed-1988 retakes show the same pattern.
- **The cast mapping:** cast.json is correct.

QC did not catch it. `qc_vv.py` checks only WER and F0 drift, F0 drift is a soft flag, and Carter and Elliot have similar F0. No pipeline step compared speaker identity.

The 3-speaker test in v1.9 was 2 chunks with refs Carter first, so only a few non-reference-0 lines were tested. The problem was missed there.

**Fix (v1.11):**
1. **Turn mode** (the default): every request contains exactly one speaker, and only that speaker's ref, as speaker:0. In the data, speaker:0 was right 81 of 81 times. Chunks break at every speaker change.
2. **Automatic voice gate** (`spk_check.py`, ECAPA, CPU):
   - Every chunk is checked after QC. A chunk fails if a unit of 1.5 s or more has margin < 0, or any 3 s window has margin < -0.15.
   - A failing chunk is re-rendered with new seeds, up to 2 times.
   - If it still fails, the render STOPs (`STOP voice mismatch`, exit 5) and nothing is shipped.
3. A final check runs after the best takes are picked. The launcher additionally requires `voice_summary` with fail=0 for every segment before it swaps the episode.

**Verification:**
- **On the v1.10 audio,** the gate catches the known errors:
  - seg01: `SPKSUMMARY ok=4 fail=8` (run on the PC). This matches the scan.
  - seg00: it flags exactly lines 0 and 2.
- **On the v1.11 test render** (Thomas's lines; see "Test" below), all units pass.

---
## 2. Cut word at 0:53

**Symptom:** the end of "assassination" (line 3, Elliot) is missing.

**Evidence:**
- In `seg00.raw.wav` the word runs 45.46-46.28 s raw. Its last 0.22 s (46.06-46.28) is at -25..-34 dB in the raw TTS output, but at **-84..-115 dB** in `seg00.mp3`. It was muted digitally; the model did not drop it.
- Whisper put the word end at about 45.90 s, followed by a long "and".
- `gate_cut_check.py` compares raw and processed audio (tempo-aligned, corr 0.87-0.95). It found speech-level audio muted to silence (≥ 40 ms) in **every fl1 segment: 71 cuts, 7.5 s in total**. seg00 alone has 11 cuts (1.16 s), including 46.06 s / 0.22 s, the 0:53 word.

**Root cause:** the pause gate in `qc_vv.py` v2.2 (`--gate`) is run by `post_segment.ps1` for every engine.
- It keeps only whisper word spans ±0.04 s (merged with a 0.08 s margin) and mutes everything else.
- Whisper word end times are often 50-250 ms too early on long words and on words before pauses or breaths, so word tails and soft onsets get muted.
- The gate does not check the audio level, so speech is muted too.

**Earlier episodes share the code path** (gate in post_segment.ps1 since template v1.3). Measured on seg00/03/06 (`gatecut_sweep_old.log`):

| Episode | Cuts per segment | Muted per segment |
|---|---|---|
| ag (7B, 0.93) | 16-23 | 1.3-2.7 s |
| bb | 4-12 | 0.7-1.0 s |
| mm | 6-7 | 0.4-0.6 s |
| de | 0-45 | 0-12.4 s |

ui1 and dm_v2 could not be aligned (corr < 0.3: different tempo or post chain), so their numbers are not valid.

So clipped word endings are a pipeline-wide issue. Fault Lines #1 is not special; it is just very noticeable here.

**Fix (v1.11):**
1. **`qc_vv.py` v2.3 gate:** before the mask is applied, every frame within 24 dB of the speech level (±30 ms) is restored. The gate now only removes noise and room-level audio between words, never speech.
2. **New HARD QC flag `end_missing`:** set when the last word of a line is not heard at the end of the line, which forces a regeneration.
3. **Cut-word gate in `post_segment.ps1`:** `gate_cut_check.py` compares raw and gated audio. If any cut remains, the segment falls back to the ungated audio. The result is in `segNN.gatecut.json`.

**Verification:**
- v2.3 on the same v1.10 seg00 raw: **GATECUT 0** (2.57 s of speech restored), compared with 11 cuts for v2.2.
- The test render: see "Test".

---
## 3. Long pauses at 1:49 and 3:33

**Symptom:** dead air of several seconds.

**Evidence:**
- At 1:47-1:51, seg00 c003 (lines 8-10) has an internal silence of **4.08 s** after Carter's "Noted.". Another **3.54 s** follows before Clara's line 9 (2:04).
- At 3:33, seg01 c001 has **3.68 s** of silence after "Elliot." (end of line 13), and another 2.04 s.
- These silences are inside the raw output of a single Drama 3 request (`cNNN.wav`), not at segment or chunk joins. SegGap is 0.4 s, the chunk join is 0.35 s and StingPad is 0, so none of those explains them.
- Raw chunk audio for the whole episode has **69 internal silences > 0.9 s**.
- They cluster after very short sentences and at handoffs to another speaker inside multi-speaker requests. In other words, the model "waits" for the next speaker.

**Root cause:** the silences are generated by the model inside multi-speaker requests. Nothing in the chain limits them. The v2.2 gate only attenuates noise between words; it never shortens silence.

**Fix (v1.11):**
1. Turn mode reduces the number of handoffs inside a request to zero.
2. The pause clamp in `drama3_generate.py`:
   - leading silence is cut to 0.05 s and trailing silence to 0.12 s (silence = 32 dB below speech);
   - every internal silence > 0.9 s is shortened to 0.6 s;
   - the original audio is kept in `_d3out`, and each chunk's `clamp` record is written to chunks.json.

**Verification:** on the test render the longest pause is under 1 s (see "Test").

---
## 4. Other confirmed issues

### 4a. seg07 runaway / GENFAIL
- In the v1.10 run (2026-10-19 23:53), `audiocpp_cli` exited with code 1 on seg07. Its stderr (`drama3_20261019_235343.log.stderr`) says: `ggml_vulkan: Requested buffer size exceeds device buffer size limit: ErrorOutOfDeviceMemory`.
- The request was a 150-word multi-speaker chunk. Generation ran away (no stop token), until the KV/codec buffer exceeded what the Vulkan device could allocate.
- seg07 rendered fine when re-run with `-ChunkWords 100`: 11 chunks, 322 s.

**Fix (v1.11):**
- ChunkWords 100 by default.
- `max_tokens` 512 per text chunk (about 24 s).
- Generator retry with a new seed in a new process, for a crash, `reached_limit`, or an implausible duration.
- A QC retake in v1.10 (seg04 c005) stopped early after only 2.3 s; the same implausible-duration check now catches that case too.

### 4b. Chain ignored GENFAIL
- render.log has `GENFAIL seg07`, but `render_drama3.ps1` just continued, and `run_episode.ps1` logged `step=TTS done 9 segs`.
- FLUX still ran (545 s).
- `post_episode.ps1` counted 9 mp3 files and looped seg00..seg08. seg07.mp3 was missing, so the mix had a "dur 0 s" mix, then exit 3.
- The episode was only finished by hand later (2116.8 s).

**Fix (v1.11):**
- GENFAIL stops the render at once (exit 4).
- `run_episode.ps1` refuses FLUX/post unless every `segNN.json` has its mp3 and a final QC json with no open voice redo (exit 6, STATUS `STOP TTS incomplete`).
- `post_episode.ps1` builds its segment list from `seg??.json` and aborts if any mp3 is missing (exit 5).

### 4c. Tempo calibration (35:17 instead of 38-48 min)
- **Measured:** raw TTS was 2,161.4 s for 6,198 words = **172 wpm raw**. At tempo 1.05 that became **181 wpm** (35:17).
- **Where 1.05 came from:** the v1.10 calibration was based on the 225-word, 3-speaker test, which measured 2.48 w/s = 149 wpm raw. That test sample was too slow to be representative; the full episode runs about 15 % faster raw.
- **New value:** for 155 wpm, tempo = 155/172 = **0.90** (0.88 after the pause clamp removes about 55 s).
- **Prediction for the re-render:** about 2,340-2,400 s of speech plus about 80 s of intro, stings and outro = **about 40.5-41.5 min**, inside the 38-48 min gate.

### 4d. Notes said "VibeVoice"
`post_episode.ps1` had the engine name hard-coded. v1.11 takes it from `-EngineName` or from the `engine` field in chunks.json.


---
## Test (v1.11, short render of Thomas's lines)

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

---
## Re-render (armed)
- **What runs:** `tools\start_faultlines_01b.ps1 -FromTask`, through scheduled task `PodcastFaultlines01b`, once at 2026-10-21 01:00 (UTC+2). The task deletes itself after it starts.
- **Input and output:** the same script, with the text unchanged, rendered into a fresh `fl1b\`. The bg_fl1 FLUX images are reused.
- **Settings:** Drama 3 turn mode, tempo 0.90, ChunkWords 100, voice gate on.
- **Final gates:**
  - every segment present and voice-ok;
  - GATECUT 0 (otherwise that segment falls back to ungated audio);
  - mix duration 2280-2880 s (38-48 min).
  If a gate fails, the run STOPs for Thomas (STATUS.txt) and nothing is replaced.
- **Swap, only when every gate passes:** `episodes\faultlines_01.*` are moved (not deleted) to `episodes\_rejected\faultlines_01_v110\`, the staged files are moved in, and the registry duration and date are updated.
- **End of run:** all models are unloaded and `ollama ps` is logged to chain.log.
