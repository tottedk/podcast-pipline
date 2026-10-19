"""gen_backgrounds.py prompts.json outdir [--model ID] [--steps 30] [--w 1344 --h 768] [--seed 1234]
prompts.json: {"style": "...", "negative": "...", "images": [{"id": "c01a", "prompt": "..."}]}
Writes outdir/<id>.png (1920x1080, Lanczos upscale) and outdir/gen_log.json. Skips existing images.
Requires HIP_VISIBLE_DEVICES=1 (set here if missing). Local only."""
import os, sys, json, time, argparse
os.environ.setdefault("HIP_VISIBLE_DEVICES", "1")
import torch
from diffusers import StableDiffusionXLPipeline
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("prompts"); ap.add_argument("outdir")
ap.add_argument("--model", default="stabilityai/stable-diffusion-xl-base-1.0")
ap.add_argument("--steps", type=int, default=30); ap.add_argument("--cfg", type=float, default=6.5)
ap.add_argument("--w", type=int, default=1344); ap.add_argument("--h", type=int, default=768)
ap.add_argument("--seed", type=int, default=1234); ap.add_argument("--only", default=None)
a = ap.parse_args()
cfg = json.load(open(a.prompts, encoding="utf-8-sig"))
os.makedirs(a.outdir, exist_ok=True)
t0 = time.time()
pipe = StableDiffusionXLPipeline.from_pretrained(a.model, torch_dtype=torch.float16, variant="fp16", use_safetensors=True)
pipe.to("cuda")
pipe.vae.enable_tiling()  # fp16 VAE stability/VRAM
pipe.set_progress_bar_config(disable=True)
print(f"load {time.time()-t0:.1f}s on {torch.cuda.get_device_name(0)}", flush=True)
log = []
for i, im in enumerate(cfg["images"]):
    out = os.path.join(a.outdir, im["id"] + ".png")
    if os.path.exists(out) or (a.only and im["id"] not in a.only.split(",")):
        continue
    t = time.time()
    g = torch.Generator("cuda").manual_seed(a.seed + i)
    img = pipe(prompt=im["prompt"] + ", " + cfg["style"], negative_prompt=cfg["negative"],
               width=a.w, height=a.h, num_inference_steps=a.steps, guidance_scale=a.cfg, generator=g).images[0]
    img.resize((1920, 1080), Image.LANCZOS).save(out)
    dt = time.time() - t
    peak = torch.cuda.max_memory_allocated() / 2**30
    log.append({"id": im["id"], "sec": round(dt, 1), "peak_alloc_gb": round(peak, 2)})
    print(f"{im['id']} {dt:.1f}s peak {peak:.2f} GB", flush=True)
json.dump({"model": a.model, "steps": a.steps, "size": [a.w, a.h], "total_s": round(time.time()-t0, 1), "images": log},
          open(os.path.join(a.outdir, "gen_log.json"), "w"), indent=1)
print(f"total {time.time()-t0:.1f}s", flush=True)
