"""drama3_generate.py (template v1.11, 2026-10-20; was v1.9) - TTS engine: Fish Audio Drama 3 (full Q4_K_S GGUF) via audio.cpp
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
Logs per run in <out>.chunks\\drama3_metrics.json (CLI rtf per chunk, wall, VRAM peak via typeperf, commit/rss peak, min free RAM).
v1.11 (Fault Lines #1 root-cause fixes, see fl1\\analysis\\ANALYSIS.md):
 - --mode turn (DEFAULT): every request holds ONE speaker only (consecutive lines of the same speaker, <= --chunk_words) and gets ONLY that
   speaker's reference as <|speaker:0|>. Reason: with several references Drama 3 (audio.cpp build) voiced 54 of 83 non-first-reference lines
   with reference 0 (Carter/Elliot); first-reference lines were 77/77 right. --mode multi = old v1.10 behaviour.
 - --chunk_words default 100 (was 150; seg07 runaway/OOM at 150).
 - runaway guard: options.max_tokens = --max_frames (default 512 frames ~ 24 s per audio.cpp text chunk, was 1024) caps a runaway step before the
   decode graph explodes; chunks with reached_limit, no output (CLI crash, e.g. Vulkan ErrorOutOfDeviceMemory) or an implausible duration are
   regenerated in a new CLI process with another seed (--gen_retries, default 2) instead of failing the whole segment.
 - pause clamp per chunk (model silences): lead silence -> <= 0.05 s, tail -> <= 0.12 s, internal silences > --max_pause (0.9 s) -> --keep_pause
   (0.6 s); silence = 10 ms frames < chunk speech level - 32 dB (word tails stay). The unclamped 44.1 kHz CLI output stays in _d3out\\."""
import argparse, json, os, re, sys, time, subprocess, ctypes, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_clean import clean_lines
import numpy as np, soundfile as sf
ROOT = os.environ.get("PODCAST_ROOT", r"C:\grok\podcast"); D3 = os.environ.get("DRAMA3_HOME", r"C:\grok\drama3")
BLOCKED = {"alice": "never used (v1.3 decision)", "mary": "background music in the reference clip", "thomas": "no personal voice clones",
           "maya": "excluded (sounds artificial)", "declan": "excluded (sounds machine-like)"}
ap = argparse.ArgumentParser(); ap.add_argument("script"); ap.add_argument("out")
ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default=""); ap.add_argument("--guest2", default="")
ap.add_argument("--seed", type=int, default=42); ap.add_argument("--chunk_words", type=int, default=100); ap.add_argument("--pause", type=float, default=0.35)
ap.add_argument("--mode", choices=["turn", "multi"], default="turn"); ap.add_argument("--max_frames", type=int, default=512); ap.add_argument("--gen_retries", type=int, default=2)
ap.add_argument("--max_pause", type=float, default=0.9); ap.add_argument("--keep_pause", type=float, default=0.6); ap.add_argument("--no_clamp", action="store_true")
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
for l in lines:          # chunks end on turn boundaries; v1.11 --mode turn: also on every speaker change (one speaker per request)
    w = len(spoken(l["text"]).split())
    if cur and (n + w > a.chunk_words or (a.mode == "turn" and l["speaker"] != cur[-1]["speaker"])): chunks.append(cur); cur, n = [], 0
    cur.append(l); n += w
if cur: chunks.append(cur)
ORDER = {"Host": 0, "Guest": 1, "Guest2": 2}
cdir = a.out + ".chunks"; os.makedirs(cdir, exist_ok=True); odir = os.path.join(cdir, "_d3out"); os.makedirs(odir, exist_ok=True)
redo = {int(k): int(s) for k, s in (x.split(":") for x in a.redo.split(",") if x)}
todo = sorted(redo) if redo else list(range(1, len(chunks) + 1))
print(f"{len(lines)} lines, {sum(len(spoken(l['text']).split()) for l in lines)} words, {len(chunks)} chunk(s); Drama3-Q4KS Host={a.host} Guest={a.guest} Guest2={a.guest2} chunk_words={a.chunk_words} mode={a.mode} max_frames={a.max_frames} todo={todo}", flush=True)
sr = 24000; meta = {"chunks": [], "args": vars(a), "engine": "drama3"}; mpath = os.path.join(cdir, "chunks.json")
if redo and os.path.exists(mpath): meta = json.load(open(mpath))
reqs, ents, li = [], {}, 0
for i, ch in enumerate(chunks, 1):
    if i not in todo: li += len(ch); continue
    seed = redo.get(i, a.seed)
    spk = sorted(set(l["speaker"] for l in ch), key=lambda s: ORDER.get(s, 1)); idx = {s: k for k, s in enumerate(spk)}
    tts = [f"<|speaker:{idx[l['speaker']]}|> {clean(l['text'])}" for l in ch]
    refs = [{"text": f"<|speaker:{idx[s]}|> {REF[s][1]}", "audio_path": REF[s][0]} for s in spk]
    reqs.append({"id": f"c{i:03d}", "text": " ".join(tts), "seed": seed, "options": {"references": json.dumps(refs), "max_tokens": a.max_frames}})
    ents[i] = {"i": i, "seed": seed, "first_line": li, "n_lines": len(ch), "text": " ".join(spoken(l["text"]) for l in ch), "lines": [spoken(l["text"]) for l in ch],
               "speakers": [l["speaker"] for l in ch], "tts_lines": tts, "engine": "drama3", "mode": a.mode,
               "ref_order": spk, "words": sum(len(spoken(l["text"]).split()) for l in ch)}
    li += len(ch)
    for f in (os.path.join(cdir, f"c{i:03d}.wav"), os.path.join(odir, f"c{i:03d}.wav")):
        if os.path.exists(f): os.remove(f)
fm0 = free_mb()
if fm0 < a.min_start_gb * 1024: sys.exit(f"Error: free RAM {fm0/1024:.1f} GB < {a.min_start_gb} GB - not starting Drama 3")
def clamp(w):
    """v1.11: shorten model silences (lead/tail/internal) - returns (wav, info)"""
    h = int(sr * 0.01); n = len(w) // h
    if a.no_clamp or n < 20: return w, {}
    e = 20 * np.log10(np.sqrt((w[:n * h].reshape(n, h) ** 2).mean(1)) + 1e-9); sp = float(np.median(e[e > -45])) if (e > -45).any() else -30.0
    q = e < sp - 32; runs = []; k = 0
    while k < n:
        if q[k]:
            j = k
            while j < n and q[j]: j += 1
            runs.append((k, j)); k = j
        else: k += 1
    keep = np.ones(len(w), bool); info = {"speech_db": round(sp, 1), "clamped": []}; xf = int(sr * 0.01)
    for k, j in runs:
        L = (j - k) * h
        if k == 0: cut = max(0, L - int(sr * 0.05)); keep[:cut] = False; info["lead_cut_s"] = round(cut / sr, 2); continue
        if j >= n: cut = max(0, len(w) - k * h - int(sr * 0.12)); keep[len(w) - cut:] = False; info["tail_cut_s"] = round(cut / sr, 2); continue
        if L > a.max_pause * sr:
            s0 = k * h + int(a.keep_pause * sr / 2); s1 = j * h - int(a.keep_pause * sr / 2); keep[s0:s1] = False
            info["clamped"].append([round(k * h / sr, 2), round(L / sr, 2), a.keep_pause])
    o = w[keep]
    return o.astype(np.float32), info
def expect_s(e): return e["words"] * 60 / 172.0     # measured Drama 3 pace (fl1: 6198 words / 2161 s raw = 172 wpm)
tried = {i: [ents[i]["seed"]] for i in ents}; runs_meta = []; pending = list(sorted(ents)); attempt = 0; gen_audio = 0
mf = os.path.join(cdir, "drama3_metrics.json")
while pending:
    rq_now = [r for r in reqs if int(r["id"][1:]) in pending]
    ts = time.strftime("%Y%m%d_%H%M%S"); rq = os.path.join(cdir, f"drama3_req_{ts}.json"); json.dump({"requests": rq_now}, open(rq, "w", encoding="utf-8"), indent=1)
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
    if killed: sys.exit(f"Error: audiocpp_cli killed (low RAM) - see {log}.stderr")
    err = open(log + ".stderr", encoding="utf-8", errors="ignore").read()
    if rc: print(f"WARNING audiocpp_cli exit {rc}{' (Vulkan out of device memory - runaway step?)' if 'OutOfDeviceMemory' in err else ''} - see {log}.stderr; checking which chunks finished", flush=True)
    again = []
    for i in pending:
        e = ents[i]; src_ = os.path.join(odir, f"c{i:03d}.wav"); dst = os.path.join(cdir, f"c{i:03d}.wav"); key = f"c{i:03d}"
        why = None
        if not os.path.exists(src_) or key not in M: why = "no output" + (f" (cli exit {rc})" if rc else "")
        elif key in reached: why = "reached_limit (runaway step)"
        if why is None:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src_, "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", dst], check=True)
            w0 = sf.read(dst, dtype="float32")[0]; w0 = w0.mean(1) if w0.ndim > 1 else w0; d0 = len(w0) / sr; ex = expect_s(e)
            if d0 > 2.3 * ex + 4 or d0 < 0.4 * ex - 1: why = f"implausible duration {d0:.1f}s vs ~{ex:.1f}s expected"
        if why and attempt < a.gen_retries:
            ns = [s for s in (1988, 3042, 4096, 777, 31337) if s not in tried[i]][0]; tried[i].append(ns)
            print(f"chunk {i}: {why} -> regenerate with seed {ns} (attempt {attempt + 1}/{a.gen_retries})", flush=True)
            for r in reqs:
                if r["id"] == key: r["seed"] = ns
            e["seed"] = ns; e.setdefault("gen_retries", []).append(why); again.append(i)
            for f in (src_, dst):
                if os.path.exists(f): os.remove(f)
            continue
        if why and not os.path.exists(dst): sys.exit(f"Error: Drama 3 produced no usable audio for chunk {i}: {why} (after {attempt} retries)")
        if why: print(f"chunk {i}: WARNING {why} - kept (retries exhausted), QC decides", flush=True); e.setdefault("gen_warn", []).append(why)
        w, ci = clamp(w0); sf.write(dst, w, sr, subtype="PCM_16"); d = len(w) / sr; gen_audio += d; mm = M.get(key, {})
        e["d3_rtf"] = mm.get("rtf"); e["d3_wall_s"] = round(mm.get("wall_ms", 0) / 1000, 1); e["gen_dur_s"] = round(d0, 2); e["dur_s"] = round(d, 2); e["clamp"] = ci
        meta["chunks"] = [c for c in meta["chunks"] if c["i"] != i] + [e]
        cl = f" clamp {d0:.1f}->{d:.1f}s ({len(ci.get('clamped', []))} long pauses)" if ci else ""
        print(f"chunk {i}/{len(chunks)} seed {e['seed']}: {d:.1f}s audio in {e['d3_wall_s']}s (rtf {e['d3_rtf']}){' REACHED_LIMIT' if key in reached else ''}{cl}", flush=True)
    peak_fp = max([v.get("memory.peak_footprint_mb", 0) for v in M.values()] or [0]); peak_rss = max([v.get("memory.peak_rss_mb", 0) for v in M.values()] or [0])
    run = {"time": ts, "todo": pending, "attempt": attempt, "rc": rc, "wall_s": round(wall, 1), "rtf_gen": {k: v.get("rtf") for k, v in M.items()}, "vram_peak_mb": vpk, "vram_base_mb": vbase,
           "commit_peak_mb": peak_fp, "rss_peak_mb": peak_rss, "sys_free_min_mb": round(fmin), "reached_limit": reached, "regenerate": again}
    runs = json.load(open(mf)) if os.path.exists(mf) else []; runs.append(run); json.dump(runs, open(mf, "w"), indent=1)
    print(f"D3RUN attempt {attempt} wall {run['wall_s']}s rc {rc} vram_peak {vpk} MB (base {vbase}) commit_peak {peak_fp} MB rss_peak {peak_rss} MB sys_free_min {run['sys_free_min_mb']} MB regenerate {again}", flush=True)
    pending = again; attempt += 1
meta["chunks"].sort(key=lambda c: c["i"]); json.dump(meta, open(mpath, "w"), indent=1)
gap = np.zeros(int(sr * a.pause), dtype=np.float32); o = []
for i in range(1, len(chunks) + 1):
    w = sf.read(os.path.join(cdir, f"c{i:03d}.wav"), dtype="float32")[0]; o += [w.mean(1) if w.ndim > 1 else w, gap]
sf.write(a.out, np.concatenate(o), sr)
print(f"DONE {a.out} {sum(len(x) for x in o)/sr:.1f}s", flush=True)
