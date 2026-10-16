import sys, os, json, glob, hashlib, copy, collections
sys.argv = ["qc_vv.py", "x", "y"]
import faster_whisper
faster_whisper.WhisperModel = type("S", (), {"__init__": lambda s, *a, **k: None})
src = open(r"C:\grok\podcast\qc_vv.py", encoding="utf-8-sig").read(); src = src[:src.index("if a.rescore:")]
G = {"__file__": r"C:\grok\podcast\qc_vv.py", "__name__": "qcvv"}; exec(compile(src, "qcvv", "exec"), G)
load, metrics = G["load"], G["metrics"]
md5 = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()
rows = []; missing = 0
for ep in ("mm", "ui1", "dm_v2"):
    for d in sorted(glob.glob(rf"C:\grok\podcast\{ep}\seg??.raw.wav.chunks")):
        seg = os.path.basename(d)[:5]
        fin = {md5(w): os.path.basename(w)[:-4] for w in glob.glob(os.path.join(d, "c???.wav"))}
        tk = json.load(open(os.path.join(d, "takes", "takes.json")))
        for c, takes in tk.items():
            for t in takes:
                w = t["wav"].replace("\\\\", "\\")
                h = md5(w)
                cf = rf"C:\grok\podcast\noise_check\words\{ep}_{seg}_{fin[h]}.json" if h in fin else rf"C:\grok\podcast\noise_check\words_takes\{ep}_{seg}_{os.path.basename(w)[:-4]}.json"
                if not os.path.exists(cf): missing += 1; continue
                j = json.load(open(cf)); G["LOWP"] = j["lowp"]; x = load(w)
                m, _ = metrics(x, [tuple(z) for z in j["words"]], "")
                fl = t["flags"]; dur = len(x) / 16000
                rows.append(dict(ep=ep, seg=seg, c=c, p=t["pass"], old=fl, ne=m["noise_events"], nr=m["noise_events_real"], nv=m["noise_events_voiced"], dur=dur,
                                 new_noise=m["noise_events_real"] > max(6, dur / 15), final=h in fin))
print("rows", len(rows), "missing", missing)
json.dump(rows, open(r"C:\grok\podcast\noise_check\take_eval.json", "w"))
SOFTO = {"f0_drift"}; SOFTN = {"f0_drift", "noise"}
def newflags(r): return [f for f in r["old"] if f != "noise"] + (["noise"] if r["new_noise"] else [])
for ep in ("mm", "ui1", "dm_v2", "ALL"):
    R = [r for r in rows if ep == "ALL" or r["ep"] == ep]
    ob = [r for r in R if set(r["old"]) - SOFTO]; nb = [r for r in R if set(newflags(r)) - SOFTN]
    noise_old = [r for r in R if "noise" in r["old"]]; only = [r for r in noise_old if not set(r["old"]) - {"noise", "f0_drift"}]; both = [r for r in noise_old if set(r["old"]) - {"noise", "f0_drift"}]
    print(f"{ep}: takes {len(R)} | old noise-flagged {len(noise_old)} (noise-only {len(only)}, noise+other hard {len(both)}) | would-retry old {len(ob)} -> new {len(nb)} | noise still flagged (soft) {sum(r['new_noise'] for r in R)} | events {sum(r['ne'] for r in R)} -> real {sum(r['nr'] for r in R)}")
    print("    positive controls (noise + other hard): still hard-flagged after change:", sum(bool(set(newflags(r)) - SOFTN) for r in both), "/", len(both))
# retries simulation per chunk
oldt = newt = 0
by = collections.defaultdict(list)
for r in rows: by[(r["ep"], r["seg"], r["c"])].append(r)
for k, v in by.items():
    v.sort(key=lambda r: r["p"]); oldt += len(v)
    n = 0
    for r in v:
        n += 1
        if not (set(newflags(r)) - SOFTN): break
    newt += n
print("takes generated (actual) ->", oldt, "simulated with v1.7 rule (stop at first take without hard flag):", newt)
