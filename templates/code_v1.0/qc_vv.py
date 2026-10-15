"""qc_vv.py - QC + metrics + pause gate for VibeVoice output (adapted from pw/qc.py: whisper words, per-line match, non-speech energy).
  python qc_vv.py audio script.json [--chunks DIR] [--gate OUT.wav] [--json OUT.json] [--model large-v3-turbo]
Metrics: wer, gap_db (RMS in pauses rel. speech), nonspeech_s (seconds of >-35 dB-rel energy outside words),
pitch_events (octave jumps), lowprob_words; per-chunk bad flags (any script line < 75% recognised, wer > 0.08, a pitch jump that coincides with a low-confidence word, >2 low-confidence words, or > max(6, dur/15) noise events; normal pause/turn-onset bursts are removed by --gate instead) -> prints REDO i,i,...
--gate writes a copy where pauses (>=0.26 s outside whisper words, 80 ms margins) are faded to -60 dB.
"""
import sys, json, re, subprocess, difflib, argparse, os, numpy as np
from faster_whisper import WhisperModel
ap = argparse.ArgumentParser(); ap.add_argument("audio"); ap.add_argument("script")
ap.add_argument("--chunks"); ap.add_argument("--gate"); ap.add_argument("--json"); ap.add_argument("--model", default="large-v3-turbo")
a = ap.parse_args()
SR = 16000
norm = lambda t: re.sub(r"[^a-z0-9' ]", " ", t.lower().replace("\u2019", "'")).split()
def load(p, sr=SR):
    pcm = subprocess.run(["ffmpeg","-v","error","-i",p,"-f","s16le","-ac","1","-ar",str(sr),"-"],capture_output=True,check=True).stdout
    return np.frombuffer(pcm, np.int16).astype(np.float32)/32768
m = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=6)
def words(x):
    segs,_ = m.transcribe(x, language="en", word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    segs = list(segs); global LOWP
    LOWP = [(w.word.strip(), round(w.start,2), round(w.probability,2)) for s in segs for w in s.words if w.probability < 0.2 and len(w.word.strip()) > 2]
    return [(w.word, w.start, w.end) for s in segs for w in s.words]
def pitch_events(x):
    """octave jumps / falsetto squeaks (pw ep1 4:06 'He leans' jumped 100-150 Hz -> 220-260 Hz): runs >= 0.25 s
    whose F0 is > 1.5x the median voiced F0 of the surrounding 10 s"""
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
        hit = med > 0 and v > 1.5*med and v < 2.4*med   # >2.6x is usually an autocorr sub-harmonic error
        run = run+1 if hit else 0
        if run == 10: ev.append(round((i-9)*h/SR, 2))
    return ev
def wer(ref, hyp):
    r, h = norm(ref), norm(hyp); d = list(range(len(h)+1))
    for i in range(1, len(r)+1):
        p = d[:]; d[0] = i
        for j in range(1, len(h)+1): d[j] = min(p[j]+1, d[j-1]+1, p[j-1]+(r[i-1]!=h[j-1]))
    return d[-1]/max(1,len(r))
def metrics(x, ww, ref):
    mask = np.zeros(len(x), bool)
    allsp = np.zeros(len(x), bool)
    for _, b, e in ww: allsp[int(b*SR):int(e*SR)] = 1
    spr = 20*np.log10(np.sqrt((x[allsp]**2).mean())+1e-9) if allsp.any() else -99
    pe = -9
    for _, b, e in ww:
        # onset refinement: VibeVoice puts a noise/ambience burst before a turn/pause onset and whisper
        # often folds it into the first word -> start the word where real speech energy begins
        if b - pe > .25:
            i0, i1 = int(b*SR), int(min(e, b+.9)*SR); f = 320
            seg = x[i0:i1]; nf = len(seg)//f
            if nf > 2:
                F = seg[:nf*f].reshape(nf,f); lv = 20*np.log10(np.sqrt((F**2).mean(1))+1e-9)
                P = np.abs(np.fft.rfft(F*np.hanning(f),axis=1))**2; fq = np.fft.rfftfreq(f, 1/SR)
                hf = 10*np.log10(P[:,(fq>3000)&(fq<7500)].sum(1)/(P.sum(1)+1e-12)+1e-9)
                ok = (lv > spr-7) & (hf > -42)   # real speech: loud AND has >3 kHz content; bursts are low-band
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
    return {"wer": round(wer(ref, " ".join(w for w,_,_ in ww)),4), "pitch_events": len(pe_), "pitch_t": pe_, "pitch_glitches": [t for t in pe_ if any(abs(t-b) < .8 for _, b, _ in LOWP)], "lowprob_words": LOWP, "gap_db": round(float(gdb),1), "nonspeech_s": round(ns,2), "noise_events": len(ev), "event_t": ev, "speech_db": round(float(sp),1)}, mask
lines = [l for l in json.load(open(a.script, encoding="utf-8")) if l.get("text")]
x = load(a.audio); ww = words(x)
res, mask = metrics(x, ww, " ".join(l["text"] for l in lines)); res["file"] = a.audio
redo = []
if a.chunks and os.path.exists(os.path.join(a.chunks, "chunks.json")):
    meta = json.load(open(os.path.join(a.chunks, "chunks.json"))); res["chunks"] = []
    for c in meta["chunks"]:
        cx = load(os.path.join(a.chunks, f"c{c['i']:03d}.wav")); CW = words(cx); cm, _ = metrics(cx, CW, c["text"])
        cm["i"] = c["i"]; cm["seed"] = c["seed"]
        # per-line coverage (as in pw/qc.py): a dropped short line (pw ep1 6:26 'Voting with your feet.') is
        # only ~1% chunk WER, so check every line separately
        hyp = norm(" ".join(w for w,_,_ in CW)); st, li = [], []
        for k, t in enumerate(c.get("lines", [c["text"]])):
            for tok in norm(t): st.append(tok); li.append(k)
        hit = np.zeros(len(st))
        for bl in difflib.SequenceMatcher(None, st, hyp, autojunk=False).get_matching_blocks(): hit[bl.a:bl.a+bl.size] = 1
        cov = [round(float(hit[[q for q in range(len(st)) if li[q]==k]].mean()),2) for k in range(max(li)+1)] if st else []
        cm["bad_lines"] = [(k, v) for k, v in enumerate(cov) if v < 0.75]
        res["chunks"].append(cm)
        if cm["wer"] > 0.08 or cm["bad_lines"] or cm["pitch_glitches"] or len(cm["lowprob_words"]) > 2 or cm["noise_events"] > max(6, len(cx)/SR/15): redo.append(c["i"])
res["redo"] = redo
if a.gate:
    y, sr = load(a.audio, 24000), 24000
    g = np.ones(len(y), np.float32); fl = 10**(-60/20)
    m24 = mask[np.minimum(np.arange(len(y))*SR//sr, len(mask)-1)]
    i = 0; L = len(y); mg = int(.08*sr); fade = int(.03*sr)
    while i < L:
        if m24[i]: i += 1; continue
        j = i
        while j < L and not m24[j]: j += 1
        s, e = i + (mg if i > 0 else 0), j - (mg if j < L else 0)
        if e - s > int(.10*sr) and e > s:
            g[s:e] = fl
            r = np.linspace(1, fl, min(fade, (e-s)//2)); g[s:s+len(r)] = r; g[e-len(r):e] = r[::-1]
        i = j
    pcm = (np.clip(y*g,-1,1)*32767).astype(np.int16).tobytes()
    subprocess.run(["ffmpeg","-v","error","-y","-f","s16le","-ar",str(sr),"-ac","1","-i","-",a.gate],input=pcm,check=True); res["gated"] = a.gate
print(json.dumps(res))
if a.json: json.dump(res, open(a.json, "w"), indent=1)
print("REDO " + ",".join(map(str, redo)))
