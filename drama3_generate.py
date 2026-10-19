"""drama3_generate.py (template v1.9, 2026-10-19) - EXPERIMENTAL TTS engine: Fish Audio Drama 3 (full Q4_K_S GGUF) via audio.cpp
release v0.9.2-drama3-base-small (Windows Vulkan, device 0 = RX 7900 XT).
Drop-in replacement for vv7b_generate.py: same chunking on turn boundaries, same <out>.chunks\\cNNN.wav (24 kHz mono) + chunks.json,
same --redo i:seed,... interface, so qc_vv.py / qc_takes.py / post_segment.ps1 / align.py work unchanged.
Usage: python drama3_generate.py script.json out.wav --host Carter --guest <voice> [--guest2 <voice>] [--seed 42] [--chunk_words 150]
       [--glossary file.json] [--redo 2:1988,5:1988]   (--cfg/--steps/--pace are accepted for interface compatibility and ignored)
Voices: clone references prepared by drama3_refs.py in <Root>\\drama3_refs\\<Name>.wav + <Name>.txt (whisper transcript). Per chunk the
speakers present are numbered <|speaker:0|>, <|speaker:1|>, ... in Host, Guest, Guest2 order and passed as options.references.
Blocked: Thomas (no personal clone), Alice, Mary, Maya, Declan.
Emotion/event tags like [sighs] [laughs] [whispers] are KEPT in the text sent to Drama 3 (performed, not read aloud) and STRIPPED
from the QC texts in chunks.json (lines/text), so qc_vv.py does not expect them as words.
Offload settings (PR #927/#929): disk_experts=true, expert_cache_size=8, cpu_expert_layers=0, context_length=4096,
codec_encoder_f32_accumulation=true (Vulkan cloning fix). pin_experts is NOT used (needs ~17 GB extra RAM).
Guards: refuses to start with < --min_start_gb free RAM; kills audiocpp if free RAM drops < --min_free_mb. audio.cpp runs at IDLE
priority, one process per call (all chunks of the segment in one --request-sequence session, model loaded once), and is gone on return.
Logs per run in <out>.chunks\\drama3_metrics.json (CLI rtf per chunk, wall, VRAM peak via typeperf, commit/rss peak, min free RAM)."""
import argparse, json, os, re, sys, time, subprocess, ctypes, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_clean import clean_lines
import numpy as np, soundfile as sf
ROOT = os.environ.get("PODCAST_ROOT", r"C:\grok\podcast"); D3 = os.environ.get("DRAMA3_HOME", r"C:\grok\drama3")
BLOCKED = {"alice": "never used (v1.3 decision)", "mary": "background music in the reference clip", "thomas": "no personal voice clones",
           "maya": "excluded (sounds artificial)", "declan": "excluded (sounds machine-like)"}
ap = argparse.ArgumentParser(); ap.add_argument("script"); ap.add_argument("out")
ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default=""); ap.add_argument("--guest2", default="")
ap.add_argument("--seed", type=int, default=42); ap.add_argument("--chunk_words", type=int, default=150); ap.add_argument("--pause", type=float, default=0.35)
ap.add_argument("--redo", default=""); ap.add_argument("--glossary", default="")
ap.add_argument("--cfg", type=float, default=0); ap.add_argument("--steps", type=int, default=0); ap.add_argument("--pace", default="none")
ap.add_argument("--cli", default=os.path.join(D3, "bin", "audiocpp_cli.exe"))
ap.add_argument("--model", default=os.path.join(D3, "models", "drama-3-backbone-8bit-experts-Q4_K_S.gguf"))
ap.add_argument("--refs", default=os.path.join(ROOT, "drama3_refs"))
ap.add_argument("--cache_size", type=int, default=8); ap.add_argument("--ctx", type=int, default=4096); ap.add_argument("--threads", type=int, default=6)
ap.add_argument("--min_start_gb", type=float, default=6.0); ap.add_argument("--min_free_mb", type=float, default=1200)
a = ap.parse_args()
TAG = re.compile(r"\[[A-Za-z][A-Za-z' -]{0,30}\]")
def spoken(t): return re.sub(r"\s+([,.?!;:])", r"\1", re.sub(r"\s+", " ", TAG.sub(" ", t))).strip()
class MS(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
def free_mb():
    m = MS(); m.dwLength = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)); return m.ullAvailPhys / 2**20
_used = set(l["speaker"] for l in json.load(open(a.script, encoding="utf-8-sig")) if l.get("text"))
REF = {}
for role, who in (("Host", a.host), ("Guest", a.guest), ("Guest2", a.guest2)):
    if role not in _used: continue
    if not who: sys.exit(f"Error: the script has {role} lines but no voice was given (no default cast: use pick_cast.py / run_episode.ps1 or pass --{role.lower()})")
    if who.lower() in BLOCKED: sys.exit(f"Error: voice {who} is blocked for Drama 3: {BLOCKED[who.lower()]}")
    w, t = os.path.join(a.refs, f"{who}.wav"), os.path.join(a.refs, f"{who}.txt")
    if not (os.path.exists(w) and os.path.exists(t)): sys.exit(f"Error: no Drama 3 reference for {who} in {a.refs} (run drama3_refs.py --voices {who})")
    REF[role] = (w, open(t, encoding="utf-8").read().strip())
for p in (a.cli, a.model):
    if not os.path.exists(p): sys.exit(f"Error: missing {p}")
GL = json.load(open(a.glossary, encoding="utf-8-sig")).get("terms", {}) if a.glossary and os.path.exists(a.glossary) else {}
def clean(t):
    for k in sorted(GL, key=len, reverse=True): t = re.sub(r"\b" + re.escape(k) + r"\b", GL[k], t, flags=re.I)
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2014", ", ").replace("\u2013", ", ").replace("\u2026", ".").replace("*", "")
    return re.sub(r"\s+", " ", re.sub(r"[^\x00-\x7f]", "", t)).strip()
lines = clean_lines([l for l in json.load(open(a.script, encoding="utf-8-sig")) if l.get("text")])[0]
chunks, cur, n = [], [], 0
for l in lines:          # chunks end on turn boundaries
    w = len(spoken(l["text"]).split())
    if cur and n + w > a.chunk_words: chunks.append(cur); cur, n = [], 0
    cur.append(l); n += w
if cur: chunks.append(cur)
ORDER = {"Host": 0, "Guest": 1, "Guest2": 2}
cdir = a.out + ".chunks"; os.makedirs(cdir, exist_ok=True); odir = os.path.join(cdir, "_d3out"); os.makedirs(odir, exist_ok=True)
redo = {int(k): int(s) for k, s in (x.split(":") for x in a.redo.split(",") if x)}
todo = sorted(redo) if redo else list(range(1, len(chunks) + 1))
print(f"{len(lines)} lines, {sum(len(spoken(l['text']).split()) for l in lines)} words, {len(chunks)} chunk(s); Drama3-Q4KS Host={a.host} Guest={a.guest} Guest2={a.guest2} chunk_words={a.chunk_words} todo={todo}", flush=True)
sr = 24000; meta = {"chunks": [], "args": vars(a), "engine": "drama3"}; mpath = os.path.join(cdir, "chunks.json")
if redo and os.path.exists(mpath): meta = json.load(open(mpath))
reqs, ents, li = [], {}, 0
for i, ch in enumerate(chunks, 1):
    if i not in todo: li += len(ch); continue
    seed = redo.get(i, a.seed)
    spk = sorted(set(l["speaker"] for l in ch), key=lambda s: ORDER.get(s, 1)); idx = {s: k for k, s in enumerate(spk)}
    tts = [f"<|speaker:{idx[l['speaker']]}|> {clean(l['text'])}" for l in ch]
    refs = [{"text": f"<|speaker:{idx[s]}|> {REF[s][1]}", "audio_path": REF[s][0]} for s in spk]
    reqs.append({"id": f"c{i:03d}", "text": " ".join(tts), "seed": seed, "options": {"references": json.dumps(refs)}})
    ents[i] = {"i": i, "seed": seed, "first_line": li, "n_lines": len(ch), "text": " ".join(spoken(l["text"]) for l in ch), "lines": [spoken(l["text"]) for l in ch],
               "speakers": [l["speaker"] for l in ch], "tts_lines": tts, "engine": "drama3"}
    li += len(ch)
    for f in (os.path.join(cdir, f"c{i:03d}.wav"), os.path.join(odir, f"c{i:03d}.wav")):
        if os.path.exists(f): os.remove(f)
fm0 = free_mb()
if fm0 < a.min_start_gb * 1024: sys.exit(f"Error: free RAM {fm0/1024:.1f} GB < {a.min_start_gb} GB - not starting Drama 3")
ts = time.strftime("%Y%m%d_%H%M%S"); rq = os.path.join(cdir, f"drama3_req_{ts}.json"); json.dump({"requests": reqs}, open(rq, "w", encoding="utf-8"), indent=1)
log = os.path.join(cdir, f"drama3_{ts}.log"); so = open(log + ".stdout", "w"); se = open(log + ".stderr", "w")
cmd = [a.cli, "--task", "tts", "--family", "fish_drama3", "--backend", "vulkan", "--device", "0", "--mode", "offline", "--threads", str(a.threads),
       "--model", a.model, "--request-sequence", rq, "--out-dir", odir, "--metrics", "--log-file", log,
       "--session-option", "fish_drama3.disk_experts=true", "--session-option", f"fish_drama3.expert_cache_size={a.cache_size}",
       "--session-option", "fish_drama3.cpu_expert_layers=0", "--session-option", f"fish_drama3.context_length={a.ctx}",
       "--session-option", "fish_drama3.codec_encoder_f32_accumulation=true"]
vlog = os.path.join(cdir, f"drama3_{ts}.vram.csv"); tp = None
try: tp = subprocess.Popen(["typeperf", r"\GPU Adapter Memory(*)\Dedicated Usage", "-si", "1", "-o", vlog, "-f", "CSV", "-y"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
except Exception: tp = None
t0 = time.time(); p = subprocess.Popen(cmd, stdout=so, stderr=se, creationflags=0x00000040)   # IDLE_PRIORITY_CLASS
fmin, killed = fm0, False
while p.poll() is None:
    fm = free_mb(); fmin = min(fmin, fm)
    if fm < a.min_free_mb: print(f"RAM critically low ({fm:.0f} MB) - stopping audiocpp", flush=True); p.kill(); killed = True; break
    time.sleep(1)
rc = p.wait(); wall = time.time() - t0; so.close(); se.close()
if tp:
    time.sleep(1.2); tp.terminate()
    try: tp.wait(5)
    except Exception: tp.kill()
vpk = vbase = None
try:
    rows = [r for r in csv.reader(open(vlog, encoding="utf-8", errors="ignore"))][1:]
    vals = [max(float(x) for x in r[1:] if x.strip() not in ("", " ")) / 2**20 for r in rows if len(r) > 1 and any(x.strip() for x in r[1:])]
    if vals: vpk, vbase = round(max(vals)), round(vals[0])
except Exception: pass
M, cur_id, reached = {}, None, []
for ln in open(log + ".stdout", encoding="utf-8", errors="ignore"):
    ln = ln.strip()
    if ln.startswith("request_id="): cur_id = ln.split("=", 1)[1]
    if ln.startswith("custom_schema_output=") and '"reached_limit":true' in ln.replace(" ", ""): reached.append(cur_id)
    m = re.match(r"metrics\[(\w+)\]\.([\w.]+)=(.+)", ln)
    if m:
        try: M.setdefault(m.group(1), {})[m.group(2)] = float(m.group(3))
        except ValueError: M.setdefault(m.group(1), {})[m.group(2)] = m.group(3)
if killed or rc: sys.exit(f"Error: audiocpp_cli exit {rc}{' (killed: low RAM)' if killed else ''} - see {log}.stderr")
gen_audio = 0
for i, e in sorted(ents.items()):
    src, dst = os.path.join(odir, f"c{i:03d}.wav"), os.path.join(cdir, f"c{i:03d}.wav")
    if not os.path.exists(src): sys.exit(f"Error: Drama 3 produced no audio for chunk {i}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", dst], check=True)
    d = sf.info(dst).duration; gen_audio += d; mm = M.get(f"c{i:03d}", {})
    e["d3_rtf"] = mm.get("rtf"); e["d3_wall_s"] = round(mm.get("wall_ms", 0) / 1000, 1)
    meta["chunks"] = [c for c in meta["chunks"] if c["i"] != i] + [e]
    print(f"chunk {i}/{len(chunks)} seed {e['seed']}: {d:.1f}s audio in {e['d3_wall_s']}s (rtf {e['d3_rtf']}){' REACHED_LIMIT' if f'c{i:03d}' in reached else ''}", flush=True)
peak_fp = max([v.get("memory.peak_footprint_mb", 0) for v in M.values()] or [0]); peak_rss = max([v.get("memory.peak_rss_mb", 0) for v in M.values()] or [0])
run = {"time": ts, "todo": todo, "wall_s": round(wall, 1), "audio_s": round(gen_audio, 1), "rtf_wall": round(wall / max(gen_audio, 0.1), 2),
       "rtf_gen": {k: v.get("rtf") for k, v in M.items()}, "vram_peak_mb": vpk, "vram_base_mb": vbase, "commit_peak_mb": peak_fp, "rss_peak_mb": peak_rss,
       "sys_free_min_mb": round(fmin), "reached_limit": reached}
mf = os.path.join(cdir, "drama3_metrics.json"); runs = json.load(open(mf)) if os.path.exists(mf) else []; runs.append(run); json.dump(runs, open(mf, "w"), indent=1)
print(f"D3RUN wall {run['wall_s']}s audio {run['audio_s']}s rtf_wall {run['rtf_wall']} vram_peak {vpk} MB (base {vbase}) commit_peak {peak_fp} MB rss_peak {peak_rss} MB sys_free_min {run['sys_free_min_mb']} MB", flush=True)
meta["chunks"].sort(key=lambda c: c["i"]); json.dump(meta, open(mpath, "w"), indent=1)
gap = np.zeros(int(sr * a.pause), dtype=np.float32); o = []
for i in range(1, len(chunks) + 1):
    w = sf.read(os.path.join(cdir, f"c{i:03d}.wav"), dtype="float32")[0]; o += [w.mean(1) if w.ndim > 1 else w, gap]
sf.write(a.out, np.concatenate(o), sr)
print(f"DONE {a.out} {sum(len(x) for x in o)/sr:.1f}s total {time.time()-t0:.1f}s", flush=True)
