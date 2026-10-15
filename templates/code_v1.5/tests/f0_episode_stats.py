import json,glob,numpy as np
cast={'dm_v2':{'Host':'Carter','Guest':'Frank','Guest2':'Clara'},'ui1':{'Host':'Carter','Guest':'Frank','Guest2':'Maya'}}
R={}
for d,m in cast.items():
    for f in sorted(glob.glob(f'{d}/seg*.qc.json')):
        j=json.load(open(f))
        for c in j['chunks']:
            for l in c['lines']:
                if l.get('f0') and l['n']>=5: R.setdefault((m[l['speaker']],d),[]).append(l['f0'])
out={}
for (v,d),x in sorted(R.items()):
    x=np.array(x); print(v,d,'n',len(x),'median %.1f mean %.1f p10 %.1f p90 %.1f min %.1f max %.1f'%(np.median(x),x.mean(),np.percentile(x,10),np.percentile(x,90),x.min(),x.max()))
allv={}
for (v,d),x in R.items(): allv.setdefault(v,[]).extend(x)
for v,x in allv.items(): print('ALL',v,len(x),round(float(np.median(x)),1))
json.dump({k[0]+'|'+k[1]:v for k,v in R.items()},open('dm_v2/_f0_lines.json','w'))
