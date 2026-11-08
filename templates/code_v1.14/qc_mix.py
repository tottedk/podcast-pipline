"""qc_mix.py episode.mp3 episode.timings.json [--json out.json] [--host Carter --guest Frank] - final QC of the MIXED episode (v2, 2026-10-14)
Needs align.py timings. Checks: silences < -50 dB longer than 2 s that fall inside a script line (music/stings are outside
lines); per-line median F0 vs the speaker's episode median (> 15% for >= 2 consecutive lines of that speaker); per-line rate
(final audio, >= 8 words) outside [1.9, 3.9] w/s; lines whose words were mostly interpolated (whisper missed them).
v1.12 (2026-10-21, fl1b\\analysis\\TEMPO_PAUSES.md): --gate = BLOCKING checks (exit 2 on failure; post_episode.ps1 then STOPs, nothing published):
  SPKRATE - per-speaker pace outside [--wpm_lo 145, --wpm_hi 175] wpm (speaker words / sum of line spans first->last word; speakers with
            >= --min_spk_words 150 words only). Prints 'SPKWPM <speaker> <wpm>' for every speaker.
  PAUSE   - any silence inside a line (between its first and last word) longer than --max_pause 1.5 s (20 ms frames > 30 dB below that
            line's speech level, i.e. a relative threshold, so a noisy floor cannot hide it).
Fault Lines #1 v1.11 would have failed: Elliot 135.6 wpm, 15 intra-line pauses > 1.5 s (up to 3.8 s).
v1.14 (2026-11-07, Thomas t62u: keep the original fast Carter at fixed tempo 0.86): the HOST role has its own upper limit --wpm_hi_host (default 190;
  Carter at 0.86 measured 169-180.5 wpm in full episodes). Guests keep --wpm_lo/--wpm_hi (145-175). The pause rule is unchanged."""
import sys, os, json, subprocess, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("mp3"); ap.add_argument("timings"); ap.add_argument("--json")
ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Frank"); ap.add_argument("--guest2", default=""); ap.add_argument("--f0_tol", type=float, default=0.15)
ap.add_argument("--gate", action="store_true"); ap.add_argument("--wpm_lo", type=float, default=145); ap.add_argument("--wpm_hi", type=float, default=175)
ap.add_argument("--wpm_hi_host", type=float, default=190); ap.add_argument("--max_pause", type=float, default=1.5); ap.add_argument("--min_spk_words", type=int, default=150)
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
# v1.12 blocking gate: per-speaker wpm + intra-line pauses
import re as _re
_TAG = _re.compile(r"\[[^\]]*\]"); spw = {}; longp = []
for i, l in enumerate(T):
    ws = l.get("words") or []
    b, e = (ws[0][1], ws[-1][2]) if len(ws) >= 2 and isinstance(ws[0], list) else (l["start"], l["end"])
    if e - b < 0.3: continue
    nw = len(_TAG.sub(" ", l["text"]).split()); v = spw.setdefault(l["speaker"], [0, 0.0]); v[0] += nw; v[1] += e - b
    seg = db[int(b * SR / h):int(e * SR / h)]
    if len(seg) < 10: continue
    q = seg < np.percentile(seg, 70) - 30; k = 0
    while k < len(q):
        if not q[k]: k += 1; continue
        j = k
        while j < len(q) and q[j]: j += 1
        if (j - k) * h / SR > a.max_pause: longp.append({"line": i, "speaker": l["speaker"], "t": round(b + k * h / SR, 1), "dur": round((j - k) * h / SR, 2)})
        k = j
spk_wpm = {s: round(v[0] / v[1] * 60, 1) for s, v in spw.items() if v[1] > 0}
hi_of = lambda s: a.wpm_hi_host if s == "Host" else a.wpm_hi   # v1.14: host-only upper limit
fail = [f"SPKRATE {s} {w} wpm outside {a.wpm_lo:g}-{hi_of(s):g}" for s, w in spk_wpm.items() if spw[s][0] >= a.min_spk_words and not (a.wpm_lo <= w <= hi_of(s))]
res["gate"] = {"speaker_wpm": spk_wpm, "speaker_words": {s: v[0] for s, v in spw.items()}, "long_pauses": longp, "fail": fail + [f"PAUSE {p['t']}s {p['dur']}s line {p['line']} {p['speaker']}" for p in longp],
               "limits": {"wpm": [a.wpm_lo, a.wpm_hi], "wpm_hi_host": a.wpm_hi_host, "max_pause": a.max_pause}, "blocking": a.gate}
if a.json: json.dump(res, open(a.json, "w"), indent=1)
mm = lambda t: f"{int(t//60)}:{int(t%60):02d}"
for s in sil: print(f"SILENCE {mm(s['t'])} {s['dur']}s lines {s['lines']}")
for d in drift: print(f"F0DRIFT {mm(d['t'])} {d['speaker']} line {d['from_line']} {d['f0']} Hz vs ref {d['ref']}")
for r in rate: print(f"RATE {mm(r['t'])} line {r['line']} {r['rate']} w/s")
for r in interp: print(f"INTERP {mm(r['t'])} line {r['line']}")
print("MIXQC", "OK" if res["ok"] else "ISSUES")
for s, w in spk_wpm.items(): print(f"SPKWPM {s} {w} wpm ({spw[s][0]} words)")
for f in fail: print(f)
for p in longp: print(f"PAUSE {mm(p['t'])} {p['dur']}s line {p['line']} {p['speaker']}")
if res["gate"]["fail"]:
    print(f"MIXQC GATE FAIL ({len(fail)} speaker rate, {len(longp)} long pause(s)){'' if a.gate else ' (not blocking: no --gate)'}")
    if a.gate: sys.exit(2)
else: print("MIXQC GATE OK")
