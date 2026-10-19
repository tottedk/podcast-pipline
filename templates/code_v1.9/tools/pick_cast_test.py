import subprocess, json, os, collections, sys
PY=r"C:\grok\podcast\venv_vv\Scripts\python.exe"; out=os.path.join(os.environ["TEMP"],"pc_test.json")
res={}
for mode,gen in (("M,F","M,F"),("none",None)):
    cnt=collections.Counter(); male=collections.Counter(); viol=0; warns=0; mingap=999
    for seed in range(1,151):
        a=[PY,r"C:\grok\podcast\pick_cast.py","--out",out,"--host","Carter","--roles","Guest,Guest2","--seed",str(seed),"--force"]
        if gen: a+=["--genders",gen]
        r=subprocess.run(a,capture_output=True,text=True); j=json.load(open(out))
        for v in (j["guest"],j["guest2"]): cnt[v]+=1
        male[j["guest"]]+=1
        g=list(j["f0_gaps_hz"].values()); mingap=min(mingap,min(g))
        if min(g)<12: viol+=1
        if j["warnings"]: warns+=1
    res[mode]=dict(counts=dict(cnt.most_common()),guest_role=dict(male.most_common()),declan=cnt["Declan"],maya=cnt["Maya"],hugh=cnt["Hugh"],gap_violations=viol,runs_with_warnings=warns,min_gap=mingap)
    print(mode, json.dumps(res[mode]))
r=subprocess.run([PY,r"C:\grok\podcast\pick_cast.py","--out",out,"--host","Carter","--roles","Guest,Guest2","--guests","Declan,Isla","--force"],capture_output=True,text=True); print("OVERRIDE:",r.stdout.strip()[:400])
os.remove(out)
