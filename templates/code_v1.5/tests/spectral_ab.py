import sys,json,subprocess,numpy as np,re
SR=44100
def load(p):
    b=subprocess.run(["ffmpeg","-v","error","-i",p,"-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True,check=True).stdout; return np.frombuffer(b,np.float32)
def an(p):
    y=load(p); N=2048; H=1024; w=np.hanning(N); fr=np.lib.stride_tricks.sliding_window_view(y,N)[::H]
    rms=np.sqrt((fr**2).mean(1)); db=20*np.log10(rms+1e-9); sp=db>-40
    S=np.abs(np.fft.rfft(fr*w,axis=1))**2; f=np.fft.rfftfreq(N,1/SR)
    P=S[sp].mean(0); tot=P.sum()
    band=lambda a,b:10*np.log10(P[(f>=a)&(f<b)].sum()/tot)
    cen=float((P*f).sum()/tot)
    cf=(S[sp]*f).sum(1)/S[sp].sum(1)
    # sibilant frames: >50% of energy above 4k
    hi=S[:,f>=4000].sum(1)/S.sum(1); sib=sp&(hi>0.5)
    sibdb=float(10*np.log10(S[sib][:,(f>=5000)&(f<9000)].sum(1).mean()/ (S[sp].sum(1).mean()))) if sib.sum() else 0
    floor=float(np.percentile(db[db>-80],5)) if (db>-80).any() else -99
    e=subprocess.run(["ffmpeg","-hide_banner","-i",p,"-af","ebur128=peak=true","-f","null","-"],capture_output=True,text=True).stderr
    I=float(re.findall(r"I:\s+(-?[\d.]+) LUFS",e)[-1]); LRA=float(re.findall(r"LRA:\s+([\d.]+) LU",e)[-1]); pk=float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS",e)[-1])
    return dict(centroid_hz=round(cen),centroid_med_frame_hz=round(float(np.median(cf))),presence_2_4k_db=round(band(2000,4000),2),sib_5_9k_db=round(band(5000,9000),2),air_10_12k_db=round(band(10000,12000),2),above16k_db=round(band(16000,22050),2),sibframes=int(sib.sum()),sib_5_9k_in_sibframes_db=round(sibdb,2),noise_floor_p5_db=round(floor,1),I=I,LRA=LRA,TP=pk)
R={}
for n in sys.argv[1:]: R[n]=an(n); print(n,json.dumps(R[n]),flush=True)

