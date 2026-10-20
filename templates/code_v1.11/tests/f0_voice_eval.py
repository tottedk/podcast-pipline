import subprocess,numpy as np,json,os
SR=16000
def load(p):
    pcm=subprocess.run(["ffmpeg","-v","error","-i",p,"-f","s16le","-ac","1","-ar","16000","-"],capture_output=True,check=True).stdout
    return np.frombuffer(pcm,np.int16).astype(np.float32)/32768
def f0_track(x,h=320,N=640):
    out=[]
    for i in range(0,len(x)-N,h):
        f=x[i:i+N]
        if np.sqrt((f**2).mean())<0.02: out.append(0); continue
        f=f-f.mean(); ac=np.correlate(f,f,"full")[N-1:]; lo,hi=SR//400,SR//70; k=lo+np.argmax(ac[lo:hi])
        out.append(SR/k if ac[k]>0.4*ac[0] else 0)
    return np.array(out)
def med(x):
    t=f0_track(x); t=t[t>0]; return round(float(np.median(t)),1) if len(t)>10 else 0.0
D=r'C:\grok\podcast\tests\voices_extra_test'; R={}
for n in ['Clara_woman','Isla_woman','Marcus_man','Declan_man','Maya_woman']:
    R[n.split('_')[0]]=dict(gen=med(load(f'{D}\\{n}.wav')))
    pf=f'C:\\grok\\podcast\\voices_extra\\en-{n}.wav'
    if not os.path.exists(pf): pf=f'C:\\grok\\podcast\\VibeVoice-main\\demo\\voices\\en-{n}.wav'
    R[n.split('_')[0]]['prompt']=med(load(pf))
print(json.dumps(R))
json.dump(R,open(r'C:\grok\podcast\tests\v13_check\f0_eval_qcmethod.json','w'))

