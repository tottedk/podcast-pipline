"""drama3_refs.py (template v1.9, 2026-10-19) - prepare Fish Audio Drama 3 clone references from the pipeline voice registry.
  venv_whisper\\Scripts\\python.exe drama3_refs.py --voices Carter,Clara,Lachlan [--max_s 20] [--root C:\\grok\\podcast]
For each voice: source = voices.json "file" (the same reference wavs VibeVoice uses) -> <root>\\drama3_refs\\<Name>.wav (mono, cut at the
last whisper word end <= --max_s, keeps the Drama 3 context small with 3 speakers) + <Name>.txt (faster-whisper large-v3-turbo transcript
of exactly that audio). Cached: redone only when the source is newer or --force. Blocked: Thomas, Alice, Mary, Maya, Declan.
v1.12: --ref_map (default <root>\\drama3_ref_map.json, {"map": {"Elliot": "Elliot_v2"}}): a mapped voice uses the hand-made VERSIONED reference
<root>\\drama3_refs\\<ref>.wav + .txt (never regenerated or overwritten here; see tools\\make_ref_v2.ps1); only its presence is checked."""
import argparse, json, os, subprocess, sys, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("--voices", required=True); ap.add_argument("--root", default=r"C:\grok\podcast")
ap.add_argument("--out", default=""); ap.add_argument("--max_s", type=float, default=20.0); ap.add_argument("--model", default="large-v3-turbo"); ap.add_argument("--force", action="store_true"); ap.add_argument("--ref_map", default="")
a = ap.parse_args(); out = a.out or os.path.join(a.root, "drama3_refs"); os.makedirs(out, exist_ok=True)
BLOCKED = {"thomas", "alice", "mary", "maya", "declan"}
V = {k.lower(): (k, v) for k, v in json.load(open(os.path.join(a.root, "voices.json"), encoding="utf-8-sig"))["voices"].items()}
M = None
_rm = a.ref_map or os.path.join(a.root, "drama3_ref_map.json")
RMAP = json.load(open(_rm, encoding="utf-8-sig")).get("map", {}) if os.path.exists(_rm) else {}
for nm in [x.strip() for x in a.voices.split(",") if x.strip()]:
    if nm.lower() in BLOCKED: sys.exit(f"Error: voice {nm} is blocked for Drama 3 cloning")
    if nm.lower() not in V: sys.exit(f"Error: voice {nm} not in voices.json")
    if RMAP.get(nm, nm) != nm:
        rn = RMAP[nm]; rw, rt = os.path.join(out, rn + ".wav"), os.path.join(out, rn + ".txt")
        if rn.lower().split("_")[0] in BLOCKED: sys.exit(f"Error: reference {rn} is blocked")
        if not (os.path.exists(rw) and os.path.exists(rt)): sys.exit(f"Error: versioned reference {rn} for {nm} missing in {out} (tools\\make_ref_v2.ps1)")
        print(f"REF {nm} -> {rn} versioned ({len(open(rt, encoding='utf-8').read().split())} words, not regenerated)"); continue
    name, ent = V[nm.lower()]; src = os.path.join(a.root, ent["file"].replace("/", os.sep)); dw, dt = os.path.join(out, name + ".wav"), os.path.join(out, name + ".txt")
    if not os.path.exists(src): sys.exit(f"Error: reference file missing: {src}")
    if not a.force and os.path.exists(dw) and os.path.exists(dt) and os.path.getmtime(dw) >= os.path.getmtime(src):
        print(f"REF {name} cached ({open(dt, encoding='utf-8').read().count(' ') + 1} words)"); continue
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768; dur = len(x) / 16000
    if M is None:
        from faster_whisper import WhisperModel
        M = WhisperModel(a.model, device="cpu", compute_type="int8", cpu_threads=6)
    segs, _ = M.transcribe(x, language="en", word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    ws = [(w.word, w.start, w.end) for s in segs for w in s.words]
    if dur <= a.max_s + 0.5: cut = dur; keep = ws
    else:
        keep = [w for w in ws if w[2] <= a.max_s]; cut = min(dur, (keep[-1][2] + 0.25) if keep else a.max_s)
    txt = "".join(w[0] for w in keep).strip()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-t", f"{cut:.2f}", "-ac", "1", "-c:a", "pcm_s16le", dw], check=True)
    open(dt, "w", encoding="utf-8").write(txt)
    print(f"REF {name} {cut:.1f}s of {dur:.1f}s, {len(txt.split())} words: {txt[:60]}...")
