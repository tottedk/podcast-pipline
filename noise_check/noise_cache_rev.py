import sys, os, json, glob
sys.argv = ["qc_vv.py", "x", "y"]
src = open(r"C:\grok\podcast\qc_vv.py", encoding="utf-8-sig").read()
src = src[:src.index("if a.rescore:")]
G = {"__file__": r"C:\grok\podcast\qc_vv.py", "__name__": "qcvv"}
exec(compile(src, "qc_vv_prefix", "exec"), G)
words, load = G["words"], G["load"]
out = r"C:\grok\podcast\noise_check\words"
jobs = []
for ep in ("mm", "ui1", "dm_v2"):
    for d in sorted(glob.glob(rf"C:\grok\podcast\{ep}\seg??.raw.wav.chunks")):
        seg = os.path.basename(d)[:5]
        for w in sorted(glob.glob(os.path.join(d, "c???.wav"))):
            jobs.append((ep, seg, w))
print(len(jobs), "chunks", flush=True)
for n, (ep, seg, w) in reversed(list(enumerate(jobs))):
    o = os.path.join(out, f"{ep}_{seg}_{os.path.basename(w)[:-4]}.json")
    if os.path.exists(o): continue
    x = load(w); ww = words(x)
    json.dump({"words": [(a, float(b), float(c)) for a, b, c in ww], "lowp": G["LOWP"], "wav": w}, open(o, "w"))
    print(n + 1, "/", len(jobs), ep, seg, os.path.basename(w), len(ww), "words", flush=True)
print("CACHE DONE", flush=True)


