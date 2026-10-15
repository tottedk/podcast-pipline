"""vv_generate.py - script JSON [{speaker,text}] -> WAV with VibeVoice-1.5B, chunked.
Usage: python vv_generate.py script.json out.wav [--host Carter] [--guest Frank] [--cfg 1.5] [--steps 20] [--seed 42]
       [--chunk_words 175] [--glossary glossary.json] [--pause 0.35] [--pace none] [--clean_refs 1] [--redo 2:1042,5:1042]
Defaults unchanged after the 2026-10-13 A/B (cfg 1.3, 10 steps, '...' pace, original refs were as good or better than
clean refs / cfg 1.5-1.8 / 20 steps / no '...'). Artifacts are handled downstream by qc_vv.py (redo + pause gate). Per-chunk wavs are kept in <out>.chunks/ so qc_vv.py can trigger --redo of single chunks.
"""
import argparse, json, os, re, sys, time, glob, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_clean import clean_lines   # v1.4: strip markdown marks (*x*, **x**, _x_, `x`, leading #/-/>) from the TEXT only
import numpy as np, torch, soundfile as sf
from vibevoice.modular.modeling_vibevoice_inference import VibeVoiceForConditionalGenerationInference
from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor

HERE = os.path.dirname(os.path.abspath(__file__))
VOICE_DIR = os.path.join(HERE, "VibeVoice-main", "demo", "voices")
CLEAN_DIR = os.path.join(HERE, "vv_voices_clean")
REF_AF = "highpass=f=70,afftdn=nf=-50:nr=12:tn=1,lowpass=f=11000,aresample=24000,loudnorm=I=-20:TP=-2"
def voices():
    d = {}
    for p in glob.glob(os.path.join(VOICE_DIR, "*.wav")) + glob.glob(os.path.join(HERE, "voices_extra", "*.wav")):   # v1.3: + voices_extra\ (Clara, Isla, Marcus, Declan; CC BY, see LICENSES.md)
        n = os.path.basename(p)[:-4]; short = n.split("-",1)[-1].split("_")[0]
        d[short.lower()] = p; d[n.lower()] = p
    return d
def cleaned(p):
    os.makedirs(CLEAN_DIR, exist_ok=True); q = os.path.join(CLEAN_DIR, os.path.basename(p))
    if not os.path.exists(q):
        subprocess.run(["ffmpeg","-v","error","-y","-i",p,"-af",REF_AF,"-ac","1",q], check=True)
    return q

ap = argparse.ArgumentParser()
ap.add_argument("script"); ap.add_argument("out")
ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Frank")
ap.add_argument("--guest2", default="", help="voice for speaker 'Guest2' (3-speaker scripts; v1.2)")
ap.add_argument("--cfg", type=float, default=1.3); ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--steps", type=int, default=10)
ap.add_argument("--chunk_words", type=int, default=275)  # v1.3: 275 on turn boundaries (was 175 for the 1.5B)
ap.add_argument("--pause", type=float, default=0.35)
ap.add_argument("--model", default="microsoft/VibeVoice-1.5B")
ap.add_argument("--pace", choices=["none","sentence","all"], default="sentence", help="'...' pause trick (tested: not the cause of the noise bursts)")
ap.add_argument("--clean_refs", type=int, default=0, help="denoise reference voices (tested 2026-10-13: did not remove bursts, made them harder to gate)")
ap.add_argument("--redo", default="", help="chunk:seed,... regenerate only these chunks (1-based) and reassemble")
ap.add_argument("--list_voices", action="store_true")
ap.add_argument("--glossary", default=os.path.join(HERE, "empty_glossary.json"), help="hard-term respellings applied to TTS text only; v1.3 default = empty (off); opt in with glossary.json")
a = ap.parse_args()
V = voices()
if a.list_voices:
    print("\n".join(sorted(os.path.basename(p) for p in set(V.values())))); sys.exit()

GL = json.load(open(a.glossary, encoding="utf-8-sig")).get("terms", {}) if a.glossary and os.path.exists(a.glossary) else {}
def respell(t):
    for k in sorted(GL, key=len, reverse=True):
        t = re.sub(r"\b" + re.escape(k) + r"\b", GL[k], t, flags=re.I)
    return t
def clean(t):
    t = respell(t)
    t = t.replace("\u2019","'").replace("\u2018","'").replace("\u201c",'"').replace("\u201d",'"')
    t = t.replace("\u2014",", ").replace("\u2013",", ").replace("\u2026",".").replace("*","")
    t = re.sub(r"\s+"," ",re.sub(r"[^\x00-\x7f]","",t)).strip()
    if a.pace == "none": t = re.sub(r"\.{2,}", ".", t)
    elif a.pace == "sentence": t = re.sub(r"(?<!\.)([.?!]) ", r"\1.. ", t)
    elif a.pace == "all": t = re.sub(r"(?<!\.)([.?!,]) ", r"\1.. ", t)
    return t

lines = clean_lines([l for l in json.load(open(a.script, encoding="utf-8")) if l.get("text")])[0]
chunks, cur, n = [], [], 0
for l in lines:
    w = len(l["text"].split())
    if cur and n + w > a.chunk_words: chunks.append(cur); cur, n = [], 0
    cur.append(l); n += w
if cur: chunks.append(cur)
vh, vg = V[a.host.lower()], V[a.guest.lower()]
vg2 = V[a.guest2.lower()] if a.guest2 else None
if a.clean_refs: vh, vg = cleaned(vh), cleaned(vg); vg2 = cleaned(vg2) if vg2 else None
VMAP = {"Host": vh, "Guest": vg, "Guest2": vg2}; ORDER = {"Host": 0, "Guest": 1, "Guest2": 2}
if any(l["speaker"] == "Guest2" for l in lines) and not vg2: sys.exit("script has Guest2 lines: pass --guest2 <voice>")
cdir = a.out + ".chunks"; os.makedirs(cdir, exist_ok=True)
redo = {int(k): int(s) for k, s in (x.split(":") for x in a.redo.split(",") if x)}
todo = sorted(redo) if redo else list(range(1, len(chunks)+1))
print(f"{len(lines)} lines, {sum(len(l['text'].split()) for l in lines)} words, {len(chunks)} chunk(s); Host={os.path.basename(vh)} Guest={os.path.basename(vg)}{" Guest2="+os.path.basename(vg2) if vg2 else ""} cfg={a.cfg} steps={a.steps} pace={a.pace} todo={todo}")

t0 = time.time()
proc = VibeVoiceProcessor.from_pretrained(a.model)
model = VibeVoiceForConditionalGenerationInference.from_pretrained(a.model, torch_dtype=torch.bfloat16, device_map="cuda", attn_implementation="sdpa")
model.eval(); model.set_ddpm_inference_steps(num_steps=a.steps)
print(f"model loaded {time.time()-t0:.1f}s")
sr = 24000
meta = {"chunks": [], "args": vars(a)}
mpath = os.path.join(cdir, "chunks.json")
if redo and os.path.exists(mpath): meta = json.load(open(mpath))
li = 0
for i, ch in enumerate(chunks, 1):
    if i not in todo: li += len(ch); continue
    seed = redo.get(i, a.seed)
    torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    spk = sorted(set(l["speaker"] for l in ch), key=lambda s: ORDER.get(s, 1))   # Host=Speaker 1, Guest=2, Guest2=3 (renumbered per chunk)
    idx = {s: k + 1 for k, s in enumerate(spk)}
    txt = "\n".join(f"Speaker {idx[l['speaker']]}: {clean(l['text'])}" for l in ch)
    vs = [VMAP.get(s) or vg for s in spk]
    inp = proc(text=[txt], voice_samples=[vs], padding=True, return_tensors="pt", return_attention_mask=True)
    for k, v in inp.items():
        if torch.is_tensor(v): inp[k] = v.to("cuda")
    t = time.time()
    with torch.no_grad():
        o = model.generate(**inp, max_new_tokens=None, cfg_scale=a.cfg, tokenizer=proc.tokenizer,
                           generation_config={"do_sample": False}, verbose=False, is_prefill=True)
    wav = o.speech_outputs[0].float().cpu().numpy().reshape(-1)
    sf.write(os.path.join(cdir, f"c{i:03d}.wav"), wav, sr)
    ent = {"i": i, "seed": seed, "first_line": li, "n_lines": len(ch), "text": " ".join(l["text"] for l in ch), "lines": [l["text"] for l in ch], "speakers": [l["speaker"] for l in ch], "tts_lines": [clean(l["text"]) for l in ch]}
    meta["chunks"] = [c for c in meta["chunks"] if c["i"] != i] + [ent]
    li += len(ch)
    print(f"chunk {i}/{len(chunks)} seed {seed}: {len(wav)/sr:.1f}s audio in {time.time()-t:.1f}s", flush=True)
    del o, inp; torch.cuda.empty_cache()
meta["chunks"].sort(key=lambda c: c["i"]); json.dump(meta, open(mpath, "w"), indent=1)
gap = np.zeros(int(sr*a.pause), dtype=np.float32); out = []
for i in range(1, len(chunks)+1):
    out += [sf.read(os.path.join(cdir, f"c{i:03d}.wav"), dtype="float32")[0], gap]
sf.write(a.out, np.concatenate(out), sr)
print(f"DONE {a.out} {sum(len(x) for x in out)/sr:.1f}s total {time.time()-t0:.1f}s peak VRAM {torch.cuda.max_memory_allocated()/1e9:.2f}GB")
