r"""split_segments.py (tools, 2026-10-15) - split a full script json into <outdir>\segNN.json at the chapter starts of <Ep>.chapters.in.json
(same logic as dm\\split.py). Never changes any text. Idempotent: identical existing seg files are kept; DIFFERENT existing seg files abort (use --force).
Usage: split_segments.py script.json chapters.in.json outdir [--dry] [--force] [--expect_lines 207 --expect_words 6191]
       split_segments.py --rescale_bg backgrounds.json --from_lines 165 --to_lines 207 [--dry]   (scales the 'line' indices of a backgrounds.json; keeps a .bak_pre_rescale copy)"""
import argparse, json, os, shutil, sys
ap = argparse.ArgumentParser()
ap.add_argument("script", nargs="?"); ap.add_argument("chapters", nargs="?"); ap.add_argument("outdir", nargs="?")
ap.add_argument("--dry", action="store_true"); ap.add_argument("--force", action="store_true")
ap.add_argument("--expect_lines", type=int, default=0); ap.add_argument("--expect_words", type=int, default=0)
ap.add_argument("--rescale_bg"); ap.add_argument("--from_lines", type=int, default=0); ap.add_argument("--to_lines", type=int, default=0)
a = ap.parse_args()
if a.rescale_bg:
    B = json.load(open(a.rescale_bg, encoding="utf-8-sig")); new = []
    for e in B:
        l = int(round(e["line"] * a.to_lines / a.from_lines)); l = max(l, new[-1]["line"] + 1) if new else 0; new.append({**e, "line": l})
    print("rescaled lines:", [e["line"] for e in new])
    if not a.dry:
        bak = a.rescale_bg + ".bak_pre_rescale"
        if not os.path.exists(bak): shutil.copy2(a.rescale_bg, bak)
        json.dump(new, open(a.rescale_bg, "w", encoding="utf-8"), indent=1, ensure_ascii=False); print("written; backup", bak)
    sys.exit(0)
S = json.load(open(a.script, encoding="utf-8-sig")); C = json.load(open(a.chapters, encoding="utf-8-sig"))["sections"]
st = [c["start"] for c in C] + [len(S)]
assert all(x < y for x, y in zip(st, st[1:])) and st[0] == 0, f"chapter starts not increasing from 0: {st}"
words = lambda L: sum(len(x["text"].split()) for x in L)
if a.expect_lines: assert len(S) == a.expect_lines, f"expected {a.expect_lines} lines, got {len(S)}"
if a.expect_words: assert words(S) == a.expect_words, f"expected {a.expect_words} words, got {words(S)}"
tot_l = tot_w = 0
for i in range(len(C)):
    seg = S[st[i]:st[i + 1]]; tot_l += len(seg); tot_w += words(seg)
    p = os.path.join(a.outdir, "seg%02d.json" % i); txt = json.dumps(seg, indent=1, ensure_ascii=False)
    state = "new"
    if os.path.exists(p):
        old = open(p, encoding="utf-8-sig").read()
        if json.loads(old) == seg: state = "same (kept)"
        elif a.force: state = "OVERWRITE (--force)"
        else: sys.exit(f"ABORT: {p} exists and differs from the script (use --force)")
    print(f"seg{i:02d} lines {st[i]}-{st[i+1]-1} n={len(seg)} words={words(seg)} [{state}]")
    if not a.dry and state != "same (kept)":
        os.makedirs(a.outdir, exist_ok=True); open(p, "w", encoding="utf-8").write(txt)
assert tot_l == len(S) and tot_w == words(S)
print(f"OK {len(C)} segments, {tot_l} lines, {tot_w} words" + (" (dry run, nothing written)" if a.dry else ""))
