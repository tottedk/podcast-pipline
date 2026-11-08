# Technical template
**Version 1.13 - 2026-11-01** = v1.12 + topic-first episode briefs and content style v2.5 in `tools\brief_gen.py`. Rendering, TTS, post and gates are unchanged; everything not listed here is as in `technical_v1.12.md`. v1.12 and older files stay unedited. Keeps the QC fix (qc3: `strip_label`, `fc_fix_ok`, echo-drop, `tools\episode_qc.py`, `tools\qc_eval.py`) byte-for-byte in the functions qc_eval imports.

## v1.13 changes
1. **Brief schema v2 (topic first), v1 still accepted.**
   - v2: `"schema_version": 2, "source": {"type": "topic", "topic": "<up to 600 chars>", "files": [0-2 optional books/PDFs], "research": "web"|"none"}`, optional `"content_style": "v2.5"|"v2.3"`.
   - v1 `theme` = topic with web research; v1 `files` = as before (no research).
   - Checks: topic non-empty and <= 600 chars, <= 2 files that exist, `research: none` needs a file. Elliot is rejected ("out"), as are Hugh and the banned names.
2. **No whole-shelf fallback.** Books are only the attached files plus shelf books whose author surname or title words the topic names (filename metadata only). If research is off and no book is readable: ABORT.
3. **Web research step** (`tools\research.py`, stdlib only, no API key):
   - gemma writes 7 queries (explainer, case for, case against, real cases x2, data, named experts) + 3 Wikipedia titles.
   - Search: DuckDuckGo **lite** (POST, 4 s between queries, one 12 s retry on rate limit), then DuckDuckGo html; Wikipedia API as backstop.
   - Fetch: robots.txt respected, HTML/text only, 3 MB cap, 20 s timeout, max 2 pages per site, max 14 pages, min 300 words; Wikipedia via the extracts API. Text split into 400-word "web sections".
   - Output `gen\research\sources.json` (queries, every URL with status, pages used). Web pages join books in the existing focus -> page pick -> notes -> verbatim quote verification.
4. **Relevance gate:** gemma scores every fact 0-2 against the topic (batches of 45); only 2s are kept; quotes only from sources that gave relevant facts. **< 15 relevant facts -> exit 4** `ABORT research too thin: only N facts directly relevant to the topic (need 15) - rephrase the topic or attach a book / PDF` (rejected notes kept in `gen\notes_rejected.json`).
5. **Content style v2.5 path** (default; `content_style` field or `--content_style`; `v2.3` runs the old prompts):
   - `templates\cast_bible_v1.json` injected verbatim; pairing note from the bible.
   - Plan: question, crux, position + stake per guest, one concession per guest (point, reason, chapter), running gag (keyword, setup, escalation, payoff), Carter's story, cold-open scene, chapters with shape + case.
   - Script: speaker enum = real names; parts = cold open (<= 230 words), chapters by shape, quiz game (3/4 questions), split "Takeaways".
   - `gen_part` gets the used-material ledger + last 6 lines; attempts with average turn > 50 words or > 20% of turns over 90 are rejected (best kept).
   - `clean_v25` after every `clean()`: self-address vocatives, near-duplicates (>= 0.85), banned phrases, quote cap 1 / statistic cap 2, URLs + file names, max one `[laughs]`/`[sighs]` per turn; logs gag overuse and turns > 90 words.
   - Names mapped back to Host/Guest/Guest2 before `script_final.json`; outputs unchanged in format. `result.json` gains `content_style` and `topic`; sources/read-for-yourself list web URLs.
   - Length-gate extension skips the cold open, quiz and takeaways.
6. **`--stop_after research|notes|plan|coldopen`** for cheap partial runs (coldopen = exactly one script call, writes `gen\coldopen.json` with turn stats). Models are unloaded on exit as before.
7. **Not done (future):** turn-split rewrite call for turns > 90 words; per-chapter self-review pass; new delivery tags (episode_qc allows only [laughs]/[sighs]); desk UI (see DESK_CHANGES.md).
8. Code snapshot `code_v1.13\`: brief_gen.py, research.py, episode_qc.py, qc_eval.py, start_brief.ps1 + `SHA256SUMS.txt`. New templates: content_style_v2.5.md, cast_bible_v1.json. Backups: `tools\brief_gen_backup_pre_v113.py`, `templates\README_backup_pre_v25.md`.
