import json, glob, os, re
ev=json.load(open(r"noise_check\events.json")); ba=json.load(open(r"noise_check\before_after.json"))
tim=json.load(open(r"mm\mike_ma_ep1.timings.json"))["lines"]
off={}; c=0
for f in sorted(glob.glob(r"mm\seg??.json")): off[os.path.basename(f)[:5]]=c; c+=len(json.load(open(f)))
def locate(key,t):
    ep,seg,cc=key.rsplit("_",2); i=int(cc[1:])
    q=json.load(open(rf"mm\{seg}.qc.json")); cm=[x for x in q["chunks"] if x["i"]==i][0]
    ch=[x for x in json.load(open(rf"mm\{seg}.raw.wav.chunks\chunks.json"))["chunks"] if x["i"]==i][0]
    w=json.load(open(rf"noise_check\words\{ep}_{seg}_c{i:03d}.json"))["words"]
    L=cm["lines"]; li=max(k for k,l in enumerate(L) if l["t"][0]<=t+0.05)
    prev=[k for k,x in enumerate(w) if x[2]<=t+0.06]; wi=prev[-1]
    cum=sum(l["n"] for l in L[:li]); wo=wi-cum
    g=off[seg]+ch["first_line"]+li
    tw=tim[g]["words"]; wo2=min(max(wo,0),len(tw)-1)
    p=tw[wo2]
    return dict(g=g,line_i=li,word=w[wi][0],tim_word=p[0],ep_end=float(p[2]),spk=tim[g]["speaker"],wo=wo,nw=len(tw),ctx=" ".join(x[0] for x in tw[max(0,wo2-6):wo2+4]))
sel=[("mm_seg02_c002",29.54),("mm_seg02_c001",94.24),("mm_seg05_c003",2.42),("mm_seg06_c003",26.38)]
# control: most prominent non-voiced event in a still-flagged mm chunk
ctl=[e for e in ev if e["ep"]=="mm" and e["key"]=="mm_seg07_c001" and not(e["lf"]>=-6 and e["flat"]<0.2)]
ctl.sort(key=lambda e:-e["rel_mean_act"]); print("control cands",[(e["t"],e["act_s"],e["rel_mean_act"],e["lf"],e["flat"],e["hf"]) for e in ctl[:5]])
sel.append(("mm_seg07_c001",[e for e in ctl if abs(e["t"]-23.02)<0.02][0]["t"]))
out=[]
for k,t in sel:
    e=[x for x in ev if x["key"]==k and abs(x["t"]-t)<0.02][0]; r=locate(k,t); r.update(key=k,t=t,voice=e["voice"],act_s=e["act_s"],rel=e["rel_mean_act"],lf=e["lf"],flat=e["flat"],hf=e["hf"]); out.append(r); print(r)
json.dump(out,open(r"noise_check\clip_sel.json","w"),indent=1)



