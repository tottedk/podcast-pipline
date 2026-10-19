"""spk_check.py audio timings.json [--host Carter --guest Alice --guest2 Samuel] - 3-speaker test: per-line F0 + voice-ID.
Per line: median F0 (autocorr, as qc_mix.py) and a mean log-mel + delta-free spectral embedding; nearest voice by cosine
similarity to (a) the VibeVoice voice prompts and (b) leave-one-out centroids of the other lines labelled with that speaker."""
import sys, os, json, subprocess, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("audio"); ap.add_argument("timings"); ap.add_argument("--json")
ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Alice"); ap.add_argument("--guest2", default="Samuel")
a = ap.parse_args(); SR = 16000; HERE = r"C:\grok\podcast"
load = lambda p: np.frombuffer(subprocess.check_output(["ffmpeg","-v","error","-i",p,"-ac","1","-ar",str(SR),"-f","f32le","-"]), np.float32)
def f0(x, h=320, N=640):
    o = []
    for i in range(0, len(x)-N, h):
        f = x[i:i+N]
        if np.sqrt((f**2).mean()) < 0.02: continue
        f = f-f.mean(); ac = np.correlate(f, f, "full")[N-1:]; k = SR//400+np.argmax(ac[SR//400:SR//70])
        if ac[k] > .4*ac[0]: o.append(SR/k)
    return float(np.median(o)) if len(o) > 10 else 0.0
NF = 512; mel_lo, mel_hi = 80, 7600
def melfb(n=40):
    m = lambda f: 2595*np.log10(1+f/700); im = lambda m_: 700*(10**(m_/2595)-1)
    pts = im(np.linspace(m(mel_lo), m(mel_hi), n+2)); bins = np.floor((NF+1)*pts/SR).astype(int); fb = np.zeros((n, NF//2+1))
    for j in range(n):
        l, c, r = bins[j], bins[j+1], bins[j+2]
        fb[j, l:c] = (np.arange(l, c)-l)/max(1, c-l); fb[j, c:r] = (r-np.arange(c, r))/max(1, r-c)
    return fb
FB = melfb()
def emb(x):
    fr = np.lib.stride_tricks.sliding_window_view(x, NF)[::160] * np.hanning(NF)
    e = np.sqrt((fr**2).mean(1)); fr = fr[e > 0.02]      # voiced/loud frames only
    if len(fr) < 20: return None
    S = np.log(FB @ (np.abs(np.fft.rfft(fr, axis=1))**2).T + 1e-8)   # 40 x T
    c = np.fft.irfft(S, axis=0)[1:20] if False else S            # log-mel
    v = np.concatenate([S.mean(1), S.std(1)]); return v
def cos(u, v): u = u-u.mean(); v = v-v.mean(); return float(u@v/np.linalg.norm(u)/np.linalg.norm(v))
names = {"Host": a.host, "Guest": a.guest, "Guest2": a.guest2}
vd = os.path.join(HERE, "VibeVoice-main", "demo", "voices"); P = {}
for s, n in names.items():
    f = next(f for f in os.listdir(vd) if f.lower().split("-",1)[-1].split("_")[0] == n.lower()); x = load(os.path.join(vd, f))
    P[s] = {"emb": emb(x), "f0": round(f0(x), 1)}
y = load(a.audio); T = json.load(open(a.timings, encoding="utf-8"))["lines"]
rows = []
for i, l in enumerate(T):
    x = y[int(l["start"]*SR):int(l["end"]*SR)]
    rows.append({"k": i, "speaker": l["speaker"], "t": round(l["start"], 2), "dur": round(l["end"]-l["start"], 2), "f0": round(f0(x), 1), "emb": emb(x)})
med = {s: float(np.median([r["f0"] for r in rows if r["speaker"] == s and r["f0"]])) for s in names}
out = []
for r in rows:
    pr = {s: round(cos(r["emb"], P[s]["emb"]), 3) for s in names}
    loo = {}
    for s in names:
        o = [q["emb"] for q in rows if q["speaker"] == s and q["k"] != r["k"] and q["emb"] is not None]
        loo[s] = round(cos(r["emb"], np.mean(o, 0)), 3) if o else None
    f0n = min(names, key=lambda s: abs(np.log(r["f0"]/med[s])) if r["f0"] else 0)
    best_loo = max(loo, key=lambda s: loo[s] or -9); best_pr = max(pr, key=pr.get)
    out.append({k: v for k, v in r.items() if k != "emb"} | {"f0_vs_spkmed_pct": round(100*(r["f0"]/med[r["speaker"]]-1), 1),
                "nearest_f0": f0n, "sim_prompt": pr, "nearest_prompt": best_pr, "sim_centroid": loo, "nearest_centroid": best_loo,
                "suspect": best_loo != r["speaker"]})
res = {"voices": names, "prompt_f0": {s: P[s]["f0"] for s in names}, "speaker_median_f0": {s: round(v, 1) for s, v in med.items()}, "lines": out}
if a.json: json.dump(res, open(a.json, "w"), indent=1)
print("prompt F0", res["prompt_f0"], "speaker median F0", res["speaker_median_f0"])
for o in out:
    print(f"{o['k']:2d} {o['t']:6.1f}s {o['speaker']:6s} F0 {o['f0']:6.1f} ({o['f0_vs_spkmed_pct']:+5.1f}%)  centroid-sim "
          + " ".join(f"{s}={v}" for s, v in o["sim_centroid"].items()) + f"  -> {o['nearest_centroid']}  prompt-> {o['nearest_prompt']}" + ("  SUSPECT" if o["suspect"] else ""))
