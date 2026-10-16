import sys, os, json, glob, hashlib
sys.argv = ["qc_vv.py", "x", "y"]
src = open(r"C:\grok\podcast\qc_vv.py", encoding="utf-8-sig").read(); src = src[:src.index("if a.rescore:")]
G = {"__file__": r"C:\grok\podcast\qc_vv.py", "__name__": "qcvv"}
exec(compile(src, "qc_vv_prefix", "exec"), G)
words, load = G["words"], G["load"]
rev = len(sys.argv) > 0 and os.environ.get("REV") == "1"
h = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()
jobs = []
for ep in ("mm", "ui1", "dm_v2"):
    for d in sorted(glob.glob(rf"C:\grok\podcast\{ep}\seg??.raw.wav.chunks")):
        seg = os.path.basename(d)[:5]
        finals = {h(w) for w in glob.glob(os.path.join(d, "c???.wav"))}
        for w in sorted(glob.glob(os.path.join(d, "takes", "c???_p?.wav"))):
            if h(w) in finals: continue
            jobs.append((ep, seg, w))
print(len(jobs), "non-final takes", flush=True)
if rev: jobs = jobs[::-1]
for n, (ep, seg, w) in enumerate(jobs):
    o = os.path.join(r"C:\grok\podcast\noise_check\words_takes", f"{ep}_{seg}_{os.path.basename(w)[:-4]}.json")
    if os.path.exists(o): continue
    x = load(w); ww = words(x)
    json.dump({"words": [(a, float(b), float(c)) for a, b, c in ww], "lowp": G["LOWP"], "wav": w}, open(o, "w"))
    print(n + 1, "/", len(jobs), ep, seg, os.path.basename(w), flush=True)
print("TAKES CACHE DONE", flush=True)
