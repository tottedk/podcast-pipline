import json,glob,os,numpy as np,soundfile as sf,re
W=r'C:\grok\podcast\fl1b'; NM={'Host':'Carter','Guest':'Elliot','Guest2':'Clara'}
M=json.load(open(W+r'\analysis\metrics.json'))
for k,v in M['SIM'].items():
    if k.split()[0] in ('Elliot','Clara') or 'cap0.45' in k: print('SIM',k,v['wpm'],v['delta_s'])
def runs(m):
    d=np.diff(np.concatenate([[0],m.astype(np.int8),[0]])); s=np.where(d==1)[0]; e=np.where(d==-1)[0]; return list(zip(s,e-s))
A={s:dict(n32=0,n20=0,floor=[],lvl=[]) for s in NM}
for cj in sorted(glob.glob(W+r'\seg??.raw.wav.chunks\chunks.json')):
    d=os.path.dirname(cj)
    for c in json.load(open(cj,encoding='utf-8'))['chunks']:
        s=c['speakers'][0]; f=os.path.join(d,'c%03d.wav'%c['i'])
        if not os.path.exists(f): continue
        y,sr=sf.read(f,dtype='float32'); y=y if y.ndim==1 else y.mean(1); h=int(sr*0.01); n=len(y)//h
        e=20*np.log10(np.sqrt((y[:n*h].reshape(n,h)**2).mean(1))+1e-9); sl=c['clamp']['speech_db'] if 'clamp' in c else np.percentile(e,70)
        A[s]['n32']+=sum(1 for a,m in runs(e<sl-32) if m>=90); A[s]['n20']+=sum(1 for a,m in runs(e<sl-20) if m>=90)
        A[s]['floor'].append(np.percentile(e,5)-sl); A[s]['lvl'].append(sl)
for s,v in A.items(): print('CLAMPCHK',NM[s],'raw pauses>=0.9s below speech-32dB:',v['n32'],' below speech-20dB:',v['n20'],' median noise floor rel speech dB:',round(float(np.median(v['floor'])),1),' speech_db med',round(float(np.median(v['lvl'])),1))
rows={r['i']:r for r in M['rows']}
for i in (47,63,93,103,114,143):
    r=rows[i]; print('LINE',i,round(r['t'],1),'sil',[p for p in r['sil'] if p[1]>0.5],'|',r['text'][:300])
