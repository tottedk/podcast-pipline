"""gen_backgrounds_flux.py prompts.json outdir [--model ID] [--steps 4] [--w 1344 --h 768] [--seed 1234] [--only ids] [--offload staged|model|seq] [--fp8 1]
Same prompts.json as gen_backgrounds.py; "negative" is ignored (FLUX has no negative prompt) -> keep "no text" in style.
Seed per image = seed + index in the full images list (same as SDXL script). Writes outdir/<id>.png (1920x1080) + gen_log.json.
fp8: transformer weights stored as float8_e4m3fn, computed in bf16 (layerwise casting) -> ~12 GB instead of 24 GB."""
import os, sys, json, time, argparse
os.environ.setdefault("HIP_VISIBLE_DEVICES", "1")
import torch
from diffusers import FluxPipeline, FluxTransformer2DModel
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("prompts"); ap.add_argument("outdir")
ap.add_argument("--model", default="black-forest-labs/FLUX.1-schnell")
ap.add_argument("--steps", type=int, default=4); ap.add_argument("--cfg", type=float, default=0.0)
ap.add_argument("--w", type=int, default=1344); ap.add_argument("--h", type=int, default=768)
ap.add_argument("--seed", type=int, default=1234); ap.add_argument("--only", default=None)
ap.add_argument("--offload", default="staged"); ap.add_argument("--fp8", type=int, default=1)
a = ap.parse_args()
cfg = json.load(open(a.prompts, encoding="utf-8-sig"))
os.makedirs(a.outdir, exist_ok=True)
t0 = time.time()
tr = FluxTransformer2DModel.from_pretrained(a.model, subfolder="transformer", torch_dtype=torch.bfloat16, low_cpu_mem_usage=True)
if a.fp8:
    tr.enable_layerwise_casting(storage_dtype=torch.float8_e4m3fn, compute_dtype=torch.bfloat16)
pipe = FluxPipeline.from_pretrained(a.model, transformer=tr, torch_dtype=torch.bfloat16)
todo = [(i, im) for i, im in enumerate(cfg["images"]) if not os.path.exists(os.path.join(a.outdir, im["id"] + ".png"))
        and not (a.only and im["id"] not in a.only.split(","))]
embeds = {}
if a.offload == "staged":  # encode all prompts with CLIP+T5 on GPU, free them, then keep transformer+VAE resident
    pipe.text_encoder.to("cuda"); pipe.text_encoder_2.to("cuda")
    with torch.no_grad():
        for i, im in todo:
            pe, ppe, _ = pipe.encode_prompt(prompt=im["prompt"] + ", " + cfg["style"], prompt_2=None, device="cuda", max_sequence_length=256)
            embeds[im["id"]] = (pe, ppe)
    pipe.text_encoder.to("cpu"); pipe.text_encoder_2.to("cpu"); torch.cuda.empty_cache()
    pipe.transformer.to("cuda"); pipe.vae.to("cuda")
elif a.offload == "seq": pipe.enable_sequential_cpu_offload()
elif a.offload == "none": pipe.to("cuda")
else: pipe.enable_model_cpu_offload()
pipe.vae.enable_tiling()
pipe.set_progress_bar_config(disable=True)
print(f"load {time.time()-t0:.1f}s on {torch.cuda.get_device_name(0)}", flush=True)
log = []
for i, im in enumerate(cfg["images"]):
    out = os.path.join(a.outdir, im["id"] + ".png")
    if os.path.exists(out) or (a.only and im["id"] not in a.only.split(",")):
        continue
    t = time.time(); torch.cuda.reset_peak_memory_stats()
    g = torch.Generator("cpu").manual_seed(a.seed + i)
    kw = dict(prompt_embeds=embeds[im["id"]][0], pooled_prompt_embeds=embeds[im["id"]][1]) if im["id"] in embeds else dict(prompt=im["prompt"] + ", " + cfg["style"], max_sequence_length=256)
    img = pipe(**kw, width=a.w, height=a.h, num_inference_steps=a.steps,
               guidance_scale=a.cfg, generator=g).images[0]
    img.resize((1920, 1080), Image.LANCZOS).save(out)
    dt = time.time() - t
    peak = torch.cuda.max_memory_allocated() / 2**30
    log.append({"id": im["id"], "sec": round(dt, 1), "peak_alloc_gb": round(peak, 2)})
    print(f"{im['id']} {dt:.1f}s peak {peak:.2f} GB", flush=True)
json.dump({"model": a.model, "steps": a.steps, "size": [a.w, a.h], "fp8": a.fp8, "offload": a.offload,
           "total_s": round(time.time()-t0, 1), "images": log}, open(os.path.join(a.outdir, "gen_log.json"), "w"), indent=1)
print(f"total {time.time()-t0:.1f}s", flush=True)

