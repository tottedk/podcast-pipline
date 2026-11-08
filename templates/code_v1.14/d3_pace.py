"""d3_pace.py (template v1.12, 2026-10-21) - pause clamp + per-speaker tempo for drama3_generate.py (importable, unit-tested in tests\\test_v112.py).
Why (fl1b\\analysis\\TEMPO_PAUSES.md): v1.11 detected silence as 'chunk speech median - 32 dB'. Elliot's raw noise floor sits only ~37 dB below his
speech, so none of his 69 long raw pauses (>= 0.9 s) was ever clamped and the later pause gate turned them into 1-3.8 s of dead air; the global
atempo 0.90 then stretched speech and pauses of every speaker alike (Carter 166 / Elliot 136 / Clara 146 wpm in the final mix).
v1.12:
  clamp(): INTERNAL silence = 10 ms frames more than rel_db (default 20) dB below the chunk speech level (median of frames > -45 dBFS); runs longer
           than max_pause are cut to keep_pause (the middle is removed, keep_pause/2 stays on each side, so word tails survive). Chunks with a
           [whispers] tag keep the v1.11 32 dB rule (soft speech must never count as silence). Lead/tail trimming keeps the conservative 32 dB rule.
           drama3_generate.py runs it AFTER the per-chunk tempo, so max_pause/keep_pause are in final-tempo seconds (default cap 0.4 s).
  stretch(): ffmpeg atempo on one chunk wav (pitch preserved).
  plan_tempo(): per-speaker tempo by REFERENCE name: drama3_tempo.json "voices" map = fixed values for known refs (Thomas-approved defaults for the
           current refs); refs not in the map (or every ref with auto_all) are auto-calibrated: tempo = target_wpm / measured raw wpm of that ref's
           first chunks in the run, clamped [min_tempo, max_tempo]; locked in <Dir>\\drama3_tempo_lock.json once >= min_words_lock words were measured,
           so every later segment of the episode uses the same value.
v1.14 (2026-11-07, Carter tempo root fix, see templates\\technical_v1.14.md):
  "voices" values may be a number (fixed tempo, as before) OR a dict {"mode": "per_segment", "target_wpm": 156, "min_tempo": 0.72, "max_tempo": 0.95}:
           per_segment = tempo = target_wpm / raw wpm of THIS segment's chunks of that reference, never locked (Carter's raw Drama 3 pace swings
           181-227 wpm between segments, so the fixed 0.86 landed at 177-180.5 wpm in the mix). With < min_words_provisional words the "fallback"
           value of the dict (or the run fallback) is used.
  pitch_std_st(): F0 std in semitones (librosa pyin 60-450 Hz, 16 kHz, frame 1024 - the voice_design qc_f0.py / Elliot-finding method) for the
           drama3_generate.py pitch-variation gate."""
import json, os, subprocess
import numpy as np

DEFAULT_CFG = {"target_wpm": 160.0, "min_tempo": 0.85, "max_tempo": 1.10, "auto": True, "auto_all": False, "min_words_lock": 60, "min_words_provisional": 15,
               "voices": {"Carter": 0.90, "Clara": 0.95, "Elliot": 1.00}}

def load_cfg(path):
    c = json.loads(json.dumps(DEFAULT_CFG))
    if path and os.path.exists(path):
        u = json.load(open(path, encoding="utf-8-sig")); c.update({k: v for k, v in u.items() if k != "voices"}); c["voices"] = dict(u.get("voices", c["voices"]))
    return c

def frames_db(w, sr, hop_s=0.01):
    h = int(sr * hop_s); n = len(w) // h
    if n == 0: return np.zeros(0), h
    return 20 * np.log10(np.sqrt((w[:n * h].astype(np.float64).reshape(n, h) ** 2).mean(1)) + 1e-9), h

def _runs(q):
    d = np.diff(np.concatenate([[0], q.astype(np.int8), [0]])); return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))

def clamp(w, sr, max_pause=0.4, keep_pause=0.4, rel_db=20.0, quiet=False, lead_s=0.05, tail_s=0.12, edge_db=32.0):
    """shorten silences of one chunk -> (wav, info). max_pause/keep_pause in seconds of THIS audio."""
    e, h = frames_db(w, sr); n = len(e)
    if n < 20: return w.astype(np.float32), {}
    sp = float(np.median(e[e > -45])) if (e > -45).any() else -30.0
    floor = float(np.percentile(e, 5)); rel = edge_db if quiet else rel_db
    info = {"speech_db": round(sp, 1), "floor_db": round(floor - sp, 1), "thr_rel_db": -rel, "clamped": [], "lead_cut_s": 0.0, "tail_cut_s": 0.0}
    keep = np.ones(len(w), bool)
    edge = _runs(e < sp - edge_db)
    if edge and edge[0][0] == 0:
        L = edge[0][1] * h; cut = max(0, L - int(sr * lead_s)); keep[:cut] = False; info["lead_cut_s"] = round(cut / sr, 2)
    if edge and edge[-1][1] >= n:
        k = edge[-1][0]
        if k > 0: cut = max(0, len(w) - k * h - int(sr * tail_s)); keep[len(w) - cut:] = False; info["tail_cut_s"] = round(cut / sr, 2)
    for k, j in _runs(e < sp - rel):
        if k == 0 or j >= n: continue          # lead/tail handled above (conservative rule)
        L = (j - k) * h
        if L > max_pause * sr:
            s0 = k * h + int(keep_pause * sr / 2); s1 = j * h - int(keep_pause * sr / 2)
            if s1 > s0: keep[s0:s1] = False; info["clamped"].append([round(k * h / sr, 2), round(L / sr, 2), keep_pause])
    return w[keep].astype(np.float32), info

def stretch(src, dst, tempo, sr=24000, ffmpeg="ffmpeg"):
    """atempo one chunk (pitch preserved); tempo > 1 = faster"""
    if abs(tempo - 1.0) < 1e-4:
        subprocess.run([ffmpeg, "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", dst], check=True); return
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", src, "-af", f"atempo={tempo:.4f}", "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", dst], check=True)

def _clip(t, c): return round(float(min(c["max_tempo"], max(c["min_tempo"], t))), 3)

def pitch_std_st(w, sr):
    """-> (F0 std in semitones around the chunk median, voiced seconds); (None, 0) when < 20 voiced frames. Same method as qc_f0.py."""
    import librosa
    y = np.asarray(w, dtype=np.float32)
    if sr != 16000: y = librosa.resample(y, orig_sr=sr, target_sr=16000)
    f0, _, _ = librosa.pyin(y, fmin=60, fmax=450, sr=16000, frame_length=1024)
    f = f0[~np.isnan(f0)]
    if len(f) < 20: return None, 0.0
    return float(np.std(12 * np.log2(f / np.median(f)))), round(len(f) * 256 / 16000, 2)   # pyin hop = frame_length // 4 = 256

def plan_tempo(cfg, refs_by_role, stats_by_ref, lock, fallback):
    """refs_by_role {role: refname}; stats_by_ref {ref: [words, pace_seconds]} measured on this run's chunks (raw, provisional clamp);
    lock {ref: {...}} (mutated: new auto values with enough words are locked). Returns {role: {"tempo", "src", "raw_wpm"}}."""
    out = {}
    for role, ref in refs_by_role.items():
        w, d = stats_by_ref.get(ref, [0, 0.0]); raw = round(w / d * 60, 1) if d > 0 else None
        fixed = cfg["voices"].get(ref)
        if isinstance(fixed, dict):   # v1.14 per-voice rule (e.g. Carter per_segment), never locked
            lo, hi = float(fixed.get("min_tempo", cfg["min_tempo"])), float(fixed.get("max_tempo", cfg["max_tempo"]))
            if fixed.get("mode") == "per_segment" and raw and w >= cfg["min_words_provisional"]:
                t = round(min(hi, max(lo, float(fixed.get("target_wpm", cfg["target_wpm"])) / raw)), 3)
                out[role] = {"tempo": t, "src": "per_segment", "raw_wpm": raw}
            else: out[role] = {"tempo": float(fixed.get("fallback", fallback)), "src": "voice-fallback", "raw_wpm": raw}
            continue
        if ref in lock: out[role] = {"tempo": lock[ref]["tempo"], "src": "locked", "raw_wpm": raw}; continue
        if fixed and not cfg.get("auto_all"): out[role] = {"tempo": float(fixed), "src": "map", "raw_wpm": raw}; continue
        if cfg.get("auto", True) and raw and w >= cfg["min_words_provisional"]:
            t = _clip(cfg["target_wpm"] / raw, cfg)
            if w >= cfg["min_words_lock"]:
                lock[ref] = {"tempo": t, "raw_wpm": raw, "words": int(w), "target_wpm": cfg["target_wpm"]}; out[role] = {"tempo": t, "src": "auto", "raw_wpm": raw}
            else: out[role] = {"tempo": t, "src": "auto-provisional", "raw_wpm": raw}
            continue
        out[role] = {"tempo": float(fixed) if fixed else float(fallback), "src": "map" if fixed else "fallback", "raw_wpm": raw}
    return out
