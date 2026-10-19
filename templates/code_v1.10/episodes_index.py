r"""episodes_index.py (template v1.8, 2026-10-16) - episode registry + naming convention. Stdlib only (ffprobe for backfill).
Registry: <root>\episodes_index.json (source of truth, git) + episodes_index.md (generated table).
Naming convention (Thomas, 2026-10-16):
  - every episode gets a RUNNING NUMBER across all podcasts created so far ("number"); a re-render (<ep>_v2) keeps the number of the original and shows "(v2)".
  - series that have several episodes ("multi": true) are titled "<Series> #<n>" (n = number within the series); the video corner label is the same text.
  - one-offs (default!) are titled with the subject only (a trailing ", Episode 1" / "- Episode 1" / "(v2)" is stripped from -Title); the video corner label is the DATE (YYYY-MM-DD).
  - the words "Episode 1" never appear in the video, title, notes or chapters.
  A series is multi-episode when: --multi is given, or it is already marked multi in the registry. Everything else is a one-off.
Usage:
  python episodes_index.py plan --ep <ep> [--series S] [--multi|--oneoff] [--title T] [--date D] [--index file]   (dry run: prints the JSON naming plan, writes nothing)
  python episodes_index.py add  --ep <ep> ... --dur <seconds> [--cast "Carter, X, Y"]                              (register; no-op if already registered)
  python episodes_index.py backfill [--dry]                                                                          (register the episodes found in episodes\*.mp3, oldest first)
  python episodes_index.py show"""
import argparse, glob, json, os, re, shutil, subprocess, sys, time
ROOT = os.path.dirname(os.path.abspath(__file__))
BACKFILL = {"fanged": ("Fanged Noumena", True), "dark_enlightenment": ("Dark Enlightenment", False), "patchwork": ("Patchwork", False),
            "das_man": ("Das Man", False), "uploaded_intelligence": ("Uploaded Intelligence", True), "mike_ma": ("Mike Ma", False)}

def idx_paths(a): p = a.index or os.path.join(ROOT, "episodes_index.json"); return p, os.path.splitext(p)[0] + ".md"
def load(p):
    if os.path.exists(p): return json.load(open(p, encoding="utf-8-sig"))
    return {"_doc": "Episode registry (episodes_index.py, template v1.8). number = running number across all podcasts; series_no = number inside a multi-episode series; re-renders (_v2) keep the number. Naming: multi series '<Series> #<n>', one-offs subject only, corner label = date.", "series": {}, "episodes": []}
def no_ep(t):
    t = (t or "").replace('"', "'").strip()
    t = re.sub(r"\s*\(v\d+\)\s*$", "", t)
    t = re.sub(r"\s*[,:;\u2013\u2014-]?\s*\b(?:episode|ep\.?)\s*#?\d+\b\s*$", "", t, flags=re.I)
    return t.strip(" ,:;-\u2013\u2014")
def pretty_series(ep): s = re.sub(r"_v\d+$", "", ep); s = re.sub(r"_ep\d+$", "", s); return " ".join(w[:1].upper() + w[1:] for w in s.split("_") if w)
def parse_ep(ep):
    m = re.match(r"^(.*?)(?:_v(\d+))?$", ep); base = m.group(1); d = re.search(r"_ep(\d+)$", base)
    return base, int(m.group(2) or 1), (int(d.group(1)) if d else None)
def fmt_dur(s): s = int(round(s)); return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"
def plan(ix, ep, series="", multi=None, title="", date=""):
    eps = ix["episodes"]; base, ver, dg = parse_ep(ep); date = date or time.strftime("%Y-%m-%d")
    same = next((e for e in eps if e["ep"] == ep), None)
    orig = next((e for e in eps if e["ep"] == base and ep != base), None)
    if same: return dict(same, note="already registered")
    series = series or (orig["series"] if orig else pretty_series(ep))
    if multi is None: multi = bool(ix["series"].get(series, {}).get("multi", False))
    if orig and ver > 1: number, sno = orig["number"], orig.get("series_no")
    else:
        number = max([e["number"] for e in eps], default=0) + 1; sno = None
        if multi:
            used = {e.get("series_no") for e in eps if e["series"] == series and e.get("series_no")}
            sno = dg if (dg and dg not in used) else max(used, default=0) + 1
    subject = no_ep(title) or (orig["subject"] if orig else "") or series
    if multi and sno: disp = f"{series} #{sno}"; label = disp
    else: disp = subject; label = date
    if ver > 1: disp += f" (v{ver})"
    return {"ep": ep, "number": number, "series": series, "multi": bool(multi), "series_no": sno, "version": ver, "rerender_of": base if (orig and ver > 1) else None,
            "display_title": disp, "subject": subject, "label": label, "date": date}
def write(ix, p, mdp):
    json.dump(ix, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    rows = ["# Episodes (running number across all podcasts; generated from episodes_index.json)", "", "| # | Series | Title | Date | Duration | Name |", "|---|---|---|---|---|---|"]
    for e in sorted(ix["episodes"], key=lambda e: (e["number"], e["version"])):
        rows.append(f"| {e['number']} | {e['series']}{' (multi)' if e['multi'] else ''} | {e['display_title']} | {e['date']} | {fmt_dur(e['duration_s']) if e.get('duration_s') else ''} | {e['ep']} |")
    open(mdp, "w", encoding="utf-8").write("\n".join(rows) + "\n")
def probe(f):
    ff = shutil.which("ffprobe") or next(iter(glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin\ffprobe.exe"))), None)
    return round(float(subprocess.run([ff, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout.strip()), 1) if ff else None
def add_entry(ix, pl, dur, cast=""):
    e = dict(pl); e.pop("note", None); e["duration_s"] = dur; e["cast"] = cast
    ix["episodes"].append(e); ix["series"].setdefault(pl["series"], {"multi": pl["multi"]}); return e
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["plan", "add", "backfill", "show"])
    ap.add_argument("--ep", default=""); ap.add_argument("--series", default=""); ap.add_argument("--title", default=""); ap.add_argument("--date", default="")
    ap.add_argument("--multi", action="store_true"); ap.add_argument("--oneoff", action="store_true"); ap.add_argument("--dur", type=float, default=0); ap.add_argument("--cast", default="")
    ap.add_argument("--index", default=""); ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(); p, mdp = idx_paths(a); ix = load(p); multi = True if a.multi else (False if a.oneoff else None)
    if a.cmd == "show": print(open(mdp, encoding="utf-8").read() if os.path.exists(mdp) else "(empty)"); return
    if a.cmd == "plan": print(json.dumps(plan(ix, a.ep, a.series, multi, a.title, a.date), ensure_ascii=True)); return
    if a.cmd == "add":
        if not a.ep: sys.exit("--ep required")
        pl = plan(ix, a.ep, a.series, multi, a.title, a.date)
        if pl.get("note"): print("registry: already registered", a.ep); return
        add_entry(ix, pl, a.dur or None, a.cast); write(ix, p, mdp); print(f"registry: #{pl['number']} {pl['display_title']} ({pl['date']}, {fmt_dur(a.dur) if a.dur else '?'})"); return
    # backfill
    ed = os.path.join(ROOT, "episodes"); mp3s = sorted([f for f in glob.glob(os.path.join(ed, "*.mp3")) if not f.endswith("_64k.mp3")], key=os.path.getmtime); n = 0
    for f in mp3s:
        ep = os.path.basename(f)[:-4]; base, ver, dg = parse_ep(ep)
        if any(e["ep"] == ep for e in ix["episodes"]): continue
        key = re.sub(r"_ep\d+$", "", base); ser, mu = BACKFILL.get(key, (pretty_series(ep), False)); ix["series"].setdefault(ser, {"multi": mu})
        legacy = None
        for src in (os.path.join(ed, ep + ".chapters.json"), ):
            if os.path.exists(src):
                try: j = json.load(open(src, encoding="utf-8-sig")); legacy = j.get("title") if isinstance(j, dict) else None
                except Exception: pass
        nf = os.path.join(ed, ep + ".notes.md")
        if not legacy and os.path.exists(nf): legacy = (open(nf, encoding="utf-8-sig").readline().lstrip("# ").strip() or None)
        pl = plan(ix, ep, ser, mu, legacy or "", time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(f))))
        e = add_entry(ix, pl, probe(f)); e["legacy_title"] = legacy; e["files"] = sorted(os.path.basename(x)[len(ep):] for x in glob.glob(os.path.join(ed, ep + ".*")) + glob.glob(os.path.join(ed, ep + "_64k.mp3")))
        n += 1; print(f"#{e['number']:<2} {e['display_title']:<42} {e['date']} {fmt_dur(e['duration_s']) if e['duration_s'] else '?':>7}  {ep}  (series {ser}, multi={mu}; legacy title: {legacy})")
    if not a.dry and n: write(ix, p, mdp)
    print(f"backfill: {n} episode(s) {'(dry run, nothing written)' if a.dry else 'registered'}")
main()