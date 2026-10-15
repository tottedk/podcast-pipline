"""qc_vv.py v2 (2026-10-14) - QC + metrics + safe pause gate for VibeVoice output.
  python qc_vv.py audio script.json [--chunks DIR] [--gate OUT.wav] [--json OUT.json] [--model large-v3-turbo]
                  [--glossary glossary.json] [--host Carter --guest Frank] [--f0_tol 0.15]
Per chunk (flags -> REDO list, plus a numeric 'score' used for best-take selection, lower = better):
  v1 checks: line coverage < 75%, chunk WER > 8%, octave jump on a low-prob word, > 2 low-prob words, noise events > max(6, dur/15)
  v2 checks (DE ep1 diagnosis):
   - line_wer: per-line WER (lines >= 4 words) > 0.25
   - glossary: a hard term of the line not recognised (original or respelling, fuzzy >= 0.7)
   - f0_drift: per-line median F0 vs the voice's calibrated F0 (voice_f0.json, else file median); >= 2 lines (or the chunk median) off by > f0_tol
   - rate: per-line words/s (raw audio, lines >= 12 words) outside [2.1, 5.0] (slow voice after hallucination, DE 17:40)
   - unrecognised: >= 1.0 s of speech-level audio with no whisper words (dropped speech, babble, music); 'tonal' marks music-like runs
--gate: pauses outside whisper words are faded to -60 dB EXCEPT long (> 0.8 s) gaps that still carry speech-level
energy (whisper dropped real speech, DE 30:27) - those are left untouched and reported in gate_kept.
"""
import sys, json, re, subprocess, difflib, argparse, os, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("audio"); ap.add_argument("script")
ap.add_argument("--chunks"); ap.add_argument("--gate"); ap.add_argument("--json"); ap.add_argument("--model", default="large-v3-turbo")
ap.add_argument("--glossary", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "glossary.json"))
ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Frank"); ap.add_argument("--guest2", default=""); ap.add_argument("--f0_tol", type=float, default=0.15)
ap.add_argument("--rescore", help="re-apply flags/thresholds to an existing qc json (no audio/whisper)"); ap.add_argument("--unrec_s", type=float, default=1.0)
ap.add_argument("--rate_lo", type=float, default=2.1); ap.add_argument("--rate_hi", type=float, default=5.0)
a = ap.parse_args()
from faster_whisper import WhisperModel
SR = 16000
HERE = os.path.dirname(os.path.abspath(__file__))
norm = lambda t: re.sub(r"[^a-z0-9' ]", " ", t.lower().replace("\u2019", "'")).split()
def load(p, sr=SR):
    pcm = subprocess.run(["ffmpeg","-v","error","-i",p,"-f","s16le","-ac","1","-ar",str(sr),"-"],capture_output=True,check=True).stdout
    return np.frombuffer(pcm, np.int16).astype(np.float32)/32768
GL = {}
if a.glossary and os.path.exists(a.glossary): GL = json.load(open(a.glossary, encoding="utf-8-sig")).get("terms", {})
m = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=6)
def words(x):
    segs,_ = m.transcribe(x, language="en", word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    segs = list(segs); global LOWP
    LOWP = [(w.word.strip(), round(w.start,2), round(w.probability,2)) for s in segs for w in s.words if w.probability < 0.2 and len(w.word.strip()) > 2]
    return [(w.word, w.start, w.end) for s in segs for w in s.words]
def f0_track(x, h=320, N=640):
    out = []
    for i in range(0, len(x)-N, h):
        f = x[i:i+N]
        if np.sqrt((f**2).mean()) < 0.02: out.append(0); continue
        f = f - f.mean(); ac = np.correlate(f, f, "full")[N-1:]; lo, hi = SR//400, SR//70; k = lo+np.argmax(ac[lo:hi])
        out.append(SR/k if ac[k] > 0.4*ac[0] else 0)
    return np.array(out)
def med_f0(x):
    t = f0_track(x); t = t[t > 0]; return float(np.median(t)) if len(t) > 10 else 0.0
REF = {}
def ref_f0(name):
    if name in REF: return REF[name]
    vd = os.path.join(HERE, "VibeVoice-main", "demo", "voices"); p = None
    for f in os.listdir(vd):
        if f.lower().split("-",1)[-1].split("_")[0] == name.lower(): p = os.path.join(vd, f)
    REF[name] = round(med_f0(load(p)), 1) if p else 0.0
    return REF[name]
def pitch_events(x):
    h, N = 400, 1024; f0 = []
    for i in range(0, len(x)-N, h):
        f = x[i:i+N]*np.hanning(N)
        if np.sqrt((f**2).mean()) < 0.01: f0.append(0); continue
        ac = np.correlate(f, f, "full")[N-1:]; lo, hi = SR//500, SR//60; k = lo+np.argmax(ac[lo:hi])
        f0.append(SR/k if ac[k]/ac[0] > 0.6 else 0)
    f0 = np.array(f0); ev = []; run = 0
    for i, v in enumerate(f0):
        w = f0[max(0,i-200):i+200]; w = w[w > 0]
        med = np.median(w) if len(w) > 20 else 0
        hit = med > 0 and v > 1.5*med and v < 2.4*med
        run = run+1 if hit else 0
        if run == 10: ev.append(round((i-9)*h/SR, 2))
    return ev
def wer_tok(r, h):
    d = list(range(len(h)+1))
    for i in range(1, len(r)+1):
        p = d[:]; d[0] = i
        for j in range(1, len(h)+1): d[j] = min(p[j]+1, d[j-1]+1, p[j-1]+(r[i-1]!=h[j-1]))
    return d[-1]/max(1,len(r))
wer = lambda ref, hyp: wer_tok(norm(ref), norm(hyp))
def unrecognised(x, ww, sp):
    """runs >= 1.0 s of speech-level energy (> sp-20 dB) farther than 0.15 s from any whisper word"""
    h = 320; n = len(x)//h; fr = x[:n*h].reshape(n,h); fdb = 20*np.log10(np.sqrt((fr**2).mean(1))+1e-9)
    near = np.zeros(n, bool)
    for _, b, e in ww: near[max(0,int((b-.15)*SR/h)):int((e+.15)*SR/h)+1] = 1
    loud = (fdb > sp-20) & ~near; out = []; k = 0
    while k < n:
        if not loud[k]: k += 1; continue
        j = k; gapc = 0
        while j < n and (loud[j] or gapc < 10):
            gapc = 0 if loud[j] else gapc+1; j += 1
        j -= gapc; d = (j-k)*h/SR
        if d >= 1.0:
            seg = x[k*h:j*h]; t = f0_track(seg); v = t[t > 0]
            tonal = bool(len(v) > 20 and (len(v)/max(1,len(t))) > .7 and np.std(np.log(v)) < .05)
            out.append({"t": round(k*h/SR,2), "dur": round(d,2), "tonal": tonal})
        k = max(j, k+1)
    return out
def metrics(x, ww, ref):
    mask = np.zeros(len(x), bool); allsp = np.zeros(len(x), bool)
    for _, b, e in ww: allsp[int(b*SR):int(e*SR)] = 1
    spr = 20*np.log10(np.sqrt((x[allsp]**2).mean())+1e-9) if allsp.any() else -99
    pe = -9
    for _, b, e in ww:
        if b - pe > .25:
            i0, i1 = int(b*SR), int(min(e, b+.9)*SR); f = 320
            seg = x[i0:i1]; nf = len(seg)//f
            if nf > 2:
                F = seg[:nf*f].reshape(nf,f); lv = 20*np.log10(np.sqrt((F**2).mean(1))+1e-9)
                P = np.abs(np.fft.rfft(F*np.hanning(f),axis=1))**2; fq = np.fft.rfftfreq(f, 1/SR)
                hf = 10*np.log10(P[:,(fq>3000)&(fq<7500)].sum(1)/(P.sum(1)+1e-12)+1e-9)
                ok = (lv > spr-7) & (hf > -42)
                on = np.argmax(ok) if ok.any() else 0
                if on*f/SR > .2: b = b + on*f/SR - .05
        mask[max(0,int((b-.04)*SR)):int((e+.04)*SR)] = 1; pe = e
    h = 320; n = len(x)//h; fr = x[:n*h].reshape(n,h); fdb = 20*np.log10(np.sqrt((fr**2).mean(1))+1e-9)
    fm = mask[:n*h].reshape(n,h).mean(1) > .5
    sp = 20*np.log10(np.sqrt((x[mask]**2).mean())+1e-9) if mask.any() else -99
    gap = x[~mask]; gdb = 20*np.log10(np.sqrt((gap**2).mean())+1e-9) - sp if len(gap) > 1600 else -99
    ns = float(((~fm) & (fdb > sp-35)).sum()*h/SR)
    ev = []; k = 0
    while k < n:
        if fm[k]: k += 1; continue
        j = k
        while j < n and not fm[j]: j += 1
        if j - k >= 15 and (fdb[k+2:j-2] > sp-30).sum() >= 8: ev.append(round(k*h/SR, 2))
        k = j
    pe_ = pitch_events(x)
    return {"wer": round(wer(ref, " ".join(w for w,_,_ in ww)),4), "pitch_events": len(pe_), "pitch_t": pe_, "pitch_glitches": [t for t in pe_ if any(abs(t-b) < .8 for _, b, _ in LOWP)], "lowprob_words": LOWP, "gap_db": round(float(gdb),1), "nonspeech_s": round(ns,2), "noise_events": len(ev), "event_t": ev, "speech_db": round(float(sp),1), "unrecognised": unrecognised(x, ww, sp)}, mask
def fuzzy_has(term, rsp, hyp_toks):
    cands = set(hyp_toks + [hyp_toks[i]+hyp_toks[i+1] for i in range(len(hyp_toks)-1)] + [hyp_toks[i]+hyp_toks[i+1]+hyp_toks[i+2] for i in range(len(hyp_toks)-2)])
    tgt = ["".join(norm(term)), "".join(norm(rsp.replace("-", " ")))]
    return max((difflib.SequenceMatcher(None, c, t).ratio() for c in cands for t in tgt), default=0) >= 0.7
def line_checks(cx, CW, c, spk):
    """per-line coverage, WER, glossary, F0 and rate, using difflib alignment of script tokens to whisper words"""
    hw = [(t, b, e) for w, b, e in CW for t in norm(w)]; hyp = [t for t, _, _ in hw]
    st, li = [], []
    for k, t in enumerate(c.get("lines", [c["text"]])):
        for tok in norm(t): st.append(tok); li.append(k)
    st_h = [-1]*len(st)
    for bl in difflib.SequenceMatcher(None, st, hyp, autojunk=False).get_matching_blocks():
        for q in range(bl.size): st_h[bl.a+q] = bl.b+q
    res = []
    for k, t in enumerate(c.get("lines", [c["text"]])):
        qs = [q for q in range(len(st)) if li[q] == k]
        if not qs: continue
        hs = [st_h[q] for q in qs if st_h[q] >= 0]
        cov = len(hs)/len(qs)
        r = {"k": k, "speaker": spk[k] if k < len(spk) else "?", "n": len(qs), "cov": round(cov,2)}
        if hs:
            h0, h1 = min(hs), max(hs); b, e = hw[h0][1], hw[h1][2]
            r["t"] = [round(b,2), round(e,2)]
            r["wer"] = round(wer_tok([st[q] for q in qs], hyp[h0:h1+1]), 2)
            if e - b > 1.0: r["rate"] = round(len(qs)/(e-b), 2)
            r["f0"] = round(med_f0(cx[int(b*SR):int(e*SR)]), 1)
            win = hyp[max(0,h0-3):h1+4]
        else: r["wer"] = 1.0; win = []
        miss = [g for g in GL if re.search(r"\b"+re.escape(g.lower())+r"\b", t.lower()) and not fuzzy_has(g, GL[g], win)]
        if miss: r["glossary_missing"] = miss
        res.append(r)
    return res
def finalize(res):
    """flags + score per chunk (no audio needed -> --rescore qc.json re-applies thresholds).
    F0 reference per speaker = median line F0 of that speaker over the whole file (>= 6 lines), else the voice prompt F0
    (the prompt differs from generated speech: Frank prompt 116 Hz vs ~127 Hz generated)."""
    allf = {}
    for cm in res["chunks"]:
        for r in cm["lines"]:
            if r.get("f0") and r["n"] >= 5: allf.setdefault(r["speaker"], []).append(r["f0"])
    vf = os.path.join(HERE, "voice_f0.json"); VF = json.load(open(vf)) if os.path.exists(vf) else {}
    names = {"Host": a.host, "Guest": a.guest, "Guest2": a.guest2}
    # 1) calibrated generated-speech F0 of the voice (voice_f0.json), 2) file median (>= 6 lines), 3) voice prompt F0
    ref = {s: (VF.get(names.get(s, "")) or (round(float(np.median(v)),1) if len(v) >= 6 else res["ref_f0"].get(s, 0))) for s, v in allf.items()}
    res["f0_ref_used"] = ref; redo = []
    for cm in res["chunks"]:
        L = cm["lines"]; drift = []; per = {}
        for r in L:
            rf = ref.get(r["speaker"], 0)
            if rf and r.get("f0") and r["n"] >= 5:
                per.setdefault(r["speaker"], []).append(r["f0"])
                if abs(r["f0"]/rf - 1) > a.f0_tol: drift.append((r["k"], r["speaker"], r["f0"], rf))
        cm["f0_med"] = {s: round(float(np.median(v)),1) for s, v in per.items()}
        cm["f0_drift"] = drift
        chunk_drift = [s for s, v in per.items() if len(v) >= 2 and abs(np.median(v)/ref[s]-1) > a.f0_tol]
        cm["rate_bad"] = [(r["k"], r["rate"]) for r in L if r["n"] >= 12 and "rate" in r and not (a.rate_lo <= r["rate"] <= a.rate_hi)]
        cm["unrecognised_long"] = [u for u in cm["unrecognised"] if u["dur"] >= a.unrec_s]
        dur = cm.get("dur", 120)
        flags = {"wer": cm["wer"] > 0.08, "bad_lines": bool(cm["bad_lines"]), "pitch_glitch": bool(cm["pitch_glitches"]),
                 "lowprob": len(cm["lowprob_words"]) > 2, "noise": cm["noise_events"] > max(6, dur/15),
                 "line_wer": bool(cm["line_wer"]), "glossary": bool(cm["glossary_missing"]),
                 "f0_drift": len(drift) >= 2 or bool(chunk_drift), "rate": bool(cm["rate_bad"]), "unrecognised": bool(cm["unrecognised_long"])}
        cm["flags"] = [k for k, v in flags.items() if v]
        cm["score"] = round(10*len(cm["flags"]) + 100*cm["wer"] + 3*len(cm["line_wer"]) + 5*len(drift) + 4*len(cm["rate_bad"]) + 5*sum(u["dur"] for u in cm["unrecognised_long"]) + cm["noise_events"]/2, 2)
        if cm["flags"]: redo.append(cm["i"])
    res["redo"] = redo
if a.rescore:
    res = json.load(open(a.rescore)); finalize(res)
    for cm in res["chunks"]: print(f"chunk {cm['i']} seed {cm['seed']} score {cm['score']} flags {cm['flags']}")
    if a.json: json.dump(res, open(a.json, "w"), indent=1)
    print("REDO " + ",".join(map(str, res["redo"]))); sys.exit()
lines = [l for l in json.load(open(a.script, encoding="utf-8-sig")) if l.get("text")]
x = load(a.audio); ww = words(x)
res, mask = metrics(x, ww, " ".join(l["text"] for l in lines)); res["file"] = a.audio
res["ref_f0"] = {"Host": ref_f0(a.host), "Guest": ref_f0(a.guest)}
if a.guest2: res["ref_f0"]["Guest2"] = ref_f0(a.guest2)
redo = []
if a.chunks and os.path.exists(os.path.join(a.chunks, "chunks.json")):
    meta = json.load(open(os.path.join(a.chunks, "chunks.json"))); res["chunks"] = []
    for c in meta["chunks"]:
        cx = load(os.path.join(a.chunks, f"c{c['i']:03d}.wav")); CW = words(cx); cm, _ = metrics(cx, CW, c["text"])
        cm["i"] = c["i"]; cm["seed"] = c["seed"]
        spk = c.get("speakers") or [lines[c["first_line"]+k]["speaker"] for k in range(c["n_lines"])]
        L = line_checks(cx, CW, c, spk); cm["lines"] = L
        cm["bad_lines"] = [(r["k"], r["cov"]) for r in L if r["cov"] < 0.75]
        cm["line_wer"] = [(r["k"], r["wer"]) for r in L if r["n"] >= 4 and r["wer"] > 0.25]
        cm["glossary_missing"] = [(r["k"], r["glossary_missing"]) for r in L if r.get("glossary_missing")]
        cm["dur"] = round(len(cx)/SR, 2)
        res["chunks"].append(cm)
    finalize(res)
redo = res.get("redo", [])
if a.gate:
    y, sr = load(a.audio, 24000), 24000
    g = np.ones(len(y), np.float32); fl = 10**(-60/20)
    m24 = mask[np.minimum(np.arange(len(y))*SR//sr, len(mask)-1)]
    i = 0; L_ = len(y); mg = int(.08*sr); fade = int(.03*sr); kept = []
    sp_lin = 10**(res["speech_db"]/20)
    while i < L_:
        if m24[i]: i += 1; continue
        j = i
        while j < L_ and not m24[j]: j += 1
        s, e = i + (mg if i > 0 else 0), j - (mg if j < L_ else 0)
        if e - s > int(.10*sr) and e > s:
            seg = y[s:e]; fr_ = seg[:len(seg)//480*480].reshape(-1, 480) if len(seg) >= 480 else seg.reshape(1,-1)
            loud_frac = float((np.sqrt((fr_**2).mean(1)) > sp_lin*10**(-20/20)).mean())
            if (e - s) > int(.8*sr) and loud_frac > .4:
                kept.append([round(s/sr,2), round(e/sr,2), round(loud_frac,2)])   # real (unrecognised) speech: never mute
            else:
                g[s:e] = fl
                r = np.linspace(1, fl, min(fade, (e-s)//2)); g[s:s+len(r)] = r; g[e-len(r):e] = r[::-1]
        i = j
    pcm = (np.clip(y*g,-1,1)*32767).astype(np.int16).tobytes()
    subprocess.run(["ffmpeg","-v","error","-y","-f","s16le","-ar",str(sr),"-ac","1","-i","-",a.gate],input=pcm,check=True)
    res["gated"] = a.gate; res["gate_kept"] = kept
print(json.dumps({k: v for k, v in res.items() if k != "chunks"}))
for cm in res.get("chunks", []): print(f"chunk {cm['i']} seed {cm['seed']} score {cm['score']} flags {cm['flags']}")
if a.json: json.dump(res, open(a.json, "w"), indent=1)
print("REDO " + ",".join(map(str, redo)))
