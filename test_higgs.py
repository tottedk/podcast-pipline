import json,re,time,torch
from transformers import AutoProcessor, HiggsAudioV2ForConditionalGeneration
torch.manual_seed(42)
lines=json.load(open("script_gemma.json",encoding="utf-8"))[:4]
def clean(t): return re.sub(r"[^\x00-\x7f]","",t.replace("\u2019","'").replace("\u2014",", ").replace("*",""))
msg="\n".join(f"[SPEAKER{0 if l['speaker']=='Host' else 1}] {clean(l['text'])}" for l in lines)
mid="bosonai/higgs-audio-v2-generation-3B-base"
proc=AutoProcessor.from_pretrained(mid, device_map="cuda")
model=HiggsAudioV2ForConditionalGeneration.from_pretrained(mid, device_map="cuda", dtype=torch.bfloat16)
sysm="""You are an AI assistant designed to convert text into speech.
If the user's message includes a [SPEAKER*] tag, do not read out the tag and generate speech for the following text, using the specified voice.
If no speaker tag is present, select a suitable voice on your own."""
conv=[{"role":"system","content":[{"type":"text","text":sysm}]},
 {"role":"scene","content":[{"type":"text","text":"Audio is recorded from a quiet room."},{"type":"text","text":"SPEAKER0: masculine"},{"type":"text","text":"SPEAKER1: feminine"}]},
 {"role":"user","content":[{"type":"text","text":msg}]}]
inp=proc.apply_chat_template(conv,add_generation_prompt=True,tokenize=True,return_dict=True,sampling_rate=24000,return_tensors="pt").to(model.device)
print("loaded VRAM GB",round(torch.cuda.memory_allocated()/1e9,2),flush=True)
t=time.time()
out=model.generate(**inp,max_new_tokens=2600,do_sample=True,temperature=0.7,top_p=0.95,top_k=50)
g=time.time()-t
dec=proc.batch_decode(out); proc.save_audio(dec,"poc_higgs.wav")
import soundfile as sf; i=sf.info("poc_higgs.wav")
print("gen s",round(g,1),"audio s",round(i.duration,1),"peak VRAM GB",round(torch.cuda.max_memory_allocated()/1e9,2))
