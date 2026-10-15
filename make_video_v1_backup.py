"""make_video.py - narrated slideshow video from podcast mp3 + script json.
Usage: python make_video.py episode.mp3 script.json out.mp4 [--title "Fanged Noumena - Episode 2"]
       [--host Carter --guest Frank --sections 8 --fps 2 --frames-dir video_frames]
Timing is estimated from character counts (no ASR). Needs Pillow + ffmpeg/ffprobe on PATH."""
import argparse, json, os, re, subprocess, sys, time, math, random, shutil, collections
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1920, 1080
FD = r"C:\Windows\Fonts"
def font(name, size):
    for n in (name, "segoeui.ttf", "arial.ttf"):
        try: return ImageFont.truetype(os.path.join(FD, n), size)
        except OSError: pass
    return ImageFont.load_default()
F = {k: font(n, s) for k, (n, s) in {
    "title": ("segoeuib.ttf", 96), "sub": ("segoeuil.ttf", 46), "hdr": ("segoeui.ttf", 30),
    "sec": ("segoeuib.ttf", 80), "quote": ("segoeuisl.ttf", 54), "plate": ("segoeuib.ttf", 40),
    "cap": ("segoeui.ttf", 40), "small": ("segoeui.ttf", 26)}.items()}
COL = {"Host": (240, 170, 60), "Guest": (80, 190, 230)}
STOP = set("""the a an and or but of to in on at for with by from as is are was were be been it its this that these those
he she they we you i me my our your his her their them not no so if then than there here what which who whom when where why how
all any some more most very just also into about over after before because while only own same such can will would should could
do does did done have has had one two three like yes well right really think thing things way much many even still back now today
let lets say says said get got going know mean kind sort point lot part first second book essay essays text land land's nick
took built though asking every time side something everything nothing people where whole always never other another making actually exactly carter frank episode listeners because through without""" .split())

def ffprobe_dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", p], text=True).strip())

def sentences(t):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', t.strip()) if s.strip()]

def chunks(t, maxw=14):
    out = []
    for s in sentences(t):
        w = s.split()
        if len(w) <= maxw: out.append(s); continue
        n = math.ceil(len(w) / maxw); k = math.ceil(len(w) / n)
        out += [" ".join(w[i:i + k]) for i in range(0, len(w), k)]
    return out

def keyquote(t):
    ss = [s for s in sentences(t) if 6 <= len(s.split()) <= 26]
    if not ss: ss = [" ".join(t.split()[:22]) + ("..." if len(t.split()) > 22 else "")]
    return max(ss, key=lambda s: sum(1 for w in re.findall(r"[A-Za-z']+", s) if w.lower() not in STOP) / (len(s.split()) ** .3))

def terms(text):
    ws = re.findall(r"[A-Za-z][A-Za-z'-]+", text)
    out = []
    for i, w in enumerate(ws):
        lw = w.lower()
        if lw in STOP or "'" in lw or len(lw) < (4 if w[0].isupper() else 6): continue
        out.append(lw)
        if i + 1 < len(ws) and w[0].isupper() and ws[i + 1][0].isupper() and ws[i + 1].lower() not in STOP:
            out.append(w + " " + ws[i + 1])
    return out

def make_sections(lines, n):
    words = [len(l["text"].split()) for l in lines]; tot = sum(words)
    bounds, acc, target = [0], 0, tot / n
    for i, w in enumerate(words):
        acc += w
        if len(bounds) < n and acc >= target * len(bounds) and i + 1 < len(lines):
            j = i + 1  # snap forward to next Host turn (max 4 lines)
            for k in range(i + 1, min(i + 5, len(lines))):
                if lines[k]["speaker"] == "Host": j = k; break
            if j > bounds[-1]: bounds.append(j)
    bounds.append(len(lines))
    groups = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1) if bounds[i + 1] > bounds[i]]
    cnts = [collections.Counter(terms(" ".join(l["text"] for l in lines[a:b]))) for a, b in groups]
    df = collections.Counter(t for c in cnts for t in c)
    secs = []
    for (a, b), c in zip(groups, cnts):
        sc = {t: v * math.log(1 + len(cnts) / df[t]) * (2.5 if " " in t or t[0].isupper() else 1) for t, v in c.items()}
        top = []
        for t, _ in sorted(sc.items(), key=lambda x: -x[1]):
            if any(t.lower() in u.lower() or u.lower() in t.lower() for u in top): continue
            top.append(t)
            if len(top) == 3: break
        secs.append({"start": a, "end": b, "title": " · ".join(x[:1].upper() + x[1:] for x in top)})
    secs[0]["title"] = "Introduction · " + secs[0]["title"].split(" · ")[0]
    return secs

def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

_bg = {}
def background(seed):
    if seed in _bg: return _bg[seed].copy()
    rnd = random.Random(seed)
    im = Image.new("RGB", (W, H), (12, 13, 20)); d = ImageDraw.Draw(im)
    for y in range(H):
        c = int(10 + 12 * y / H); d.line([(0, y), (W, y)], fill=(c, c, c + 10))
    lay = Image.new("RGB", (W, H), (0, 0, 0)); ld = ImageDraw.Draw(lay)
    hue = [(110, 40, 160), (30, 90, 160), (150, 50, 60), (30, 120, 110)][seed % 4]
    for _ in range(7):
        x, y, r = rnd.randint(0, W), rnd.randint(0, H), rnd.randint(150, 480)
        ld.ellipse([x - r, y - r, x + r, y + r], fill=tuple(int(v * rnd.uniform(.25, .55)) for v in hue))
    for _ in range(14):
        y = rnd.randint(0, H); ld.line([(0, y), (W, y + rnd.randint(-300, 300))], fill=(40, 40, 60), width=2)
    lay = lay.filter(ImageFilter.GaussianBlur(60))
    im = Image.blend(im, Image.eval(lay, lambda v: v), .5)
    im = Image.composite(im, im, Image.new("L", (W, H), 255))
    _bg[seed] = im
    return im.copy()

def center(d, y, text, f, fill, maxw=1600, gap=1.2):
    for ln in wrap(d, text, f, maxw):
        tw = d.textlength(ln, font=f); d.text(((W - tw) / 2, y), ln, font=f, fill=fill)
        y += int(f.size * gap)
    return y

def subtitle(d, text):
    ls = wrap(d, text, F["sub"], 1600)[:3]; lh = 60; y0 = H - 70 - lh * len(ls)
    d.rounded_rectangle([140, y0 - 20, W - 140, H - 50], 18, fill=(0, 0, 0, 170))
    for i, ln in enumerate(ls):
        tw = d.textlength(ln, font=F["sub"]); d.text(((W - tw) / 2, y0 + i * lh), ln, font=F["sub"], fill=(245, 245, 245))

def render(cue, ctx):
    im = background(cue["sec"]).convert("RGBA"); ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)
    sec = ctx["secs"][cue["sec"]]
    if cue["mode"] == "title":
        y = center(d, 300, ctx["title"], F["title"], (255, 255, 255))
        d.line([(W / 2 - 220, y + 20), (W / 2 + 220, y + 20)], fill=(240, 170, 60), width=4)
        y = center(d, y + 60, ctx["topic"], F["quote"], (210, 210, 225), 1500)
        center(d, y + 30, f"with {ctx['host']} (host) and {ctx['guest']} (guest)", F["hdr"], (170, 170, 190))
    elif cue["mode"] == "section":
        center(d, 260, f"PART {cue['sec'] + 1} / {len(ctx['secs'])}", F["hdr"], (240, 170, 60))
        y = center(d, 330, sec["title"], F["sec"], (255, 255, 255), 1600)
        d.line([(W / 2 - 160, y + 20), (W / 2 + 160, y + 20)], fill=(80, 190, 230), width=4)
    else:
        d.text((80, 50), ctx["title"], font=F["hdr"], fill=(200, 200, 215))
        d.text((80, 92), f"{cue['sec'] + 1}/{len(ctx['secs'])}  {sec['title']}", font=F["small"], fill=(150, 150, 170))
        # key quote card
        ql = wrap(d, "\u201c" + cue["quote"] + "\u201d", F["quote"], 1400)[:5]
        top = 300 - 0 * len(ql); d.rounded_rectangle([220, top - 50, W - 220, top + len(ql) * 70 + 40], 26,
                                                      fill=(255, 255, 255, 18), outline=(*COL[cue["spk"]], 120), width=2)
        for i, ln in enumerate(ql):
            tw = d.textlength(ln, font=F["quote"]); d.text(((W - tw) / 2, top + i * 70), ln, font=F["quote"], fill=(235, 235, 245))
    # speaker plate
    c = COL[cue["spk"]]; name = ctx["host"] + " (host)" if cue["spk"] == "Host" else ctx["guest"] + " (guest)"
    tw = d.textlength(name, font=F["plate"]); x0 = W - 120 - tw - 90; y0 = 60
    d.rounded_rectangle([x0, y0, W - 80, y0 + 76], 38, fill=(*c, 230))
    d.ellipse([x0 + 22, y0 + 24, x0 + 52, y0 + 54], fill=(20, 20, 28))
    d.text((x0 + 70, y0 + 10), name, font=F["plate"], fill=(15, 15, 22))
    subtitle(d, cue["text"])
    return Image.alpha_composite(im, ov).convert("RGB")

def srt_t(t):
    ms = int(round(t * 1000)); return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp3"); ap.add_argument("json"); ap.add_argument("out")
    ap.add_argument("--title"); ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Frank")
    ap.add_argument("--sections", type=int, default=8); ap.add_argument("--fps", type=float, default=2)
    ap.add_argument("--frames-dir"); ap.add_argument("--keep-tmp", action="store_true")
    a = ap.parse_args(); t0 = time.time()
    lines = [l for l in json.load(open(a.json, encoding="utf-8")) if l.get("text", "").strip()]
    dur = ffprobe_dur(a.mp3)
    base = os.path.splitext(os.path.basename(a.mp3))[0]
    m = re.search(r"ep(\d+)", base)
    title = a.title or (f"Fanged Noumena - Episode {m.group(1)}" if m else base)
    first = " ".join(l["text"] for l in lines[:4])
    ts = [s for s in sentences(first) if re.search(r"\btoday\b", s, re.I)]
    topic = ts[0] if ts else sentences(lines[0]["text"])[0]
    topic = re.sub(r"^(Today,?\s*)", "", topic).rstrip(".")
    topic = topic[:1].upper() + topic[1:]
    if len(topic) > 140: topic = topic[:137].rsplit(" ", 1)[0] + "..."
    secs = make_sections(lines, a.sections)
    # timing: chars + pauses per sentence/turn, scaled to audio length
    sec_of = {}
    for i, s in enumerate(secs):
        for k in range(s["start"], s["end"]): sec_of[k] = i
    raw = []
    for li, l in enumerate(lines):
        q = keyquote(l["text"])
        for j, c in enumerate(chunks(l["text"])):
            wgt = len(c) + 12 + (25 if c.endswith((".", "?", "!")) else 0) + (35 if j == 0 else 0)
            raw.append({"line": li, "spk": "Guest" if l["speaker"].lower().startswith("g") else "Host",
                        "text": c, "quote": q, "sec": sec_of[li], "w": wgt})
    scale = dur / sum(c["w"] for c in raw); t = 0.0
    for c in raw:
        c["start"] = t; t += c["w"] * scale; c["end"] = t
    sec_start = {s["start"]: i for i, s in enumerate(secs)}
    starts = {}
    for c in raw:
        starts.setdefault(c["line"], c["start"])
    for c in raw:
        if c["start"] < 9: c["mode"] = "title"
        elif c["line"] in sec_start and sec_start[c["line"]] > 0 and c["start"] - starts[c["line"]] < 6: c["mode"] = "section"
        else: c["mode"] = "slide"
    for s in secs: s["time"] = starts[s["start"]]
    # srt
    srt = os.path.splitext(a.out)[0] + ".srt"
    with open(srt, "w", encoding="utf-8") as f:
        for i, c in enumerate(raw, 1):
            f.write(f"{i}\n{srt_t(c['start'])} --> {srt_t(c['end'] - 0.05)}\n{c['text']}\n\n")
    tmp = os.path.splitext(a.out)[0] + "_tmp"; os.makedirs(tmp, exist_ok=True)
    ctx = {"title": title, "topic": topic, "secs": secs, "host": a.host, "guest": a.guest}
    lst = []
    for i, c in enumerate(raw):
        p = os.path.join(tmp, f"f{i:05}.png"); render(c, ctx).save(p, compress_level=1)
        lst.append(f"file '{os.path.abspath(p)}'\nduration {c['end'] - c['start']:.3f}\n")
    lst.append(f"file '{os.path.abspath(p)}'\n")
    lp = os.path.join(tmp, "list.txt"); open(lp, "w", encoding="utf-8").write("".join(lst).replace("\\", "/"))
    t_img = time.time() - t0
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-f", "concat", "-safe", "0", "-i", lp, "-i", a.mp3, "-i", srt,
           "-map", "0:v", "-map", "1:a", "-map", "2:s", "-vf", f"fps={a.fps},format=yuv420p",
           "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage", "-crf", "20", "-threads", "4",
           "-g", str(int(a.fps * 10)), "-c:a", "aac", "-b:a", "160k", "-c:s", "mov_text",
           "-metadata:s:s:0", "language=eng", "-shortest", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    if a.frames_dir:
        os.makedirs(a.frames_dir, exist_ok=True); vd = ffprobe_dur(a.out)
        for name, tt in (("start", 3), ("middle", vd / 2), ("end", vd - 3)):
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{tt:.2f}", "-i", a.out, "-frames:v", "1",
                            os.path.join(a.frames_dir, f"{base}_{name}.png")], check=True)
    if not a.keep_tmp: shutil.rmtree(tmp, ignore_errors=True)
    vd = ffprobe_dur(a.out)
    json.dump({"title": title, "topic": topic, "sections": secs, "cues": len(raw)},
              open(os.path.splitext(a.out)[0] + ".chapters.json", "w", encoding="utf-8"), indent=1)
    print("SECTIONS:"); [print(f"  {srt_t(s['time'])[:8]}  {s['title']}") for s in secs]
    print(f"TOPIC: {topic}\ncues={len(raw)} audio={dur:.2f}s video={vd:.2f}s diff={vd - dur:+.2f}s "
          f"size={os.path.getsize(a.out) / 1e6:.1f}MB images={t_img:.0f}s total={time.time() - t0:.0f}s")

if __name__ == "__main__":
    main()

