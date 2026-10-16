import json, glob, os, re
ev=json.load(open(r"noise_check\events.json")); ba=json.load(open(r"noise_check\before_after.json"))
def locate(ep, key):
    pass
EPD={"mm":"mm","ui1":"ui1"}
TIM={"mm":json.load(open(r"mm\mike_ma_ep1.timings.json"))}
print(glob.glob(r"ui1\*timings*.json"), glob.glob(r"episodes\uploaded*"))
segs=sorted(glob.glob(r"mm\seg??.json")); off={}; c=0
for f in segs:
    off[os.path.basename(f)[:5]]=c; c+=len(json.load(open(f)))
print(off, c, len(TIM["mm"]["lines"]))
cands=[]
for e in ev:
    if e["ep"]!="mm": continue
    b=ba[e["key"]]
    if b["old_flags"]==["noise"] and not b["new_flags"] and e["lf"]>=-6 and e["flat"]<0.2 and e["voice"] in("Declan","Isla"):
        cands.append(e)
cands.sort(key=lambda e:-(e["act_s"]*1+e["rel_mean_act"]/20))
seen=set()
for e in cands[:40]:
    print(e["voice"],e["key"],e["t"],"act_s",e["act_s"],"gap",e["gap"],"relmean",e["rel_mean_act"],"hf",e["hf"],"lf",e["lf"],"flat",e["flat"])
