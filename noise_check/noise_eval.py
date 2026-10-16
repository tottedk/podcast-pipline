import sys, os, json, glob, copy, collections, numpy as np
sys.argv = ["qc_vv.py", "x", "y"]
import faster_whisper
class _S:
    def __init__(self,*a,**k): pass
faster_whisper.WhisperModel=_S
src = open(r"C:\grok\podcast\qc_vv.py", encoding="utf-8-sig").read(); src = src[:src.index("if a.rescore:")]
G = {"__file__": r"C:\grok\podcast\qc_vv.py", "__name__": "qcvv"}; exec(compile(src, "qcvv", "exec"), G)
a = G["a"]; load = G["load"]; metrics = G["metrics"]; finalize = G["finalize"]
CAST = {"mm": ("Carter","Declan","Isla"), "ui1": ("Carter","Frank","Maya"), "dm_v2": ("Carter","Frank","Clara")}
out = {}
for ep, (h_, g1, g2) in CAST.items():
    a.host, a.guest, a.guest2 = h_, g1, g2
    for f in sorted(glob.glob(f"{ep}/seg??.qc.json")):
        seg = os.path.basename(f)[:5]; old = json.load(open(f))
        new = copy.deepcopy(old)
        for cm in new["chunks"]:
            c = json.load(open(rf"C:\grok\podcast\noise_check\words\{ep}_{seg}_c{cm['i']:03d}.json")); x = load(c["wav"]); ww = [tuple(w) for w in c["words"]]; G["LOWP"] = c["lowp"]
            m, _ = metrics(x, ww, ""); assert m["noise_events"] == cm["noise_events"]
            for k in ("noise_events_voiced", "noise_events_real", "event_voiced_t"): cm[k] = m[k]
        # OLD behaviour reproduced with current code: soft=f0_drift, no real counts
        o2 = copy.deepcopy(old); a.soft = "f0_drift"; finalize(o2)
        for co, cs in zip(o2["chunks"], old["chunks"]): assert co["flags"] == cs["flags"], (ep, seg, co["flags"], cs["flags"])
        a.soft = "f0_drift,noise"; finalize(new)
        for co, cn in zip(old["chunks"], new["chunks"]):
            out[f"{ep}_{seg}_c{cn['i']:03d}"] = dict(ep=ep, dur=cn["dur"], old_flags=co["flags"], old_hard=[k for k in co["flags"] if k != "f0_drift"], new_flags=cn["flags"], new_hard=[k for k in cn["flags"] if k not in ("f0_drift","noise")], ne=cn["noise_events"], nv=cn["noise_events_voiced"], nr=cn["noise_events_real"])
json.dump(out, open(r"C:\grok\podcast\noise_check\before_after.json", "w"), indent=1)
for ep in CAST:
    R = [v for v in out.values() if v["ep"] == ep]
    print(f"{ep}: chunks {len(R)} | OLD flagged any {sum(bool(r['old_flags']) for r in R)}, 'noise' {sum('noise' in r['old_flags'] for r in R)}, retry-triggering(hard) {sum(bool(r['old_hard']) for r in R)} | NEW 'noise'(soft) {sum('noise' in r['new_flags'] for r in R)}, retry-triggering(hard) {sum(bool(r['new_hard']) for r in R)}, events total {sum(r['ne'] for r in R)} -> real {sum(r['nr'] for r in R)} (voiced tails {sum(r['nv'] for r in R)})")
