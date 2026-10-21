"""gate_cut_check.py (template v1.11, 2026-10-20) - cut-off word detector: finds speech in the RAW TTS audio that is muted in the processed audio.
  python gate_cut_check.py RAW.wav PROCESSED.(wav|mp3) [--tempo 0.90] [--json out.json] [--min_ms 40]
A cut = >= --min_ms of consecutive 20 ms frames where the raw audio is speech-level (> raw speech median - 18 dB) but the processed audio is
> 40 dB below its own speech median (gate floor / hard mute). PROCESSED may be time-stretched (atempo): t_proc = t_raw / tempo (+ fitted offset).
Root cause it guards against (Fault Lines #1, 0:53): qc_vv.py v2.2 --gate muted word tails after early whisper word end times.
Prints 'GATECUT <n> <total_s> s' (n = 0 means clean) and the runs; numpy + ffmpeg only (any venv)."""
import argparse, json, subprocess, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("raw"); ap.add_argument("proc"); ap.add_argument("--tempo", type=float, default=1.0)
ap.add_argument("--json"); ap.add_argument("--min_ms", type=float, default=40); a = ap.parse_args()
SR = 16000; H = 320
def load(p): return np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout, np.int16).astype(np.float32) / 32768
def env(x): n = len(x) // H; return 20 * np.log10(np.sqrt((x[:n * H].reshape(n, H) ** 2).mean(1)) + 1e-9)
r, p = load(a.raw), load(a.proc); er = env(r)
def proc_env(off):
    t = (np.arange(len(er)) * H / SR) / a.tempo + off; idx = np.clip((t * SR).astype(int), 0, len(p) - H - 1)
    return np.array([20 * np.log10(np.sqrt((p[i:i + H] ** 2).mean()) + 1e-9) for i in idx])
n0 = min(len(er), int(60 * SR / H)); best = (-2, 0.0)
for off in np.arange(-0.5, 0.501, 0.01):
    t = (np.arange(n0) * H / SR) / a.tempo + off; idx = np.clip((t * SR).astype(int), 0, len(p) - H - 1)
    ep = np.array([20 * np.log10(np.sqrt((p[i:i + H] ** 2).mean()) + 1e-9) for i in idx[::2]])
    c = np.corrcoef(np.maximum(er[:n0:2], -70), np.maximum(ep, -90))[0, 1]
    if c > best[0]: best = (c, off)
ep = proc_env(best[1]); spr = np.median(er[er > -40]) if (er > -40).any() else -25; spp = np.median(ep[ep > -40]) if (ep > -40).any() else -20
hit = (er > spr - 18) & (ep < spp - 40); runs = []; k = 0; mf = max(1, int(round(a.min_ms / 20)))
while k < len(hit):
    if hit[k]:
        j = k
        while j < len(hit) and hit[j]: j += 1
        if j - k >= mf: runs.append([round(k * H / SR, 2), round((j - k) * H / SR, 2)])
        k = j
    else: k += 1
res = {"raw": a.raw, "proc": a.proc, "tempo": a.tempo, "offset_s": round(float(best[1]), 3), "corr": round(float(best[0]), 3), "cuts": runs, "n": len(runs), "total_s": round(sum(x[1] for x in runs), 2)}
if a.json: json.dump(res, open(a.json, "w"), indent=1)
print(f"GATECUT {len(runs)} {res['total_s']} s (corr {res['corr']}, offset {res['offset_s']} s){' at raw ' + ', '.join(f'{t}s/{d}s' for t, d in runs[:12]) if runs else ''}")
