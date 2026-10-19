r"""align.py - exact timings for a podcast script via faster-whisper + forced alignment.
Usage: venv_whisper\Scripts\python.exe align.py episode.mp3 episode.json [-o episode.timings.json]
       [--model large-v3-turbo] [--threads 6] [--words cached_whisper_words.json]
Transcribes with word_timestamps (CPU int8), caches raw Whisper words to <base>.whisper.json,
then maps the script words (ground truth) onto Whisper words with difflib on normalized tokens.
Unmatched script words are interpolated between matched neighbours.
Output: {"duration", "model", "lines":[{speaker,text,start,end,words:[[word,start,end],...]}]}"""
import argparse, json, os, re, sys, time, difflib, bisect

def norm_tokens(w):
    w = w.lower().replace("\u2019", "'")
    w = re.sub(r"'(s|re|ve|ll|d|m|t)\b", r"\1", w)
    return [t for t in re.split(r"[^a-z0-9]+", w) if t]

def transcribe(mp3, model, threads):
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=threads)
    import numpy as np, subprocess
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", mp3, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout  # decode via ffmpeg (avoids PyAV version issues)
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    segs, info = m.transcribe(audio, language="en", word_timestamps=True, beam_size=5,
                              vad_filter=True, condition_on_previous_text=False)
    out = []
    for s in segs:
        for w in s.words or []:
            out.append([w.word.strip(), round(w.start, 3), round(w.end, 3)])
        print(f"\r  {s.end:7.1f}/{info.duration:.0f}s", end="", flush=True)
    print()
    return out, info.duration

def align(lines, wwords):
    # whisper tokens
    wt, wtime = [], []
    for w, s, e in wwords:
        toks = norm_tokens(w)
        for k, t in enumerate(toks):
            d = (e - s) / len(toks); wt.append(t); wtime.append((s + k * d, s + (k + 1) * d))
    # script tokens, each pointing to (line, word)
    st, sref, swords = [], [], []
    for li, l in enumerate(lines):
        ws = l["text"].split(); swords.append(ws)
        for wi, w in enumerate(ws):
            for t in norm_tokens(w): st.append(t); sref.append((li, wi))
    sm = difflib.SequenceMatcher(None, st, wt, autojunk=False)
    tt = [None] * len(st)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n): tt[a + k] = wtime[b + k]
    matched = sum(1 for x in tt if x)
    # interpolate gaps
    idx = [i for i, x in enumerate(tt) if x]
    for i in range(len(tt)):
        if tt[i]: continue
        p = bisect.bisect_left(idx, i)
        lo = idx[p - 1] if p > 0 else None; hi = idx[p] if p < len(idx) else None
        t0 = tt[lo][1] if lo is not None else 0.0; t1 = tt[hi][0] if hi is not None else t0 + 0.4 * (i - (lo or 0))
        a0 = lo if lo is not None else -1; a1 = hi if hi is not None else len(tt)
        f0 = (i - a0 - 1) / (a1 - a0 - 1); f1 = (i - a0) / (a1 - a0 - 1)
        tt[i] = (t0 + (t1 - t0) * f0, t0 + (t1 - t0) * f1)
    wtimes = {}
    for (li, wi), x in zip(sref, tt):
        if (li, wi) in wtimes: wtimes[(li, wi)] = (wtimes[(li, wi)][0], x[1])
        else: wtimes[(li, wi)] = x
    out = []
    for li, l in enumerate(lines):
        ws = []
        for wi, w in enumerate(swords[li]):
            if (li, wi) in wtimes: s, e = wtimes[(li, wi)]
            else: s = e = ws[-1][2] if ws else (out[-1]["end"] if out else 0.0)  # punctuation-only token
            ws.append([w, round(s, 3), round(e, 3)])
        out.append({"speaker": l["speaker"], "text": l["text"], "start": ws[0][1] if ws else 0, "end": ws[-1][2] if ws else 0, "words": ws})
    # monotonic fix
    last = 0.0
    for l in out:
        for w in l["words"]:
            w[1] = max(w[1], last); w[2] = max(w[2], w[1]); last = w[2]
        l["start"], l["end"] = l["words"][0][1], l["words"][-1][2]
    return out, matched / max(1, len(st))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp3"); ap.add_argument("json"); ap.add_argument("-o", "--out")
    ap.add_argument("--model", default="large-v3-turbo"); ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--words", help="cached Whisper words json (skip ASR)")
    a = ap.parse_args(); t0 = time.time()
    base = os.path.splitext(a.mp3)[0]
    out = a.out or base + ".timings.json"
    lines = [l for l in json.load(open(a.json, encoding="utf-8")) if l.get("text", "").strip()]
    cache = a.words or base + ".whisper.json"
    if os.path.exists(cache):
        d = json.load(open(cache, encoding="utf-8")); ww, dur, model = d["words"], d["duration"], d.get("model", "?")
        print(f"using cached Whisper words {cache}")
    else:
        ww, dur = transcribe(a.mp3, a.model, a.threads); model = a.model
        json.dump({"model": model, "duration": dur, "asr_seconds": round(time.time() - t0, 1), "words": ww},
                  open(cache, "w", encoding="utf-8"))
    t_asr = time.time() - t0
    al, ratio = align(lines, ww)
    json.dump({"duration": dur, "model": model, "match_ratio": round(ratio, 4), "lines": al},
              open(out, "w", encoding="utf-8"), indent=0)
    print(f"lines={len(al)} whisper_words={len(ww)} matched={ratio:.1%} asr={t_asr:.0f}s total={time.time() - t0:.0f}s -> {out}")

if __name__ == "__main__":
    main()
