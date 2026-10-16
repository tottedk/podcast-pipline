"""make_video.py - narrated slideshow video from podcast mp3 + script json.
Usage: python make_video.py episode.mp3 script.json out.mp4 [--title "Uploaded Intelligence #2"] [--label "<top-right text>"] [--layout speaker|quote] [--dry-label]
v1.8: --label = discreet top-right corner text (episodes_index.py: "<Series> #<n>" for multi-episode series, the date for one-offs); default = the title. "Episode N" is never printed (stripped from the title/label).
Default layout (Oct 2026): speaker = name + pulsing level meter (from --timings, needs --backgrounds), chapter label top-left, subtitles; --layout quote = old key-quote cards.
       [--host Carter --guest Frank --sections 8 --fps 2 --frames-dir video_frames]
       [--timings episode.timings.json (from align.py)] [--chapters episode.chapters.json]
Without --timings, timing is estimated from character counts. Needs Pillow + ffmpeg/ffprobe on PATH."""
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
COL = {"Host": (240, 170, 60), "Guest": (80, 190, 230), "Guest2": (220, 50, 70)}   # host amber, guest blue, guest2 crimson (v1.2)
def spk_of(s):
    s = s.lower().replace(" ", "")
    return "Guest2" if s in ("guest2", "speaker3") else ("Guest" if s.startswith("g") else "Host")
def spk_name(ctx, k): return {"Host": ctx["host"], "Guest": ctx["guest"], "Guest2": ctx.get("guest2") or "Guest 2"}[k]
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

_grad = None
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
    ov = Image.new("RGBA", (W, H)); d = ImageDraw.Draw(ov)
    sec = ctx["secs"][cue["sec"]]
    if bgmode and cue["mode"] in ("title", "section"):
        d.rounded_rectangle([160, 200, W - 160, 760], 30, fill=(4, 6, 12, 140))
    if cue["mode"] == "title":
        y = center(d, 300, ctx["title"], F["title"], (255, 255, 255))
        d.line([(W / 2 - 220, y + 20), (W / 2 + 220, y + 20)], fill=(240, 170, 60), width=4)
        y = center(d, y + 60, ctx["topic"], F["quote"], (210, 210, 225), 1500)
        center(d, y + 30, (f"with {ctx['host']} (host), {ctx['guest']} and {ctx['guest2']} (guests)" if ctx.get("guest2") else f"with {ctx['host']} (host) and {ctx['guest']} (guest)"), F["hdr"], (170, 170, 190))
    elif cue["mode"] == "section":
        center(d, 260, f"PART {cue['sec'] + 1} / {len(ctx['secs'])}", F["hdr"], (240, 170, 60))
        y = center(d, 330, sec["title"], F["sec"], (255, 255, 255), 1600)
        d.line([(W / 2 - 160, y + 20), (W / 2 + 160, y + 20)], fill=(80, 190, 230), width=4)
    elif ctx.get("layout") == "speaker":
        # discreet chapter label top-left, no centre quote
        d.text((70, 46), f"{cue['sec'] + 1}/{len(ctx['secs'])}  \u00b7  {sec['title']}", font=F["small"], fill=(225, 225, 235, 200))
        d.line([(70, 84), (70 + min(520, d.textlength(sec['title'], font=F['small']) + 90), 84)], fill=(240, 170, 60, 150), width=2)
        if ctx.get("label"): d.text((W - 70 - d.textlength(ctx["label"], font=F["small"]), 46), ctx["label"], font=F["small"], fill=(190, 190, 205, 160))
    else:
        d.text((80, 50), ctx["title"], font=F["hdr"], fill=(200, 200, 215))
        d.text((80, 92), f"{cue['sec'] + 1}/{len(ctx['secs'])}  {sec['title']}", font=F["small"], fill=(150, 150, 170))
        # key quote card
        ql = wrap(d, "\u201c" + cue["quote"] + "\u201d", F["quote"], 1400)[:5]
        top = 300 - 0 * len(ql); d.rounded_rectangle([220, top - 50, W - 220, top + len(ql) * 70 + 40], 26,
                                                      fill=(6, 8, 14, 150) if ctx.get("bgmode") else (255, 255, 255, 18), outline=(*COL[cue["spk"]], 120), width=2)
        for i, ln in enumerate(ql):
            tw = d.textlength(ln, font=F["quote"]); d.text(((W - tw) / 2, top + i * 70), ln, font=F["quote"], fill=(235, 235, 245))
    if ctx.get("layout") == "speaker":
        if cue["mode"] != "title":
            c = COL[cue["spk"]]; y0 = SPK_Y
            nm = spk_name(ctx, cue["spk"]); role = "host" if cue["spk"] == "Host" else "guest"
            d.rounded_rectangle([60, y0, 60 + IND_W + 40 + d.textlength(nm, font=F["plate"]) + 30 + d.textlength(role, font=F["small"]) + 34, y0 + IND_H + 16], 20, fill=(6, 8, 14, 165))
            d.rectangle([60, y0 + 8, 65, y0 + IND_H + 8], fill=(*c, 255))
            x = 60 + IND_W + 40; d.text((x, y0 + 6), nm, font=F["plate"], fill=(*c, 255))
            d.text((x + d.textlength(nm, font=F["plate"]) + 16, y0 + 20), role, font=F["small"], fill=(200, 200, 210, 220))
        if ctx.get("burn"): subtitle(d, cue["text"])
        out = Image.alpha_composite(im, ov)
        return out if bgmode else out.convert("RGB")
    # speaker plate
    c = COL[cue["spk"]]; name = spk_name(ctx, cue["spk"]) + (" (host)" if cue["spk"] == "Host" else " (guest)")
    tw = d.textlength(name, font=F["plate"]); x0 = W - 120 - tw - 90; y0 = 60
    d.rounded_rectangle([x0, y0, W - 80, y0 + 76], 38, fill=(*c, 230))
    d.ellipse([x0 + 22, y0 + 24, x0 + 52, y0 + 54], fill=(20, 20, 28))
    d.text((x0 + 70, y0 + 10), name, font=F["plate"], fill=(15, 15, 22))
    if ctx.get("burn"): subtitle(d, cue["text"])
    out = Image.alpha_composite(im, ov)
    return out if bgmode else out.convert("RGB")

IND_W, IND_H, SPK_Y = 150, 56, 1080 - 300
def build_indicator(tim, lines, dur, fps, tmp):
    """pulsing level bars driven by aligned word timings; returns concat list path (deduped frames)"""
    import hashlib
    d0 = os.path.join(tmp, "ind"); os.makedirs(d0, exist_ok=True)
    words = sorted((w[1], w[2], spk_of(l["speaker"])) for l, t in zip(lines, tim) for w in t["words"])
    starts = sorted((t["words"][0][1] if t["words"] else 0, spk_of(l["speaker"])) for l, t in zip(lines, tim))
    nb, step = 7, 1.0 / fps; cache = {}; lst = []; prev = None; acc = 0.0; wi = 0; si = 0; spk = "Host"; lv = [0.0] * nb
    n = int(dur * fps) + 1
    for k in range(n):
        t = k * step
        while si < len(starts) and starts[si][0] <= t: spk = starts[si][1]; si += 1
        while wi < len(words) and words[wi][1] < t - 0.05: wi += 1
        act = wi < len(words) and words[wi][0] - 0.05 <= t <= words[wi][1] + 0.05
        tgt = []
        for b in range(nb):
            if act:
                h = int(hashlib.md5(f"{k}:{b}".encode()).hexdigest()[:4], 16) / 65535
                env = 0.55 + 0.45 * math.sin(math.pi * min(1, max(0, (t - words[wi][0]) / max(0.05, words[wi][1] - words[wi][0]))))
                tgt.append((0.25 + 0.75 * h) * env * (1 - 0.35 * abs(b - nb // 2) / (nb // 2)))
            else: tgt.append(0.0)
        lv = [max(x, y * 0.55) if x >= y else y * 0.55 + x * 0.45 for x, y in zip(tgt, lv)]
        key = (spk, tuple(int(x * 12) for x in lv))
        if key != prev:
            if prev is not None: lst.append(f"file '{cache[prev]}'\nduration {acc:.3f}\n")
            if key not in cache:
                im = Image.new("RGBA", (IND_W, IND_H), (0, 0, 0, 0)); dd = ImageDraw.Draw(im); c = COL[key[0]]
                bw = (IND_W - 20) / nb
                for b, q in enumerate(key[1]):
                    hh = max(6, int((IND_H - 8) * q / 12)); x0 = 10 + b * bw
                    dd.rounded_rectangle([x0 + 3, (IND_H - hh) / 2, x0 + bw - 3, (IND_H + hh) / 2], 4, fill=(*c, 240 if q else 120))
                p = os.path.abspath(os.path.join(d0, f"i{len(cache):05}.png")); im.save(p); cache[key] = p
            prev = key; acc = 0.0
        acc += step
    lst.append(f"file '{cache[prev]}'\nduration {acc:.3f}\n"); lst.append(f"file '{cache[prev]}'\n")
    lp = os.path.join(tmp, "ind.txt"); open(lp, "w").write("".join(lst).replace("\\", "/"))
    print(f"indicator: {len(cache)} unique frames", flush=True)
    return lp

def srt_t(t):
    ms = int(round(t * 1000)); return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"

def split2(text, maxc=42):
    """balanced 1-2 line split, each <= maxc chars when possible"""
    if len(text) <= maxc: return text
    ws = text.split(); best = None
    for k in range(1, len(ws)):
        a, b = " ".join(ws[:k]), " ".join(ws[k:])
        sc = max(len(a), len(b)) + (0 if max(len(a), len(b)) <= maxc else 100)
        if best is None or sc < best[0]: best = (sc, a + "\n" + b)
    return best[1]

def timed_chunks(words, maxc=78, maxdur=5.6):
    """words [[w,s,e],...] of one script line -> list of (text, start, end)"""
    out, cur = [], []
    def flush():
        if cur: out.append((" ".join(w[0] for w in cur), cur[0][1], cur[-1][2])); cur.clear()
    for w in words:
        txt = " ".join(x[0] for x in cur + [w])
        if cur and (len(txt) > maxc or w[2] - cur[0][1] > maxdur):
            # back off to the last comma/semicolon in the second half if possible
            cut = None
            for k in range(len(cur) - 1, 0, -1):
                if cur[k][0].endswith((",", ";", ":")) and len(" ".join(x[0] for x in cur[:k + 1])) >= 30: cut = k + 1; break
            if cut and cut < len(cur):
                rest = cur[cut:]; del cur[cut:]; flush(); cur.extend(rest)
            else: flush()
        cur.append(w)
        if w[0].endswith((".", "?", "!")) and len(" ".join(x[0] for x in cur)) >= 20: flush()
    flush()
    # merge very short/fast fragments into a neighbour if the result still fits (<= 84 chars, <= 6 s)
    i = 0
    while len(out) > 1 and i < len(out):
        t, s, e = out[i]
        if len(t) < 14 or e - s < 0.8:
            for j in ((i - 1, i), (i, i + 1)):
                if j[0] >= 0 and j[1] < len(out):
                    a, b = out[j[0]], out[j[1]]
                    if len(a[0]) + len(b[0]) < 84 and b[2] - a[1] <= 6:
                        out[j[0]:j[1] + 1] = [(a[0] + " " + b[0], a[1], b[2])]; break
            else: i += 1; continue
            i = max(0, i - 1); continue
        i += 1
    return out

def load_chapters(path, lines, timed_starts):
    d = json.load(open(path, encoding="utf-8"))
    secs = d["sections"] if isinstance(d, dict) else d
    secs = sorted(secs, key=lambda s: s["start"]); out = []
    for i, s in enumerate(secs):
        st = 0 if i == 0 else int(s["start"]); en = int(secs[i + 1]["start"]) if i + 1 < len(secs) else len(lines)
        out.append({"start": st, "end": en, "title": s["title"]})
    return out, (d.get("title"), d.get("topic")) if isinstance(d, dict) else (None, None)

def build_bg_video(segs, dur, fps, out, xf=1.5, zoom=0.10, jobs=3):
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
    open(lp, "w").write("".join(f"file '{os.path.abspath(o)}'\n" for o in outs).replace("\\", "/"))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lp, "-c", "copy", out], check=True)

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

def hms(t):
    t = int(t); return f"{t // 3600}:{t // 60 % 60:02}:{t % 60:02}" if t >= 3600 else f"{t // 60:02}:{t % 60:02}"

def no_ep(t):
    """v1.8: never print "Episode N" (title/label): strips a trailing ", Episode 1" / "- Episode 1" / "(v2)" """
    t = re.sub(r"\s*\(v\d+\)\s*$", "", (t or "").strip())
    return re.sub(r"\s*[,:;\u2013\u2014-]?\s*\b(?:episode|ep\.?)\s*#?\d+\b\s*$", "", t, flags=re.I).strip(" ,:;-\u2013\u2014")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mp3"); ap.add_argument("json"); ap.add_argument("out")
    ap.add_argument("--title"); ap.add_argument("--label"); ap.add_argument("--dry-label", action="store_true", help="print the resolved title/label/topic as JSON and exit (no rendering)"); ap.add_argument("--topic"); ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Frank")
    ap.add_argument("--guest2", default="", help="name of the 2nd guest (script speaker 'Guest2'; crimson plate)")
    ap.add_argument("--burn-subs", action="store_true", help="burn subtitles into the frames + soft mov_text track (pre-v1.2 default); default: separate .srt only")
    ap.add_argument("--sections", type=int, default=8); ap.add_argument("--fps", type=float, default=2)
    ap.add_argument("--timings", help="timings json from align.py (exact word times)")
    ap.add_argument("--chapters", help="chapters json: {sections:[{start:<line index>, title}]} or a list of those")
    ap.add_argument("--backgrounds", help="json list of {image, start (s) | line (script idx)}: Ken Burns photo backgrounds")
    ap.add_argument("--frame-times", help="comma list of seconds for extra frame grabs")
    ap.add_argument("--layout", choices=["speaker", "quote"], default="speaker", help="speaker (default): name + level meter, corner chapter, subtitles; quote: old key-quote cards")
    ap.add_argument("--frames-dir"); ap.add_argument("--frame-suffix", default=""); ap.add_argument("--keep-tmp", action="store_true")
    a = ap.parse_args(); t0 = time.time()
    lines = [l for l in json.load(open(a.json, encoding="utf-8")) if l.get("text", "").strip()]
    dur = ffprobe_dur(a.mp3)
    base = os.path.splitext(os.path.basename(a.mp3))[0]
    title = a.title or re.sub(r"_ep\d+(_v\d+)?$", "", base).replace("_", " ").title()   # v1.8: no hard-coded series / "Episode N"
    first = " ".join(l["text"] for l in lines[:4])
    ts = [s for s in sentences(first) if re.search(r"\btoday\b", s, re.I)]
    topic = ts[0] if ts else sentences(lines[0]["text"])[0]
    topic = re.sub(r"^(Today,?\s*)", "", topic).rstrip(".")
    topic = topic[:1].upper() + topic[1:]
    if len(topic) > 140: topic = topic[:137].rsplit(" ", 1)[0] + "..."
    tim = None
    if a.timings:
        tim = json.load(open(a.timings, encoding="utf-8"))["lines"]
        if len(tim) != len(lines) or any(x["text"] != l["text"] for x, l in zip(tim, lines)):
            sys.exit("timings file does not match the script json (re-run align.py)")
    if a.chapters:
        secs, (ct, ctp) = load_chapters(a.chapters, lines, None)
        title = a.title or ct or title; topic = a.topic or ctp or topic
    else:
        secs = make_sections(lines, a.sections)
    if a.topic: topic = a.topic
    title = no_ep(title); label = no_ep(a.label) if a.label is not None else title   # v1.8: corner label (top right) separate from the title card
    if a.dry_label:
        print(json.dumps({"title": title, "label": label, "topic": topic}, ensure_ascii=True)); return
    sec_of = {}
    for i, s in enumerate(secs):
        for k in range(s["start"], s["end"]): sec_of[k] = i
    raw = []
    if tim:
        for li, (l, t) in enumerate(zip(lines, tim)):
            q = keyquote(l["text"]); spk = spk_of(l["speaker"])
            for txt, s, e in timed_chunks(t["words"]):
                raw.append({"line": li, "spk": spk, "text": split2(txt), "quote": q, "sec": sec_of[li], "s0": s, "e0": e})
        # display times: lead-in 0.1 s, hold 0.4 s, 1-6 s, never overlapping
        for i, c in enumerate(raw):
            nxt = raw[i + 1]["s0"] - 0.1 if i + 1 < len(raw) else dur
            prev = raw[i - 1]["end"] if i else 0.0
            c["start"] = max(prev, c["s0"] - 0.1)
            end = max(c["e0"] + 0.4, c["start"] + 1.0)
            c["end"] = max(min(end, c["start"] + 6.0, nxt, dur), c["start"] + 0.3)
    else:
        for li, l in enumerate(lines):
            q = keyquote(l["text"])
            for j, c in enumerate(chunks(l["text"])):
                wgt = len(c) + 12 + (25 if c.endswith((".", "?", "!")) else 0) + (35 if j == 0 else 0)
                raw.append({"line": li, "spk": spk_of(l["speaker"]),
                            "text": c, "quote": q, "sec": sec_of[li], "w": wgt})
        scale = dur / sum(c["w"] for c in raw); t = 0.0
        for c in raw:
            c["start"] = t; t += c["w"] * scale; c["end"] = t - 0.05
    sec_start = {s["start"]: i for i, s in enumerate(secs)}
    starts = {}
    for c in raw: starts.setdefault(c["line"], c["start"])
    for c in raw:
        if c["start"] < 9: c["mode"] = "title"
        elif c["line"] in sec_start and sec_start[c["line"]] > 0 and c["start"] - starts[c["line"]] < (4 if a.layout == "speaker" else 6): c["mode"] = "section"
        else: c["mode"] = "slide"
    for i, s in enumerate(secs): s["time"] = 0.0 if i == 0 else round(starts[s["start"]], 2)
    stem = os.path.splitext(a.out)[0]
    srt = stem + ".srt"
    with open(srt, "w", encoding="utf-8") as f:
        for i, c in enumerate(raw, 1):
            f.write(f"{i}\n{srt_t(c['start'])} --> {srt_t(c['end'])}\n{c['text']}\n\n")
    # chapters: YouTube text + ffmetadata
    with open(stem + ".chapters.txt", "w", encoding="utf-8") as f:
        for s in secs: f.write(f"{hms(s['time'])} {s['title']}\n")
    tmp = stem + "_tmp"; os.makedirs(tmp, exist_ok=True)
    meta = os.path.join(tmp, "chapters.ffmeta")
    with open(meta, "w", encoding="utf-8") as f:
        esc = lambda x: re.sub(r"([=;#\\\n])", r"\\\1", x)
        f.write(f";FFMETADATA1\ntitle={esc(title)}\n")
        for i, s in enumerate(secs):
            e = secs[i + 1]["time"] if i + 1 < len(secs) else dur
            f.write(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(s['time'] * 1000)}\nEND={int(e * 1000)}\ntitle={esc(s['title'])}\n")
    ctx = {"title": title, "label": label, "topic": topic, "secs": secs, "host": a.host, "guest": a.guest, "guest2": a.guest2, "burn": a.burn_subs, "bgmode": bool(a.backgrounds), "layout": a.layout}
    lst, n, t = [], 0, 0.0
    def add(cue, t1):
        nonlocal n, t
        if t1 - t < 0.02: return
        p = os.path.join(tmp, f"f{n:05}.png"); render(cue, ctx).save(p, compress_level=1); n += 1
        lst.append(f"file '{os.path.abspath(p)}'\nduration {t1 - t:.3f}\n"); t = t1
    for i, c in enumerate(raw):
        if c["start"] > t + 0.02:  # gap: same slide, no subtitle
            add(dict(c, text=""), c["start"])
        add(c, c["end"])
    if dur > t + 0.02: add(dict(raw[-1], text=""), dur)
    lst.append(lst[-1].split("\n")[0] + "\n")
    lp = os.path.join(tmp, "list.txt"); open(lp, "w", encoding="utf-8").write("".join(lst).replace("\\", "/"))
    t_img = time.time() - t0
    if a.backgrounds:
        lt = [starts.get(i, 0.0) for i in range(len(lines))] if tim else None
        segs = load_backgrounds(a.backgrounds, lt, dur)
        print("BACKGROUNDS:"); [print(f"  {hms(s)}-{hms(e)} {os.path.basename(im)}") for s, e, im in segs]
        bgv = os.path.join(tmp, "bg.mp4"); tb = time.time(); build_bg_video(segs, dur, a.fps, bgv)
        print(f"bg video {time.time() - tb:.0f}s", flush=True)
        ind = a.layout == "speaker" and tim
        extra, fc = [], f"[1:v]fps={a.fps}[ov];[0:v][ov]overlay=format=auto:eof_action=repeat,format=yuv420p[v]"
        if ind:
            il = build_indicator(tim, lines, dur, a.fps, tmp)
            extra = ["-f", "concat", "-safe", "0", "-i", il]
            # hide meter during the title card (first 9 s)
            fc = (f"[1:v]fps={a.fps}[ov];[0:v][ov]overlay=format=auto:eof_action=repeat[b];[5:v]fps={a.fps},format=rgba[m];"
                  f"[b][m]overlay=x=70:y={SPK_Y + 8}:format=auto:eof_action=repeat:enable='gte(t,9)',format=yuv420p[v]")
        cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-i", bgv, "-f", "concat", "-safe", "0", "-i", lp, "-i", a.mp3,
               "-i", srt, "-i", meta] + extra + ["-filter_complex", fc,
               "-map", "[v]", "-map", "2:a", "-map", "3:s", "-map_metadata", "4", "-map_chapters", "4",
               "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-threads", "8", "-g", str(int(a.fps * 5)),
               "-c:a", "aac", "-b:a", "160k", "-c:s", "mov_text", "-metadata:s:s:0", "language=eng", "-t", f"{dur:.3f}",
               "-movflags", "+faststart", a.out]
        subprocess.run(nosubs(cmd, a.burn_subs), check=True); cmd = None
    else: cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-f", "concat", "-safe", "0", "-i", lp, "-i", a.mp3, "-i", srt,
           "-i", meta, "-map", "0:v", "-map", "1:a", "-map", "2:s", "-map_metadata", "3", "-map_chapters", "3",
           "-vf", f"fps={a.fps},format=yuv420p",
           "-c:v", "libx264", "-preset", "medium", "-tune", "stillimage", "-crf", "20", "-threads", "4",
           "-g", str(int(a.fps * 10)), "-c:a", "aac", "-b:a", "160k", "-c:s", "mov_text",
           "-metadata:s:s:0", "language=eng", "-shortest", "-movflags", "+faststart", a.out]
    if cmd: subprocess.run(nosubs(cmd, a.burn_subs), check=True)
    if a.frames_dir:
        os.makedirs(a.frames_dir, exist_ok=True); vd = ffprobe_dur(a.out)
        grabs = [("start", 3), ("middle", vd / 2), ("end", vd - 3)]
        if a.frame_times: grabs = [(f"f{i + 1}", float(x)) for i, x in enumerate(a.frame_times.split(","))]
        for name, tt in grabs:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{tt:.2f}", "-i", a.out, "-frames:v", "1",
                            os.path.join(a.frames_dir, f"{base}{a.frame_suffix}_{name}.png")], check=True)
    if not a.keep_tmp: shutil.rmtree(tmp, ignore_errors=True)
    vd = ffprobe_dur(a.out)
    json.dump({"title": title, "topic": topic, "timing": "aligned" if tim else "estimated",
               "sections": secs, "cues": len(raw)},
              open(stem + ".chapters.json", "w", encoding="utf-8"), indent=1)
    print("SECTIONS:"); [print(f"  {hms(s['time'])}  {s['title']}") for s in secs]
    print(f"TOPIC: {topic}\ncues={len(raw)} timing={'aligned' if tim else 'estimated'} audio={dur:.2f}s video={vd:.2f}s "
          f"diff={vd - dur:+.2f}s size={os.path.getsize(a.out) / 1e6:.1f}MB images={t_img:.0f}s total={time.time() - t0:.0f}s")

def nosubs(cmd, burn):
    """v1.2: without --burn-subs, drop the mov_text subtitle stream (the .srt is written next to the mp4)"""
    if burn: return cmd
    out, i = [], 0
    while i < len(cmd):
        if cmd[i] in ("-map", "-c:s", "-metadata:s:s:0") and i + 1 < len(cmd) and (cmd[i+1].endswith(":s") or cmd[i] != "-map"): i += 2; continue
        out.append(cmd[i]); i += 1
    return out

if __name__ == "__main__":
    main()