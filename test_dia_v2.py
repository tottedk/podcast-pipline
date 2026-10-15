import json, time, torch, re, numpy as np, soundfile as sf
from transformers import AutoProcessor, DiaForConditionalGeneration
torch.manual_seed(42)
lines = json.load(open("script_gemma.json", encoding="utf-8"))[:4]
def clean(t):
    t = t.replace("\u2019","'").replace("\u2014",", ").replace("*","")
    return re.sub(r"[^\x00-\x7f]", "", t)
def chunks(t, maxw=30):
    sents = re.split(r"(?<=[.?!])\s+", t); out=[]; cur=""
    for s in sents:
        if cur and len((cur+" "+s).split())>maxw: out.append(cur); cur=s
        else: cur=(cur+" "+s).strip()
    if cur: out.append(cur)
    return out
mid = "nari-labs/Dia-1.6B-0626"
proc = AutoProcessor.from_pretrained(mid)
model = DiaForConditionalGeneration.from_pretrained(mid, torch_dtype=torch.float16).to("cuda")
kw = dict(guidance_scale=3.0, temperature=1.3, top_p=0.95, top_k=45)
ref_text = "[S1] So, where do we even start with this one? [S2] Well, it's a big book, so let's take it slowly."
t0=time.time()
inp = proc(text=[ref_text], padding=True, return_tensors="pt").to("cuda")
ref = proc.batch_decode(model.generate(**inp, max_new_tokens=1200, **kw))[0]
ref = ref.float().cpu().numpy().squeeze() if torch.is_tensor(ref) else np.asarray(ref).squeeze()
sf.write("dia_ref.wav", ref, 44100); print("ref s", len(ref)/44100)
pieces=[]
for l in lines:
    tag = "[S1] " if l["speaker"]=="Host" else "[S2] "
    for c in chunks(clean(l["text"])):
        torch.manual_seed(42)
        txt = ref_text + " " + tag + c
        inp = proc(text=[txt], audio=[ref], padding=True, return_tensors="pt").to("cuda")
        pl = proc.get_audio_prompt_len(inp["decoder_attention_mask"])
        out = model.generate(**inp, max_new_tokens=int(len(c.split())*0.5*86*1.6)+400, **kw)
        a = proc.batch_decode(out, audio_prompt_len=pl)[0]
        a = a.float().cpu().numpy().squeeze() if torch.is_tensor(a) else np.asarray(a).squeeze()
        print(tag, len(c.split()), "words ->", round(len(a)/44100,1), "s", flush=True)
        pieces += [a, np.zeros(int(0.3*44100))]
gen=time.time()-t0
audio=np.concatenate(pieces); sf.write("poc_dia_v2.wav", audio, 44100)
print("gen s", round(gen,1), "audio s", round(len(audio)/44100,1), "peak VRAM GB", round(torch.cuda.max_memory_allocated()/1e9,2))
