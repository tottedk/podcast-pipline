r"""episode_qc.py (desk tools, 2026-11-01) - script and audio quality checks for the Episode desk chain (start_brief.ps1).
Read-only, except `pre --fix`, which rewrites the segment files it sanitized and keeps <seg>.pre_epqc.json first.

  pre  <dir> [--names Carter,Clara,Lachlan] [--fix] [--script file.json]
       Pre-TTS: every line of <dir>\seg??.json (or --script) must be clean spoken text:
         - no speaker labels ("Guest 1:", "Host:", "Speaker 2:", "Clara:", "**Carter:**"), at the start or after a sentence end
         - no stage directions ([pauses], (leans in), *smiles*); only [laughs] / [sighs] are allowed
         - no markdown (* _ ` # bullets, [text](url))
         - no duplicated passages: two lines >= 15 words that are >= 80 % the same, or a shared run of >= 25 words
       --fix removes labels / stage directions / markdown first, then checks again. Duplicates are never auto-fixed.
  post <dir> --ep EP [--srt file.srt] [--rep_s 15] [--names ...]
       Post-TTS gate before the swap: <dir>\<ep>.whisper.json (what the audio says) against <dir>\<ep>_script.json:
         - repeated passages in the audio (the same words twice, >= --rep_s seconds, default 15)
         - dropped lines (script line >= 5 words with < 50 % of its words heard), extra speech (>= 25 unmatched heard words in a row)
         - leftover labels / stage directions / markdown in the srt and script, and "guest one" / "speaker two" heard in the audio
Prints one summary line "EPQC PRE|POST OK|FAIL ..." and writes <dir>\epqc_<mode>.json. Exit 0 = pass, 1 = hits, 2 = usage / missing input."""
import argparse, difflib, glob, json, os, re, shutil, sys

ALLOWED_TAGS = ("laughs", "sighs")
STAGE_WORDS = r"laugh(?:s|ing)?|chuckl\w*|sigh\w*|paus\w*|beat|smil\w*|grin\w*|lean\w*|nod\w*|clear\w*|whisper\w*|shout\w*|sarcastic\w*|interrupt\w*|excited\w*|softly|quietly|loudly|groan\w*|scoff\w*|gasp\w*|sip\w*|tap\w*|music|sfx|applause|silence|cough\w*|inhal\w*|exhal\w*"

def label_re(names):
    nm = "|".join(re.escape(n) for n in names if n)
    who = r"(?:Host|Guest\s*\d*|Guest\s*(?:one|two)|Speaker\s*\d+|Speaker\s*(?:one|two|three)|Narrator|Interviewer|Moderator" + (("|" + nm) if nm else "") + r")"
    # at the very start (optionally in ** or quotes) or right after a sentence end
    role = r"(?:Host|Guest\s*\d*|Guest\s*(?:one|two)|Speaker\s*\d+|Speaker\s*(?:one|two|three)|Narrator)"
    # NAME: / ROLE: at the very start (optionally in ** or quotes) or right after a sentence end; "GUEST 1 -" / "Host \u2014" (role words only) at the start
    return re.compile(r"(?:(?:^|(?<=[.!?\"\u201d])\s+)[*_\"\u201c]*" + who + r"[*_]*\s*:(?!\d)|^\s*[*_]*" + role + r"[*_]*\s+[-\u2013\u2014]\s)", re.I)

STAGE_RE = [re.compile(r"\[(?!(?:%s)\])[^\]\n]{1,60}\]" % "|".join(ALLOWED_TAGS), re.I),
            re.compile(r"\((?:%s)\b[^)\n]{0,60}\)" % STAGE_WORDS, re.I),
            re.compile(r"(?<![\w*])\*(?:%s)\b[^*\n]{0,60}\*(?![\w*])" % STAGE_WORDS, re.I)]
MD_RE = re.compile(r"\*\*|__|`|^\s*#{1,6}\s|^\s*[-\u2022>]\s|!?\[[^\]\n]+\]\([^)]*\)|(?<![\w*])\*(?=[^\W_])|(?<=[^\W_])\*(?![\w*])", re.M)

NUMW = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten", "first": "first"}
def norm_tokens(s):
    s = s.lower().replace("\u2019", "'").replace("all right", "alright").replace("\u2014", " ").replace("\u2013", " ").replace("-", " ")
    return [NUMW.get(t, t) for t in re.findall(r"[a-z0-9']+", s)]

def line_issues(t, LBL):
    out = []; spans = []
    for m in LBL.finditer(t): out.append(("label", m.group(0).strip())); spans.append(m.span())
    for r in STAGE_RE:
        for m in r.finditer(t): out.append(("stage", m.group(0))); spans.append(m.span())
    for m in MD_RE.finditer(t):   # ** / * that belong to a label or stage direction already found are the same defect
        if any(a <= m.start() < b + 1 for a, b in spans): continue
        out.append(("markdown", m.group(0).strip() or "md"))
    return out

def sanitize(t, LBL):
    s = t
    for _ in range(3): s = LBL.sub(" ", s)
    for r in STAGE_RE: s = r.sub(" ", s)
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        from md_clean import clean_markdown; s = clean_markdown(s)
    except Exception: s = re.sub(r"\*+|__|`", "", s)
    s = re.sub(r"\s+([,.!?;:])", r"\1", re.sub(r"\s{2,}", " ", s)).strip()
    return s

def dup_lines(L, min_words=12, ratio=0.8, run_words=25, near=3):
    """script-level repeats: near-identical lines anywhere, or a shared run of >= run_words words between lines <= near apart.
    A shared run between lines further apart (a re-used book quote, a long callback) is returned with warn=True (reported, not failed)."""
    toks = [norm_tokens(l["text"]) for l in L]; hits = []
    for i in range(len(L)):
        if len(toks[i]) < min(min_words, run_words): continue
        for j in range(i):
            if len(toks[j]) < min(min_words, run_words): continue
            sm = difflib.SequenceMatcher(None, toks[j], toks[i], autojunk=False)
            r = sm.ratio(); longest = max((b.size for b in sm.get_matching_blocks()), default=0)
            if (r >= ratio and min(len(toks[i]), len(toks[j])) >= min_words) or longest >= run_words:
                warn = not (r >= ratio and min(len(toks[i]), len(toks[j])) >= min_words) and i - j > near
                hits.append({"line": i, "same_as": j, "ratio": round(r, 2), "shared_run_words": longest, "warn": warn, "text": L[i]["text"][:120]})
    return hits

def load_segs(d, script):
    if script: return [(script, json.load(open(script, encoding="utf-8-sig")))]
    fs = sorted(f for f in glob.glob(os.path.join(d, "seg??.json")) if re.search(r"seg\d\d\.json$", f))
    return [(f, json.load(open(f, encoding="utf-8-sig"))) for f in fs]

def cmd_pre(a):
    names = [n.strip() for n in a.names.split(",") if n.strip()]; LBL = label_re(names)
    segs = load_segs(a.dir, a.script)
    if not segs: print("EPQC PRE FAIL no seg??.json / script found"); return 2
    fixed = []
    if a.fix:
        for f, L in segs:
            ch = 0
            for l in L:
                s = sanitize(l["text"], LBL)
                if s != l["text"]: fixed.append({"file": os.path.basename(f), "old": l["text"][:120], "new": s[:120]}); l["text"] = s; ch += 1
            if ch:
                bak = f[:-5] + ".pre_epqc.json"
                if not os.path.exists(bak): shutil.copy2(f, bak)
                json.dump(L, open(f, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    allL = []; where = []
    for f, L in segs:
        for k, l in enumerate(L): allL.append(l); where.append(f"{os.path.basename(f)}#{k}")
    hits = []
    for i, l in enumerate(allL):
        t = l.get("text") or ""
        if len(t.split()) == 0: hits.append({"at": where[i], "kind": "empty", "what": ""})
        for kind, what in line_issues(t, LBL): hits.append({"at": where[i], "kind": kind, "what": what, "text": t[:120]})
    warns = []
    for h in dup_lines(allL):
        (warns if h["warn"] else hits).append({"at": where[h["line"]], "kind": "duplicate", "what": f"same as {where[h['same_as']]} (ratio {h['ratio']}, shared run {h['shared_run_words']} words)", "text": h["text"]})
    plan = {}
    for h in hits: plan.setdefault(h["at"].split("#")[0], set()).add("regenerate_section_script" if h["kind"] in ("duplicate", "empty") else "sanitize_text(--fix)")
    rep = {"mode": "pre", "lines": len(allL), "sanitized": fixed, "hits": hits, "warnings": warns,
           "plan": [{"file": f, "action": "regenerate_section_script" if "regenerate_section_script" in v else "sanitize_text(--fix)"} for f, v in sorted(plan.items())]}
    json.dump(rep, open(os.path.join(a.dir, a.out or "epqc_pre.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    kinds = {}
    for h in hits: kinds[h["kind"]] = kinds.get(h["kind"], 0) + 1
    msg = f"EPQC PRE {'FAIL' if hits else 'OK'}: {len(allL)} lines, sanitized {len(fixed)}, hits {len(hits)} {kinds if kinds else ''}".strip() + (f", {len(warns)} distant repeat warning(s)" if warns else "")
    if hits: msg += " | " + " | ".join(f"{h['at']} {h['kind']}: {h['what']}"[:160] for h in hits[:6])
    print(msg); return 1 if hits else 0

def srt_cues(p):
    out = []
    for b in re.split(r"\n\s*\n", open(p, encoding="utf-8-sig").read().strip()):
        l = b.strip().split("\n")
        if len(l) >= 3 and "-->" in l[1]: out.append((l[0].strip(), l[1][:12], " ".join(l[2:])))
    return out

def fmt(s): return f"{int(s//60)}:{s%60:04.1f}"

def seg_map(d, n_lines):
    """script line -> segment name, from <dir>/seg??.json line counts (None if they do not add up to the script)"""
    m = []
    for f, L in load_segs(d, ""):
        m += [os.path.basename(f)[:-5]] * len(L)
    return m if len(m) == n_lines else None

def cmd_post(a):
    names = [n.strip() for n in a.names.split(",") if n.strip()]; LBL = label_re(names)
    wp = os.path.join(a.dir, f"{a.ep}.whisper.json"); sp = a.script or os.path.join(a.dir, f"{a.ep}_script.json")
    tp = os.path.join(a.dir, f"{a.ep}.timings.json")
    if not os.path.exists(wp) or not os.path.exists(sp): print(f"EPQC POST FAIL missing input: {wp if not os.path.exists(wp) else sp}"); return 2
    W = json.load(open(wp, encoding="utf-8-sig"))["words"]; S = json.load(open(sp, encoding="utf-8-sig"))
    T = json.load(open(tp, encoding="utf-8-sig"))["lines"] if os.path.exists(tp) else None
    SM = seg_map(a.dir, len(S))
    def line_at(t):   # heard time -> script line (timings.json from align), else None
        if not T: return None
        best = None
        for i, l in enumerate(T):
            if l.get("start") is not None and l["start"] <= t + 0.05: best = i
        return best
    ht, hs = [], []   # heard tokens + start times
    for w, s_, e in W:
        for t in norm_tokens(w): ht.append(t); hs.append(s_)
    st_, sl = [], []  # script tokens + line index
    for i, l in enumerate(S):
        for t in norm_tokens(l["text"]): st_.append(t); sl.append(i)
    hits = []
    # 1 repeated passages in the audio: seeds = equal 6-grams at a constant offset, merged across small gaps
    n = 6; seen = {}; seeds = {}
    for i in range(len(ht) - n + 1):
        g = tuple(ht[i:i + n])
        for j in seen.get(g, []):
            if i - j >= n: seeds.setdefault(i - j, []).append(i)
        seen.setdefault(g, []).append(i)
    runs = []
    for d, pos in seeds.items():
        pos.sort(); a0 = b0 = pos[0]
        for p in pos[1:] + [None]:
            if p is not None and p - b0 <= n + 6: b0 = p; continue
            s0, e0 = a0, b0 + n - 1; dur = (hs[e0 + 1] if e0 + 1 < len(hs) else hs[e0] + 0.4) - hs[s0]
            runs.append({"start_s": hs[s0], "dur_s": round(dur, 1), "words": e0 - s0 + 1, "first_at_s": hs[s0 - d], "text": " ".join(ht[s0:s0 + 14])})
            if p is not None: a0 = b0 = p
    runs.sort(key=lambda r: -r["dur_s"]); kept = []
    for r in runs:
        if any(abs(r["start_s"] - k["start_s"]) < k["dur_s"] for k in kept): continue
        kept.append(r)
    for r in kept:
        if r["dur_s"] >= a.rep_s:
            hits.append({"kind": "repeat", "at_s": r["start_s"], "line": line_at(r["start_s"]), "what": f"{fmt(r['start_s'])}-{fmt(r['start_s'] + r['dur_s'])} ({r['dur_s']} s, {r['words']} words) repeats {fmt(r['first_at_s'])}: '{r['text']}...'"})
    warn = [r for r in kept if 8 <= r["dur_s"] < a.rep_s]
    # 2 dropped lines / truncated ending / extra speech: align script tokens to heard tokens
    sm = difflib.SequenceMatcher(None, st_, ht, autojunk=False); okS = [False] * len(st_); okH = [False] * len(ht)
    for b in sm.get_matching_blocks():
        for k in range(b.size): okS[b.a + k] = True; okH[b.b + k] = True
    per = {}
    for k, i in enumerate(sl): per.setdefault(i, [0, 0]); per[i][0] += 1; per[i][1] += okS[k]
    lost = [i for i, (tot, ok) in sorted(per.items()) if (tot >= 5 and ok / tot < 0.5) or (tot < 5 and ok == 0)]
    tail = []
    for i in reversed(range(len(S))):
        if i in lost: tail.append(i)
        else: break
    for i in lost:
        tot, ok = per[i]
        hits.append({"kind": "truncated_end" if i in tail else "dropped", "line": i, "what": f"script line {i} ({S[i]['speaker']}, {tot} words) only {ok}/{tot} heard{' (episode ends early)' if i in tail else ''}: '{S[i]['text'][:70]}'"})
    k = 0
    while k < len(ht):
        if okH[k]: k += 1; continue
        e = k
        while e < len(ht) and not okH[e]: e += 1
        xa, xb = hs[k], hs[e - 1] + 0.4   # the repeat itself (reported above, or a < rep_s warning): either copy overlaps most of this span
        in_rep = any(min(xb, t0 + r["dur_s"] + 1) - max(xa, t0 - 1) >= 0.5 * (xb - xa) for r in kept for t0 in (r["start_s"], r["first_at_s"]))   # the repeat itself (reported above or as a warning)
        if e - k >= 25 and not in_rep: hits.append({"kind": "extra", "at_s": hs[k], "line": line_at(hs[k]), "what": f"{fmt(hs[k])}: {e-k} heard words not in the script: '{' '.join(ht[k:k+14])}...'"})
        k = e
    # 3 leftover labels / stage directions / markdown / duplicates in the script and srt; spoken labels in the audio (only if not in the script text)
    for i, l in enumerate(S):
        for kind, what in line_issues(l["text"], LBL): hits.append({"kind": kind, "line": i, "where": "script", "what": f"script line {i}: {what} | '{l['text'][:70]}'"})
    dwarn = []
    for h in dup_lines(S):
        x = {"kind": "duplicate", "line": h["line"], "where": "script", "what": f"script line {h['line']} repeats line {h['same_as']} (ratio {h['ratio']}, shared run {h['shared_run_words']} words): '{h['text'][:70]}'"}
        (dwarn if h["warn"] else hits).append(x)
    if a.srt and os.path.exists(a.srt):
        for no, tc, txt in srt_cues(a.srt):
            for kind, what in line_issues(txt, LBL): hits.append({"kind": kind, "cue": no, "where": "srt", "what": f"srt cue {no} ({tc}): {what} | '{txt[:70]}'"})
    for k in range(len(ht) - 1):
        if ht[k] in ("guest", "speaker", "host") and (ht[k + 1] in ("one", "two", "three") or ht[k] == "host") and not okH[k]:
            if ht[k] == "host" and (k == 0 or okH[k - 1]) and (k + 1 >= len(ht) or okH[k + 1]): continue
            hits.append({"kind": "spoken_label", "at_s": hs[k], "line": line_at(hs[k]), "what": f"{fmt(hs[k])}: heard '{' '.join(ht[k:k+2])}' (not in the script)"})
    # 4 the smallest fix: which segments, and whether the script (text) or only the audio (TTS) is at fault
    plan = {}
    for h in hits:
        i = h.get("line")
        sg = (SM[i] if SM and i is not None and i < len(SM) else "unknown")
        if h["kind"] in ("label", "stage", "markdown") : act = "fix_text_deterministic+rerender_seg"   # epqc pre --fix rules, no LLM
        elif h["kind"] == "duplicate": act = "regenerate_section_script+rerender_seg"                     # the script itself is broken
        elif h["kind"] == "repeat" and any(x["kind"] == "duplicate" for x in hits): act = "regenerate_section_script+rerender_seg"
        else: act = "rerender_seg"                                                                         # audio-only defect (TTS)
        if h.get("where") == "srt" and h["kind"] in ("label", "stage", "markdown"): sg = "srt"; act = "fix_text_deterministic+rebuild_srt"
        p = plan.setdefault(sg, set()); p.add(act)
    order = ["regenerate_section_script+rerender_seg", "fix_text_deterministic+rerender_seg", "rerender_seg", "fix_text_deterministic+rebuild_srt"]
    plan = [{"segment": k, "action": next(o for o in order if o in v)} for k, v in sorted(plan.items())]
    rep = {"mode": "post", "ep": a.ep, "heard_words": len(ht), "script_words": len(st_), "match": round(sum(okS) / max(1, len(st_)), 3), "hits": hits, "plan": plan,
           "warnings_repeats_8_15s": warn, "warnings_distant_repeats": dwarn}
    json.dump(rep, open(os.path.join(a.dir, a.out or "epqc_post.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    kinds = {}
    for h in hits: kinds[h["kind"]] = kinds.get(h["kind"], 0) + 1
    msg = f"EPQC POST {'FAIL' if hits else 'OK'}: {a.ep} heard {len(ht)} / script {len(st_)} words, match {rep['match']*100:.1f}%, hits {len(hits)} {kinds if kinds else ''}".strip()
    if warn: msg += f", {len(warn)} shorter repeat(s) 8-{a.rep_s:g} s (warning)"
    if dwarn: msg += f", {len(dwarn)} distant repeat warning(s)"
    if hits: msg += " | plan: " + ", ".join(f"{p['segment']}={p['action']}" for p in plan) + " | " + " | ".join(h["what"][:170] for h in hits[:6])
    print(msg); return 1 if hits else 0

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["pre", "post"]); ap.add_argument("dir")
    ap.add_argument("--names", default="Carter"); ap.add_argument("--fix", action="store_true"); ap.add_argument("--script", default="")
    ap.add_argument("--ep", default=""); ap.add_argument("--srt", default=""); ap.add_argument("--rep_s", type=float, default=15.0); ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.mode == "post" and not a.ep: sys.exit("post needs --ep")
    sys.exit(cmd_pre(a) if a.mode == "pre" else cmd_post(a))
