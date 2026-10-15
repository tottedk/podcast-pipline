# Technical template
**Version 1.4 - 2026-10-15** = v1.3 + markdown-mark stripping before TTS. Everything not listed here is exactly as in `technical_v1.3.md` (which stays unedited).

## v1.4 change
- **Why:** the 15 Oct 2026 LLM shootout (`tests\llm_shootout\results.md`) showed Gemma 4 26B leaves markdown emphasis (`*word*` ...) in the dialogue text. The 7B/1.5B generators already dropped every `*`, but `_x_`, backticks and headings reached TTS, and subtitles/alignment still saw the raw marks.
- **What:** new `md_clean.py` (`clean_markdown` / `clean_lines` + CLI). Removes only the marks, never words: `*x*`, `**x**`, `***x***`, `_x_`, `__x__`, `~~x~~`, inline code/backticks, `[text](url)` -> text, leading `#`, `>`, `-`, `*`, `+` bullets. Left alone: speaker field, `snake_case`, `a*b`/`3*4`/`2 * 3` math, numbers like `1990` or `-5`. `**Host:** hi` -> `Host: hi`.
- **Where (all before TTS):** `write_script.py` (at write time) -> `prep_script.py` (podcast.ps1 path, `--no_md_clean` to skip) -> `run_episode.ps1` (all `segNN.json` in place, original kept as `segNN.pre_md.json` only if something changed) -> `vv7b_generate.py` / `vv_generate.py` (in memory as a last safety net). The generators still strip every remaining `*` as before.
- **Test:** `python tests\test_md_clean.py` (9 tests: italic/bold/nested, underscore emphasis, snake_case, math asterisks, stray marks, leading markdown, speaker tags, no other text changes, CLI in place). Also checked on 5 real shootout outputs: word sequence identical, no `*`/backticks left.
- **Versioning/git:** from v1.4 on, changes are committed to git (tottedk/podcast-pipline) instead of manual `_backup_*` copies; the template folder `code_v1.4` mirrors the live files.
