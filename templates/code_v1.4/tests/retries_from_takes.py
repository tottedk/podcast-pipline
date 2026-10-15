import json,glob
for d in ('dm_v2','ui1'):
    tot=0; gens=0; newgens=0; ch=0; avoided=[]
    for f in sorted(glob.glob(f'{d}/seg*.raw.wav.chunks/takes/takes.json')):
        T=json.load(open(f))
        for k,tk in T.items():
            ch+=1; gens+=len(tk); stop=len(tk)
            for i,t in enumerate(tk):
                if not [x for x in t['flags'] if x!='f0_drift']: stop=i+1; break
            newgens+=stop
            if stop<len(tk): avoided.append((f.split('\\')[1][:5],k,[t['flags'] for t in tk]))
    print(d,'chunks',ch,'takes generated',gens,'-> with soft f0_drift',newgens,'(retries avoided',gens-newgens,')')
    for a in avoided: print('  ',a)
