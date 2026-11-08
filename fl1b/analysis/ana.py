import json,os,re,subprocess,glob,time
import numpy as np
R=r'C:\grok\podcast'; W=os.path.join(R,'fl1b'); O=os.path.join(W,'analysis')
FF=os.environ.get('FFMPEG') or 'ffmpeg'
NM={'Host':'Carter','Guest':'Elliot','Guest2':'Clara'}; SPK=['Host','Guest','Guest2']
SR=16000; H=160
def dec(f):
    p=subprocess.run([FF,'-v','error','-i',f,'-ac','1','-ar',str(SR),'-f','f32le','-'],capture_output=True)
    return np.frombuffer(p.stdout,dtype=np.float32).copy()
def env(x):
    n=len(x)//H; return 20*np.log10(np.sqrt((x[:n*H].reshape(n,H).astype(np.float64)**2).mean(1))+1e-9)
def runs(m):
    d=np.diff(np.concatenate([[0],m.astype(np.int8),[0]])); s=np.where(d==1)[0]; e=np.where(d==-1)[0]; return list(zip(s,e-s))
TAG=re.compile(r'\[[^\]]*\]')
def nw(t): return len(TAG.sub(' ',t).split())
def mmss(t): return f"{int(t//60):02d}:{int(t%60):02d}"
P=[]
def pr(*a):
    s=' '.join(str(v) for v in a); P.append(s); print(s,flush=True)
import librosa
def f0st(y):
    if len(y)<SR*0.5: return np.array([])
    f,v,_=librosa.pyin(y,fmin=55,fmax=500,sr=SR,frame_length=1024,hop_length=320)
    f=f[v&np.isfinite(f)]; return f
t0=time.time()
T=json.load(open(os.path.join(W,'faultlines_01.timings.json'),encoding='utf-8')); L=T['lines']
x=dec(os.path.join(R,'episodes','faultlines_01.mp3')); e=env(x)
pr('mp3_dur',round(len(x)/SR,1),'timings_dur',round(T['duration'],1),'lines',len(L))
rows=[]
for k,l in enumerate(L):
    ws=l.get('words') or []
    if len(ws)<2: continue
    st=ws[0][1]; en=ws[-1][2]; a=int(st*100); b=int(en*100); seg=e[a:b]
    if len(seg)<30: continue
    ref=np.percentile(seg,70); sil=seg<ref-30
    rr=[(st+s/100.0,n/100.0) for s,n in runs(sil) if n>=25]
    wg=[(ws[i][2],round(ws[i+1][1]-ws[i][2],2)) for i in range(len(ws)-1) if ws[i+1][1]-ws[i][2]>=0.25]
    f=f0st(x[int(st*SR):int(en*SR)])
    rows.append(dict(i=k,spk=l['speaker'],t=st,end=en,words=nw(l['text']),span=en-st,sil=[(round(s,2),round(n,2)) for s,n in rr],wgap=wg,
                     f0=f.tolist(),tags=TAG.findall(l['text']),text=l['text']))
pr('analysed lines',len(rows),'in',int(time.time()-t0),'s')
S={}
for s in SPK:
    rs=[r for r in rows if r['spk']==s]; W_=sum(r['words'] for r in rs); sp=sum(r['span'] for r in rs)
    allp=[n for r in rs for _,n in r['sil']]
    p25=sum(allp); p5=[n for n in allp if n>0.5]; p10=[n for n in allp if n>1.0]
    wgp=[g for r in rs for _,g in r['wgap']]
    f=np.concatenate([np.array(r['f0']) for r in rs if r['f0']]); med=np.median(f); stn=12*np.log2(f/med); stn=stn[np.abs(stn)<15]
    wl=[np.std(12*np.log2(np.array(r['f0'])/med)) for r in rs if len(r['f0'])>50]
    S[s]=dict(name=NM[s],lines=len(rs),words=W_,speech_s=round(sp,1),wpm_incl=round(W_/sp*60,1),wpm_excl_gt05=round(W_/(sp-sum(p5))*60,1),wpm_artic=round(W_/(sp-p25)*60,1),
        n_gt05=len(p5),s_gt05=round(sum(p5),1),n_gt10=len(p10),s_gt10=round(sum(p10),1),per100w_gt05=round(len(p5)/W_*100,2),
        whisper_gaps_gt05=len([g for g in wgp if g>0.5]),whisper_gaps_gt10=len([g for g in wgp if g>1.0]),
        f0_med_hz=round(float(med),1),f0_std_st=round(float(np.std(stn)),2),f0_p5_95_st=round(float(np.percentile(stn,95)-np.percentile(stn,5)),2),
        f0_within_line_std_st=round(float(np.mean(wl)),2),
        hist=dict(zip(['0.25-0.5','0.5-0.7','0.7-1.0','1.0-1.5','>1.5'],np.histogram(allp,[0.25,0.5,0.7,1.0,1.5,99])[0].tolist())))
    pr(s,json.dumps(S[s]))
# Elliot worst lines
ell=[r for r in rows if r['spk']=='Guest' and r['words']>=10]
for r in ell:
    r['wpm']=r['words']/r['span']*60; ps=[n for _,n in r['sil']]; r['maxp']=max(ps) if ps else 0; r['wpm_ex']=r['words']/(r['span']-sum(p for p in ps if p>0.5))*60
    r['maxp_t']=max(r['sil'],key=lambda z:z[1])[0] if ps else None
worst=sorted(ell,key=lambda r:r['wpm'])[:10]
pr('ELLIOT WORST (mm:ss line words span wpm wpm_ex maxpause@)')
for r in worst: pr(mmss(r['t']),r['i'],r['words'],round(r['span'],1),round(r['wpm']),round(r['wpm_ex']),r['maxp'],mmss(r['maxp_t']) if r['maxp_t'] else '-','|',r['text'][:60])
allE=sorted([(n,t,r['i']) for r in rows if r['spk']=='Guest' for t,n in r['sil']],reverse=True)[:12]
pr('ELLIOT LONGEST INTERNAL PAUSES', [(mmss(t),n,i) for n,t,i in allE])
for s in ('Host','Guest2'):
    a2=sorted([(n,t,r['i']) for r in rows if r['spk']==s for t,n in r['sil']],reverse=True)[:5]; pr(NM[s],'longest',[(mmss(t),n,i) for n,t,i in a2])
# mixqc flagged lines
pr('MIXQC lines', [(i,L[i]['speaker'],mmss(L[i]['start'])) for i in (47,51,57,63,93,103,114,143,148) if i<len(L)])
# raw native pace from chunks
C={s:dict(w=0,d=0,g=0,nc=0,ncl=0,cl_s=0) for s in SPK}
for cj in sorted(glob.glob(os.path.join(W,'seg??.raw.wav.chunks','chunks.json'))):
    for c in json.load(open(cj,encoding='utf-8'))['chunks']:
        sp=set(c['speakers'])
        if len(sp)!=1: continue
        s=sp.pop(); C[s]['w']+=c['words']; C[s]['d']+=c['dur_s']; C[s]['g']+=c.get('gen_dur_s',c['dur_s']); C[s]['nc']+=1
        cl=c.get('clamp',{}).get('clamped',[]); C[s]['ncl']+=len(cl); C[s]['cl_s']+=sum(z[1]-z[2] for z in cl)
for s in SPK:
    c=C[s]; pr('RAW',NM[s],'chunks',c['nc'],'raw_wpm(clamped)',round(c['w']/c['d']*60,1),'raw_wpm(unclamped)',round(c['w']/c['g']*60,1),'x0.9=',round(c['w']/c['d']*60*0.9,1),'clamps',c['ncl'],'removed_s',round(c['cl_s'],1))
# refs
for n in ('Carter','Elliot','Clara'):
    w=os.path.join(R,'drama3_refs',n+'.wav')
    if not os.path.exists(w): pr('REF',n,'missing'); continue
    y=dec(w); ee=env(y); sp=np.where(ee>np.percentile(ee,70)-30)[0]; a,b=sp[0],sp[-1]; seg=ee[a:b]
    rr=[m/100 for s0,m in runs(seg<np.percentile(seg,70)-30) if m>=25]
    words=nw(open(w[:-4]+'.txt',encoding='utf-8').read()); dur=(b-a)/100
    f=f0st(y[a*H:b*H]); med=np.median(f); stn=12*np.log2(f/med)
    pr('REF',n,'dur',round(dur,1),'words',words,'wpm',round(words/dur*60),'pauses>=0.25',len(rr),round(sum(rr),1),'max',max(rr) if rr else 0,'f0med',round(float(med),1),'std_st',round(float(np.std(stn)),2),'p5-95',round(float(np.percentile(stn,95)-np.percentile(stn,5)),2))
# tempo compare clips
for f in sorted(glob.glob(os.path.join(R,'tests','tempo_compare','*.mp3'))):
    y=dec(f); ee=env(y); pr('TEMPOCLIP',os.path.basename(f),'dur',round(len(y)/SR,1),'silent_frac',round(float((ee<np.percentile(ee,70)-30).mean()),3))
# script punctuation per speaker
for s in SPK:
    tx=' '.join(l['text'] for l in L if l['speaker']==s); w=nw(tx)
    pr('PUNCT',NM[s],'words',w,'per100w: comma',round(tx.count(',')/w*100,1),'sent',round(len(re.findall(r'[.?!]+',tx))/w*100,1),'dash',round((tx.count('\u2014')+tx.count(' - ')+tx.count('--'))/w*100,2),'ellipsis',tx.count('...')+tx.count('\u2026'),'?',tx.count('?'),'!',tx.count('!'),'tags',len(TAG.findall(tx)),sorted(set(TAG.findall(tx)))[:8])
# simulation
SIM={}
for s in SPK:
    rs=[r for r in rows if r['spk']==s]; W_=sum(r['words'] for r in rs)
    for tn in (0.90,0.95,1.00,1.05):
        for cap in (None,0.6,0.45):
            sp=0
            for r in rs:
                k=0.9/tn; v=r['span']*k
                if cap: v-=sum(max(0,n*k-cap) for _,n in r['sil'])
                sp+=v
            SIM[f"{NM[s]} t{tn:.2f} cap{cap}"]=dict(wpm=round(W_/sp*60,1),speech_s=round(sp,1),delta_s=round(sp-sum(r['span'] for r in rs),1))
pr('SIM',json.dumps(SIM))
json.dump(dict(S=S,C=C,SIM=SIM,worst=[{k:v for k,v in r.items() if k!='f0'} for r in worst],rows=[{k:v for k,v in r.items() if k!='f0'} for r in rows]),open(os.path.join(O,'metrics.json'),'w'),indent=1)
open(os.path.join(O,'ana_out.txt'),'w',encoding='utf-8').write('\n'.join(P))
pr('done',int(time.time()-t0),'s')
