# Technical template
**Version 1.7 - 2026-10-16** = v1.6 + a calibrated QC noise detector (`qc_vv.py` v2.2) + one comment in `render7b.ps1`. Everything not listed here is as in `technical_v1.6.md` (and v1.5/v1.4/v1.3), which stay unedited.

## Why
Mike Ma ep1 (Carter / Declan / Isla, VibeVoice 7B) shipped 19 of 27 chunks flagged (14 "noise"), and 39 of 66 takes were retries that almost never cleared the flag. Analysis of every noise event (385 events in the 73 final chunks of mm, ui1 and dm_v2; per-event spectrum, level, distance to the neighbouring whisper words) showed a false-positive problem, not bad audio:
- The v2.1 detector counts every run >= 0.3 s outside the whisper word mask (word +-0.04 s) with >= 8 frames (20 ms) above speech-30 dB. Every event starts ~0.04 s after a word end.
- For the deep Declan (F0 ~95 Hz) and the high Isla (F0 ~200 Hz) most of these runs are the **voiced decay of the last word** (harmonic, > half of the energy below 400 Hz, spectral flatness < 0.2) that whisper's word-end timestamp cuts off. Share of such events: Declan 52 %, Isla 65 %, Carter 33-48 %, Maya 14 %.
- The fixed threshold `max(6, dur/15)` was calibrated on Carter / Frank / Clara (short tails, so few events). A long chunk with a low voice easily exceeds it.
- Noise bursts that are really garbage are caught by the other flags (unrecognised >= 1 s speech-level audio, wer, line_wer, bad_lines, pitch_glitch, rate, lowprob), and `post_segment.ps1` gates non-word pauses in the final mix anyway.

## v1.7 changes (`qc_vv.py` v2.2)
- **Voiced-tail classification.** An event is still found exactly as in v2.1 (`noise_events`, `event_t` unchanged). New per event: mean over the active frames of the power share below 400 Hz (dB) and of the spectral flatness (100-7500 Hz). `lf >= --noise_voiced_lf` (default -6) **and** `flat < --noise_voiced_flat` (default 0.2) = voiced tail. New fields: `noise_events_voiced`, `noise_events_real`, `event_voiced_t`.
- **`noise` flag** now uses `noise_events_real > max(6, dur/15)` (same threshold, voiced tails no longer counted); the best-take score uses `noise_events_real/2`.
- **`noise` is a SOFT flag by default** (`--soft f0_drift,noise`): reported, scored for best-take choice, never triggers a retry alone. Hard flags that cause retries: unrecognised, wer, line_wer, bad_lines, pitch_glitch, rate, lowprob (all unchanged).
- **Compatibility.** `--rescore` works on old qc.json (no `noise_events_real` -> falls back to `noise_events`). `--soft f0_drift --noise_voiced_lf 99` = exact v2.1 behaviour (verified: reproduces the stored flags and REDO lists of mm/ui1/dm_v2).
- `render7b.ps1`: comment only ("f0_drift and noise are SOFT"); no behaviour change.

## Validation (offline, existing audio, CPU only; nothing re-rendered)
Final chunks (73): chunks with any flag 28 -> 13; retry-triggering (hard) 23 -> 3.
| episode | chunks | flagged (any) old -> new | hard old -> new | "noise" old -> new |
|---|---|---|---|---|
| Mike Ma ep1 (mm) | 27 | 19 -> 8 | 15 -> 2 | 14 -> 1 |
| Uploaded Intelligence ep1 (ui1) | 23 | 4 -> 4 | 3 -> 1 | 2 -> 2 |
| das Man v2 (dm_v2) | 23 | 5 -> 1 | 5 -> 0 | 5 -> 1 |
The remaining new flags in mm are soft f0_drift (6, unchanged) + 2 real hard ones (seg04 c003 bad_lines, seg07 c001 rate).
All 142 takes (finals + retries): hard-flagged takes 84 -> 24; takes that carried noise AND another hard flag (11 positive controls) are still hard-flagged 11/11. Retries that the new rule would not have needed: takes generated 142 -> 86 (mm 66 -> 33, ui1 40 -> 27, dm_v2 36 -> 26).
Events per 100 words after excluding voiced tails: Declan 1.71, Isla 1.45 (comparable to Carter/Frank/Clara).

## Notes
- Analysis scripts and per-event data: `noise_check\` (git; the whisper word caches are git-ignored because they contain script text).
- If a future voice still false-triggers, tune `--noise_voiced_lf` / `--noise_voiced_flat` or raise the count threshold; to restore the old strictness use `--soft f0_drift --noise_voiced_lf 99`.