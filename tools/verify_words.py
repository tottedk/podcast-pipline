"""verify_words.py (template v1.11 test helper) - whisper check of a test dir: every line's last word present in the segment mp3 (in order),
the 0:53 word 'assassination' (full duration), longest pause inside speech, words per minute.  venv_whisper\\Scripts\\python.exe verify_words.py <dir>"""
import sys, os, json, re, subprocess, difflib, numpy as np
from faster_whisper import WhisperModel
D = sys.argv[1]; SR = 16000
norm = lambda t: re.sub(r"[^a-z0-9' ]", " ", re.sub(r"\[[a-z ]+\]", " ", t.lower().replace("\u2019", "'"))).split()
def load(p): return np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout, np.int16).astype(np.float32) / 32768
m = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=6)
tw = tdur = 0
for s in sorted(f[3:5] for f in os.listdir(D) if re.match(r"seg\d\d\.json$", f)):
    L = json.load(open(os.path.join(D, f"seg{s}.json"), encoding="utf-8-sig")); x = load(os.path.join(D, f"seg{s}.mp3")); dur = len(x) / SR
    segs, _ = m.transcribe(x, language="en", word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    W = [(w.word.strip(), w.start, w.end, w.probability) for sg in segs for w in sg.words]; hyp = [t for w in W for t in norm(w[0])[:1]] 
    words = sum(len(norm(l["text"])) for l in L); tw += words; tdur += dur
    # last word of every line, in order
    pos = 0; miss = []
    for k, l in enumerate(L):
        lw = norm(l["text"])[-1]; found = -1
        for j in range(pos, len(hyp)):
            if difflib.SequenceMatcher(None, lw, hyp[j]).ratio() >= 0.75: found = j; break
        if found < 0: miss.append((k, lw))
        else: pos = found + 1
    print(f"seg{s}: {len(L)} lines, {words} words, mp3 {dur:.1f}s -> {words / dur * 60:.0f} wpm (incl. pauses); line endings found {len(L) - len(miss)}/{len(L)}" + (f" MISSING {miss}" if miss else ""))
    for w in W:
        if "assassin" in w[0].lower(): print(f"  word '{w[0]}' {w[1]:.2f}-{w[2]:.2f} ({w[2] - w[1]:.2f}s, p={w[3]:.2f})")
    gaps = sorted(((W[i + 1][1] - W[i][2], W[i][2], W[i][0], W[i + 1][0]) for i in range(len(W) - 1)), reverse=True)[:3]
    print("  longest pauses: " + "; ".join(f"{g:.2f}s at {t:.1f}s after '{a}' before '{b}'" for g, t, a, b in gaps))
print(f"TOTAL {tw} words in {tdur:.1f}s -> {tw / tdur * 60:.0f} wpm (mp3, incl. pauses)")
