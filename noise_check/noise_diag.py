import sys, os, json, glob, numpy as np
sys.argv = ["qc_vv.py", "x", "y"]
src = open(r"C:\grok\podcast\qc_vv.py", encoding="utf-8-sig").read(); src = src[:src.index("if a.rescore:")]
G = {"__file__": r"C:\grok\podcast\qc_vv.py", "__name__": "qcvv"}
import types
# avoid loading whisper model for diag: stub WhisperModel
import faster_whisper
class _Stub:
    def __init__(self,*a,**k): pass
faster_whisper.WhisperModel = _Stub
exec(compile(src, "qc_vv_prefix", "exec"), G)
SR = G["SR"]; load = G["load"]; metrics = G["metrics"]
H = 320
def mask_frames(x, ww):
    """exact copy of the mask construction in qc_vv.metrics (v2.1)"""
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
    return mask
def events_detail(x, ww):
    mask = mask_frames(x, ww)
    n = len(x)//H; fr = x[:n*H].reshape(n,H); fdb = 20*np.log10(np.sqrt((fr**2).mean(1))+1e-9)
    fm = mask[:n*H].reshape(n,H).mean(1) > .5
    sp = 20*np.log10(np.sqrt((x[mask]**2).mean())+1e-9) if mask.any() else -99
    P = np.abs(np.fft.rfft(fr*np.hanning(H), axis=1))**2 + 1e-12; fq = np.fft.rfftfreq(H, 1/SR)
    tot = P.sum(1)
    hfr = 10*np.log10(P[:, (fq>3000)&(fq<7500)].sum(1)/tot)       # HF share dB
    lfr = 10*np.log10(P[:, fq<400].sum(1)/tot)
    band = (fq>100)&(fq<7500); flat = np.exp(np.log(P[:,band]).mean(1))/P[:,band].mean(1)   # spectral flatness 0..1
    ev = []; k = 0
    wb = np.array([[b, e] for _, b, e in ww]) if ww else np.zeros((0,2))
    while k < n:
        if fm[k]: k += 1; continue
        j = k
        while j < n and not fm[j]: j += 1
        if j - k >= 15 and (fdb[k+2:j-2] > sp-30).sum() >= 8:
            sl = slice(k+2, j-2); act = fdb[sl] > sp-30
            t0 = k*H/SR; t1 = j*H/SR
            pw = wb[wb[:,1] <= t0+0.05][-1] if (wb[:,1] <= t0+0.05).any() else None
            nw = wb[wb[:,0] >= t1-0.05][0] if (wb[:,0] >= t1-0.05).any() else None
            ev.append(dict(t=round(t0,2), gap=round(t1-t0,2), act_s=round(float(act.sum())*H/SR,2), rel_peak=round(float(fdb[sl].max()-sp),1), rel_mean_act=round(float(fdb[sl][act].mean()-sp),1),
                           floor=round(float(np.percentile(fdb[sl],10)-sp),1), hf=round(float(hfr[sl][act].mean()),1), lf=round(float(lfr[sl][act].mean()),1), flat=round(float(flat[sl][act].mean()),3),
                           since_word=round(t0-pw[1],2) if pw is not None else None, to_word=round(nw[0]-t1,2) if nw is not None else None))
        k = j
    return ev, sp
if __name__ == "__main__":
    out = {}
    for f in sorted(glob.glob(r"C:\grok\podcast\noise_check\words\*.json")):
        c = json.load(open(f)); x = load(c["wav"]); ww = [tuple(w) for w in c["words"]]
        G["LOWP"] = c["lowp"]
        m, _ = metrics(x, ww, "")
        ev, sp = events_detail(x, ww)
        assert len(ev) == m["noise_events"], (f, len(ev), m["noise_events"])
        out[os.path.basename(f)[:-5]] = dict(dur=len(x)/SR, noise_events=m["noise_events"], event_t=m["event_t"], speech_db=m["speech_db"], events=ev)
    json.dump(out, open(r"C:\grok\podcast\noise_check\diag.json", "w"))
    print("diag done", len(out))
