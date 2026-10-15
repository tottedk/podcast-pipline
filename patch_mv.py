import re
p="make_video.py"; s=open(p,encoding="utf-8").read()
def rep(a,b):
    global s
    assert s.count(a)==1, a[:60]; s=s.replace(a,b)
# render(): transparent overlay + gradient in bg mode
rep('''def render(cue, ctx):
    im = background(cue["sec"]).convert("RGBA"); ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)''',
'''_grad = None
def gradient():
    """dark overlay for photo backgrounds: strong at top (header/plate) and bottom (subtitles), light dim in the middle"""
    global _grad
    if _grad is None:
        a = Image.new("L", (1, H))
        for y in range(H):
            top = max(0.0, 1 - y / 300); bot = max(0.0, (y - (H - 430)) / 430)
            a.putpixel((0, y), int(255 * min(0.88, 0.30 + 0.55 * top ** 1.5 + 0.62 * bot ** 1.3)))
        _grad = Image.new("RGBA", (W, H), (4, 5, 10, 0)); _grad.putalpha(a.resize((W, H)))
    return _grad.copy()

def render(cue, ctx):
    bgmode = ctx.get("bgmode")
    im = gradient() if bgmode else background(cue["sec"]).convert("RGBA")
    ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)''')
rep('''fill=(255, 255, 255, 18), outline''','''fill=(6, 8, 14, 150) if ctx.get("bgmode") else (255, 255, 255, 18), outline''')
rep('''    return Image.alpha_composite(im, ov).convert("RGB")''','''    out = Image.alpha_composite(im, ov)
    return out if bgmode else out.convert("RGB")''')
# title/section cards get a central dark panel in bg mode
rep('''    if cue["mode"] == "title":''','''    if bgmode and cue["mode"] in ("title", "section"):
        d.rounded_rectangle([160, 200, W - 160, 760], 30, fill=(4, 6, 12, 140))
    if cue["mode"] == "title":''')
# background video builder
rep('''def hms(t):''','''def build_bg_video(segs, dur, fps, out, xf=1.5, zoom=0.10):
    """segs: [(start, end, image)], covering 0..dur. Ken Burns zoom/pan per image (zoompan on a 2x source to avoid
    jitter), xfade crossfades of xf s starting at each boundary, then blur + darken. Writes an intermediate mp4."""
    ins, fl = [], []
    n = len(segs)
    for i, (s, e, img) in enumerate(segs):
        L = (e - s) + (xf if i < n - 1 else 0); N = max(2, int(math.ceil(L * fps)) + 1)
        ins += ["-loop", "1", "-framerate", str(fps), "-t", f"{L:.3f}", "-i", img]
        zin = i % 2 == 0  # alternate zoom in / out, alternate pan direction
        z = f"(1+{zoom}*on/{N})" if zin else f"(1+{zoom}-{zoom}*on/{N})"
        px = ["0.5", "0.35+0.3*on/%d" % N, "0.65-0.3*on/%d" % N][i % 3]
        py = ["0.5", "0.45+0.1*on/%d" % N, "0.55-0.1*on/%d" % N][(i // 3) % 3]
        fl.append(f"[{i}:v]scale=3840:2160:flags=lanczos,setsar=1,"
                  f"zoompan=z='{z}':x='(iw-iw/zoom)*({px})':y='(ih-ih/zoom)*({py})':d=1:s={W}x{H}:fps={fps},"
                  f"trim=duration={L:.3f},setpts=PTS-STARTPTS,format=yuv420p[v{i}]")
    cur = "v0"
    for i in range(1, n):
        fl.append(f"[{cur}][v{i}]xfade=transition=fade:duration={xf}:offset={segs[i][0]:.3f}[x{i}]"); cur = f"x{i}"
    fl.append(f"[{cur}]gblur=sigma=3,eq=brightness=-0.06:saturation=0.85,trim=duration={dur:.3f},format=yuv420p[bg]")
    fp = out + ".filter.txt"; open(fp, "w", encoding="utf-8").write(";\\n".join(fl))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stats", *ins, "-filter_complex_script", fp, "-map", "[bg]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-threads", "8", "-g", str(int(fps * 4)), out], check=True)

def load_backgrounds(path, lines_t, dur):
    """json: list of {"image", "start": sec} or {"image", "line": script line} (line needs --timings); end = next start"""
    d = json.load(open(path, encoding="utf-8")); base = os.path.dirname(os.path.abspath(path))
    items = d["backgrounds"] if isinstance(d, dict) else d; segs = []
    for it in items:
        if "start" in it: st = float(it["start"])
        else:
            if not lines_t: sys.exit("--backgrounds with 'line' entries needs --timings")
            st = lines_t[int(it["line"])]
        img = it["image"] if os.path.isabs(it["image"]) else os.path.join(base, it["image"])
        segs.append([st, img])
    segs.sort(); segs[0][0] = 0.0
    return [(s, segs[i + 1][0] if i + 1 < len(segs) else dur, img) for i, (s, img) in enumerate(segs)]

def hms(t):''')
rep('''ap.add_argument("--frames-dir");''','''ap.add_argument("--backgrounds", help="json list of {image, start (s) | line (script idx)}: Ken Burns photo backgrounds")
    ap.add_argument("--frame-times", help="comma list of seconds for extra frame grabs")
    ap.add_argument("--frames-dir");''')
rep('''    ctx = {"title": title, "topic": topic, "secs": secs, "host": a.host, "guest": a.guest}''',
'''    ctx = {"title": title, "topic": topic, "secs": secs, "host": a.host, "guest": a.guest, "bgmode": bool(a.backgrounds)}''')
rep('''    t_img = time.time() - t0
    cmd = [''','''    t_img = time.time() - t0
    if a.backgrounds:
        lt = [starts.get(i, 0.0) for i in range(len(lines))] if tim else None
        segs = load_backgrounds(a.backgrounds, lt, dur)
        print("BACKGROUNDS:"); [print(f"  {hms(s)}-{hms(e)} {os.path.basename(im)}") for s, e, im in segs]
        bgv = os.path.join(tmp, "bg.mp4"); tb = time.time(); build_bg_video(segs, dur, a.fps, bgv)
        print(f"bg video {time.time() - tb:.0f}s", flush=True)
        cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-i", bgv, "-f", "concat", "-safe", "0", "-i", lp, "-i", a.mp3,
               "-i", srt, "-i", meta, "-filter_complex", f"[1:v]fps={a.fps}[ov];[0:v][ov]overlay=format=auto:eof_action=repeat,format=yuv420p[v]",
               "-map", "[v]", "-map", "2:a", "-map", "3:s", "-map_metadata", "4", "-map_chapters", "4",
               "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-threads", "8", "-g", str(int(a.fps * 5)),
               "-c:a", "aac", "-b:a", "160k", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng", "-t", f"{dur:.3f}",
               "-movflags", "+faststart", a.out]
        subprocess.run(cmd, check=True); cmd = None
    else: cmd = [''')
rep('''    subprocess.run(cmd, check=True)
    if a.frames_dir:''','''    if cmd: subprocess.run(cmd, check=True)
    if a.frames_dir:''')
rep('''        for name, tt in (("start", 3), ("middle", vd / 2), ("end", vd - 3)):''','''        grabs = [("start", 3), ("middle", vd / 2), ("end", vd - 3)]
        if a.frame_times: grabs = [(f"f{i + 1}", float(x)) for i, x in enumerate(a.frame_times.split(","))]
        for name, tt in grabs:''')
open(p,"w",encoding="utf-8").write(s)
