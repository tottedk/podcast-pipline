"""qc_takes.py - best-take bookkeeping for podcast.ps1 (v2, 2026-10-14)
  record <chunks_dir> <qc.json> <pass>  : copy every chunk wav to takes/cNNN_p<pass>.wav and store its QC score/flags in takes.json
  pick   <chunks_dir> <raw.wav> [--pause 0.35] : per chunk restore the lowest-score take, reassemble raw.wav; prints CHANGED i,i (chunks whose best take is not the last one)
"""
import sys, os, json, shutil, numpy as np, soundfile as sf
cmd, cd = sys.argv[1], sys.argv[2]; td = os.path.join(cd, "takes"); os.makedirs(td, exist_ok=True)
tj = os.path.join(td, "takes.json"); T = json.load(open(tj)) if os.path.exists(tj) else {}
meta = json.load(open(os.path.join(cd, "chunks.json")))
if cmd == "record":
    q = json.load(open(sys.argv[3])); p = int(sys.argv[4])
    for c in q.get("chunks", []):
        i = c["i"]; key = f"c{i:03d}"; seed = c["seed"]
        prev = T.get(key, [])
        if prev and prev[-1]["seed"] == seed: prev[-1].update(score=c["score"], flags=c["flags"]); continue   # unchanged chunk re-QCed
        dst = os.path.join(td, f"{key}_p{p}.wav"); shutil.copy(os.path.join(cd, f"{key}.wav"), dst)
        m = next(x for x in meta["chunks"] if x["i"] == i)
        prev.append({"pass": p, "seed": seed, "score": c["score"], "flags": c["flags"], "wav": dst, "meta": m}); T[key] = prev
    json.dump(T, open(tj, "w"), indent=1); print("recorded", len(q.get("chunks", [])))
elif cmd == "pick":
    raw = sys.argv[3]; pause = float(sys.argv[5]) if len(sys.argv) > 5 else 0.35; changed = []
    for key, takes in sorted(T.items()):
        best = min(takes, key=lambda t: t["score"])
        if best is not takes[-1]:
            shutil.copy(best["wav"], os.path.join(cd, f"{key}.wav")); changed.append(int(key[1:]))
            meta["chunks"] = [x for x in meta["chunks"] if x["i"] != best["meta"]["i"]] + [best["meta"]]
        print(f"{key}: takes " + ", ".join(f"p{t['pass']}/s{t['seed']}={t['score']}" for t in takes) + f" -> best p{best['pass']}")
    meta["chunks"].sort(key=lambda c: c["i"]); json.dump(meta, open(os.path.join(cd, "chunks.json"), "w"), indent=1)
    sr = 24000; gap = np.zeros(int(sr*pause), np.float32); out = []
    for c in meta["chunks"]: out += [sf.read(os.path.join(cd, f"c{c['i']:03d}.wav"), dtype="float32")[0], gap]
    sf.write(raw, np.concatenate(out), sr); print("CHANGED " + ",".join(map(str, changed)))
