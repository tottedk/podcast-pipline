# Changelog

Entries describe changes checked on the PC or in this tree. They are not a GitHub release. Merge the sync pull request and this documentation pull request before treating v1.14 as published.

## Unreleased — 2026-11-07

- Technical v1.14: sentence- and emotion-aware Drama 3 chunk boundaries, 240-character internal chunks, whitelisted delivery directions (`drama3_directions.json`), flat-pitch detection, and up to two retries.
- Carter stays on fixed tempo 0.86 in `drama3_tempo.json`. The per-segment rule (plan 156, bounds 0.72–0.95) remains available in `d3_pace.py` and is unused by the tempo file. Mix QC is 145–175 wpm for guests and 145–190 for the host, and no intra-line pause over 1.5 seconds. A short test of the unused per-segment plan measured about 162–165 wpm. A full episode on v1.14 has not been rendered.
- Content v2.6: humanity low/medium/high (medium default), everyday beats, fictional personal angles, one returning tangent, a jargon cap, and shorter turns. `templates/content_style_v2.6.md` and `templates/technical_v1.14.md` were added. Older template versions were not edited.
- `tools/brief_gen.py` and `tools/start_brief.ps1` were added from the PC. They still need `tools/research.py`, `tools/episode_qc.py`, and `templates/cast_bible_v1.json`, which were not in the drop. See `KNOWN_ISSUES.md`.
- The Episode desk v2.6 default and Humanity field were updated on the PC (76 local tests passed there, one admin-dependent skip). That project is a separate repository and is not part of this changelog's tree.
- `tests/test_v112.py` now expects Carter's mapped tempo of 0.86, which is what `drama3_tempo.json` has contained since the v1.12 addendum, and it covers the per-segment rule.

## 2026-11-03

- Lachlan was dropped from production casting after a quality review. Elliot was also left out for flat delivery. Those exclusions are operational notes. `pick_cast.py` still lists both names in the random pool. Voice assets are not part of this source tree.

## 2026-11-01

- Pre- and post-episode QC, duplicate and label guards, part-join echo removal, and a guarded fact-check replacement were added on the PC. The reported regression set was 32 cases with zero misses and zero false alarms in that finite set (`tools/qc_eval.py`). That file was not in the drop, so the set was not re-run here.
- Technical v1.13 / content v2.5 on the PC: topic-first briefs, web research, and optional books. The v1.13 template files are not in this repository yet.
- Desk, on the PC only: topic-first setup, optional book uploads, disabled unready guests, Angle and Skip controls, and the quiz control removed. Local tests there reached 75 passing with one skip.

## 2026-10-25

- Fixed incompatible Windows detached-process spawn flags in the desk.
- Fixed a false startup failure when the short-lived launcher exits successfully. The brief-to-launch path and a 52-test suite (one skip) were checked on the PC. The desk tests are not in this repository.
