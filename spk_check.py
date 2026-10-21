"""spk_check.py (template v1.11, 2026-10-20) - AUTOMATIC VOICE-MATCH GATE: per chunk / per line speaker check against the cast references.
  venv_spk\\Scripts\\python.exe spk_check.py --chunks <seg>.raw.wav.chunks --cast Host=Carter,Guest=Elliot,Guest2=Clara [--qc seg.qc.json] [--json out.json]
Speaker embeddings: SpeechBrain ECAPA-TDNN (spkrec-ecapa-voxceleb, CPU, <Root>\\models\\spkrec-ecapa-voxceleb). References = the Drama 3 clone refs
<Root>\\drama3_refs\\<Name>.wav (embeddings cached in drama3_refs\\_ecapa\\). Units: v1.11 turn-mode chunks = one speaker -> the whole chunk
(+ 3 s windows, hop 1.5 s, for turns >= 6 s: voice switching mid-turn); old multi-speaker chunks -> per line via the qc.json line times.
Score = cosine(own voice) - max cosine(other cast voice) ("margin"), averaged with the same margin against this segment's generated-speech
centroids when >= 2 confident units of that voice exist (Drama 3 output is less similar to its LibriVox/VCTK prompt than to itself).
FAIL (wrong voice) = unit >= 1.5 s with margin < --margin (0.0: another cast voice is closer than the own one), unit 0.8-1.5 s with margin
< -0.10, or a window with margin < -0.15. Units < 0.8 s are not judged. Calibration (Fault Lines #1 v1.10, 164 lines): wrong-voice lines
margin median -0.55 (max +0.06), right-voice lines median +0.24..+0.71 (min +0.06).
With --qc the result is merged into the qc json: per chunk "voice" {...}; failing chunks get the HARD flag "voice", score +1000 (best-take
pick never prefers a wrong voice) and are added to "redo". Prints 'SPK c<i> ...' lines, 'SPKREDO i,j' and 'SPKSUMMARY ok=<n> fail=<m> units=<u>'."""
import argparse, json, os, sys, subprocess, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("--chunks", required=True); ap.add_argument("--cast", required=True); ap.add_argument("--qc"); ap.add_argument("--json")
ap.add_argument("--root", default=os.path.dirname(os.path.abspath(__file__))); ap.add_argument("--refs", default="")
ap.add_argument("--ref_map", default=""); ap.add_argument("--margin", type=float, default=0.0); ap.add_argument("--win", type=float, default=3.0); a = ap.parse_args()
import torch
torch.set_num_threads(4)
from speechbrain.inference.speaker import EncoderClassifier
SR = 16000; refs = a.refs or os.path.join(a.root, "drama3_refs")
def load(p): return np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout, np.int16).astype(np.float32) / 32768
_md = os.path.join(a.root, "models", "spkrec-ecapa-voxceleb")
try:
    from speechbrain.utils.fetching import LocalStrategy
    _kw = {"local_strategy": LocalStrategy.COPY}  # Windows: no symlink privilege
except Exception:
    _kw = {}
_src = _md if os.path.exists(os.path.join(_md, "hyperparams.yaml")) else "speechbrain/spkrec-ecapa-voxceleb"
M = EncoderClassifier.from_hparams(source=_src, savedir=_md, run_opts={"device": "cpu"}, **_kw)
def emb(x):
    with torch.no_grad(): e = M.encode_batch(torch.from_numpy(np.ascontiguousarray(x)).unsqueeze(0)).squeeze().numpy()
    return e / (np.linalg.norm(e) + 1e-9)
cast = dict(kv.split("=") for kv in a.cast.split(",") if "=" in kv and kv.split("=")[1])
# v1.12: voice name -> versioned Drama 3 reference (drama3_ref_map.json, e.g. Elliot -> Elliot_v2): compare against the ref that was actually cloned
_rm = a.ref_map or os.path.join(a.root, "drama3_ref_map.json")
if os.path.exists(_rm): _m = json.load(open(_rm, encoding="utf-8-sig")).get("map", {}); cast = {r: _m.get(n, n) for r, n in cast.items()}
os.makedirs(os.path.join(refs, "_ecapa"), exist_ok=True); R = {}
for role, name in cast.items():
    w = os.path.join(refs, name + ".wav"); c = os.path.join(refs, "_ecapa", name + ".npy")
    if os.path.exists(c) and os.path.getmtime(c) >= os.path.getmtime(w): R[role] = np.load(c)
    else: R[role] = emb(load(w)); np.save(c, R[role])
meta = json.load(open(os.path.join(a.chunks, "chunks.json")))
Q = json.load(open(a.qc)) if a.qc and os.path.exists(a.qc) else None
QL = {cm["i"]: cm for cm in (Q or {}).get("chunks", [])}
units = []   # (chunk i, k or None, expected role, start, end, emb, windows[(t, emb)])
for c in meta["chunks"]:
    x = load(os.path.join(a.chunks, f"c{c['i']:03d}.wav")); spk = c.get("speakers") or []
    if len(set(spk)) == 1:
        segs = [(None, spk[0], 0.0, len(x) / SR)]
    else:   # old multi-speaker chunk: per line from the qc line times
        segs = [(r["k"], r["speaker"], r["t"][0], r["t"][1]) for r in QL.get(c["i"], {}).get("lines", []) if r.get("t")]
    for k, role, t0, t1 in segs:
        y = x[int(t0 * SR):int(t1 * SR)]
        if len(y) < 0.8 * SR or role not in R: units.append((c["i"], k, role, t0, t1, None, [])); continue
        wins = []
        if len(y) >= 6 * SR:
            fr = y[:len(y) // 160 * 160].reshape(-1, 160); fdb = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9); sp = np.median(fdb[fdb > -45]) if (fdb > -45).any() else -30
            for s in np.arange(0, len(y) / SR - a.win + 0.01, a.win / 2):
                act = fdb[int(s * 100):int((s + a.win) * 100)] > sp - 30
                if act.mean() >= 0.6: wins.append((round(float(t0 + s), 2), emb(y[int(s * SR):int((s + a.win) * SR)])))   # skip mostly-silent windows
        units.append((c["i"], k, role, t0, t1, emb(y), wins))
roles = list(R)
def margin(e, role, ref):
    s = {r: float(e @ ref[r]) for r in ref}; o = s[role]; oth = max(v for r, v in s.items() if r != role) if len(s) > 1 else -1
    return o - oth, s
# generated-speech centroids from confident units (ref margin >= 0.25)
C = {}
for role in roles:
    es = [u[5] for u in units if u[5] is not None and u[2] == role and margin(u[5], role, R)[0] >= 0.25]
    if len(es) >= 2: v = np.mean(es, 0); C[role] = v / np.linalg.norm(v)
def score(e, role):
    m1, s1 = margin(e, role, R)
    if len(C) == len(roles) and role in C:
        m2, _ = margin(e, role, C); return (m1 + m2) / 2, s1
    return m1, s1
res = {"cast": cast, "centroids": sorted(C), "chunks": {}}; fails = {}; nok = nf = 0
for i, k, role, t0, t1, e, wins in units:
    d = t1 - t0; ent = {"k": k, "role": role, "voice": cast.get(role), "t": [round(t0, 2), round(t1, 2)], "dur": round(d, 2)}
    if e is None: ent["verdict"] = "short"; res["chunks"].setdefault(i, []).append(ent); continue
    m, s = score(e, role); ent["margin"] = round(m, 3); ent["sims"] = {cast[r]: round(v, 3) for r, v in s.items()}
    ent["sounds_like"] = cast[max(s, key=s.get)]
    bad = (d >= 1.5 and m < a.margin) or (d < 1.5 and m < -0.10)
    wbad = []
    for t, we in wins:
        wm, ws = score(we, role)
        if wm < -0.15: wbad.append([t, round(wm, 3), cast[max(ws, key=ws.get)]])
    if wbad: ent["windows_bad"] = wbad; bad = True
    ent["verdict"] = "FAIL" if bad else "ok"
    if bad: fails.setdefault(i, []).append(ent); nf += 1
    else: nok += 1
    res["chunks"].setdefault(i, []).append(ent)
for i in sorted(res["chunks"]):
    for ent in res["chunks"][i]:
        print(f"SPK c{i:03d}{'' if ent['k'] is None else ' line ' + str(ent['k'])} {ent['role']}={ent['voice']} {ent['dur']}s -> {ent.get('sounds_like', '-')} margin {ent.get('margin', '-')} {ent['verdict']}" + (f" windows {ent['windows_bad']}" if ent.get("windows_bad") else ""))
res["redo"] = sorted(fails); res["ok"] = nok; res["fail"] = nf
if Q is not None:
    for cm in Q.get("chunks", []):
        v = res["chunks"].get(cm["i"], []); cm["voice"] = v
        cm["flags"] = [f for f in cm.get("flags", []) if f != "voice"]
        if cm["i"] in fails:
            cm["flags"].append("voice"); cm["score"] = round(cm.get("score", 0) % 1000 + 1000, 2)
        elif cm.get("score", 0) >= 1000: cm["score"] = round(cm["score"] - 1000, 2)
    Q["redo"] = sorted(set(Q.get("redo", [])) | set(fails)); Q["voice_redo"] = sorted(fails); Q["voice_summary"] = {"ok": nok, "fail": nf}
    json.dump(Q, open(a.qc, "w"), indent=1)
if a.json: json.dump(res, open(a.json, "w"), indent=1)
print("SPKREDO " + ",".join(map(str, sorted(fails))))
print(f"SPKSUMMARY ok={nok} fail={nf} units={len(units)} centroids={','.join(sorted(C)) or '-'}")
