p="make_video.py"; s=open(p,encoding="utf-8").read()
a=s.index("def build_bg_video("); b=s.index("def load_backgrounds(")
new='''def build_bg_video(segs, dur, fps, out, xf=1.5, zoom=0.10, jobs=3):
    """segs: [(start, end, image)], covering 0..dur. Ken Burns zoom/pan per image (zoompan on a 2x source to avoid
    jitter), xf s crossfade at each boundary, blur + darken. Each segment is encoded as its own clip (with the
    previous image's motion tail crossfaded in), then the clips are concatenated losslessly (-c copy)."""
    from concurrent.futures import ThreadPoolExecutor
    tmp = os.path.dirname(out); n = len(segs); fr = [int(round(s * fps)) for s, _, _ in segs] + [int(round(dur * fps))]
    def motion(i, off):
        N = (fr[i + 1] - fr[i]) + int(xf * fps) + 1; k = f"(on+{off})"
        z = f"(1+{zoom}*{k}/{N})" if i % 2 == 0 else f"(1+{zoom}-{zoom}*{k}/{N})"
        px = ["0.5", f"0.35+0.3*{k}/{N}", f"0.65-0.3*{k}/{N}"][i % 3]
        py = ["0.5", f"0.45+0.1*{k}/{N}", f"0.55-0.1*{k}/{N}"][(i // 3) % 3]
        return (f"scale=3840:2160:flags=lanczos,setsar=1,zoompan=z='{z}':x='(iw-iw/zoom)*({px})':"
                f"y='(ih-ih/zoom)*({py})':d=1:s={W}x{H}:fps={fps}")
    def clip(i):
        nf = fr[i + 1] - fr[i]; L = nf / fps; o = os.path.join(tmp, f"bg{i:02}.mp4")
        cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(fps), "-t", f"{L + 1:.3f}", "-i", segs[i][2]]
        post = f"gblur=sigma=3,eq=brightness=-0.06:saturation=0.85,format=yuv420p"
        if i > 0 and nf > xf * fps:
            pn = fr[i] - fr[i - 1]
            cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{xf + 1:.3f}", "-i", segs[i - 1][2]]
            fl = (f"[0:v]{motion(i, 0)},format=yuv420p[c];[1:v]{motion(i - 1, pn)},trim=end_frame={int(xf * fps) + 2},format=yuv420p[p];"
                  f"[p][c]xfade=transition=fade:duration={xf}:offset=0,{post}[v]")
        else:
            fl = f"[0:v]{motion(i, 0)},{post}[v]"
        cmd += ["-filter_complex", fl, "-map", "[v]", "-frames:v", str(nf), "-r", str(fps),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-threads", "4", "-g", str(int(fps * 4)), o]
        subprocess.run(cmd, check=True); return o
    with ThreadPoolExecutor(jobs) as ex: outs = list(ex.map(clip, range(n)))
    lp = os.path.join(tmp, "bglist.txt")
    open(lp, "w").write("".join(f"file '{os.path.abspath(o)}'\\n" for o in outs).replace("\\\\", "/"))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lp, "-c", "copy", out], check=True)

'''
s=s[:a]+new+s[b:]; open(p,"w",encoding="utf-8").write(s)
