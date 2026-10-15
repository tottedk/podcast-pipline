"""run_soulx.py - SoulX-Podcast-1.7B on tests\three_speaker\three_speaker.json (test only, no pipeline code).
Patches torchaudio.load -> soundfile (torchaudio 2.11 CPU wheel needs torchcodec for load)."""
import os, sys, json, time, argparse
ap = argparse.ArgumentParser(); ap.add_argument("--out", default="out"); ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--cast", default="Carter,Alice,Samuel"); ap.add_argument("--fp16_flow", action="store_true"); ap.add_argument("--script", required=True); ap.add_argument("--gap", type=float, default=0.3); a = ap.parse_args()
SX = r"C:\grok\podcast\tests\soulx"; HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.join(SX, "SoulX-Podcast-main"); sys.path.insert(0, REPO)
import torch, soundfile as sf, numpy as np, torchaudio
def _load(p, *args, **kw):
    y, sr = sf.read(p, dtype="float32", always_2d=True); return torch.from_numpy(y.T.copy()), sr
torchaudio.load = _load
from soulxpodcast.utils.infer_utils import initiate_model, process_single_input
script = json.load(open(a.script, encoding="utf-8-sig"))
P = json.load(open(os.path.join(SX, "prompts", "prompts.json"), encoding="utf-8"))
cast = a.cast.split(","); role = {"Host": cast[0], "Guest": cast[1], "Guest2": cast[2]}; sid = {"Host": "S1", "Guest": "S2", "Guest2": "S3"}
prompt_wav = [os.path.join(SX, "prompts", role[r] + ".wav") for r in ("Host", "Guest", "Guest2")]
prompt_text = [P[role[r]]["text"] for r in ("Host", "Guest", "Guest2")]
text = [f"[{sid[l['speaker']]}]{l['text']}" for l in script]
os.makedirs(os.path.join(HERE, a.out), exist_ok=True)
torch.cuda.reset_peak_memory_stats(); t0 = time.time()
model, ds = initiate_model(a.seed, os.path.join(SX, "pretrained_models", "SoulX-Podcast-1.7B"), "hf", a.fp16_flow)
t_load = time.time() - t0; print(f"model loaded {t_load:.1f}s", flush=True)
data = process_single_input(ds, text, prompt_wav, prompt_text, False, ["", "", ""])
torch.cuda.synchronize(); t1 = time.time()
res = model.forward_longform(**data); torch.cuda.synchronize(); t_gen = time.time() - t1
wavs = [w.float().cpu().squeeze(0).numpy() for w in res["generated_wavs"]]
G = np.zeros(int(24000*a.gap), np.float32); y = np.concatenate([x for w in wavs for x in (w, G)][:-1]); dur = len(y) / 24000
sf.write(os.path.join(HERE, a.out, "soulx.raw.wav"), y, 24000)
t = 0; lines = []
for l, w in zip(script, wavs):
    d = len(w) / 24000; lines.append({"speaker": l["speaker"], "voice": role[l["speaker"]], "start": round(t, 3), "end": round(t + d, 3), "text": l["text"]}); t += d + a.gap
for i, w in enumerate(wavs): sf.write(os.path.join(HERE, a.out, f"line{i:02d}.wav"), w, 24000)
peak = torch.cuda.max_memory_allocated() / 2**30; peak_r = torch.cuda.max_memory_reserved() / 2**30
st = {"seed": a.seed, "cast": role, "load_s": round(t_load, 1), "gen_s": round(t_gen, 1), "audio_s": round(dur, 2), "rtf": round(t_gen / dur, 3),
      "peak_alloc_gb": round(peak, 2), "peak_reserved_gb": round(peak_r, 2), "device": torch.cuda.get_device_name(0), "torch": torch.__version__, "lines": lines}
json.dump(st, open(os.path.join(HERE, a.out, "run_stats.json"), "w"), indent=1)
print(f"DONE audio {dur:.1f}s gen {t_gen:.1f}s RTF {t_gen/dur:.2f} peak {peak:.2f} GB alloc / {peak_r:.2f} GB reserved on {st['device']}", flush=True)

