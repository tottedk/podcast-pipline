import json,re,sys
lines=json.load(open("script_gemma.json",encoding="utf-8"))[:4]
def clean(t): return re.sub(r"[^\x00-\x7f]","",t.replace("\u2019","'").replace("\u2014",", ").replace("*",""))
open(sys.argv[1],"w",encoding="utf-8").write("\n".join(f"Speaker {1 if l['speaker']=='Host' else 2}: {clean(l['text'])}" for l in lines))
