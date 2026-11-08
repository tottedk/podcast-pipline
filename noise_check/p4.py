import json, subprocess, os, shutil
FF=os.environ.get("FFMPEG") or "ffmpeg"
D=r"C:\grok\podcast\noise_check\clips_staging"; shutil.rmtree(D,ignore_errors=True); os.makedirs(D)
sel=json.load(open(r"noise_check\clip_sel.json")); rows=[]
def mmss(s): return f"{int(s//60)}:{s%60:05.2f}"
for n,r in enumerate(sel,1):
    _,seg,cc=r["key"].rsplit("_",2) if False else (None,)+tuple(r["key"].split("_")[1:3])
    base=f"{n}_{r['voice']}_{seg}_{cc}_t{r['t']:.1f}"
    t0=max(0,r["t"]-5)
    subprocess.run([FF,"-hide_banner","-loglevel","error","-y","-ss",f"{t0:.2f}","-t","8.5","-i",rf"mm\{seg}.raw.wav.chunks\{cc}.wav","-ac","1","-b:a","64k",os.path.join(D,base+"_raw.mp3")],check=True)
    e0=max(0,r["ep_end"]-5)
    subprocess.run([FF,"-hide_banner","-loglevel","error","-y","-ss",f"{e0:.2f}","-t","8.5","-i",r"episodes\mike_ma_ep1.mp3","-ac","1","-b:a","64k",os.path.join(D,base+"_final.mp3")],check=True)
    rows.append(f"{n}. {r['voice']} ({seg} {cc}) event at chunk t={r['t']}s, lasts {r['act_s']}s, level {r['rel']} dB re speech, tail after word '{r['word'].strip()}'. Raw chunk clip starts at chunk t={t0:.2f}s (event at 5.0 s into the clip). Final-mix clip starts at {mmss(e0)} in mike_ma_ep1.mp3 (word '{r['tim_word']}' ends at {mmss(r['ep_end'])}, i.e. 5.0 s into the clip). Context: ...{r['ctx']}...")
open(os.path.join(D,"README.txt"),"w").write("\n".join(rows)+"\n"); print("\n".join(rows)); print(os.listdir(D))
