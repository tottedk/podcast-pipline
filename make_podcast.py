"""make_podcast.py - JSON script [{speaker, text}] -> mp3 using Kokoro TTS (CPU).
Usage: python make_podcast.py script.json out.mp3 [--host am_michael] [--guest bm_george] [--pause 0.45]
"""
import argparse, json, re, subprocess, time, os, tempfile
import numpy as np, soundfile as sf
from kokoro import KPipeline

SR = 24000
ap = argparse.ArgumentParser()
ap.add_argument("script"); ap.add_argument("out")
ap.add_argument("--host", default="am_michael"); ap.add_argument("--guest", default="bm_george")
ap.add_argument("--pause", type=float, default=0.45); ap.add_argument("--speed", type=float, default=1.0)
a = ap.parse_args()

lines = json.load(open(a.script, encoding="utf-8-sig"))
voices = {"host": a.host, "guest": a.guest}
pipes = {}
def pipe_for(voice):
    lang = voice[0]  # 'a' = American, 'b' = British
    if lang not in pipes: pipes[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    return pipes[lang]

t0 = time.time(); chunks = []; gap = np.zeros(int(SR * a.pause), dtype=np.float32)
for i, ln in enumerate(lines):
    voice = voices.get(ln["speaker"].strip().lower(), a.host)
    text = re.sub(r"[*_#]", "", ln["text"]).replace("\u2014", ", ")
    t = time.time()
    for _, _, audio in pipe_for(voice)(text, voice=voice, speed=a.speed):
        chunks.append(np.asarray(audio, dtype=np.float32))
    chunks.append(gap)
    print(f"[{i+1}/{len(lines)}] {ln['speaker']} ({voice}) {time.time()-t:.1f}s")
audio = np.concatenate(chunks)
wav = os.path.join(tempfile.gettempdir(), "podcast_tmp.wav")
sf.write(wav, audio, SR)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-codec:a", "libmp3lame", "-b:a", "128k", a.out], check=True)
print(f"Done: {a.out} | audio {len(audio)/SR:.1f}s | generation {time.time()-t0:.1f}s")
