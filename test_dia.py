import json, time, torch, re
from transformers import AutoProcessor, DiaForConditionalGeneration
lines = json.load(open("script_gemma.json", encoding="utf-8"))[:4]
def clean(t):
    t = t.replace("\u2019","'").replace("\u2014",", ").replace("*","")
    return re.sub(r"[^\x00-\x7f]", "", t)
text = " ".join(("[S1] " if l["speaker"]=="Host" else "[S2] ") + clean(l["text"]) for l in lines)
print(text)
mid = "nari-labs/Dia-1.6B-0626"
proc = AutoProcessor.from_pretrained(mid)
model = DiaForConditionalGeneration.from_pretrained(mid, torch_dtype=torch.float16).to("cuda")
inp = proc(text=[text], padding=True, return_tensors="pt").to("cuda")
t = time.time()
out = model.generate(**inp, max_new_tokens=3072, guidance_scale=3.0, temperature=1.8, top_p=0.90, top_k=45)
print("gen s", round(time.time()-t,1))
audio = proc.batch_decode(out)
proc.save_audio(audio, "poc_dia.wav")
