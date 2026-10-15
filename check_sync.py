import json,re,difflib,sys
EP=sys.argv[1] if len(sys.argv)>1 else "fanged_ep2"
from align import norm_tokens
W=json.load(open(EP+".whisper.json"))["words"]
def t(s):h,m,r=s.split(":");x,ms=r.split(",");return int(h)*3600+int(m)*60+int(x)+int(ms)/1000
cues=[]
for b in open(EP+".srt",encoding="utf-8").read().strip().split("\n\n"):
    l=b.split("\n");a,e=l[1].split(" --> ");cues.append((t(a),t(e),"\n".join(l[2:])))
d=[e-s for s,e,_ in cues];ov=sum(1 for i in range(1,len(cues)) if cues[i][0]<cues[i-1][1]-1e-3)
ll=max(len(x) for _,_,c in cues for x in c.split("\n"));nl=max(c.count("\n")+1 for *_,c in cues)
print(f"cues={len(cues)} dur min={min(d):.2f} max={max(d):.2f} overlaps={ov} maxline={ll} maxlines={nl} over42={sum(1 for *_,c in cues for x in c.split(chr(10)) if len(x)>42)} under1s={sum(1 for x in d if x<1)}")
for T in (120,600,1200,1800,2400):
    c=next(c for c in cues if c[1]>T)
    ct=[x for w in c[2].split() for x in norm_tokens(w)]
    ws=[w for w in W if c[0]-3<w[1]<c[1]+3]; wt=[];wi=[]
    for w in ws:
        for x in norm_tokens(w[0]): wt.append(x);wi.append(w)
    sm=difflib.SequenceMatcher(None,ct,wt,autojunk=False);bl=[b for b in sm.get_matching_blocks() if b.size]
    ws0=wi[bl[0].b];we=wi[bl[-1].b+bl[-1].size-1]
    print(f"T={T//60}:00 cue {c[0]:.2f}-{c[1]:.2f} {c[2]!r}\n   whisper '{' '.join(w[0] for w in ws if c[0]-0.3<=w[1]<c[1])}'\n   first-word {ws0[0]}@{ws0[1]:.2f} (cue in {c[0]-ws0[1]:+.2f}s) last-word {we[0]}@{we[2]:.2f} (cue out {c[1]-we[2]:+.2f}s)")
