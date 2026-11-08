r"""tools\brief_gen.py (v1.14 2026-11-07: content style v2.6 = v2.5 + humanity dial (brief.humanity low|medium|high, default medium), everyday beats, personal angles, one tangent, nerd cap, shorter turns - templates\content_style_v2.6.md; was 2026-11-01, content template v2.5 default (v2.3 legacy selectable) / technical v1.13) - Episode desk brief -> ready-to-render episode inputs.
v1.13: TOPIC-FIRST briefs (schema v2: source {type topic, topic, files 0-2 optional, research web|none}; schema v1 still accepted: theme = topic + web
  research, files = as before). Web research = tools\research.py (gemma queries -> DuckDuckGo lite/html, no key -> Wikipedia backstop -> page
  extraction) feeding the normal notes + verbatim-quote verification. NO whole-shelf fallback: books only when attached or named in the topic.
  Relevance gate: gemma scores every fact 0-2 against the topic, keeps 2s; < 15 -> exit 4 "ABORT research too thin".
  Style v2.5 (templates\content_style_v2.5.md + cast_bible_v1.json): fixed character bibles, real-name speaker labels (mapped back to
  Host/Guest/Guest2 in the output files), story-first chapter shapes, scene cold open, short turns, named crux + one concession per guest,
  used-material ledger (quote/statistic caps, gag budget, banned phrases) + clean_v25 (self-address, dedup, caps). brief.content_style or
  --content_style picks the style (default v2.5). --stop_after research|notes|plan|coldopen = cheap partial run (smoke tests).
Stdlib only (run with venv_vv python); talks to Ollama over HTTP (gemma4:26b-a4b-it-qat, reasoning off); ALWAYS unloads the model at the end.
Called by tools\start_brief.ps1 (-Inner). Never touches episodes\, learn\ or notes\ (the launcher copies results there only after every gate passed).
Usage: brief_gen.py --brief <brief.json> --work <run dir> --root C:\grok\podcast [--books_text <cache dir>] [--dry] [--content_style v2.5|v2.3] [--stop_after research|notes|plan|coldopen]
Pipeline (all files in <work>\gen\):
  0 brief check (host Carter, 1-2 guests with drama3 refs, never banned / Hugh, length 20|30|40)
  1 sources: .pdf via the text cache books_text\<pdf stem>.txt (pdftotext, one form feed per PDF page; the PC has no PDF library),
    .epub (zip + html strip) / .txt / .md read directly, cut into ~400-word "locations"
  2 focus: gemma -> search keywords (theme brief: from the theme; file brief: from the table of contents, avoiding covered topics) -> page scoring
  3 notes: gemma reads the chosen pages in batches -> facts (with page), verbatim quotes AUTO-VERIFIED against the page text (unverified = dropped)
  4 plan: title, short id, advocate / antagonist, chapters scaled to length (40: 8, 30: 6, 20: 4), cold open, quiz questions
  5 script by parts (cold open, chapters, [quiz], five takeaways) with summaries + last lines as context; >= 88 % of each part budget or retry
  6 clean + checks: speaker labels, tags only [laughs]/[sighs], no markdown, no spoken page/section/chapter numbers, quotes only verified ones
  7 gemma fact-check pass per part against the notes (fixes applied, logged in factcheck.md)
  8 LENGTH GATE (pre-TTS): predicted = 60 s + 0.367 s/word (facing_death_ep1: 6172 words -> 2324 s); must sit inside the duration window
    with margin, else gemma inserts extra exchanges (max 4 rounds) or condenses the longest chapter; still outside -> exit 3 (no TTS)
  9 learn materials (takeaways, quiz only if brief.quiz, Anki, read-for-yourself, details_meta with voice credits, factcheck) + FLUX prompts
Exit 0 = ready (gen\result.json); 2 = brief invalid; 3 = length gate failed; 4 = sources / notes failed; 5 = generation failed."""
import argparse, csv, io, json, os, random, re, sys, time, unicodedata, urllib.error, urllib.request, zipfile, html

MODEL = "gemma4:26b-a4b-it-qat"; HOST = "http://127.0.0.1:11434"
BANNED = {"maya", "declan", "alice", "mary"}; NEVER_WITH_CARTER = "hugh"; OUT = {"elliot": "Elliot is out (monotone Drama 3 voice, see handover)"}
STYLES = ("v2.6", "v2.5", "v2.3"); DEFAULT_STYLE = "v2.6"; HUMANITY_LEVELS = ("low", "medium", "high"); DEFAULT_HUMANITY = "medium"; MIN_FACTS = 15; MAX_TOPIC = 600
SHAPES = {"case_file": "CASE FILE: one concrete story from the notes (say where it comes from) told by one guest in vivid detail, then picked apart by the other; Carter asks what it means on a Tuesday.",
          "hot_seat": "HOT SEAT: Carter grills ONE guest with short, pointed questions; the other guest heckles and gets one proper rebuttal; the grilled guest must answer concretely.",
          "steelman_swap": "STEELMAN SWAP: Carter makes each guest argue the OTHER side for about a minute, as well as they can; then they react to how their own view sounded in the other's mouth; ends back on the crux.",
          "rapid_fire": "RAPID FIRE: Carter fires 5-7 quick yes/no or this-or-that questions about the case; answers are one or two sentences, each answer can trigger a short clash; then one longer exchange on the answer they split on.",
          "what_would_you_do": "WHAT WOULD YOU DO: Carter sets up a concrete scenario (from the notes or a clearly labelled hypothetical) with a decision to make; each guest decides and defends it; the scenario gets one twist halfway."}
WINDOWS = {40: (2280, 2880), 30: (1680, 2160), 20: (1080, 1440)}          # duration gates (s): 38-48 / 28-36 / 18-24 min
TARGET_WORDS = {40: 6600, 30: 4900, 20: 3250}
N_CHAPTERS = {40: 8, 30: 6, 20: 4}; N_IMAGES = {40: 15, 30: 12, 20: 9}; N_PAGES = {"intro": 16, "standard": 24, "deep": 32}
SEC_PER_WORD = 0.367; OVERHEAD_S = 60.0; MARGIN_LO = 90; MARGIN_HI = 120
GENDER = {"Carter": "M", "Clara": "F", "Lachlan": "M", "Elliot": "M", "Frank": "M", "Isla": "F", "Marcus": "M", "Willa": "F", "Zara": "F", "Imogen": "F", "Samuel": "M"}
TONE = {"calm": "Calm and reflective: the guests still disagree for real, but they argue patiently, with fewer interruptions and more room for thought. Warm humour, no shouting.",
        "playful": "Playful: lots of natural humour, teasing and absurd everyday comparisons; the disagreement is real but light-footed; never at the expense of accuracy.",
        "debate": "Debate: a heated, contested argument. Interruptions inside lines, sharp rebuttals, irritation, sarcasm, scored points; disagreements may stay unresolved. Fair: no straw men, no insults.",
        "serious": "Serious: earnest and sober; humour only where it truly arises; the stakes of the question are felt; still a real disagreement."}
DEPTH = {"intro": "Depth INTRO: assume no background. Explain every technical term in plain words the first time, use many everyday examples, few names beyond the book's author.",
         "standard": "Depth STANDARD: an educated non-specialist listener. Explain technical terms briefly, bring in a few named critics and defenders.",
         "deep": "Depth DEEP: go further into the structure of the arguments, objections and replies; more named thinkers and positions from the wider debate (only well-known, verifiable ones); still explain terms briefly."}
STOP = set("a an the and or of to in on for with without is are was were be been being do does did we you i it its this that these those what which who whom why how not no yes can could should would will shall may might must from by as at about into over under than then so if but our their his her they them there here anything something nothing everything any some all one people book books author".split())

def now(): return time.strftime("%H:%M:%S")
class Ctx: pass
C = Ctx()
def st(m):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + "step=gen " + m
    with open(os.path.join(C.work, "STATUS.txt"), "w", encoding="utf-8") as f: f.write(line + "\n")
    log(m)
def log(m):
    with open(os.path.join(C.work, "chain.log"), "a", encoding="utf-8") as f: f.write(f"{now()} gen: {m}\n")
    print(now(), m, flush=True)
def wj(name, obj):
    with open(os.path.join(C.gen, name), "w", encoding="utf-8") as f: json.dump(obj, f, indent=1, ensure_ascii=False)
def wt(name, txt, d=None):
    with open(os.path.join(d or C.gen, name), "w", encoding="utf-8", newline="\n") as f: f.write(txt)
def words(s): return len(s.split())
# QC 2026-11-01: speaker labels the LLM may put in front of a line ("Guest 1:", "**Clara:**", "GUEST 1 -"), and a word-level similarity
LBL_ROLE = r"(?:Host|Guest\s*\d*|Guest\s*(?:one|two)|Speaker\s*\d+|Narrator)"
def strip_label(t, names=()):
    nm = "|".join(re.escape(n.strip()) for n in names if n and n.strip())
    t = re.sub(r"^\s*[*_\"\u201c]*(?:" + LBL_ROLE + ("|" + nm if nm else "") + r")[*_]*\s*:\s*(?:[*_]+\s*)?", "", t, flags=re.I)
    return re.sub(r"^\s*[*_]*" + LBL_ROLE + r"[*_]*\s+[-\u2013\u2014]\s+", "", t, flags=re.I)
def wsim(a, b):
    import difflib; f = lambda x: re.findall(r"[a-z0-9']+", x.lower())
    return difflib.SequenceMatcher(None, f(a), f(b), autojunk=False).ratio()
def fc_fix_ok(seg, j, ft):
    """a fact-check fix must belong to line j: False when it is closer to another line of the part (index shift: ep1 lines 68-73,
    ep14 line 1) or shares almost nothing with line j. -> (ok, similarity to line j, best similarity to another line)"""
    r_self = wsim(seg[j]["text"], ft); r_oth = max((wsim(x["text"], ft) for m, x in enumerate(seg) if m != j), default=0)
    return (not ((r_oth >= 0.6 and r_oth > r_self) or r_self < 0.3)), r_self, r_oth
def lwords(L): return sum(words(l["text"]) for l in L)
def norm(s):
    s = unicodedata.normalize("NFKC", s).replace("\u00ad", "")
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)
    s = s.lower().replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"[^a-z0-9']+", " ", s).strip()

# ---------------- Ollama ----------------
def post(path, d, to=1200):
    req = urllib.request.Request(HOST + path, data=json.dumps(d).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=to))
def call(prompt, schema, temp=0.7, predict=4500, tries=3):
    last = None
    for t in range(tries):
        for think in (False, None):
            d = {"model": MODEL, "prompt": prompt, "stream": False, "format": schema, "keep_alive": "15m",
                 "options": {"temperature": temp, "top_p": 0.95, "num_ctx": 16384, "num_predict": predict, "repeat_penalty": 1.08}}
            if think is not None: d["think"] = think
            try:
                r = post("/api/generate", d); C.calls += 1
                return json.loads(r["response"])
            except urllib.error.HTTPError as e:
                last = e
                if think is not None: continue
            except Exception as e:
                last = e; break
        log(f"ollama call failed (try {t+1}): {last}"); time.sleep(10)
    raise RuntimeError(f"ollama failed after {tries} tries: {last}")
def unload():
    try: post("/api/generate", {"model": MODEL, "keep_alive": 0}, 120); log("gemma unloaded (keep_alive 0)")
    except Exception as e: log(f"unload error {e}")
S_STR = {"type": "string"}; S_INT = {"type": "integer"}
def arr(items): return {"type": "array", "items": items}
def obj(props, req=None): return {"type": "object", "properties": props, "required": req or list(props)}

# ---------------- sources ----------------
def book_meta(path):
    stem = os.path.splitext(os.path.basename(path))[0]; parts = [p.strip() for p in stem.split(" -- ")]
    title = parts[0].replace(" _ ", ": ").replace("_", "").strip()
    title = re.sub(r"\s*\((?:[^)]*trans[^)]*)\)", "", title).strip()
    author = ""
    if len(parts) > 1:
        a = re.sub(r"^by\s+", "", parts[1]); a = re.split(r"\s*\(|;|,\s*\d|\s+author", a)[0].strip(" ,")
        if "," in a and len(a.split(",")) == 2 and len(a.split(",")[0].split()) == 1: a = a.split(",")[1].strip() + " " + a.split(",")[0].strip()
        author = a
    return {"title": title, "author": author, "file": os.path.basename(path)}
def chunk_words(text, n=400):
    w = text.split(); return [" ".join(w[i:i + n]) for i in range(0, len(w), n)] or [""]
def load_book(path):
    ext = os.path.splitext(path)[1].lower(); kind = "page"
    if ext == ".pdf":
        cache = os.path.join(C.books_text, os.path.splitext(os.path.basename(path))[0] + ".txt")
        if not os.path.exists(cache): return None, f"no text cache {cache} (PDFs are pre-extracted on the box with pdftotext; the PC has no PDF library)"
        pages = open(cache, encoding="utf-8", errors="replace").read().split("\f")
    elif ext == ".epub":
        z = zipfile.ZipFile(path); names = z.namelist(); spine = []
        try:
            cont = z.read("META-INF/container.xml").decode("utf-8", "replace"); opf = re.search(r'full-path="([^"]+)"', cont).group(1)
            ox = z.read(opf).decode("utf-8", "replace"); base = os.path.dirname(opf)
            man = {m.group(1): m.group(2) for m in re.finditer(r'<item\b[^>]*?id="([^"]+)"[^>]*?href="([^"]+)"', ox)}
            man.update({m.group(2): m.group(1) for m in re.finditer(r'<item\b[^>]*?href="([^"]+)"[^>]*?id="([^"]+)"', ox)})
            for m in re.finditer(r'<itemref\b[^>]*idref="([^"]+)"', ox):
                h = man.get(m.group(1));
                if h: spine.append(os.path.normpath(os.path.join(base, urllib.request.unquote(h))).replace("\\", "/"))
        except Exception: spine = []
        if not spine: spine = sorted(n for n in names if n.lower().endswith((".xhtml", ".html", ".htm")))
        txt = []
        for n in spine:
            if n not in names: continue
            h = z.read(n).decode("utf-8", "replace"); h = re.sub(r"(?is)<(script|style).*?</\1>", " ", h)
            h = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</div>", "\n", h); txt.append(html.unescape(re.sub(r"<[^>]+>", " ", h)))
        pages = chunk_words("\n".join(txt)); kind = "loc"
    elif ext in (".txt", ".md"):
        raw = open(path, encoding="utf-8", errors="replace").read()
        pages = chunk_words(raw, 400 if len(raw.split()) > 4000 else 110); kind = "loc"
        if len(pages) > 1 and len(pages[-1].split()) < 60: pages[-2:] = [pages[-2] + " " + pages[-1]]   # short articles: ~110-word locations so short sources still give enough citable units
    else: return None, f"unsupported {ext}"
    b = book_meta(path); b.update(path=path, pages=pages, kind=kind); return b, None
def page_ok(t):
    w = t.split()
    if len(w) < 60: return False
    dig = sum(ch.isdigit() for ch in t) / max(1, len(t))
    return dig < 0.06
def score_pages(book, kws):
    sc = []
    for i, p in enumerate(book["pages"]):
        if not page_ok(p): sc.append(0.0); continue
        n = norm(p); s = 0.0
        for k in kws:
            kk = norm(k)
            if not kk: continue
            c = n.count(kk)
            if c: s += c * (3.0 if " " in kk else 1.0)
        sc.append(s)
    return sc
def pick_pages(books, kws, npages):
    cand = []
    for bi, b in enumerate(books):
        sc = score_pages(b, kws)
        for i, s in enumerate(sc):
            sm = s + 0.5 * ((sc[i - 1] if i else 0) + (sc[i + 1] if i + 1 < len(sc) else 0))
            if s > 0: cand.append((sm, bi, i))
    cand.sort(reverse=True); chosen = set()
    for sm, bi, i in cand:
        if len(chosen) >= npages: break
        chosen.add((bi, i))
    return sorted(chosen)

# ---------------- brief ----------------
def check_brief(B, root):
    err = []
    if B.get("schema_version") not in (1, 2): err.append(f"schema_version {B.get('schema_version')} not 1 or 2")
    if B.get("host") != "Carter": err.append("host must be Carter")
    L = B.get("length_minutes")
    if L not in WINDOWS: err.append(f"length_minutes {L} not 20/30/40")
    G = B.get("guest_voices") or []
    if not (1 <= len(G) <= 2) or len(set(g.lower() for g in G)) != len(G): err.append(f"guest_voices {G}: need 1-2 different names")
    rm = {}
    try: rm = json.load(open(os.path.join(root, "drama3_ref_map.json"), encoding="utf-8-sig")).get("map", {})
    except Exception: pass
    for g in G:
        if g.lower() in BANNED: err.append(f"{g} is banned")
        if g.lower() in (NEVER_WITH_CARTER, "carter"): err.append(f"{g} never as guest with host Carter")
        if g.lower() in OUT: err.append(OUT[g.lower()])
        if not os.path.exists(os.path.join(root, "drama3_refs", rm.get(g, g) + ".wav")): err.append(f"{g}: no drama3_refs\\{rm.get(g, g)}.wav")
    if B.get("tone") not in TONE: err.append(f"tone {B.get('tone')}")
    if B.get("depth") not in DEPTH: err.append(f"depth {B.get('depth')}")
    cs = B.get("content_style")
    if cs is not None and cs not in STYLES: err.append(f"content_style {cs} not in {STYLES}")
    hu = B.get("humanity")
    if hu is not None and hu not in HUMANITY_LEVELS: err.append(f"humanity {hu} not in {HUMANITY_LEVELS}")
    s = B.get("source") or {}
    if s.get("type") == "files":
        if not s.get("files"): err.append("no files")
        for f in s.get("files") or []:
            if not os.path.isfile(f): err.append(f"missing file {f}")
    elif s.get("type") == "theme":   # schema v1: theme = topic + web research
        if not (s.get("theme") or "").strip(): err.append("empty theme")
    elif s.get("type") == "topic":   # schema v2: the topic is primary; books / PDFs are an optional extra
        if B.get("schema_version") != 2: err.append("source.type topic needs schema_version 2")
        t = (s.get("topic") or "").strip()
        if not t: err.append("empty topic")
        if len(t) > MAX_TOPIC: err.append(f"topic {len(t)} chars > {MAX_TOPIC}")
        if len(s.get("files") or []) > 2: err.append("at most 2 books / PDFs with a topic")
        for f in s.get("files") or []:
            if not os.path.isfile(f): err.append(f"missing file {f}")
        if s.get("research", "web") not in ("web", "none"): err.append(f"source.research {s.get('research')} not web|none")
        if s.get("research", "web") == "none" and not s.get("files"): err.append("topic with research 'none' needs at least one book / PDF")
    else: err.append(f"source.type {s.get('type')}")
    return err

def norm_source(B):
    """schema v1 + v2 -> {topic, files, research}. v1 theme = topic with web research; v1 files = files, no research (as before)."""
    s = B.get("source") or {}
    if s.get("type") == "topic": return {"topic": (s.get("topic") or "").strip(), "files": list(s.get("files") or []), "research": s.get("research", "web"), "type": "topic"}
    if s.get("type") == "theme": return {"topic": (s.get("theme") or "").strip(), "files": [], "research": "web", "type": "theme"}
    return {"topic": (s.get("theme") or "").strip(), "files": list(s.get("files") or []), "research": "none", "type": "files"}

def named_books(topic, books_dir):
    """books on the shelf the topic NAMES (author surname or >= 2 title words), by filename metadata only. No whole-shelf fallback (v1.13)."""
    if not topic or not os.path.isdir(books_dir): return []
    tn = norm(topic); out = []
    for n in sorted(os.listdir(books_dir)):
        if not n.lower().endswith((".pdf", ".epub", ".txt", ".md")): continue
        b = book_meta(os.path.join(books_dir, n))
        sur = norm(b["author"]).split()[-1:] if b["author"] else []
        tw = [w for w in norm(b["title"]).split() if w not in STOP and len(w) > 3]
        if (sur and len(sur[0]) > 2 and re.search(r"\b" + re.escape(sur[0]) + r"\b", tn)) or (len(tw) >= 2 and sum(w in tn.split() for w in tw) >= min(2, len(tw))): out.append(os.path.join(books_dir, n))
    return out

def coverage(root):
    out = []
    try:
        ix = json.load(open(os.path.join(root, "episodes_index.json"), encoding="utf-8-sig"))
        out += [f"{e.get('ep')}: {e.get('title') or e.get('display_title') or ''}" for e in ix.get("episodes", [])]
    except Exception as e: log(f"coverage: index unreadable {e}")
    nd = os.path.join(root, "notes")
    if os.path.isdir(nd): out += ["notes file: " + n for n in sorted(os.listdir(nd))]
    return out
def taken_ids(root):
    t = set()
    try: t |= {e.get("ep", "") for e in json.load(open(os.path.join(root, "episodes_index.json"), encoding="utf-8-sig")).get("episodes", [])}
    except Exception: pass
    for d in ("episodes", "notes", "learn"):
        p = os.path.join(root, d)
        if os.path.isdir(p): t |= {re.sub(r"\.(mp3|mp4|srt|json|md|txt|csv)$", "", n) for n in os.listdir(p)}
    return t

# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--brief", required=True); ap.add_argument("--work", required=True); ap.add_argument("--root", default=r"C:\grok\podcast")
    ap.add_argument("--books_text", default=""); ap.add_argument("--books_dir", default=r"C:\grok\books"); ap.add_argument("--dry", action="store_true"); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--content_style", default="", choices=["", *STYLES]); ap.add_argument("--stop_after", default="", choices=["", "research", "notes", "plan", "coldopen"])
    a = ap.parse_args()
    C.work = a.work; C.gen = os.path.join(a.work, "gen"); C.root = a.root; C.books_text = a.books_text or os.path.join(a.root, "books_text"); C.calls = 0
    os.makedirs(C.gen, exist_ok=True)
    B = json.load(open(a.brief, encoding="utf-8-sig")); err = check_brief(B, a.root)
    if err: st("ABORT brief invalid: " + " | ".join(err)); return 2
    L = B["length_minutes"]; G = B["guest_voices"]; two = len(G) == 2; lo, hi = WINDOWS[L]
    random.seed(a.seed or int(time.time()))
    S = norm_source(B); C.style = a.content_style or B.get("content_style") or DEFAULT_STYLE; C.stop_after = a.stop_after
    paths = list(S["files"])
    if S["topic"]: paths += [p for p in named_books(S["topic"], a.books_dir) if p not in paths]   # only books the topic names; never the whole shelf
    books, skipped = [], []
    for p in paths:
        b, e = load_book(p)
        if b: books.append(b)
        else: skipped.append(f"{os.path.basename(p)}: {e}")
    for s in skipped: log("source skipped: " + s)
    if not books and S["research"] != "web": st("ABORT no readable source (" + ("; ".join(skipped) or "no books attached and web research off") + ")"); return 4
    theme = S["topic"]
    log(f"sources: topic {'yes' if theme else 'no'}, research {S['research']}, {len(books)} book(s)" + (": " + "; ".join(f"{b['author']} - {b['title']} ({len(b['pages'])} {b['kind']}s)" for b in books) if books else "") + f", content style {C.style}")
    cov = coverage(a.root)
    if a.dry:
        print(json.dumps({"ok": True, "schema_version": B.get("schema_version"), "topic": theme, "research": S["research"], "content_style": C.style, "humanity": (B.get("humanity") or DEFAULT_HUMANITY) if C.style == "v2.6" else None, "length": L, "window": [lo, hi], "target_words": TARGET_WORDS[L],
                          "guests": G, "books": [b["file"] for b in books], "skipped": skipped, "coverage_items": len(cov)}, indent=1)); return 0
    try: return run(B, books, cov, theme, L, G, two, lo, hi, S)
    finally: unload()

def web_research(theme, notes_user, books):
    """v1.13 research step: gemma -> search queries -> tools\\research.py (DuckDuckGo lite/html, Wikipedia backstop, page extraction) -> book-like docs"""
    import research as RS   # tools\\research.py, stdlib only
    st("research: generating search queries")
    have = "; ".join(f"{b['author']}, {b['title']}" for b in books) or "none"
    Q = call(f"A study podcast episode (a debate between two experts and a host) will be built on this TOPIC:\n{theme}\n" + (f"Thomas's notes: {notes_user}\n" if notes_user else "") +
             f"Books attached: {have}\n\nWrite web search queries to research it from several sides. Return JSON: queries (7 English web-search queries, 3-9 words each: one plain explainer, "
             "one for the strongest case FOR, one for the strongest case AGAINST / critics, two for concrete real cases, incidents or experiments, one for studies or data, one for named experts' views), "
             "wikipedia (3 exact English Wikipedia article titles that cover the core concepts).", obj({"queries": arr(S_STR), "wikipedia": arr(S_STR)}), temp=0.3, predict=600)
    qs = [q.strip() for q in Q.get("queries", []) if q.strip()][:8] or [theme[:120]]
    wk = [w.strip() for w in Q.get("wikipedia", []) if w.strip()][:4]
    log(f"research: queries {qs} | wikipedia {wk}")
    st(f"research: searching the web ({len(qs)} queries, DuckDuckGo + Wikipedia)")
    srcs, docs = RS.research(theme, qs, log=log, wiki_titles=wk)
    rd = os.path.join(C.gen, "research"); os.makedirs(rd, exist_ok=True)
    with open(os.path.join(rd, "sources.json"), "w", encoding="utf-8") as f:
        json.dump({"topic": theme, "queries": qs, "wikipedia": wk, "sources": srcs, "used": [{"title": d["title"], "site": d["author"], "url": d["url"], "sections": len(d["pages"])} for d in docs]}, f, indent=1, ensure_ascii=False)
    return docs

def relevance_gate(theme, facts):
    """gemma scores each fact 0-2 for relevance to the topic (2 = directly about it); keeps the 2s. Never the shelf: thin = abort upstream."""
    keep = []
    for k in range(0, len(facts), 45):
        part = facts[k:k + 45]
        listing = "\n".join(f"{j}: {f['claim']}" for j, f in enumerate(part))
        try: R = call(f"TOPIC of a debate podcast episode:\n{theme}\n\nScore every fact for how directly it helps an evidence-based debate on THIS topic: 2 = directly about the topic or a concrete case / study / argument "
                      "the debate can use; 1 = loosely related background; 0 = off-topic. Facts:\n" + listing + "\n\nReturn JSON: scores (one item per fact: i = the number, s = 0, 1 or 2).",
                      obj({"scores": arr(obj({"i": S_INT, "s": S_INT}))}), temp=0.1, predict=1500)
        except Exception as e: log(f"relevance batch {k // 45} failed: {e}"); continue
        sc = {x.get("i"): x.get("s") for x in R.get("scores", []) if isinstance(x, dict)}
        for j, f in enumerate(part):
            f["relevance"] = sc.get(j, 0)
            if f["relevance"] == 2: keep.append(f)
    return keep

def run(B, books, cov, theme, L, G, two, lo, hi, S=None):
    t0 = time.time(); host = "Carter"; adv = G[0]; ant = G[1] if two else None
    depth, tone = B["depth"], B["tone"]; notes_user = (B.get("notes") or "").strip()
    S = S or norm_source(B); v25 = getattr(C, "style", DEFAULT_STYLE) in ("v2.5", "v2.6"); stop = getattr(C, "stop_after", "")
    # ---- 1b web research (topic-first, v1.13)
    if S["research"] == "web" and theme:
        docs = web_research(theme, notes_user, books)
        books = books + docs
        if not books: st("ABORT research found no readable web pages (DuckDuckGo blocked or offline?) - rephrase the topic or attach a book / PDF"); return 4
        if stop == "research": st(f"stop_after research: {len(docs)} web pages; see gen\\research\\sources.json"); return 0
    # ---- 2 focus
    st("focus: choosing pages")
    blist = "\n".join(f"[{i}] {b['author']}, {b['title']}" + (" (web page)" if b.get("kind") == "web" else "") for i, b in enumerate(books))
    if theme:   # topic-first (v2 topic, v1 theme; a file brief may also carry a theme)
        q = (f"A study podcast episode will be built on this topic:\n{theme}\n\nSources available (books and/or web pages found by research):\n{blist}\n\nAlready covered in earlier episodes (avoid repeating them):\n" + "\n".join(cov[-40:]) +
             (f"\n\nThomas's notes: {notes_user}" if notes_user else "") +
             "\n\nReturn JSON: focus (one sentence: the precise contested question of the topic, as the sources can support it), keywords (15-25 words or short phrases that literally occur in the source text on the relevant pages, e.g. key terms, names of cases, experiments, technical vocabulary; lower case).")
    else:
        toc = "\n\n".join(f"== {b['author']}, {b['title']} ==\n" + " ".join(" ".join(b["pages"][:24]).split()[:5000 // len(books)]) for b in books)
        q = (f"A study podcast episode will be built on these book(s):\n{blist}\n\nThe opening pages (table of contents) are:\n{toc}\n\nAlready covered in earlier episodes (pick a part NOT yet covered):\n" + "\n".join(cov[-40:]) +
             (f"\n\nThomas's notes: {notes_user}" if notes_user else "") +
             "\n\nPick ONE part or chapter of the book(s) with a genuinely contested question that suits a debate, not yet covered. Return JSON: focus (one sentence naming the part and the question), keywords (15-25 words or short phrases that literally occur in that part's text; lower case).")
    F = call(q, obj({"focus": S_STR, "keywords": arr(S_STR)}), temp=0.4, predict=800)
    kws = [k.strip().lower() for k in F.get("keywords", []) if k.strip()][:25]
    sel = pick_pages(books, kws, N_PAGES[depth])
    allok = [(bi, i) for bi, b in enumerate(books) for i, p in enumerate(b["pages"]) if page_ok(p)]
    if sum(len(b["pages"]) for b in books) <= N_PAGES[depth]: sel = allok   # short source (article): use all of it
    if len(sel) < min(6, len(allok)) or not sel: st(f"ABORT focus: only {len(sel)} relevant pages for keywords {kws}"); return 4
    log(f"focus: {F.get('focus')} | keywords {kws} | {len(sel)} pages: " + ", ".join(f"{books[bi]['title'][:20]} {books[bi]['kind']} {i+1}" for bi, i in sel))
    wj("focus.json", {"focus": F.get("focus"), "keywords": kws, "pages": [[books[bi]["file"], i + 1] for bi, i in sel]})
    # ---- 3 notes
    batches, cur = [], []
    for bi, i in sel:
        if cur and (cur[-1][0] != bi or len(cur) >= 4): batches.append(cur); cur = []
        cur.append((bi, i))
    if cur: batches.append(cur)
    NS = obj({"facts": arr(obj({"claim": S_STR, "page": S_INT})), "quotes": arr(obj({"text": S_STR, "page": S_INT, "about": S_STR})),
              "positions": arr(S_STR), "objections": arr(S_STR), "examples": arr(S_STR)})
    facts, quotes, pos, objs, exs, qdrop = [], [], [], [], [], 0
    for k, bt in enumerate(batches, 1):
        b = books[bt[0][0]]; kind = "PDF page" if b["kind"] == "page" else ("web section" if b["kind"] == "web" else "location")
        txt = "\n\n".join(f"[{kind} {i+1}]\n{b['pages'][i]}" for _, i in bt)
        st(f"notes: reading batch {k}/{len(batches)} ({b['title'][:30]})")
        q = (f"You are taking careful study notes on {b['author']}, \"{b['title']}\"" + (" (a web page)" if b["kind"] == "web" else "") + f". Focus: {F.get('focus')}." + (f" Topic: {theme}." if theme else "") + f"\nText:\n{txt}\n\n"
             "Return JSON: facts (8-14 precise claims the text actually makes or reports, each with the page number in brackets above it), "
             "quotes (3-6 short memorable sentences copied EXACTLY, character for character, from the text, each 6-35 words, with page; no ellipses, no edits), "
             "positions (the author's main theses here), objections (objections the author discusses or that critics would raise), examples (thought experiments, cases, examples used). "
             "Only what is in this text. English.")
        try: N = call(q, NS, temp=0.3, predict=3000)
        except Exception as e: log(f"notes batch {k} failed: {e}"); continue
        pages = {i + 1: b["pages"][i] for _, i in bt}
        for f in N.get("facts", []): facts.append({"claim": f.get("claim", "").strip(), "page": f.get("page"), "book": b["title"], "author": b["author"], "kind": kind, **({"url": b["url"]} if b.get("url") else {})})
        for qq in N.get("quotes", []):
            t = qq.get("text", "").strip().strip('"\u201c\u201d'); p = qq.get("page")
            hay = norm(" ".join(pages.get(x, "") for x in (p - 1, p, p + 1))) if isinstance(p, int) else ""
            whole = norm(" ".join(pages.values()))
            if 6 <= words(t) <= 45 and norm(t) and (norm(t) in hay or norm(t) in whole):
                if norm(t) not in hay:  # fix page
                    p = next((x for x, v in pages.items() if norm(t) in norm(v)), p)
                quotes.append({"text": t, "page": p, "about": qq.get("about", ""), "book": b["title"], "author": b["author"], "kind": kind, **({"url": b["url"]} if b.get("url") else {})})
            else: qdrop += 1
        pos += N.get("positions", []); objs += N.get("objections", []); exs += N.get("examples", [])
    seen = set(); quotes = [q for q in quotes if not (norm(q["text"]) in seen or seen.add(norm(q["text"])))]
    log(f"notes: {len(facts)} facts, {len(quotes)} verified quotes ({qdrop} unverifiable quotes dropped)")
    facts = [f for f in facts if f["claim"]]
    if theme and facts:   # v1.13 relevance gate: only facts that are directly about the topic count
        st(f"notes: relevance gate on {len(facts)} facts"); nall = len(facts); facts = relevance_gate(theme, facts)
        log(f"relevance gate: {len(facts)} of {nall} facts directly relevant to the topic")
        if len(facts) < MIN_FACTS:
            wj("notes_rejected.json", {"focus": F.get("focus"), "facts_relevant": facts, "quotes": quotes})
            st(f"ABORT research too thin: only {len(facts)} facts directly relevant to the topic (need {MIN_FACTS}) - rephrase the topic or attach a book / PDF"); return 4
        rel = {f["book"] for f in facts}; quotes = [q for q in quotes if q["book"] in rel]   # quotes only from sources that gave relevant facts
    if len(facts) < MIN_FACTS: st(f"ABORT notes too thin ({len(facts)} facts)"); return 4
    wj("notes.json", {"focus": F.get("focus"), "topic": theme, "facts": facts, "quotes": quotes, "positions": pos, "objections": objs, "examples": exs})
    if stop == "notes": st(f"stop_after notes: {len(facts)} relevant facts, {len(quotes)} verified quotes"); return 0
    facts_txt = "\n".join(f"- {f['claim']} ({f['author']}, {f['kind']} {f['page']})" for f in facts[:140])
    quotes_txt = "\n".join(f"- \"{q['text']}\" ({q['author']}, {q['book']})" for q in quotes[:40]) or "(none: paraphrase only)"
    extra_txt = ("POSITIONS:\n" + "\n".join("- " + x for x in pos[:25]) + "\nOBJECTIONS:\n" + "\n".join("- " + x for x in objs[:25]) + "\nEXAMPLES:\n" + "\n".join("- " + x for x in exs[:25]))
    srcs = sorted({(f["author"], f["book"]) for f in facts if "url" not in f}); src_line = "; ".join(f"{a_}, \"{b_}\"" for a_, b_ in srcs)
    webs = sorted({f["author"] for f in facts if "url" in f})
    if webs: src_line = ((src_line + "; plus ") if src_line else "") + f"web research ({len(webs)} sources incl. {', '.join(webs[:4])})"
    # ---- 4 plan
    st("plan: title, roles, chapters")
    nch = N_CHAPTERS[L]; pronoun = lambda n: "she" if GENDER.get(n) == "F" else "he"
    if not v25:
        roles = (f"Guest = {adv.upper()} ({pronoun(adv)}), the ADVOCATE who defends the book's strongest version; Guest2 = {ant.upper()} ({pronoun(ant)}), the ANTAGONIST from a named critical tradition."
                 if two else f"Guest = {adv.upper()} ({pronoun(adv)}), the ADVOCATE; Carter himself plays the sceptic and pushes back hard.")
        q = (f"Plan a {L}-minute episode of a private English study podcast (content template v2.3: a real argument about the book(s), warm funny host who mediates and gives his own view).\n"
             f"Theme / focus: {theme or F.get('focus')}\nFocus found in the text: {F.get('focus')}\nSources: {src_line}\nHost = CARTER (always). {roles}\n"
             f"{TONE[tone]}\n{DEPTH[depth]}\n" + (f"Thomas's notes: {notes_user}\n" if notes_user else "") +
             f"NOTES FROM THE BOOK:\n{facts_txt}\n{extra_txt}\n\nAlready covered episodes (do not repeat their angle):\n" + "\n".join(cov[-25:]) +
             f"\n\nReturn JSON: short_id (2-3 lower-case English words joined by _, e.g. future_people), title (catchy question-style episode title naming the author, max 70 chars, no 'Episode'), "
             f"question (the one contested question), advocate_persona (2-3 sentences: who {adv} is, field, temperament, allies and sources {pronoun(adv)} draws on beyond the book, one modest invented personal detail), "
             + (f"antagonist_persona (same for {ant}: the named critical tradition and critics {pronoun(ant)} draws on), " if two else "antagonist_persona (Carter's sceptical angle in one sentence), ") +
             "carter_detail (one everyday running situation in Carter's life that fits the topic, used for jokes and examples), "
             f"chapters (exactly {nch} items: title = a contested question in plain words; brief = 3-5 sentences: Carter's everyday framing, the advocate's case with specific points from the notes, the antagonist's attack, a tangent, an unresolved friction or a hard-won concession, Carter's own view), "
             "cold_open (2-3 sentences: a live clash mid-argument to open with, then Carter's welcome), "
             "quiz (6 short quiz questions with answers based only on the notes), content_note (empty or one sentence if the topic needs a content note).")
        PS_ = obj({"short_id": S_STR, "title": S_STR, "question": S_STR, "advocate_persona": S_STR, "antagonist_persona": S_STR, "carter_detail": S_STR,
                   "chapters": arr(obj({"title": S_STR, "brief": S_STR})), "cold_open": S_STR, "quiz": arr(obj({"q": S_STR, "a": S_STR})), "content_note": S_STR})
        P = call(q, PS_, temp=0.8, predict=3500)
        P["chapters"] = [c for c in P.get("chapters", []) if c.get("title")][:nch]
        if len(P["chapters"]) < max(3, nch - 2): st(f"ABORT plan: {len(P['chapters'])} chapters"); return 5
    else:
        P = plan_v25(B, theme, L, G, two, F, facts_txt, extra_txt, src_line, cov, notes_user, nch)
        if not P: return 5
    sid = re.sub(r"[^a-z0-9]+", "_", (P.get("short_id") or "").lower()).strip("_")[:28].strip("_")
    if not re.match(r"^[a-z][a-z0-9_]{2,}$", sid): sid = "_".join([w for w in norm(P.get("title", "")).split() if w not in STOP][:3]) or "desk_episode"
    taken = taken_ids(C.root); ep = sid + "_ep1"; n = 2
    while ep in taken or os.path.exists(os.path.join(C.root, "bg_" + sid)) or any(x.startswith(ep) for x in taken):
        sid = re.sub(r"_\d+$", "", sid) + f"_{n}"; ep = sid + "_ep1"; n += 1
    title = re.sub(r"\s+", " ", P.get("title", "").replace('"', "")).strip()[:90] or sid.replace("_", " ").title()
    P["short_id"], P["ep"], P["title"] = sid, ep, title
    wj("plan.json", P); log(f"plan: ep={ep} title='{title}' chapters={len(P['chapters'])}")
    if stop == "plan": st(f"stop_after plan: ep={ep} title='{title}' {len(P['chapters'])} chapters; see gen\\plan.json"); return 0
    # ---- 5 script
    V = None
    if not v25:
        T = TARGET_WORDS[L]; cold_w = round(T * 0.06); fin_w = round(T * 0.09); quiz_w = round(T * 0.06) if B.get("quiz") else 0
        ch_w = round((T - cold_w - fin_w - quiz_w) / len(P["chapters"]))
        names = f"Carter, {adv}" + (f" and {ant}" if two else "")
        spk = ["Host", "Guest", "Guest2"] if two else ["Host", "Guest"]
        system = (f"You are writing a script for a private study podcast in English. Format: content template v2.3.\nEPISODE: \"{title}\". A real argument about {src_line}. The contested question: {P.get('question')}\n"
                  f"SPEAKERS (use exactly these labels in the \"speaker\" field):\n"
                  f"- Host = CARTER. Always the host. Average Joe outside, sharp mind inside. Relaxed, self-ironic, warm, funny through everyday examples ({P.get('carter_detail')}). Mediator who keeps it on track, summarises the disagreement in plain words, gives his OWN view every few minutes and sometimes disagrees with both. About 30% of the words.\n"
                  f"- Guest = {adv.upper()} ({pronoun(adv)}). The advocate. {P.get('advocate_persona')} About {35 if two else 65}%.\n" +
                  (f"- Guest2 = {ant.upper()} ({pronoun(ant)}). The antagonist. {P.get('antagonist_persona')} About 35%.\n" if two else f"- Carter also plays the sceptic: {P.get('antagonist_persona')}\n") +
                  f"TONE: {TONE[tone]}\nDEPTH: {DEPTH[depth]}\n" + (f"THOMAS'S NOTES FOR THIS EPISODE: {notes_user}\n" if notes_user else "") +
                  "STYLE RULES (hard):\n- A real conflict, warm and lively, like smart friends at a kitchen table after dinner. Fair: no straw men, no personal insults. Disagreements may stay unresolved. Avoid 'good point' / 'you're right' reflexes. No stock concessions like 'I'll grant that' or 'I'll concede'.\n"
                  "- Not strictly turn-by-turn: vary rhythm, sometimes a long passionate speech that others cut into, sometimes three quick lines. Speakers address each other by name. Tangents into everyday life (food, family, work, literature) are welcome before Carter steers back. Callbacks to earlier jokes.\n"
                  "- The guests are experts who draw on a deeper pool than the book (other authors, history, cases), but only well-known, verifiable material.\n"
                  "- Humour arises naturally; no forced dad jokes.\n- Name only the book and the author. NEVER mention section numbers, page numbers, chapter numbers, part numbers, translators or editions in the spoken text.\n"
                  "- NEVER invent quotes. Word-for-word quotes only from the ALLOWED VERBATIM QUOTES list; everything else is paraphrase without quotation marks. Do not invent statistics, studies, dates or facts.\n"
                  "- Write for text-to-speech: no stage directions except rarely [laughs] or [sighs] inside a line. No markdown, no asterisks, no emojis, no ellipses. No one-word lines; merge short reactions into fuller lines. Lines are usually 15-120 words.\n"
                  f"- The characters ({names}) are fictional AI voices; their personal stories are invented and modest.")
        parts = [{"title": "Cold open: " + (P.get("question") or title)[:80], "words": cold_w,
                  "brief": f"COLD OPEN. Start mid-argument, no welcome first: {P.get('cold_open')} A quick sharp exchange of 5-7 lines. Then Carter breaks in warmly and welcomes the listeners: today {src_line} and one question: {P.get('question')}. He introduces {adv}" + (f" and {ant}" if two else "") + " with a joke from his own life, and adds one plain sentence that this is an AI-voiced discussion with fictional characters."}]
        for c in P["chapters"]:
            parts.append({"title": c["title"], "words": ch_w, "brief": f"CHAPTER: '{c['title']}'. {c['brief']} Structure: Carter's short framing, the advocate's case, the antagonist's attack, real back-and-forth with interruptions and a tangent, Carter's own view or verdict."})
        if B.get("quiz"):
            qq = "; ".join(f"{x['q']} (answer: {x['a']})" for x in P.get("quiz", [])[:4])
            parts.append({"title": "Quick quiz", "words": quiz_w, "brief": f"QUICK QUIZ for the listeners. Carter announces a quick three-question quiz, asks each question, tells the listeners to answer in their heads, and the guests answer with banter and one-sentence explanations, teasing each other. Use three of these: {qq}"})
        parts.append({"title": "Five takeaways", "words": fin_w, "brief": "FINAL: 'Five takeaways'. Carter gives exactly five numbered takeaways in plain spoken words (First, Second, ... Fifth), each 2-3 sentences, fair to both sides, including what is disputed. Then each guest gets one closing line, and Carter wraps up warmly and mentions that the book details and further reading are in the episode notes."})
    else:
        parts, system, names, spk, V = setup_v25(B, P, title, L, G, two, src_line, quotes, notes_user)
    allL, summ, chap = [], [], []
    for i, p in enumerate(parts, 1):
        r = gen_part(system, quotes_txt, facts_txt, extra_txt, parts, i, p, allL, summ, spk, V=V, attempts=1 if stop == "coldopen" else 3)
        if not r: st(f"ABORT script part {i} failed"); return 5
        while r["lines"] and any(wsim(r["lines"][0]["text"], x["text"]) >= 0.8 for x in allL[-3:]):   # QC: the LLM echoed a line from the end of the last part
            log(f"part {i}: dropped echoed first line (repeats the previous part): {r['lines'][0]['text'][:80]}"); r["lines"].pop(0)
        chap.append({"start": len(allL), "title": p["title"]}); allL += r["lines"]; summ.append(r.get("summary", ""))
        if stop == "coldopen":   # smoke test: one script call only
            cl_, ch_, lg_ = cleanx(allL, chap, spk, names, V); wj("coldopen.json", {"title": p["title"], "lines": cl_, "clean_log": lg_, "stats": turn_stats(cl_)})
            st(f"stop_after coldopen: {len(cl_)} lines {lwords(cl_)} words, {turn_stats(cl_)}; see gen\\coldopen.json"); return 0
    wj("draft_raw.json", allL)
    # ---- 6/7 clean + fact-check
    qok = [q["text"] for q in quotes]; pages_all = [norm(" ".join(b["pages"])) for b in books]
    allL, chap, clog = cleanx(allL, chap, spk, names, V)
    st(f"fact-check: {len(chap)} parts"); fixes = []
    FS = obj({"issues": arr(obj({"line": S_INT, "problem": S_STR, "fixed_text": S_STR}))})
    for k, c in enumerate(chap):
        e = chap[k + 1]["start"] if k + 1 < len(chap) else len(allL); seg = allL[c["start"]:e]
        listing = "\n".join(f"{j}: {l['speaker']}: {l['text']}" for j, l in enumerate(seg))
        q = (f"Fact-check this podcast script part about {src_line}.\nNOTES (what the book says):\n{facts_txt}\n\nALLOWED VERBATIM QUOTES:\n{quotes_txt}\n\nSCRIPT PART '{c['title']}':\n{listing}\n\n"
             "List ONLY real problems: (a) words in quotation marks presented as a quote from the book that are not in the allowed list; (b) claims about what the book or author says that contradict the notes or are unsupported; "
             "(c) invented statistics, studies, dates, or misattributed claims about other thinkers (only flag if clearly wrong or invented); (d) spoken page/section/chapter numbers, translators or editions; (e) markdown or stage directions other than [laughs]/[sighs]. "
             "For each give line (the number), problem, and fixed_text = the full corrected line, same speaker, same length and voice, only the problem changed. Return {\"issues\":[]} if none.")
        try: R = call(q, FS, temp=0.2, predict=3000)
        except Exception as ex: log(f"fact-check part {k} failed: {ex}"); fixes.append({"part": c["title"], "line": None, "problem": f"FACT-CHECK CALL FAILED: {ex}", "old": "", "new": ""}); continue
        for it in R.get("issues", []):
            j = it.get("line"); ft = (it.get("fixed_text") or "").strip()
            if not isinstance(j, int) or not (0 <= j < len(seg)) or not ft: continue
            ft = strip_label(ft, ["Carter"] + list(G))
            if words(ft) < 0.5 * words(seg[j]["text"]): continue
            ok, r_self, r_oth = fc_fix_ok(seg, j, ft)   # QC: reject index-shifted / unrelated fixes
            if not ok:
                log(f"fact-check part {k} line {j}: REJECTED fix (self {r_self:.2f}, other line {r_oth:.2f}; index shift?): {ft[:80]}")
                fixes.append({"part": c["title"], "line": c["start"] + j, "problem": "REJECTED (fix does not match this line - index shift?): " + it.get("problem", ""), "old": seg[j]["text"], "new": seg[j]["text"]}); continue
            old = seg[j]["text"]; allL[c["start"] + j]["text"] = ft
            fixes.append({"part": c["title"], "line": c["start"] + j, "problem": it.get("problem", ""), "old": old, "new": ft})
    allL, chap, clog2 = cleanx(allL, chap, spk, names, V); clog += clog2
    allL, qlog = check_quotes(allL, qok, pages_all); clog += qlog
    log(f"fact-check: {len(fixes)} fix(es) applied; clean: {len(clog)} change(s)")
    # ---- 8 length gate
    for rnd in range(5):
        w = lwords(allL); pred = OVERHEAD_S + SEC_PER_WORD * w
        log(f"length gate round {rnd}: {len(allL)} lines {w} words -> predicted {pred:.0f} s (window {lo}-{hi}, aim {lo+MARGIN_LO}-{hi-MARGIN_HI})")
        if lo + MARGIN_LO <= pred <= hi - MARGIN_HI or rnd == 4: break
        if pred < lo + MARGIN_LO:
            need = int(((lo + MARGIN_LO + 60) - pred) / SEC_PER_WORD) + 1
            allL, chap = extend(system, quotes_txt, facts_txt, allL, chap, need, spk, parts)
        else:
            allL, chap = condense(system, allL, chap, int((pred - (hi - MARGIN_HI - 60)) / SEC_PER_WORD) + 1, spk)
        allL, chap, c3 = cleanx(allL, chap, spk, names, V); allL, q3 = check_quotes(allL, qok, pages_all); clog += c3 + q3
    w = lwords(allL); pred = OVERHEAD_S + SEC_PER_WORD * w
    if V:   # v2.5 writes with real names; renders expect Host/Guest/Guest2 -> map back here (everything below is role-based as before)
        log(f"v2.5 turn stats: {turn_stats(allL)}")
        allL = [{"speaker": V["role"][l["speaker"]], "text": l["text"]} for l in allL]; spk = ["Host", "Guest", "Guest2"] if two else ["Host", "Guest"]
    wj("script_final.json", allL); wj("chapters_final.json", {"title": title, "sections": chap})
    if not (lo + 30 <= pred <= hi - 60):
        st(f"ABORT length gate (pre-TTS): {w} words -> predicted {pred:.0f} s outside {lo+30}-{hi-60} s; no TTS"); return 3
    share = {s: sum(words(l["text"]) for l in allL if l["speaker"] == s) / max(1, w) for s in spk}
    log("speaker share: " + ", ".join(f"{s} {v*100:.0f}%" for s, v in share.items()))
    # ---- 9 learn + images
    st("learn materials + FLUX prompts")
    scr = "\n".join(f"{'Carter' if l['speaker']=='Host' else (adv if l['speaker']=='Guest' else ant)}: {l['text']}" for l in allL)
    sw = scr.split(); scr_short = " ".join(sw[:9000])
    LS = obj({"description": S_STR, "takeaways": arr(S_STR), "quiz": arr(obj({"q": S_STR, "a": S_STR})), "anki": arr(obj({"front": S_STR, "back": S_STR})),
              "mentioned": arr(S_STR), "tags": arr(S_STR)})
    q = (f"Episode \"{title}\" on {src_line}. Script:\n{scr_short}\n\nNOTES:\n{facts_txt}\n\nReturn JSON: description (YouTube description, 90-140 words, who argues what, warm, mention that it is an AI-voiced discussion with fictional characters), "
         "takeaways (exactly 5 strings, each 2-3 sentences, " + ("covering what each speaker took away and the question left open" if V else "matching Carter's five takeaways") + ", fair, including what is disputed), quiz (10 questions with short answers, only from the notes and the script), "
         "anki (12 flashcards: front = term or question, back = short answer; no semicolons), mentioned (other authors and works the speakers mention beyond the source books, as 'Author, Title' strings; only real, well-known ones), tags (10 short tags).")
    LR = call(q, LS, temp=0.3, predict=4000)
    IS = obj({"style": S_STR, "images": arr(obj({"chapter": S_INT, "subject": S_STR}))})
    chl = "\n".join(f"{k}: {c['title']}" for k, c in enumerate(chap))
    q = (f"Design {N_IMAGES[L]} background images for a podcast video, episode \"{title}\" ({src_line}). Chapters:\n{chl}\n\nReturn JSON: style (one palette/mood phrase, e.g. 'deep teal and slate blue palette with warm amber highlights'), "
         f"images ({N_IMAGES[L]} items, in chapter order, every chapter at least one: chapter = index above; subject = one concrete visual scene, symbolic, 12-25 words, objects and places only: NO people, NO faces, NO text, NO letters, NO logos, no gore).")
    IR = call(q, IS, temp=0.8, predict=2000)
    write_outputs(B, P, allL, chap, facts, quotes, fixes, clog, LR, IR, src_line, books, share, pred, F, t0)
    return 0

# ---------------- content style v2.6 (2026-11-07): humanity dial on top of v2.5 ----------------
HUMANITY = {"low": "HUMANITY LOW: mostly on the topic. One everyday 'what does this mean for me' moment per two chapters; personal angles brief.",
            "medium": "HUMANITY MEDIUM: every chapter touches down in ordinary life at least once (Carter's everyday beat); each guest brings their own experience once or twice in the episode; one tangent.",
            "high": "HUMANITY HIGH: the topic is seen through ordinary lives. Every chapter has a real everyday beat plus a personal moment from one of the guests; more warmth, teasing and small talk between the points; one tangent; technical detail only where it changes what a listener would do."}
NERD_CAP = {"low": 3, "medium": 2, "high": 1}
def v26_on(): return getattr(C, "style", DEFAULT_STYLE) == "v2.6"
def human_level(B): return B.get("humanity") or DEFAULT_HUMANITY
def v26_system(B, names_l, G):
    h = human_level(B); cap = NERD_CAP[h]
    return (f"HUMANITY (content style v2.6): {HUMANITY[h]}\n"
            "HUMAN RULES (hard):\n"
            "- EVERYDAY BEAT: Carter is the listener's stand-in. In every chapter he asks, in plain words, what this means for an ordinary person (my phone, my job, my kids, my money, my Tuesday), and the guests answer with a concrete daily-life picture, not a principle.\n"
            f"- PERSONAL ANGLE: each guest tells something from their OWN life as that character (their job, family, a mistake they made, something that happened to them this year), in first person, consistent with their bible ('running life', 'who'). Invented and modest; never presented as a real person's life.\n"
            "- ANALOGIES OVER JARGON: explain every mechanism with an everyday comparison first (kitchen, traffic, a pub quiz, a group chat), the technical term second, if at all.\n"
            f"- NERD CAP: never more than {cap} turn(s) in a row of pure technical detail (names, numbers, mechanisms, history) - after that someone brings it back to daily life, reacts, jokes or asks 'so what?'.\n"
            "- REAL CONVERSATION: light disagreement, teasing and small laughs; people interrupt each other (a line may break off with '...' and the other jumps in), finish each other's sentences now and then, and sometimes admit they don't know. Warmth over cleverness.\n")
def v26_chapter_extra(B, P, k, G):
    t = P.get("tangent") or {}; pa = P.get("personal_angles") or []
    x = " EVERYDAY BEAT (required): Carter asks what this means for an ordinary listener, and the answer is a concrete daily-life picture."
    for a_ in pa:
        if a_.get("chapter") == k: x += f" PERSONAL ANGLE: {a_.get('guest')} tells, in first person, their own experience: {a_.get('experience')}."
    if t.get("chapter") == k:
        x += (f" TANGENT (30-60 seconds, about 80-150 words over several short turns): {t.get('who')} drifts off-topic into {t.get('story')}; "
              f"someone teases them for it; then it lands back with a point: {t.get('point')}.")
    return x

# ---------------- content style v2.5 (cast bible, named speakers, story-first shapes, ledger) ----------------
def load_bible():
    for d in (os.path.join(C.root, "templates"), os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")):
        f = os.path.join(d, "cast_bible_v1.json")
        if os.path.isfile(f): return json.load(open(f, encoding="utf-8-sig"))
    raise RuntimeError("templates\\cast_bible_v1.json missing (needed by content style v2.5)")

def bible_txt(n, b):
    x = b["host"] if n == b["host"]["name"] else b["guests"][n]
    keys = ["archetype", "who", "job", "expertise", "lens", "natural_side", "voice", "quirk", "flaw", "hates", "running_life", "concedes_like", "stake_hint"]
    return f"{n.upper()} ({x.get('gender', '')}, {x.get('accent', '')}, {x.get('age', '')}): " + " ".join(f"{k.replace('_', ' ').capitalize()}: {x[k]}" for k in keys if x.get(k))

def pairing_txt(G, b):
    if len(G) < 2: return ""
    key = {G[0], G[1]}
    for p in b.get("pairings", {}).get("best", []):
        if set(p.get("pair", [])) == key: return f"WHY THIS PAIR CLASHES WELL: {p.get('clash') or p.get('why', '')}"
    for p in b.get("pairings", {}).get("avoid", []):
        if set(p.get("pair", [])) == key: log(f"WARNING cast bible lists {G[0]}+{G[1]} under 'avoid': {p.get('why', '')}")
    return "PAIRING: no curated note for this pair; make their bibles collide on the crux."

def plan_v25(B, theme, L, G, two, F, facts_txt, extra_txt, src_line, cov, notes_user, nch):
    b = load_bible(); C.bible = b; host = "Carter"
    cast = "\n".join(bible_txt(n, b) for n in [host] + list(G))
    q = (f"Plan a {L}-minute episode of a private English study podcast (content style v2.5: a story-first debate between fixed recurring characters).\n"
         f"TOPIC: {theme or F.get('focus')}\nContested question found in the sources: {F.get('focus')}\nSources: {src_line}\n{TONE[B['tone']]}\n{DEPTH[B['depth']]}\n"
         + (f"Thomas's notes: {notes_user}\n" if notes_user else "") + f"CAST (fixed character bibles; never change who they are):\n{cast}\n{pairing_txt(G, b)}\n"
         + ("" if two else "Carter himself plays the sceptic against the one guest.\n") +
         f"NOTES FROM THE SOURCES:\n{facts_txt}\n{extra_txt}\n\nAlready covered episodes (do not repeat their angle):\n" + "\n".join(cov[-40:]) +
         f"\n\nReturn JSON: short_id (2-3 lower-case English words joined by _), title (catchy, max 70 chars), question (the one contested question in plain words), "
         f"crux (one sentence: the precise point {G[0]} and {G[1] if two else 'Carter'} disagree on, which the episode must NOT resolve), "
         f"position_a ({G[0]}'s position in 1-2 sentences, true to {G[0]}'s bible), position_b (same for {G[1] if two else 'Carter, as sceptic'}), "
         f"stake_a (what {G[0]} personally has riding on it, one sentence, consistent with the bible), stake_b (same for {G[1] if two else 'Carter'}), "
         "concession_a (a side point - NOT the crux - that A concedes to B, with the concrete reason that convinces A; and the chapter number where it happens), concession_b (same for B to A), "
         "running_gag (one gag born from the topic or a character quirk: keyword = one short distinctive word or phrase, setup, escalation, payoff for the last part), "
         "carter_story (an everyday situation from Carter's life that fits the topic: setup in the cold open, a twist mid-episode, a payoff at the end), "
         "cold_open_scene (2-3 sentences: a concrete scene to open inside - a real case from the notes or Carter's situation - that makes the disagreement erupt within 4 lines), "
         f"chapters (exactly {nch} items in story order: title = a contested question or a case in plain words; shape = one of {', '.join(SHAPES)} (use at least 3 different shapes, at most 2 case_file); "
         "case = the concrete case, story, study or scenario from the notes the chapter is built on (say which source); brief = 2-4 sentences of what happens and how the argument moves), "
         "quiz (6 short quiz questions with answers based only on the notes), content_note (empty or one sentence if the topic is sensitive)."
         + (f"\n{HUMANITY[human_level(B)]}\nAlso return: tangent (ONE 30-60 second detour for the whole episode: chapter = number, who = a guest or Carter, story = an everyday "
            "off-topic story or hobby rant true to that character's bible, point = the point it lands back on, tied to the chapter's case), personal_angles "
            f"(for each guest {', '.join(G)}: 1-2 items, chapter = number, guest = name, experience = one sentence, first person, an experience from that character's own "
            "life that makes the topic personal; invented, modest, consistent with the bible)." if v26_on() else ""))
    CS = obj({"point": S_STR, "reason": S_STR, "chapter": S_INT})
    PS_ = obj({"short_id": S_STR, "title": S_STR, "question": S_STR, "crux": S_STR, "position_a": S_STR, "position_b": S_STR, "stake_a": S_STR, "stake_b": S_STR,
               "concession_a": CS, "concession_b": CS, "running_gag": obj({"keyword": S_STR, "setup": S_STR, "escalation": S_STR, "payoff": S_STR}),
               "carter_story": obj({"setup": S_STR, "twist": S_STR, "payoff": S_STR}), "cold_open_scene": S_STR,
               "chapters": arr(obj({"title": S_STR, "shape": {"type": "string", "enum": list(SHAPES)}, "case": S_STR, "brief": S_STR})),
               "quiz": arr(obj({"q": S_STR, "a": S_STR})), "content_note": S_STR})
    if v26_on():   # v2.6: extra plan fields (same schema helpers)
        PS_["properties"]["tangent"] = obj({"chapter": S_INT, "who": S_STR, "story": S_STR, "point": S_STR}); PS_["required"] = list(PS_.get("required", [])) + ["tangent", "personal_angles"]
        PS_["properties"]["personal_angles"] = arr(obj({"chapter": S_INT, "guest": S_STR, "experience": S_STR}))
    P = call(q, PS_, temp=0.8, predict=4000)
    P["chapters"] = [c for c in P.get("chapters", []) if c.get("title")][:nch]
    if len(P["chapters"]) < max(3, nch - 2): st(f"ABORT plan: {len(P['chapters'])} chapters"); return None
    for c in P["chapters"]:
        if c.get("shape") not in SHAPES: c["shape"] = "case_file"
    P["content_style"] = getattr(C, "style", "v2.5"); P["cast"] = [host] + list(G)
    if v26_on(): P["humanity"] = human_level(B); log(f"v2.6 plan: humanity {P['humanity']}, tangent ch {(P.get('tangent') or {}).get('chapter')}, personal angles {len(P.get('personal_angles') or [])}")
    return P

def setup_v25(B, P, title, L, G, two, src_line, quotes, notes_user):
    b = getattr(C, "bible", None) or load_bible(); C.bible = b
    names_l = ["Carter"] + list(G); spk = names_l[:]; role = dict(zip(names_l, ["Host", "Guest", "Guest2"]))
    A, Bn = G[0], (G[1] if two else "Carter"); gag = P.get("running_gag") or {}; cs = P.get("carter_story") or {}
    ca, cb = P.get("concession_a") or {}, P.get("concession_b") or {}
    banned = list(b.get("banned_phrases", [])); caps = b.get("caps", {})
    T = TARGET_WORDS[L]; nq = 3 if L <= 20 else 4
    cold_w = min(230, round(T * 0.06)); fin_w = round(T * 0.07); quiz_w = round(T * 0.06) if B.get("quiz") else 0
    ch_w = round((T - cold_w - fin_w - quiz_w) / len(P["chapters"]))
    system = (f"You are writing a script for a private study podcast in English. Format: content style {'v2.6 (story-first, human, everyday conversation' if v26_on() else 'v2.5 (story-first debate'} between fixed recurring characters). "
              f"The episode is about {L} minutes long. EPISODE: \"{title}\".\nTHE QUESTION: {P.get('question')}\nTHE CRUX (never resolved; it is still open at the end): {P.get('crux')}\n"
              f"POSITIONS: {A}: {P.get('position_a')} | {Bn}: {P.get('position_b')}\nSTAKES: {A}: {P.get('stake_a')} | {Bn}: {P.get('stake_b')}\n"
              f"CONCESSIONS (exactly one each, earned, on a side point, never the crux): {A} concedes to {Bn} in chapter {ca.get('chapter')}: {ca.get('point')} (because {ca.get('reason')}). "
              f"{Bn} concedes to {A} in chapter {cb.get('chapter')}: {cb.get('point')} (because {cb.get('reason')}). Each concession is in the character's own words (see 'concedes like').\n"
              f"RUNNING GAG (keyword '{gag.get('keyword')}', at most {caps.get('running_gag_uses', 3)} uses: setup, escalation, payoff at the end): {gag.get('setup')} / {gag.get('escalation')} / {gag.get('payoff')}\n"
              f"CARTER'S STORY: setup {cs.get('setup')} / twist {cs.get('twist')} / payoff {cs.get('payoff')}\n"
              "CAST (fixed character bibles: keep every voice, quirk and flaw consistent; the speaker field is the character's NAME):\n" + "\n".join("- " + bible_txt(n, b) for n in names_l) + "\n" +
              pairing_txt(G, b) + f"\nShare of words: Carter about 30%, the guests about {'35% each' if two else '70%'}.\n"
              f"TONE: {TONE[B['tone']]}\nDEPTH: {DEPTH[B['depth']]}\n" + (f"THOMAS'S NOTES FOR THIS EPISODE: {notes_user}\n" if notes_user else "") +
              (v26_system(B, names_l, G) if v26_on() else "") +
              ("TURN RULES (hard):\n- Short, back-and-forth turns: average 15-30 words, never more than 70 words in one turn. A long thought is split by the others cutting in. Carter speaks in relaxed, complete sentences, not clipped rapid-fire.\n" if v26_on() else
               "TURN RULES (hard):\n- Short, interruptive turns: average 25-40 words, never more than 90 words in one turn. A long thought is split by the others cutting in.\n") +
              "- At least a third of the turns react directly to the line before (challenge, joke, 'wait, back up', a question). Reactions are 3-10 words, never a single word.\n"
              "- The guests talk to EACH OTHER, not only to Carter. Nobody says their own name. Names are used sparingly, never as filler.\n"
              "- Every chapter is built on its concrete case or story first; the abstract argument grows out of the case.\n"
              "- Never invent quotes: word-for-word quotes only from the ALLOWED VERBATIM QUOTES list, each quote at most once in the whole episode. Statistics: each number at most twice.\n"
              "- Name sources as people or sites say them out loud ('a Stanford study', 'Wikipedia's article on...'); NEVER spell out URLs, file names, page, section or chapter numbers.\n"
              "- BANNED PHRASES (never use them): " + "; ".join(f"'{x}'" for x in banned) + "\n"
              "- Write for text-to-speech: the only allowed stage directions are [laughs] or [sighs] inside a line, at most one per turn and rarely. No markdown, no asterisks, no emojis, no brackets otherwise.\n"
              f"- The characters ({', '.join(names_l)}) are fictional AI voices; their personal stories are invented and modest.")
    parts = [{"title": "Cold open: " + (P.get("question") or title)[:80], "words": cold_w,
              "brief": f"COLD OPEN (max ~90 seconds). Open INSIDE this scene, no welcome first: {P.get('cold_open_scene')} The disagreement erupts within 4 lines in short, quick turns. "
                       f"Carter's story setup appears ({cs.get('setup')}). Then Carter names the question in one plain sentence, welcomes the listeners, introduces {', '.join(G)} in one short line each, "
                       "and adds one plain sentence that this is an AI-voiced discussion with fictional characters."}]
    for k, c in enumerate(P["chapters"], 1):
        parts.append({"title": c["title"], "words": ch_w, "shape": c.get("shape"),
                      "brief": f"CHAPTER {k}: '{c['title']}'. SHAPE: {SHAPES.get(c.get('shape'), SHAPES['case_file'])} CASE: {c.get('case')}. {c.get('brief')} "
                               + (f"This is where {A} makes the concession. " if ca.get("chapter") == k else "") + (f"This is where {Bn} makes the concession. " if cb.get("chapter") == k else "")
                               + (v26_chapter_extra(B, P, k, G) if v26_on() else "")
                               + " End on a short hook into the next chapter, not a summary."})
    if B.get("quiz"):
        qq = "; ".join(f"{x['q']} (answer: {x['a']})" for x in P.get("quiz", [])[:nq])
        parts.append({"title": "Quick quiz", "words": quiz_w, "brief": f"QUICK QUIZ as a game: Carter quizzes the guests (and the listeners) with exactly {nq} questions: {qq}. "
                      "Guests answer in character, banter, Carter keeps score; one guest gets one wrong. Short turns."})
    parts.append({"title": "Takeaways", "words": fin_w, "brief": f"TAKEAWAYS: Carter asks each person for their takeaway. Each speaker (Carter last) gives ONE takeaway in their own voice, max 40 words each, "
                  f"true to their position; the crux ({P.get('crux')}) is explicitly left open. Running-gag payoff: {gag.get('payoff')}. Carter's story payoff: {cs.get('payoff')}. "
                  "Then Carter's short warm sign-off (1-2 lines). No numbered list, no recap of every chapter."})
    V = {"role": role, "names": names_l, "quotes": [q["text"] for q in quotes], "gag": (gag.get("keyword") or "").strip(), "banned": banned,
         "cap_quote": caps.get("verbatim_quote_uses", 1), "cap_stat": caps.get("statistic_uses", 2), "cap_gag": caps.get("running_gag_uses", 3)}
    return parts, system, ", ".join(names_l[:-1]) + " and " + names_l[-1], spk, V

STAT_RE = re.compile(r"\b\d[\d,.]*\s*(?:%|percent|per cent|million|billion|trillion|thousand)|\b\d+\s+(?:out of|in)\s+\d+\b", re.I)
def stats_in(t): return [re.sub(r"\s+", " ", m.group(0).lower().replace("per cent", "percent").replace("%", " percent")).strip() for m in STAT_RE.finditer(t)]

def turn_stats(L):
    w = [words(l["text"]) for l in L] or [0]; tot = max(1, sum(w))
    car = sum(words(l["text"]) for l in L if l["speaker"] in ("Carter", "Host"))
    return {"turns": len(L), "avg_words": round(sum(w) / max(1, len(L)), 1), "max_words": max(w), "over90": sum(x > 90 for x in w), "carter_share": round(car / tot, 2)}

def turns_ok(L):
    if not L: return False
    w = [words(l["text"]) for l in L]
    if v26_on(): return sum(w) / len(w) <= 35 and sum(x > 70 for x in w) <= 0.1 * len(w)   # v2.6: more back-and-forth
    return sum(w) / len(w) <= 50 and sum(x > 90 for x in w) <= 0.2 * len(w)

def ledger_text(allL, V):
    """used-material tracker fed into every v2.5 part: caps repeats before they happen"""
    txt = " ".join(l["text"] for l in allL); n = norm(txt); out = ["USED-MATERIAL LEDGER (obey it):"]
    used_q = [q for q in V["quotes"] if norm(q) and norm(q) in n]
    if used_q: out.append("- Quotes ALREADY USED (do not quote them again): " + " | ".join(q[:90] for q in used_q[:20]))
    sc = {}
    for x in stats_in(txt): sc[x] = sc.get(x, 0) + 1
    full = [k for k, v in sc.items() if v >= V["cap_stat"]]
    if full: out.append(f"- Statistics used {V['cap_stat']} times already (do not repeat): " + ", ".join(full[:20]))
    if V["gag"]:
        g = sum(V["gag"].lower() in l["text"].lower() for l in allL)
        out.append(f"- Running gag '{V['gag']}' used {g} of {V['cap_gag']} times" + (" (budget spent: no more uses)" if g >= V["cap_gag"] else ""))
    grams = {}
    for l in allL:
        ws = norm(l["text"]).split()
        for k in range(len(ws) - 3): grams[" ".join(ws[k:k + 4])] = grams.get(" ".join(ws[k:k + 4]), 0) + 1
    rep_ = [g for g, c in sorted(grams.items(), key=lambda z: -z[1]) if c >= 2][:10]
    if rep_: out.append("- Phrases already repeated (do not use again): " + "; ".join(rep_))
    if allL:
        ts = turn_stats(allL); out.append(f"- Turns so far: average {ts['avg_words']} words (target {'15-30' if v26_on() else '25-40'}), Carter share {int(ts['carter_share'] * 100)}% (target ~30%).")
    out.append("- Banned phrases: " + "; ".join(V["banned"]))
    return "\n".join(out)

def clean_v25(L, chap, V):
    """v2.5 mechanical checks after clean(): self-address, near-duplicates, banned phrases, quote/statistic caps, URLs/file names, tag cap"""
    log_ = []; out = []; starts = {c["start"]: k for k, c in enumerate(chap)}; newstart = {}
    qn = [norm(q) for q in V["quotes"] if words(q) >= 4]; qused = {}; sused = {}; gag = V["gag"].lower(); guses = 0
    def drop_sent(t, pred_):
        ss = re.split(r"(?<=[.!?])\s+", t); keep = [x for x in ss if not pred_(x)]
        return " ".join(keep) if keep else t
    for i, l in enumerate(L):
        if i in starts: newstart[starts[i]] = len(out)
        t0 = l["text"]; t = t0; sp = l["speaker"]
        nm = re.escape(sp)   # self-address: the speaker's own name used as a vocative
        t = re.sub(r"(^|[.!?]\s+)" + nm + r"\s*,\s*(\w)", lambda m: m.group(1) + m.group(2).upper(), t)
        t = re.sub(r",\s*" + nm + r"\s*([.!?])", r"\1", t)
        t = re.sub(r"https?://\S+|www\.\S+", "", t)
        t = re.sub(r"\b[\w\-]+\.(?:pdf|epub|txt|md|html?)\b", "the source", t, flags=re.I)
        for bp in V["banned"]:
            if bp.lower() in t.lower(): t = drop_sent(t, lambda x, bp=bp: bp.lower() in x.lower())
            if bp.lower() in t.lower(): t = re.sub(r"\s*,?\s*" + re.escape(bp) + r"\s*,?", " ", t, flags=re.I)
        for m in list(re.finditer(r"[\"\u201c]([^\"\u201c\u201d]{10,400})[\"\u201d]", t)):
            n = norm(m.group(1)); hit = next((k for k, q in enumerate(qn) if n and (n in q or q in n)), None)
            if hit is None: continue
            qused[hit] = qused.get(hit, 0) + 1
            if qused[hit] > V["cap_quote"]: t = t.replace(m.group(0), "").strip()
        for x in stats_in(t):
            sused[x] = sused.get(x, 0) + 1
            if sused[x] > V["cap_stat"]: t = drop_sent(t, lambda y, x=x: x in " ".join(stats_in(y)))
        tags = list(re.finditer(r"\[(?:laughs|sighs)\]", t, flags=re.I))
        for m in reversed(tags[1:]): t = t[:m.start()] + t[m.end():]
        t = re.sub(r"\s+([,.!?;:])", r"\1", re.sub(r"\s{2,}", " ", t)).replace(",,", ",").strip(" ,")
        if gag and gag in t.lower():
            guses += 1
            if guses > V["cap_gag"]: log_.append({"line": i, "old": t0[:120], "new": f"(note: running gag use {guses} > budget {V['cap_gag']})"})
        if words(t) >= 8 and any(wsim(t, x["text"]) >= 0.85 for x in out[-40:]):
            log_.append({"line": i, "old": t0, "new": "(dropped: near-duplicate of an earlier line)"}); continue
        if words(t) < 3:
            log_.append({"line": i, "old": t0, "new": "(dropped: nothing left after v2.5 checks)"}); continue
        if t != t0: log_.append({"line": i, "old": t0, "new": t})
        if words(t) > (70 if v26_on() else 90): log_.append({"line": i, "old": t[:120], "new": f"(note: long turn, {words(t)} words)"})
        out.append({"speaker": sp, "text": t})
    ch = []
    for k, c in enumerate(chap):
        s_ = newstart.get(k, None)
        if s_ is None or (ch and s_ <= ch[-1]["start"]): continue
        ch.append({"start": s_, "title": c["title"]})
    if ch: ch[0]["start"] = 0
    return out, ch, log_

def cleanx(L, chap, spk, names, V=None):
    L, chap, lg = clean(L, chap, spk, names)
    if V: L, chap, lg2 = clean_v25(L, chap, V); lg += lg2
    return L, chap, lg

def gen_part(system, quotes_txt, facts_txt, extra_txt, parts, i, p, allL, summ, spk, V=None, attempts=3):
    SCHEMA = obj({"lines": arr(obj({"speaker": {"type": "string", "enum": spk}, "text": S_STR})), "summary": S_STR})
    tail = "\n".join(f'{l["speaker"]}: {l["text"]}' for l in allL[-(6 if V else 10):])
    prompt = (system + "\n\nALLOWED VERBATIM QUOTES (only these may be quoted word for word; attribute to author/book; never invent others):\n" + quotes_txt +
              "\n\nFACTS FROM THE BOOK YOU MAY USE:\n" + facts_txt + "\n\n" + extra_txt + "\n\nTHE EPISODE'S PARTS:\n" + "\n".join(f"{k+1} {x['title']}" for k, x in enumerate(parts)) +
              "\n\nSTORY SO FAR (summaries of earlier parts):\n" + ("\n".join(f"Part {k+1}: {s}" for k, s in enumerate(summ)) or "(this is the start)") +
              ("\n\n" + ledger_text(allL, V) if V else "") +
              "\n\nLAST LINES SO FAR:\n" + (tail or "(none)") +
              f"\n\nNOW WRITE PART {i} of {len(parts)}: {p['brief']}\nLength: about {p['words']} words in total across all lines (this matters; do not stop short). "
              "Continue seamlessly from the last lines; do not restart or re-introduce. Return JSON {\"lines\":[{\"speaker\":\"" + "|".join(spk) + "\",\"text\":...}],\"summary\":\"3-5 sentences of what happened in this part, incl. any running jokes, wounds or callbacks\"}.")
    best = None
    for att in range(attempts):
        st(f"script part {i}/{len(parts)} attempt {att+1}"); t = time.time()
        try: r = call(prompt, SCHEMA, temp=0.85, predict=4500, tries=2)
        except Exception as e: log(f"part {i} att {att} ERROR {e}"); continue
        r["lines"] = [l for l in r.get("lines", []) if l.get("text", "").strip() and l.get("speaker") in spk]
        w = lwords(r["lines"]); log(f"part {i} att {att+1}: {len(r['lines'])} lines {w} words ({time.time()-t:.0f} s)" + (f" {turn_stats(r['lines'])}" if V else ""))
        tok = turns_ok(r["lines"]) if V else True   # v2.5: reject monologue attempts (avg turn > 50 words or > 20% of turns over 90)
        if best is None or (tok, w) > (best[2], best[0]): best = (w, r, tok)
        if w >= 0.88 * p["words"] and tok: break
    if best: wj(f"part{i:02d}.json", best[1])
    return best[1] if best else None

def clean(L, chap, spk, names):
    log_ = []; out = []; starts = {c["start"]: k for k, c in enumerate(chap)}; newstart = {}
    nm = "|".join(re.escape(n.strip()) for n in names.replace(" and ", ", ").split(","))
    for i, l in enumerate(L):
        if i in starts: newstart[starts[i]] = len(out)
        t0 = l["text"]; t = t0
        t = strip_label(t, nm.split("|"))
        t = re.sub(r"\*+|__|`|^#+\s*|^[->]\s+", "", t)
        t = re.sub(r"\[(?!laughs\]|sighs\])[^\]]{0,40}\]", "", t, flags=re.I)
        t = re.sub(r"\((?:laughs|sighs|pause|beat|chuckles)[^)]*\)", "", t, flags=re.I)
        t = t.replace("\u2026", ", ").replace("...", ", ")
        t = re.sub(r",?\s*\b(?:on|at|in|from)?\s*(?:page|pages|p\.|pp\.|section|sections|\u00a7+)\s*\d+[\d\-\u2013, ]*", " ", t, flags=re.I)
        t = re.sub(r"\b(?:in|from)\s+(?:chapter|part)\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\b", "in the book", t, flags=re.I)
        t = re.sub(r"[\U0001F300-\U0001FAFF]", "", t)
        t = re.sub(r"\s+([,.!?;:])", r"\1", re.sub(r"\s{2,}", " ", t)).replace(",,", ",").strip()
        if t != t0: log_.append({"line": i, "old": t0, "new": t})
        if words(t) < 3:
            if out and out[-1]["speaker"] == l["speaker"]: out[-1]["text"] += " " + t
            log_.append({"line": i, "old": t0, "new": "(merged/dropped: too short)"}); continue
        out.append({"speaker": l["speaker"], "text": t})
    ch = []
    for k, c in enumerate(chap):
        s = newstart.get(k, None)
        if s is None: continue
        if ch and s <= ch[-1]["start"]: continue
        ch.append({"start": s, "title": c["title"]})
    if ch: ch[0]["start"] = 0
    return out, ch, log_

def check_quotes(L, qok, pages_all):
    log_ = []; nq = [norm(q) for q in qok]
    for i, l in enumerate(L):
        t = l["text"]
        for m in list(re.finditer(r"[\"\u201c]([^\"\u201c\u201d]{20,400})[\"\u201d]", t)):
            s = m.group(1); n = norm(s)
            if words(s) < 6: continue
            ok = any(n in x or (x in n and words(x) >= 6) for x in nq) or any(n in p for p in pages_all)
            if not ok:
                t = t.replace(m.group(0), s); log_.append({"line": i, "old": m.group(0), "new": "(quotation marks removed: not a verified verbatim quote)"})
        l["text"] = t
    return L, log_

def extend(system, quotes_txt, facts_txt, L, chap, need, spk, parts):
    SCHEMA = obj({"lines": arr(obj({"speaker": {"type": "string", "enum": spk}, "text": S_STR}))})
    ends = [(chap[k + 1]["start"] if k + 1 < len(chap) else len(L)) for k in range(len(chap))]
    cands = [k for k, c in enumerate(chap) if 0 < k and not c["title"].startswith(("Five takeaways", "Quick quiz", "Takeaways", "Cold open"))] or list(range(len(chap)))
    cands.sort(key=lambda k: lwords(L[chap[k]["start"]:ends[k]]))
    nch_ = min(len(cands), max(1, -(-need // 450))); per = max(250, min(700, need // nch_ + 40)); todo = need
    for k in cands:
        if todo <= 0: break
        s, e = chap[k]["start"], ends[k]; seg = L[s:e]; at = max(1, len(seg) - 2)
        before = "\n".join(f"{l['speaker']}: {l['text']}" for l in seg[:at]); after = "\n".join(f"{l['speaker']}: {l['text']}" for l in seg[at:])
        st(f"length gate: extending chapter '{chap[k]['title'][:40]}' by ~{per} words")
        prompt = (system + "\n\nALLOWED VERBATIM QUOTES:\n" + quotes_txt + "\n\nFACTS:\n" + facts_txt + f"\n\nCHAPTER '{chap[k]['title']}' SO FAR:\n{before}\n\n[INSERT HERE]\n\n{after}\n\n"
                  f"Write about {per} words of NEW lines to insert at [INSERT HERE]: a deeper round of the argument or a new tangent (a story, an everyday case, a well-known example from the wider debate), with interruptions and emotion, "
                  "that leads naturally into the lines after the insert. Do not conclude the chapter, do not repeat what was said. Return JSON {\"lines\":[...]}.")
        try: r = call(prompt, SCHEMA, temp=0.85, predict=2500, tries=2)
        except Exception as ex: log(f"extend failed: {ex}"); continue
        new = [l for l in r.get("lines", []) if l.get("text", "").strip() and l.get("speaker") in spk]
        if not new: continue
        L = L[:s + at] + new + L[s + at:]; add = len(new)
        for j in range(k + 1, len(chap)): chap[j]["start"] += add
        ends = [(chap[j + 1]["start"] if j + 1 < len(chap) else len(L)) for j in range(len(chap))]
        todo -= lwords(new); log(f"extend: +{len(new)} lines +{lwords(new)} words in '{chap[k]['title'][:40]}'")
    return L, chap

def condense(system, L, chap, cut, spk):
    SCHEMA = obj({"lines": arr(obj({"speaker": {"type": "string", "enum": spk}, "text": S_STR}))})
    ends = [(chap[k + 1]["start"] if k + 1 < len(chap) else len(L)) for k in range(len(chap))]
    k = max(range(1, len(chap) - 1) if len(chap) > 2 else range(len(chap)), key=lambda k: lwords(L[chap[k]["start"]:ends[k]]))
    s, e = chap[k]["start"], ends[k]; seg = L[s:e]; w = lwords(seg); target = max(int(w * 0.6), w - cut)
    st(f"length gate: condensing chapter '{chap[k]['title'][:40]}' {w} -> ~{target} words")
    listing = "\n".join(f"{l['speaker']}: {l['text']}" for l in seg)
    try: r = call(system + f"\n\nRewrite this chapter to about {target} words, keeping its best moments, quotes, the voice of each speaker and its first and last line. Return JSON {{\"lines\":[...]}}.\n\n{listing}", SCHEMA, temp=0.5, predict=4500, tries=2)
    except Exception as ex: log(f"condense failed: {ex}"); return L, chap
    new = [l for l in r.get("lines", []) if l.get("text", "").strip() and l.get("speaker") in spk]
    if not new or lwords(new) >= w: return L, chap
    d = len(new) - len(seg); L = L[:s] + new + L[e:]
    for j in range(k + 1, len(chap)): chap[j]["start"] += d
    log(f"condense: '{chap[k]['title'][:40]}' {w} -> {lwords(new)} words"); return L, chap

def write_outputs(B, P, L, chap, facts, quotes, fixes, clog, LR, IR, src_line, books, share, pred, F, t0):
    ep, title, sid = P["ep"], P["title"], P["short_id"]; G = B["guest_voices"]; two = len(G) == 2; out = C.work; R = C.root
    lname = {"Host": "Carter", "Guest": G[0], "Guest2": G[1] if two else ""}
    wj("script.json", L)
    json.dump(L, open(os.path.join(out, f"{ep}_script.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump({"title": title, "sections": chap}, open(os.path.join(out, f"{ep}.chapters.in.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    md = [f"# {title}\n"]; starts = {c["start"]: c["title"] for c in chap}
    for i, l in enumerate(L):
        if i in starts: md.append(f"\n## {starts[i]}\n")
        md.append(f"**{lname[l['speaker']]}:** {l['text']}\n")
    wt(f"{ep}_script.md", "\n".join(md), out)
    # FLUX prompts (fd1 format)
    tail = "semi-realistic, soft painterly brush strokes, gentle volumetric light, wide cinematic shot, film grain, no text, no letters, no faces, no recognizable people, no gore"
    style = f"cinematic concept art, {(IR.get('style') or 'deep teal and slate blue palette with warm amber highlights').strip().rstrip('.')}, {tail}"
    imgs = [x for x in IR.get("images", []) if x.get("subject")][:N_IMAGES[B["length_minutes"]]]
    lines = []
    for x in imgs:
        k = x.get("chapter") if isinstance(x.get("chapter"), int) and 0 <= x.get("chapter") < len(chap) else 0
        s = chap[k]["start"]; e = chap[k + 1]["start"] if k + 1 < len(chap) else len(L)
        lines.append([k, s, e])
    # spread images of the same chapter evenly, keep strictly increasing
    pos = []
    for k in sorted(set(z[0] for z in lines)):
        grp = [z for z in lines if z[0] == k]; s, e = grp[0][1], grp[0][2]
        for j, _ in enumerate(grp): pos.append(s + (e - s) * j // len(grp))
    pos = sorted(pos) or [0]; pos[0] = 0
    for j in range(1, len(pos)): pos[j] = max(pos[j], pos[j - 1] + 1)
    pos = [p for p in pos if p < len(L)]
    imgs = sorted(imgs, key=lambda x: x.get("chapter") if isinstance(x.get("chapter"), int) else 0)[:len(pos)]
    bg = os.path.join(R, "bg_" + sid); os.makedirs(bg, exist_ok=True)
    pj = {"style": style, "negative": "", "images": []}; bj = []
    for j, (x, p) in enumerate(zip(imgs, pos), 1):
        iid = f"{sid[:10]}{j:02d}"; subj = re.sub(r"\s+", " ", x["subject"]).strip().rstrip(".")
        pj["images"].append({"id": iid, "line": p, "prompt": f"{subj}, subject in the lower third, empty space above, {style}"}); bj.append({"line": p, "image": iid + ".png"})
    json.dump(pj, open(os.path.join(bg, "prompts.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(bj, open(os.path.join(bg, "backgrounds.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    # learn (into <work>\learn, copied to learn\ by the launcher only after all gates passed)
    ld = os.path.join(out, "learn"); os.makedirs(ld, exist_ok=True)
    tk = (LR.get("takeaways") or [])[:5]
    wt(f"{ep}_takeaways.md", f"# {title}: 5 takeaways\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(tk, 1)) + "\n", ld)
    if B.get("quiz"):
        wt(f"{ep}_quiz.md", f"# Quiz: {title}\n" + "\n".join(f"{i}. {x.get('q') or ''} **A:** {x.get('a') or ''}" for i, x in enumerate([y for y in (LR.get('quiz') or []) if isinstance(y, dict)][:10], 1)) + "\n", ld)
    buf = io.StringIO(); wcsv = csv.writer(buf, delimiter=";", lineterminator="\n"); wcsv.writerow(["front", "back"])
    for x in (LR.get("anki") or [])[:14]: wcsv.writerow([str(x.get("front") or "").replace(";", ","), str(x.get("back") or "").replace(";", ",")]) if isinstance(x, dict) else None
    wt(f"{ep}_anki.csv", buf.getvalue(), ld)
    pages_used = {}
    for f in facts + quotes: pages_used.setdefault((f["author"], f["book"], f["kind"]), set()).add(f["page"])
    def rng(ps):
        ps = sorted(p for p in ps if isinstance(p, int));
        return f"{ps[0]}-{ps[-1]}" if ps else "?"
    urls = {(f["author"], f["book"]): f["url"] for f in facts + quotes if f.get("url")}
    srcmd = "\n".join((f"- {a_}, *{b_}*, {urls[(a_, b_)]} (web page, read by the research step; sections {rng(ps)})." if (a_, b_) in urls else
                       f"- {a_}, *{b_}* ({k_}s {rng(ps)} of the source file; cited by {k_} number, not printed page).") for (a_, b_, k_), ps in pages_used.items())
    LR["mentioned"] = [str(m) for m in (LR.get("mentioned") or []) if m]; LR["tags"] = [str(m) for m in (LR.get("tags") or []) if m]; LR["takeaways"] = [str(m) for m in (LR.get("takeaways") or []) if m]
    ment = "; ".join(LR.get("mentioned") or []) or "none recorded"
    vj = {}
    try: vj = json.load(open(os.path.join(R, "voices.json"), encoding="utf-8-sig")); vj = vj.get("voices", vj)
    except Exception: pass
    cred = sorted({str((vj.get(n, {}) if isinstance(vj, dict) else {}).get("credit") or "") if isinstance(vj.get(n) if isinstance(vj, dict) else None, dict) else "" for n in ["Carter"] + G} - {""})
    cast = f"Carter (host), {G[0]} (Guest, advocate)" + (f", {G[1]} (Guest2, antagonist)" if two else "")
    meta = (f"# YouTube description / production meta: {title}\n\n## Description\n{str(LR.get('description') or '').strip()}\n\n"
            + (f"Content note: {P.get('content_note')}\n\n" if (P.get("content_note") or "").strip() else "") +
            f"This is an AI-voiced discussion; the characters are fictional and their personal stories are invented.\n\n## Sources and editions\n{srcmd}\n- Background mentioned by the speakers: {ment}.\n\n"
            "## Chapters (timestamps TBD after render)\n" + "\n".join(("00:00 " if k == 0 else "TBD ") + c["title"] for k, c in enumerate(chap)) +
            f"\n\n## Further reading\nSee {ep}_read_for_yourself.md.\n\n## Cast and voices\n- {cast}. Render flags: -Guests \"{','.join(G)}\". TTS: Fish Audio Drama 3 (template v1.13), fallback VibeVoice-7B.\n"
            + "".join(f"- Voice credit: *{c}*\n" for c in cred) +
            f"\n## Production\nMade with the Episode desk (brief {B.get('id')}, tone {B['tone']}, depth {B['depth']}, quiz {'yes' if B.get('quiz') else 'no'}, {B['length_minutes']} min). Script drafted by gemma4 from automatically verified notes; content template {getattr(C, 'style', 'v2.3')}.\n\n"
            "## Tags\n" + ", ".join(LR.get("tags") or []) + "\n")
    wt(f"{ep}_details_meta.md", meta, ld)
    rfy = (f"# Read for yourself: {title}\n\n## The source pages\n{srcmd}\n\n## Verified quotes used as the allowed quote list\n" +
           "\n".join(f"- \"{q['text']}\" ({q['author']}, {q['kind']} {q['page']})" for q in quotes[:40]) + f"\n\n## Also mentioned in the episode\n" + "\n".join(f"- {m}" for m in (LR.get("mentioned") or [])) + "\n")
    wt(f"{ep}_read_for_yourself.md", rfy, ld)
    fc = [f"# Fact-check: {title}\n", f"Automatic, by the Episode desk (brief_gen.py). Sources: {src_line}. Quotes: {len(quotes)} verbatim quotes verified against the source text; any other quoted phrase in the script had its quotation marks removed.\n",
          f"## Gemma fact-check fixes ({len(fixes)})"] + [f"- [{x['part'][:40]}] line {x['line']}: {x['problem']}\n  - was: {x['old']}\n  - now: {x['new']}" for x in fixes] + \
         [f"\n## Mechanical clean-ups ({len(clog)})"] + [f"- line {x['line']}: {x['old'][:160]} -> {x['new'][:160]}" for x in clog[:200]] + \
         ["\n## Not checked automatically", "- Outside-knowledge claims about other thinkers are only checked by gemma against general knowledge; review before publishing."]
    wt(f"factcheck_{ep}.md", "\n".join(fc) + "\n", ld)
    nb = (f"# Notes: {title}\n\nAuto-generated by the Episode desk from the source text. Focus: {F.get('focus')}\n\n## Facts\n" + "\n".join(f"- {f['claim']} ({f['author']}, *{f['book']}*, {f['kind']} {f['page']})" for f in facts) +
          "\n\n## Verified quotes\n" + "\n".join(f"- \"{q['text']}\" ({q['author']}, {q['kind']} {q['page']})" for q in quotes) + "\n")
    nd = os.path.join(out, "notes"); os.makedirs(nd, exist_ok=True); wt(f"{sid}.md", nb, nd)
    w = lwords(L)
    res = {"ep": ep, "title": title, "short_id": sid, "content_style": getattr(C, "style", "v2.3"), "topic": (norm_source(B)["topic"] or None), "bg_dir": "bg_" + sid, "suffix": "_" + sid[:10], "guests": ",".join(G), "cast": ", ".join(["Carter"] + G),
           "min_dur": WINDOWS[B["length_minutes"]][0], "max_dur": WINDOWS[B["length_minutes"]][1], "lines": len(L), "words": w, "predicted_s": round(pred), "chapters": len(chap),
           "images": len(pj["images"]), "quotes": len(quotes), "facts": len(facts), "factcheck_fixes": len(fixes), "speaker_share": {k: round(v, 3) for k, v in share.items()},
           "learn_files": sorted(os.listdir(ld)), "notes_file": f"{sid}.md", "gemma_calls": C.calls, "gen_minutes": round((time.time() - t0) / 60, 1)}
    wj("result.json", res)
    st(f"done: '{title}' ep={ep} {len(L)} lines {w} words predicted {pred/60:.1f} min, {len(chap)} chapters, {len(pj['images'])} images, {C.calls} gemma calls, {res['gen_minutes']} min")

if __name__ == "__main__":
    try: sys.exit(main())
    except SystemExit: raise
    except Exception as e:
        import traceback; tb = traceback.format_exc()
        try: log("CRASH " + tb.replace("\n", " | ")); st(f"ABORT gen crashed: {e}")
        except Exception: print(tb)
        sys.exit(5)
