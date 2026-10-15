import os, shutil, hashlib, re
R = r"C:\grok\podcast"; T = os.path.join(R, "templates")
rd = lambda p: open(p, encoding="utf-8-sig").read()
def wr(p, s): open(p, "w", encoding="utf-8", newline="\n").write(s)
# --- root README (backup README_backup_pre_3spk.md already made)
readme = os.path.join(R, "README.md"); s = rd(readme)
if "## 3 speakers + subtitles (v1.2" not in s:
    s = s.replace("Output: episode.mp4 (1920x1080, 2 fps, H.264 + AAC 160k, burned subtitles + soft mov_text track,",
                  "Output: episode.mp4 (1920x1080, 2 fps, H.264 + AAC 160k, NO subtitles in the video since v1.2 (--burn-subs = old burned + soft mov_text track),")
    s = s.rstrip("\n") + """

## 3 speakers + subtitles (v1.2, 2026-10-14)
- Script speakers: `Host`, `Guest`, `Guest2`. VibeVoice gets Host = Speaker 1, Guest = 2, Guest2 = 3 (renumbered per chunk if a speaker is absent). Model settings unchanged.
- `podcast.ps1 ... -GuestVoice Alice -Guest2Voice Samuel` (passes `--guest2` to vv_generate.py and qc_vv.py); `qc_mix.py ... --guest2 Samuel`.
- make_video.py: `--guest2 <name>` -> crimson plate/level meter (host amber, guest blue). Subtitles are **no longer burned in by default**: only `<out>.srt` is written next to the mp4 (no subtitle stream in the mp4). `--burn-subs` restores the old behaviour (burned + soft mov_text).
- Fix: podcast.ps1 runs qc_takes.py with venv_vv python (venv_whisper has no soundfile -> in v1.1 take recording + best-take pick failed silently and the LAST take shipped).
- 3-speaker test + speaker-ID check: `tests\\three_speaker\\` (spk_check.py = per-line F0 + log-mel voice-ID vs prompts/centroids). Results: templates\\technical_v1.2.md.
- Backups: *_backup_pre_3spk.* (vv_generate, qc_vv, qc_mix, podcast, make_video, README, align, prep_script, qc_takes).
"""
    wr(readme, s); print("README updated")
# --- templates README
tr = os.path.join(T, "README.md"); s = rd(tr)
if "v1.2" not in s:
    s = s.replace("ep1.- v1.1", "ep1.\n- v1.1").rstrip("\n") + "\n- v1.2 (2026-10-14) = v1.1 + 3-speaker support (Guest2), make_video crimson 2nd guest + .srt-only default, qc_takes venv fix (technical only).\n"
    wr(tr, s); print("templates README updated")
# --- code snapshot
src, dst = os.path.join(T, "code_v1.1"), os.path.join(T, "code_v1.2")
if os.path.exists(dst): shutil.rmtree(dst)
shutil.copytree(src, dst)
for f in ["podcast.ps1", "vv_generate.py", "qc_vv.py", "qc_mix.py", "make_video.py", "README.md", "align.py", "prep_script.py", "qc_takes.py", "glossary.json", "voice_f0.json"]:
    shutil.copy2(os.path.join(R, f), os.path.join(dst, f))
os.makedirs(os.path.join(dst, "tests"), exist_ok=True)
shutil.copy2(os.path.join(R, "tests", "three_speaker", "spk_check.py"), os.path.join(dst, "tests", "spk_check.py"))
os.remove(os.path.join(dst, "SHA256SUMS.txt"))
rows = []
for root, _, fs in os.walk(dst):
    for f in sorted(fs):
        p = os.path.join(root, f); rel = os.path.relpath(p, dst); b = open(p, "rb").read()
        rows.append((rel, len(b), hashlib.sha256(b).hexdigest().upper()))
rows.sort(key=lambda r: (os.sep in r[0], r[0].lower()))
wr(os.path.join(dst, "SHA256SUMS.txt"), "".join(f"{h}  {n}  {r}\n" for r, n, h in rows))
changed = {"podcast.ps1", "vv_generate.py", "qc_vv.py", "qc_mix.py", "make_video.py", "README.md", os.path.join("tests", "spk_check.py")}
# --- technical v1.2
s = rd(os.path.join(T, "technical_v1.1.md"))
s = s.replace(s.splitlines()[1], "**Version 1.2 - 2026-10-14** (v1.1 + 3-speaker support, make_video 2nd-guest colour + .srt-only subtitles, qc_takes venv fix; 3-speaker GPU test done, not yet used for an episode). Never edit; copy to v1.3+. Code snapshot: `code_v1.2\\` (+ `SHA256SUMS.txt`).")
s = s.replace("| microsoft/VibeVoice-1.5B | TTS, 2 speakers |", "| microsoft/VibeVoice-1.5B | TTS, 2-3 speakers (Host/Guest/Guest2; tested 3 in one chunk) |")
s = s.replace("-HostVoice -GuestVoice -Tempo", "-HostVoice -GuestVoice -Guest2Voice -Tempo")
s = s.replace("`--chunk_words 175 --glossary", "`--guest2 --chunk_words 175 --glossary")
s = s.replace("`--timings --chapters --backgrounds --layout speaker|quote --fps --frame-times --frames-dir --frame-suffix --host --guest --keep-tmp`",
              "`--timings --chapters --backgrounds --layout speaker|quote --fps --frame-times --frames-dir --frame-suffix --host --guest --guest2 --burn-subs --keep-tmp`; default since v1.2: no subtitles in the mp4, separate .srt only")
s = s.replace("-> mp4 (burned subs + mov_text), .srt,", "-> mp4 (v1.2: no subs in video; add `--burn-subs` for the old burned + mov_text), .srt,")
s = s.replace("## Code inventory (snapshot code_v1.0)", "## Code inventory (snapshot code_v1.2)")
s = s.replace("| check_sync.py |", "| tests\\three_speaker\\spk_check.py | 3-speaker test: per-line F0 + log-mel voice-ID vs voice prompts and leave-one-out speaker centroids (`audio timings.json --host --guest --guest2 --json`) |\n| check_sync.py |")
i = s.index("| Snapshot file (code_v1.1)"); j = s.index("\n\n", i)
tab = "| Snapshot file (code_v1.2) | Bytes | SHA256 (16) |\n|---|---|---|\n" + "\n".join(f"| `{r}`{' (changed)' if r in changed else ''} | {n} | `{h[:16]}` |" for r, n, h in rows)
s = s[:i] + tab + s[j:]
s = s.replace("## Timings per stage (DE ep1)", open(os.path.join(R, "tests", "three_speaker", "v12_results.md"), encoding="utf-8").read().rstrip() + "\n\n## Timings per stage (DE ep1)")
s = s.rstrip("\n") + "\n" + open(os.path.join(R, "tests", "three_speaker", "v12_changelog.md"), encoding="utf-8").read()
wr(os.path.join(T, "technical_v1.2.md"), s); print("technical_v1.2.md written,", len(rows), "snapshot files")
