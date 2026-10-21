import sys, subprocess, numpy as np, soundfile as sf
W=r"C:\grok\podcast\ui1"; SR=44100; EXTRA=float(sys.argv[1]); MIN=0.45
X={}; runs={}
for i in range(10):
    b=subprocess.run(["ffmpeg","-v","error","-i",f"{W}\\seg{i:02d}.mp3","-af",f"atempo={0.90/0.93:.6f}","-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True).stdout
    y=np.frombuffer(b,np.float32).copy(); X[i]=y
    h=441; n=len(y)//h; db=20*np.log10(np.sqrt((y[:n*h].reshape(n,h)**2).mean(1))+1e-9); q=db<-50
    r=[]; k=0
    while k<n:
        if q[k]:
            j=k
            while j<n and q[j]: j+=1
            if (j-k)*h/SR>=MIN and k>0 and j<n: r.append(((k+j)//2)*h)
            k=j
        else: k+=1
    runs[i]=r
N=sum(len(r) for r in runs.values()); add=min(0.6,EXTRA/max(N,1)); print("runs",N,"add per pause",round(add,3))
tot=0
for i,y in X.items():
    out=[]; p=0; z=np.zeros(int(add*SR),np.float32)
    for c in runs[i]: out+=[y[p:c],z]; p=c
    out.append(y[p:]); y2=np.concatenate(out); tot+=len(y2)/SR
    sf.write(f"{W}\\seg{i:02d}_090.wav",y2,SR)
print("speech total",round(tot,1))
