r"""fl1_sync_lines.py (tools, 2026-10-19) - keep chapter + background LINE INDICES right if the segment scripts were merged/split after the split.
Usage: fl1_sync_lines.py orig_script.json orig_chapters.in.json orig_backgrounds.json workdir out_chapters.in.json out_backgrounds.json [--dry]
Segments are cut at the chapter starts, so the TTS/align/video script = seg00..segNN concatenated. If those lines are identical in count and
speakers to the original script nothing changes (the files are copied as is). Otherwise every ORIGINAL line index is mapped to the new index:
first by replaying prep_script.py's rule (<= 2-word lines merged into the same speaker's next line) and checking that it reproduces the new
line count per segment; if not, by proportional mapping inside each segment. Chapter starts = cumulative segment lengths (exact).
Never touches the original files; writes a .bak_pre_sync of an existing output that differs."""
import json, os, shutil, sys
a = [x for x in sys.argv[1:] if not x.startswith("--")]; dry = "--dry" in sys.argv
S0 = json.load(open(a[0], encoding="utf-8-sig")); C0 = json.load(open(a[1], encoding="utf-8-sig")); B0 = json.load(open(a[2], encoding="utf-8-sig"))
W = a[3]; outC, outB = a[4], a[5]
st0 = [c["start"] for c in C0["sections"]] + [len(S0)]
segs = []
for i in range(len(C0["sections"])):
    p = os.path.join(W, "seg%02d.json" % i)
    segs.append(json.load(open(p, encoding="utf-8-sig")) if os.path.exists(p) else None)
if any(s is None for s in segs): sys.exit("ABORT: missing seg files in " + W)
def prep_map(orig, mw=2):
    """replay prep_script.py merging on a slice; returns (orig idx -> new idx list, new count)"""
    res = []; carry = {}; pend = {}; m = [None] * len(orig)
    for i, l in enumerate(orig):
        sp = l["speaker"]
        if len(l["text"].split()) <= mw and len(orig) > 1: pend.setdefault(sp, []).append(i); continue
        res.append(sp); m[i] = len(res) - 1
        for j in pend.pop(sp, []): m[j] = len(res) - 1
    for sp, js in pend.items():
        prev = [k for k, s in enumerate(res) if s == sp]
        if not prev: res.append(sp); prev = [len(res) - 1]
        for j in js: m[j] = prev[-1]
    return m, len(res)
gmap = [None] * len(S0); newst = []; changed = False; base = 0; how = []
for i, seg in enumerate(segs):
    orig = S0[st0[i]:st0[i + 1]]; n_o, n_n = len(orig), len(seg); newst.append(base)
    if n_o == n_n and [x["speaker"] for x in orig] == [x["speaker"] for x in seg]:
        for k in range(n_o): gmap[st0[i] + k] = base + k
        how.append("same")
    else:
        changed = True; m, cnt = prep_map(orig)
        if cnt == n_n: how.append("prep-merge")
        else: m = [min(n_n - 1, int(k * n_n / n_o)) for k in range(n_o)]; how.append("proportional")
        for k in range(n_o): gmap[st0[i] + k] = base + m[k]
    base += n_n
C = dict(C0); C["sections"] = [dict(c, start=newst[i]) for i, c in enumerate(C0["sections"])]
B = [dict(e, line=gmap[int(e["line"])]) for e in B0]
for k in range(1, len(B)):
    if B[k]["line"] <= B[k - 1]["line"]: B[k]["line"] = B[k - 1]["line"] + 1
print(f"SYNC lines {len(S0)} -> {base}; changed={changed}; per segment: {','.join(how)}; chapter starts {newst}; bg lines {[e['line'] for e in B]}")
if dry: sys.exit(0)
for path, obj in ((outC, C), (outB, B)):
    txt = json.dumps(obj, indent=1, ensure_ascii=False)
    if os.path.exists(path):
        if open(path, encoding="utf-8-sig").read().strip() == txt.strip(): continue
        shutil.copy2(path, path + ".bak_pre_sync")
    open(path, "w", encoding="utf-8").write(txt)
print("SYNC written", outC, outB)
