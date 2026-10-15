"""qc_mix.py episode.mp3 episode.timings.json [--json out.json] [--host Carter --guest Frank] - final QC of the MIXED episode (v2, 2026-10-14)
Needs align.py timings. Checks: silences < -50 dB longer than 2 s that fall inside a script line (music/stings are outside
lines); per-line median F0 vs the speaker's episode median (> 15% for >= 2 consecutive lines of that speaker); per-line rate
(final audio, >= 8 words) outside [1.9, 3.9] w/s; lines whose words were mostly interpolated (whisper missed them)."""
import sys, os, json, subprocess, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("mp3"); ap.add_argument("timings"); ap.add_argument("--json")
ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Frank"); ap.add_argument("--guest2", default=""); ap.add_argument("--f0_tol", type=float, default=0.15)
a = ap.parse_args(); SR = 16000; HERE = os.path.dirname(os.path.abspath(__file__))
load = lambda p: np.frombuffer(subprocess.check_output(["ffmpeg","-v","error","-i",p,"-ac","1","-ar",str(SR),"-f","f32le","-"]), np.float32)
def f0(x, h=320, N=640):
    o = []
    for i in range(0, len(x)-N, h):
        f = x[i:i+N]
        if np.sqrt((f**2).mean()) < 0.02: continue
        f = f-f.mean(); ac = np.correlate(f, f, "full")[N-1:]; k = SR//400+np.argmax(ac[SR//400:SR//70])
        if ac[k] > .4*ac[0]: o.append(SR/k)
    return float(np.median(o)) if len(o) > 10 else 0.0
def ref(name):
    for vd in (os.path.join(HERE, "VibeVoice-main", "demo", "voices"), os.path.join(HERE, "voices_extra"), r"C:\grok\podcast\voices_extra"):   # v1.3: + voices_extra\
        if not os.path.isdir(vd): continue
        for f in os.listdir(vd):
            if f.lower().endswith(".wav") and f.lower().split("-",1)[-1].split("_")[0] == name.lower(): return f0(load(os.path.join(vd, f)))
    return 0.0
y = load(a.mp3); T = json.load(open(a.timings, encoding="utf-8"))["lines"]; R = {"Host": ref(a.host), "Guest": ref(a.guest)}
if a.guest2: R["Guest2"] = ref(a.guest2)
h = 320; n = len(y)//h; db = 20*np.log10(np.sqrt((y[:n*h].reshape(n,h)**2).mean(1))+1e-9)
sil = []; k = 0
while k < n:
    if db[k] >= -50: k += 1; continue
    j = k
    while j < n and db[j] < -50: j += 1
    if (j-k)*h/SR > 2.0:
        s, e = k*h/SR, j*h/SR; ln = [i for i, l in enumerate(T) if l["start"] < e and l["end"] > s]
        if ln: sil.append({"t": round(s,1), "dur": round(e-s,1), "lines": ln})
    k = j
rows = []; drift = []; rate = []; interp = []; run = {s: [] for s in R}
F = [f0(y[int(l["start"]*SR):int(l["end"]*SR)]) for l in T]
for sp in R:   # reference = episode median of that speaker (the voice-prompt F0 differs from generated speech, e.g. Frank 116 vs ~127 Hz)
    v = [F[i] for i, l in enumerate(T) if l["speaker"] == sp and F[i] and len(l["text"].split()) >= 5]
    if len(v) >= 6: R[sp] = float(np.median(v))
for i, l in enumerate(T):
    s, e = l["start"], l["end"]; w = len(l["text"].split()); m = F[i]; rows.append((i, l["speaker"], round(m,1)))
    if m and R.get(l["speaker"]) and w >= 5:
        off = abs(m/R[l["speaker"]]-1) > a.f0_tol; run[l["speaker"]] = run[l["speaker"]] + [i] if off else []
        if len(run[l["speaker"]]) == 2: drift.append({"from_line": run[l["speaker"]][0], "t": round(T[run[l["speaker"]][0]]["start"],1), "speaker": l["speaker"], "f0": round(m,1), "ref": round(R[l["speaker"]],1)})
    if w >= 8 and e > s and not (1.9 <= w/(e-s) <= 3.9): rate.append({"line": i, "t": round(s,1), "rate": round(w/(e-s),2)})
    ws = l.get("words", [])
    if len(ws) >= 8:
        d = np.diff([x[1] for x in ws]) if isinstance(ws[0], list) else np.array([1.0])
        if len(d) > 6 and np.std(d) < 0.02: interp.append({"line": i, "t": round(s,1)})   # evenly spaced = interpolated (whisper missed it)
res = {"ref_f0": R, "silence_in_lines": sil, "f0_drift": drift, "rate": rate, "interpolated_lines": interp, "line_f0": rows}
res["ok"] = not (sil or drift or rate or interp)
if a.json: json.dump(res, open(a.json, "w"), indent=1)
mm = lambda t: f"{int(t//60)}:{int(t%60):02d}"
for s in sil: print(f"SILENCE {mm(s['t'])} {s['dur']}s lines {s['lines']}")
for d in drift: print(f"F0DRIFT {mm(d['t'])} {d['speaker']} line {d['from_line']} {d['f0']} Hz vs ref {d['ref']}")
for r in rate: print(f"RATE {mm(r['t'])} line {r['line']} {r['rate']} w/s")
for r in interp: print(f"INTERP {mm(r['t'])} line {r['line']}")
print("MIXQC", "OK" if res["ok"] else "ISSUES")
