"""vv7b_generate.py (template v1.3, 2026-10-15) - DEFAULT TTS engine: VibeVoice-7B Q8 GGUF via audio.cpp (Vulkan).
Drop-in replacement for vv_generate.py (VibeVoice-1.5B): same chunking on turn boundaries, same <out>.chunks\\cNNN.wav + chunks.json,
same --redo i:seed,... interface, so qc_vv.py / qc_takes.py work unchanged.
Usage: python vv7b_generate.py script.json out.wav [--host Carter] --guest <voice> [--guest2 <voice>] [--cfg 1.3] [--steps 10]
       [--seed 42] [--chunk_words 275] [--pace sentence] [--glossary file.json] [--redo 2:1988,5:1988]
v1.3 defaults: host Carter (guests picked per episode); ChunkWords 275 (turn boundaries; a single line longer than the limit becomes its own chunk);
glossary OFF (no respelling unless --glossary is given); voices are found by short name in VibeVoice-main\\demo\\voices\\ and voices_extra\\
(Clara, Isla, Marcus, Declan = CC BY 4.0, credit required - see voices_extra\\LICENSES.md / voices.json). Alice and Mary are blocked.
v1.3 (clarified 2026-10-15): NO default cast - only the host defaults (Carter). --guest/--guest2 are required for the roles the script uses; run_episode.ps1 / pick_cast.py choose them at random from the pool and write <Dir>\\cast.json.
audio.cpp runs at IDLE priority; needs the GPU (Vulkan device 0 = RX 7900 XT in audio.cpp numbering), ~12 GB, Ollama must be empty."""
import argparse, json, os, re, sys, time, subprocess, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_clean import clean_lines   # v1.4: strip markdown marks (*x*, **x**, _x_, `x`, leading #/-/>) from the TEXT only
import numpy as np, soundfile as sf
ROOT = os.environ.get("PODCAST_ROOT", r"C:\grok\podcast"); B = os.path.join(ROOT, "tests", "vv7b_cpp")
CLI = os.path.join(B, "bin", "audiocpp_cli.exe"); MODEL = os.path.join(B, "models", "vibevoice-7b-q8_0.gguf")
BLOCKED = {"alice": "never used (v1.3 decision)", "mary": "has background music in the reference clip", "thomas": "no personal voice clones"}
def voices():
    d = {}
    for dd in (os.path.join(ROOT, "VibeVoice-main", "demo", "voices"), os.path.join(ROOT, "voices_extra")):
        for p in glob.glob(os.path.join(dd, "*.wav")):
            n = os.path.basename(p)[:-4]; d[n.split("-", 1)[-1].split("_")[0].lower()] = p
    return d
ap = argparse.ArgumentParser(); ap.add_argument("script"); ap.add_argument("out")
ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default=""); ap.add_argument("--guest2", default="")
ap.add_argument("--cfg", type=float, default=1.3); ap.add_argument("--seed", type=int, default=42); ap.add_argument("--steps", type=int, default=10)
ap.add_argument("--chunk_words", type=int, default=275); ap.add_argument("--pause", type=float, default=0.35)
ap.add_argument("--pace", choices=["none", "sentence", "all"], default="sentence"); ap.add_argument("--redo", default="")
ap.add_argument("--glossary", default="", help="optional hard-term respellings (v1.3: off by default; write terms normally in the script)")
ap.add_argument("--list_voices", action="store_true")
a = ap.parse_args(); V = voices()
if a.list_voices: print("\n".join(sorted(V))); sys.exit()
_used = set(l["speaker"] for l in json.load(open(a.script, encoding="utf-8-sig")) if l.get("text")) if os.path.exists(a.script) else {"Host", "Guest", "Guest2"}
for role, who in (("Host", a.host), ("Guest", a.guest), ("Guest2", a.guest2)):
    if role not in _used and not who: continue
    if not who: sys.exit(f"Error: the script has {role} lines but no voice was given (no default cast: use pick_cast.py / run_episode.ps1 or pass --{role.lower()})")
    if who.lower() in BLOCKED: sys.exit(f"Error: voice {who} is blocked: {BLOCKED[who.lower()]}")
    if who.lower() not in V: sys.exit(f"Error: voice {who} not found (have: {', '.join(sorted(V))})")
GL = json.load(open(a.glossary, encoding="utf-8-sig")).get("terms", {}) if a.glossary and os.path.exists(a.glossary) else {}
def clean(t):
    for k in sorted(GL, key=len, reverse=True): t = re.sub(r"\b" + re.escape(k) + r"\b", GL[k], t, flags=re.I)
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2014", ", ").replace("\u2013", ", ").replace("\u2026", ".").replace("*", "")
    t = re.sub(r"\s+", " ", re.sub(r"[^\x00-\x7f]", "", t)).strip()
    if a.pace == "none": t = re.sub(r"\.{2,}", ".", t)
    elif a.pace == "sentence": t = re.sub(r"(?<!\.)([.?!]) ", r"\1.. ", t)
    elif a.pace == "all": t = re.sub(r"(?<!\.)([.?!,]) ", r"\1.. ", t)
    return t
lines = clean_lines([l for l in json.load(open(a.script, encoding="utf-8-sig")) if l.get("text")])[0]
chunks, cur, n = [], [], 0
for l in lines:          # chunks end on turn boundaries
    w = len(l["text"].split())
    if cur and n + w > a.chunk_words: chunks.append(cur); cur, n = [], 0
    cur.append(l); n += w
if cur: chunks.append(cur)
VMAP = {"Host": V[a.host.lower()], "Guest": V.get(a.guest.lower()), "Guest2": V.get(a.guest2.lower())}; ORDER = {"Host": 0, "Guest": 1, "Guest2": 2}
cdir = a.out + ".chunks"; os.makedirs(cdir, exist_ok=True)
redo = {int(k): int(s) for k, s in (x.split(":") for x in a.redo.split(",") if x)}
todo = sorted(redo) if redo else list(range(1, len(chunks) + 1))
print(f"{len(lines)} lines, {sum(len(l['text'].split()) for l in lines)} words, {len(chunks)} chunk(s); 7B-Q8 Host={a.host} Guest={a.guest} Guest2={a.guest2} cfg={a.cfg} steps={a.steps} chunk_words={a.chunk_words} todo={todo}", flush=True)
sr = 24000; meta = {"chunks": [], "args": vars(a)}; mpath = os.path.join(cdir, "chunks.json")
if redo and os.path.exists(mpath): meta = json.load(open(mpath))
t0 = time.time(); li = 0
for i, ch in enumerate(chunks, 1):
    if i not in todo: li += len(ch); continue
    seed = redo.get(i, a.seed)
    spk = sorted(set(l["speaker"] for l in ch), key=lambda s: ORDER.get(s, 1)); idx = {s: k + 1 for k, s in enumerate(spk)}   # Host=Speaker 1, Guest=2, Guest2=3 (renumbered per chunk)
    txt = "\n".join(f"Speaker {idx[l['speaker']]}: {clean(l['text'])}" for l in ch)
    vs = ",".join(VMAP[s] for s in spk); out = os.path.join(cdir, f"c{i:03d}.wav")
    if os.path.exists(out): os.remove(out)
    cmd = [CLI, "--task", "tts", "--family", "vibevoice", "--model", MODEL, "--backend", "vulkan", "--device", "0", "--threads", "6",
           "--seed", str(seed), "--guidance-scale", str(a.cfg), "--num-inference-steps", str(a.steps),
           "--request-option", f"voice_samples={vs}", "--text", txt, "--out", out, "--log-file", out[:-4] + ".cli.log"]
    t = time.time()
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x00000040)   # IDLE_PRIORITY_CLASS
    rc = p.wait()
    if rc or not os.path.exists(out): sys.exit(f"Error: audiocpp_cli exit {rc} on chunk {i}")
    wav, s0 = sf.read(out, dtype="float32")
    if wav.ndim > 1: wav = wav.mean(1)
    assert s0 == sr, s0
    ent = {"i": i, "seed": seed, "first_line": li, "n_lines": len(ch), "text": " ".join(l["text"] for l in ch), "lines": [l["text"] for l in ch], "speakers": [l["speaker"] for l in ch], "tts_lines": [clean(l["text"]) for l in ch]}
    meta["chunks"] = [c for c in meta["chunks"] if c["i"] != i] + [ent]; li += len(ch)
    print(f"chunk {i}/{len(chunks)} seed {seed}: {len(wav)/sr:.1f}s audio in {time.time()-t:.1f}s", flush=True)
meta["chunks"].sort(key=lambda c: c["i"]); json.dump(meta, open(mpath, "w"), indent=1)
gap = np.zeros(int(sr * a.pause), dtype=np.float32); o = []
for i in range(1, len(chunks) + 1):
    w = sf.read(os.path.join(cdir, f"c{i:03d}.wav"), dtype="float32")[0]; o += [w.mean(1) if w.ndim > 1 else w, gap]
sf.write(a.out, np.concatenate(o), sr)
print(f"DONE {a.out} {sum(len(x) for x in o)/sr:.1f}s total {time.time()-t0:.1f}s", flush=True)
