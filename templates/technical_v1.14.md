# Technical template
**Version 1.14 - 2026-11-07** = v1.13 + three fixes Thomas asked for (t58u "A, B og C"): (A) less monotone Drama 3 voices, (B) content style v2.6 with a humanity dial, (C) Carter's tempo: fixed 0.86 kept (Thomas's preference), host mix limit 190. Everything not listed here is as in `technical_v1.13.md` / `technical_v1.12.md`. v1.13 and older files stay unedited. Mix QC gate: guests 145-175 wpm, host 145-190 wpm, intra-line pause <= 1.5 s.

## A. Monotone voices (drama3_generate.py v1.14)
1. **Sentence/emotion-aware chunk boundaries** (`--chunk_mode sentence`, default; `words` = v1.12). Requests still hold one speaker (turn mode). A turn stays whole up to 150 words (`--chunk_words 100` x `--turn_cap_x 1.5`); longer turns are split at the sentence end nearest the middle, preferring a cut just before a `[tag]`. Consecutive lines of one speaker merge up to 100 words, only at line ends. v1.12 cut by word budget only.
2. **Bigger text pieces inside a request:** request options `text_chunk_size=240` (audio.cpp default 128 chars, about 20 words) and `text_chunk_mode=tag_aware` (`--text_chunk_chars`, 0 = audio.cpp default). 240 chars is about 40 words or 15 s, under `max_frames` 512 (~24 s).
3. **One delivery direction per chunk:** a chunk without any `[tag]` gets one plain-language direction (Drama 3 "describe the delivery in your own words", e.g. `[relaxed, warm, unhurried]`) from the whitelist `drama3_directions.json` (by role and question/exclamation/statement; `enabled:false` switches it off). Sent to Drama 3 only; QC texts strip it (tag regex now allows commas, up to 60 chars). Script tags stay `[laughs]`/`[sighs]` only.
4. **Pitch-variation gate:** F0 std in semitones (`d3_pace.pitch_std_st`, librosa pyin 60-450 Hz at 16 kHz, frame 1024 = the qc_f0.py method behind the Elliot finding) on every generated chunk with >= 3 s voiced audio. Below **2.5 st** the chunk is regenerated with the next seed (retry 2 also with the role's "lively" direction), up to 2 times; then the take with the highest std is kept, the chunk is flagged `flat` in chunks.json, and the render log prints `FLAT chunk i`. Threshold from passing voices in the_long_game_ep1 (178 chunks): medians Carter 4.47 / Isla 3.77 / Marcus 4.52 st, 10th percentiles 3.48 / 3.18 / 3.51; 5 of 178 chunks were under 2.5. Elliot (monotone) measured about 2-2.7.
5. **Previous context:** the installed audio.cpp has `previous_takes` (continuation history, text + audio or VQ codes). It is accepted by the installed build (7 Nov probe: one Carter line with `previous_takes` = the previous line's audio rendered OK, 40 s incl. model load, no errors). It is not used by default: within one request-sequence the previous chunk's audio does not exist yet when the requests are written, so using it means one CLI process per chunk (model reload ~40-60 s each, about +1 h per episode). Needs Thomas's call.
6. Gen retries are now counted per chunk (flat retries add CLI passes without eating the crash/runaway budget).

## B. Content style v2.6 (brief_gen.py v1.14)
- `templates\content_style_v2.6.md`; default for new briefs; `humanity` low/medium/high (default medium) in the brief; v2.5/v2.3 unchanged.
- Plan gains `tangent` and `personal_angles`; every chapter brief gets the everyday beat, planned personal angles and the tangent; system prompt gets the human rules (analogies, nerd cap, interruptions/humour); turns 15-30 words (max 70), reject at average > 35 or > 10% over 70.
- Episode desk: script style "v2.6" (default) + "Humanity" select; brief field `humanity`. Desk tests updated.

## C. Carter tempo (revised same day, Thomas t62u)
- Root cause: Carter's raw Drama 3 pace swings by segment (the_long_game_ep1: 196-222 wpm; agentic_shift_ep1: 181-227), so the fixed 0.86 landed at 177.0 / 180.5 wpm in the mix (gate 175).
- First fix (per-segment tempo, plan 156, atempo 0.72-0.95) hit ~163 wpm but Thomas preferred the ORIGINAL fast Carter: the strong stretch sounded slow and "full" (smeared). **Reverted:** `drama3_tempo.json` is back to the v1.12 file (Carter fixed 0.86, restored from `drama3_tempo.json.bak_20261107_v114`). The per_segment rule stays available in `d3_pace.py` but is unused.
- **Mix gate, host only:** `qc_mix.py --wpm_hi_host` (default **190**), `post_episode.ps1 -WpmHiHost 190`. Guests stay 145-175; the lower limit (145) and the pause rule (<= 1.5 s) are unchanged. Why 190: Carter at 0.86 measured 169.1 (algorithmic_sin_ep1), 171 (facing_death_ep1), 177.0 (agentic_shift_ep1) and 180.5 (the_long_game_ep1) wpm in full episodes, plus 174.0 in a one-segment v1.12 test. 190 leaves ~10 wpm (~5%) over the worst full episode while still catching a clearly wrong tempo (e.g. 1.0 would give ~210). The 198.8 in the Carter-only test came from 10 long, dense lines (raw 224 wpm, above any segment average) and is not representative of an episode. If a full episode ever lands over 190 that is a real outlier worth looking at, not a reason to raise the limit again.
- `tools\start_brief.ps1` preflight checks Carter fixed 0.86 and the host limit.
- Kept from A/B: Carter's chunks still get the calm directions, and v2.6 still asks for relaxed full sentences; in the test the directions lowered his raw pace ~5-7% (at 0.86 that is ~180 instead of ~193 on dense lines).

## Test (7 Nov, Carter only, 10 lines / 340 words from the_long_game_ep1, not an episode)
| run | Carter tempo | raw wpm | final wpm (qc_mix method) | pitch std median / min (st) |
|---|---|---|---|---|
| B = v1.12 generator, fixed 0.86 | 0.86 | 224.3 | 198.8 | 4.21 / 3.38 |
| N1 = v1.14, directions on, plan 163 | 0.784 | 207.9 | 170.5 | 4.77 / 3.85 |
| N0 = v1.14, directions off, plan 163 | 0.744 | 219.0 | 171.1 | 4.50 / 3.24 |
| N1 re-stretched offline, plan 154 / 157 | 0.741 / 0.755 | 207.9 | 162.0 / 164.8 | - |
(Rows N1/N0/re-stretch used the per_segment rule that was reverted the same day; B is the behaviour now in use.) Directions were performed, not read aloud (whisper transcripts start with the script words); they lowered Carter's raw pace ~5% and raised pitch variation ~13%. No chunk was flat (gate not triggered).

## Files
`drama3_generate.py`, `d3_pace.py`, `drama3_tempo.json` (back to v1.12 content), `qc_mix.py`, `post_episode.ps1`, new `drama3_directions.json`, `tools\brief_gen.py`, `tools\start_brief.ps1`, new `templates\content_style_v2.6.md`, this file, `templates\README.md` changelog line, `episode_desk\podcast_brief.py`, `server.py`, `static\index.html`, `static\app.js`, `tests\test_brief.py`, `tests\test_server.py`. Code snapshot `templates\code_v1.14\` with SHA256SUMS. Backups: `<file>.bak_20261107_v114` next to each changed file; before the Carter revert also `<file>.bak_20261107_carterrevert`.
