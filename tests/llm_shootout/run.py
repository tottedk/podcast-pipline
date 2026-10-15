r"""run.py <model> [--only a,b] - one model, all tasks, identical prompts/seed. Writes results\<safe>\*.txt and results\<safe>.json.
Tasks: write (podcast segment from notes\das_man.md), summ, json (10 trials), code (2 functions, hidden unit tests), da (Danish email).
Measures tok/s (eval_count/eval_duration), load time, warm TTFT, prompt-eval rate, Ollama-reported GPU/CPU split. keep_alive: stays loaded during tasks, unloaded at the end (keep_alive 0)."""
import sys, os, re, json, time, subprocess, tempfile, urllib.request, textwrap
H = "http://localhost:11434"; D = os.path.dirname(os.path.abspath(__file__)); NOTES = r"C:\grok\podcast\notes\das_man.md"
CTX = 16384; SEED = 42
model = sys.argv[1]; only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else ["write", "summ", "json", "code", "da"]
safe = re.sub(r"[^\w.\-]", "_", model); OUT = os.path.join(D, "results", safe); os.makedirs(OUT, exist_ok=True)
THINK = "low" if model.startswith("gpt-oss") else False
def post(path, body, timeout=900):
    req = urllib.request.Request(H + path, json.dumps(body).encode(), {"Content-Type": "application/json"}); return urllib.request.urlopen(req, timeout=timeout)
def get(path): return json.load(urllib.request.urlopen(H + path, timeout=30))
def gen(prompt, temp, num_predict, fmt=None, seed=SEED, think=None):
    """streaming generate -> dict(text, ttft, wall, stats...)"""
    global THINK
    th = THINK if think is None else think
    for attempt in range(2):
        body = {"model": model, "prompt": prompt, "stream": True, "keep_alive": "20m",
                "options": {"temperature": temp, "seed": seed, "num_ctx": CTX, "num_predict": num_predict}}
        if th is not None: body["think"] = th
        if fmt: body["format"] = fmt
        t0 = time.time(); ttft = None; txt = []; thk = []; fin = {}
        try:
            r = post("/api/generate", body)
            for line in r:
                if not line.strip(): continue
                j = json.loads(line)
                if "error" in j: raise RuntimeError(j["error"])
                if (j.get("response") or j.get("thinking")) and ttft is None: ttft = time.time() - t0
                txt.append(j.get("response", "")); thk.append(j.get("thinking", ""))
                if j.get("done"): fin = j
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="ignore")
            if "think" in msg and attempt == 0: th = None; THINK = None; print("  (think param unsupported -> retry without)", flush=True); continue
            raise RuntimeError(msg)
    wall = time.time() - t0
    text = "".join(txt); text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    ev = fin.get("eval_count", 0); ed = fin.get("eval_duration", 1) / 1e9; pe = fin.get("prompt_eval_count", 0); pd = fin.get("prompt_eval_duration", 1) / 1e9
    return dict(text=text, thinking_chars=len("".join(thk)), ttft=round(ttft or wall, 2), wall=round(wall, 1), eval_count=ev, tok_s=round(ev / max(ed, 1e-9), 1),
                prompt_tokens=pe, prompt_tok_s=round(pe / max(pd, 1e-9), 0), load_s=round(fin.get("load_duration", 0) / 1e9, 2), done_reason=fin.get("done_reason"))
def words(s): return len(re.findall(r"[\w'’\-]+", s))
R = {"model": model, "ctx": CTX, "seed": SEED, "think_param": str(THINK), "started": time.strftime("%Y-%m-%d %H:%M:%S"), "tasks": {}}
def save(): json.dump(R, open(os.path.join(D, "results", safe + ".json"), "w"), indent=1, ensure_ascii=False)
# ---- load + warm TTFT + GPU/CPU split
t0 = time.time(); post("/api/generate", {"model": model, "prompt": "", "keep_alive": "20m", "options": {"num_ctx": CTX}}).read(); R["load_wall_s"] = round(time.time() - t0, 1)
ps = [m for m in get("/api/ps")["models"] if m["name"].startswith(model.split(":")[0]) or m["model"] == model]
if ps: R["size_gb"] = round(ps[0]["size"] / 2**30, 2); R["vram_gb"] = round(ps[0]["size_vram"] / 2**30, 2); R["gpu_pct"] = round(100 * ps[0]["size_vram"] / max(ps[0]["size"], 1), 1); R["loaded_ctx"] = ps[0].get("context_length")
w = gen("Reply with the single word: ready", 0, 8); R["ttft_warm_s"] = w["ttft"]; print(f"[{model}] load {R['load_wall_s']}s size {R.get('size_gb')} GB vram {R.get('vram_gb')} GB ({R.get('gpu_pct')}% GPU) warm TTFT {w['ttft']}s", flush=True); save()
def rec(name, r, extra=None):
    d = {k: v for k, v in r.items() if k != "text"}; d.update(extra or {}); R["tasks"][name] = d
    open(os.path.join(OUT, name + ".txt"), "w", encoding="utf-8").write(r["text"]); save()
    print(f"  {name}: {r['eval_count']} tok @ {r['tok_s']} tok/s, TTFT {r['ttft']}s, wall {r['wall']}s", flush=True)
notes = open(NOTES, encoding="utf-8-sig").read()
# ---------------- A) podcast script segment (prompt = write_script.py template + content_style v2.1 rules, 3 voices, ~900 words)
if "write" in only:
    P = f"""Write a lively, natural three-person English podcast dialogue segment about the question "Is the crowd really the enemy, or is that just elitism?", based on the notes below.
Speakers: "Host" (Carter: an average Joe on the outside, sharp inside; relaxed, self-ironic, humorous, uses everyday examples like Netflix, the gym, LinkedIn or the commute; he mediates and gives his own verdict), "Guest" (the advocate: knows the book inside out and defends its strongest version) and "Guest2" (the antagonist: speaks from the critical tradition in the notes and attacks the book's premises).
Rules:
- Target length: about 900 words in total (between 800 and 1000), about 22 to 28 turns.
- Structure: a short framing by Host, then Guest's case, then Guest2's attack, then real back-and-forth with interruptions, then Host's own verdict. Speaking time roughly Host 30%, each guest 35%.
- Sound like real people talking: contractions, short reactions, the occasional interruption or joke, varied sentence length. No lecture paragraphs, no "Great question!".
- Heated is allowed, but fair: no straw men. Each guest makes one real concession, but never with stock formulas like "I'll concede that" or "I'll grant that"; make it human (hesitation, irritation, laughter, a half-concession).
- Name only the book and the author; never exact sections, chapters, page numbers or editions. No invented quotes.
- Write all names and terms normally (no phonetic respellings, no hyphenated pronunciation guides).
- Plain spoken text only: no stage directions, markdown, emojis or speaker names inside the text.
- Output ONLY a JSON array like [{{"speaker":"Host","text":"..."}}, ...] using the speaker names Host, Guest, Guest2.

NOTES:
{notes}
"""
    SCHEMA = {"type": "array", "items": {"type": "object", "properties": {"speaker": {"type": "string", "enum": ["Host", "Guest", "Guest2"]}, "text": {"type": "string"}}, "required": ["speaker", "text"]}}
    r = gen(P, 0.8, 4000, fmt=SCHEMA); data = None; txt = r["text"]
    try: data = json.loads(txt)
    except Exception:
        m = re.search(r"\[.*\]", txt, re.S)
        try: data = json.loads(m.group(0)) if m else None
        except Exception: data = None
    if isinstance(data, dict):
        l = [v for v in data.values() if isinstance(v, list)]; data = l[0] if l else [data]
    ex = {"json_ok": isinstance(data, list) and len(data) > 0}
    if ex["json_ok"]:
        turns = [(str(d.get("speaker", "")), str(d.get("text", ""))) for d in data if isinstance(d, dict)]
        alltext = " ".join(t for _, t in turns); wc = words(alltext); spk = {}
        for s, t in turns: spk[s] = spk.get(s, 0) + words(t)
        host_share = spk.get("Host", 0) / max(wc, 1)
        banned = {"concede_formula": r"\bI(?:'ll| will)? (?:concede|grant)\b|\bI concede\b|\bconcede that\b", "great_question": r"great question", "markdown": r"[*#_`]{1,}|\[[^\]]*\]\(", "stage_dir": r"\([^)]{0,60}\)|\*[^*]+\*|\[[A-Za-z ]+\]", "emoji": "[\U0001F300-\U0001FAFF\u2600-\u27BF]",
                  "exact_ref": r"\bAA ?\d+|\bH\. ?\d+|\bpp?\. ?\d+|\bchapter \d+|\bsection \d+|\b§ ?\d+", "respelling": r"\b[A-Z][a-z]+-[a-z]{2,}-[a-z]{2,}\b", "speaker_in_text": r"^(Host|Guest2?|Carter)\s*:"}
        hits = {k: len(re.findall(p, alltext, re.M)) for k, p in banned.items()}
        hits["markdown"] = len(re.findall(r"[*#`]|\[[^\]]*\]\(", alltext))
        spk_ok = set(spk) <= {"Host", "Guest", "Guest2"} and len(spk) == 3
        maxrun = 1; run = 1
        for i in range(1, len(turns)):
            run = run + 1 if turns[i][0] == turns[i - 1][0] else 1; maxrun = max(maxrun, run)
        longest = max(words(t) for _, t in turns); n = len(turns)
        s = 0.0
        s += 1.0                                              # json valid
        s += 1.5 if 800 <= wc <= 1000 else 1.0 if 720 <= wc <= 1100 else 0.5 if 600 <= wc <= 1300 else 0   # length obedience
        s += 1.0 * (1 - min(1, sum(hits.values()) / 3))       # banned patterns
        s += 0.5 if spk_ok else 0
        s += 0.5 if 0.2 <= host_share <= 0.4 else 0.25 if 0.15 <= host_share <= 0.45 else 0
        s += 0.5 if 18 <= n <= 34 and maxrun <= 2 and longest <= 140 else 0.25 if 14 <= n <= 40 else 0
        ex.update(words=wc, turns=n, speaker_words=spk, host_share=round(host_share, 2), banned_hits=hits, max_same_speaker_run=maxrun, longest_turn_words=longest, auto_score=round(min(5, s), 2))
        open(os.path.join(OUT, "write_plain.txt"), "w", encoding="utf-8").write("\n\n".join(f"{s}: {t}" for s, t in turns))
    else: ex["auto_score"] = 0
    rec("write", r, ex)
# ---------------- B) summarisation of a ~2.7k-word note
if "summ" in only:
    P = f"""Summarise the notes below for a busy reader. Format exactly: first one line starting with "TL;DR:" (max 25 words), then exactly 5 bullet points, each starting with "- " (max 30 words each). Total at most 180 words. Use only information from the notes; do not invent facts, names or quotes. No other text.

NOTES:
{notes}
"""
    r = gen(P, 0.3, 1200); t = r["text"]; wc = words(t); bl = [l for l in t.splitlines() if l.strip().startswith(("- ", "* ", "• "))]
    tl = [l for l in t.splitlines() if l.strip().lower().startswith(("tl;dr", "**tl;dr"))]
    kw = ["Heidegger", "das Man", "Han", "Adorno", "burnout", "authentic"]; cov = sum(1 for k in kw if k.lower() in t.lower())
    s = (1 if len(tl) == 1 else 0) + (1.5 if len(bl) == 5 else 0.75 if 4 <= len(bl) <= 6 else 0) + (1.0 if wc <= 180 else 0.5 if wc <= 220 else 0) + 1.5 * (cov / len(kw))
    rec("summ", r, dict(words=wc, bullets=len(bl), tldr_lines=len(tl), keyword_cov=f"{cov}/{len(kw)}", auto_score=round(min(5, s), 2)))
# ---------------- C) strict JSON, 10 trials, no format constraint
if "json" in only:
    SCH = """Extract the fields from the message and answer with ONLY one JSON object (no markdown, no explanation) with exactly these keys:
"sender" (string, full name), "date" (string, YYYY-MM-DD), "amount_dkk" (integer, amount in Danish kroner; 0 if no amount is mentioned), "category" (one of "invoice" = a request for payment or an invoice, "complaint" = expresses dissatisfaction, "inquiry" = asks a question, "other"), "urgent" (boolean, true only if the message explicitly says urgent, immediately or ASAP), "tags" (array of 1 to 3 lowercase strings).

Message: """
    CASES = [("Hi, this is Anne Holm. Invoice 4471 for DKK 12,500 dated 3 March 2026 is still unpaid, please pay immediately.", ("Anne Holm", "2026-03-03", 12500, "invoice", True)),
             ("Peter Lund here, 14 October 2026. The bus stop on Vej 12 has been broken for weeks and nobody answers my calls. I want to complain about this. No rush.", ("Peter Lund", "2026-10-14", 0, "complaint", False)),
             ("Message from Sofie Berg (2026-02-14): Could you tell me the opening hours of the citizens' service? Thanks.", ("Sofie Berg", "2026-02-14", 0, "inquiry", False)),
             ("Jens Madsen, 1 June 2026. Our supplier bills 8.750 kr. for the August training course. Payment is due within 30 days.", ("Jens Madsen", "2026-06-01", 8750, "invoice", False)),
             ("URGENT: Maria Kjær reports a burst water pipe in the community hall, 22 September 2026. Estimated damage 45,000 DKK.", ("Maria Kjær", "2026-09-22", 45000, "other", True)),
             ("Lars Ørum, 9 January 2026: When will the new playground be finished? The kids keep asking.", ("Lars Ørum", "2026-01-09", 0, "inquiry", False)),
             ("Karen Winther. 30 November 2026. Your department invoiced us twice for the same service, 3,200 DKK, this is unacceptable. Please call me back ASAP.", ("Karen Winther", "2026-11-30", 3200, "complaint", True)),
             ("Bo Nielsen (12 December 2026) sends the minutes of the team meeting. Nothing else.", ("Bo Nielsen", "2026-12-12", 0, "other", False)),
             ("Ida Frost, 7 July 2026: Here is our invoice for the room rental, 1.200 kr., due at the end of the month.", ("Ida Frost", "2026-07-07", 1200, "invoice", False)),
             ("Ole Bruun, 19 August 2026: Is it possible to get a parking permit for the new office? I need an answer ASAP.", ("Ole Bruun", "2026-08-19", 0, "inquiry", True))]
    valid = strict = correct = 0; gens = []; rows = []
    for i, (msg, exp) in enumerate(CASES):
        r = gen(SCH + msg, 0.3, 400, seed=SEED + i); gens.append(r); t = r["text"]
        try: j = json.loads(t); ok = isinstance(j, dict)
        except Exception: ok = False
        if not ok:
            m = re.search(r"\{.*\}", t, re.S)
            try: j = json.loads(m.group(0)); ok2 = isinstance(j, dict)
            except Exception: ok2 = False
        else: ok2 = True
        if ok2: valid += 1
        if ok: strict += 1
        good = False
        if ok2:
            keys = set(j) == {"sender", "date", "amount_dkk", "category", "urgent", "tags"}
            tg = isinstance(j.get("tags"), list) and 1 <= len(j["tags"]) <= 3 and all(isinstance(x, str) and x == x.lower() for x in j["tags"])
            good = keys and tg and j.get("sender") == exp[0] and j.get("date") == exp[1] and j.get("amount_dkk") == exp[2] and isinstance(j.get("amount_dkk"), int) and j.get("category") == exp[3] and j.get("urgent") is exp[4]
        correct += good; rows.append(dict(i=i, strict=ok, parsed=ok2, fully_correct=bool(good), out=t[:300]))
    tot_ev = sum(g["eval_count"] for g in gens); tot_ed = sum(g["eval_count"] / max(g["tok_s"], 1e-9) for g in gens)
    open(os.path.join(OUT, "json_trials.json"), "w", encoding="utf-8").write(json.dumps(rows, indent=1, ensure_ascii=False))
    R["tasks"]["json"] = dict(trials=10, strict_valid_json=strict, lenient_parsed=valid, fully_correct=int(correct), eval_count=tot_ev, tok_s=round(tot_ev / max(tot_ed, 1e-9), 1), ttft=round(sum(g["ttft"] for g in gens) / 10, 2), wall=round(sum(g["wall"] for g in gens), 1),
                              auto_score=round(5 * (0.3 * strict / 10 + 0.1 * valid / 10 + 0.6 * correct / 10), 2)); save()
    print(f"  json: strict {strict}/10 lenient {valid}/10 fully correct {int(correct)}/10", flush=True)
# ---------------- D) coding with hidden unit tests
CODE_TESTS = r'''
import sys, traceback
res = {}
def t(name, f):
    try: res[name] = bool(f())
    except Exception: res[name] = False
def raises(f):
    try: f()
    except ValueError: return True
    except Exception: return False
    return False
t("mi_empty", lambda: merge_intervals([]) == [])
t("mi_basic", lambda: merge_intervals([(1,3),(2,6),(8,10),(15,18)]) == [(1,6),(8,10),(15,18)])
t("mi_touch", lambda: merge_intervals([(1,4),(4,5)]) == [(1,5)])
t("mi_unsorted", lambda: merge_intervals([(5,7),(1,2),(2,3)]) == [(1,3),(5,7)])
t("mi_contained", lambda: merge_intervals([(1,10),(2,3),(4,5)]) == [(1,10)])
t("mi_lists_tuples", lambda: merge_intervals([[1,2],[2,3]]) == [(1,3)] and all(type(x) is tuple for x in merge_intervals([[1,2],[5,6]])))
def _nm():
    a=[(5,7),(1,2)]; merge_intervals(a); return a==[(5,7),(1,2)]
t("mi_no_mutation", _nm)
t("mi_single", lambda: merge_intervals([(3,3)]) == [(3,3)])
t("pd_basic", lambda: parse_duration("1h30m") == 5400)
t("pd_sec", lambda: parse_duration("90s") == 90)
t("pd_days", lambda: parse_duration("2d4h") == 187200)
t("pd_all", lambda: parse_duration("1d1h1m1s") == 90061)
t("pd_space", lambda: parse_duration(" 1h 30m ") == 5400)
t("pd_order", lambda: parse_duration("30m1h") == 5400)
t("pd_empty", lambda: raises(lambda: parse_duration("")))
t("pd_garbage", lambda: raises(lambda: parse_duration("abc")))
t("pd_unit", lambda: raises(lambda: parse_duration("5x")))
t("pd_dup", lambda: raises(lambda: parse_duration("1h1h")))
t("pd_neg", lambda: raises(lambda: parse_duration("-5m")))
t("pd_nonum", lambda: raises(lambda: parse_duration("h")))
print("RESULT", res)
'''
if "code" in only:
    P = """Write Python 3 code (standard library only) that defines these two functions. Reply with ONE python code block containing only the code (no tests, no prints, no explanation outside the block).

1. merge_intervals(intervals) -> list of tuples. `intervals` is a list of (start, end) pairs (tuples or 2-element lists) with start <= end, in any order. Merge all overlapping intervals and also intervals that merely touch (end of one equals start of next). Return a new list of (start, end) tuples sorted by start. Do not modify the input. An empty input returns [].

2. parse_duration(s) -> int, total seconds. `s` is a string made of one or more parts "<integer><unit>" with units d (days), h (hours), m (minutes), s (seconds), e.g. "1h30m" = 5400, "90s" = 90, "2d4h" = 187200. Parts may appear in any order and may be separated by spaces; leading/trailing whitespace is allowed. Each unit may appear at most once. Raise ValueError for an empty string, an unknown unit, a missing number, a negative number, a repeated unit or any other malformed input.
"""
    r = gen(P, 0.2, 2500); t = r["text"]
    m = re.findall(r"```(?:python|py)?\s*\n(.*?)```", t, re.S); code = max(m, key=len) if m else t
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "sol.py"); open(f, "w", encoding="utf-8").write(code + "\n" + CODE_TESTS)
        try:
            p = subprocess.run([sys.executable, f], capture_output=True, text=True, timeout=20); mm = re.search(r"RESULT (\{.*\})", p.stdout); res = eval(mm.group(1)) if mm else {}; err = p.stderr[-300:]
        except subprocess.TimeoutExpired: res = {}; err = "timeout"
    npass = sum(1 for v in res.values() if v); total = 20
    open(os.path.join(OUT, "code_solution.py"), "w", encoding="utf-8").write(code)
    rec("code", r, dict(tests_passed=npass, tests_total=total, failed=[k for k, v in res.items() if not v] if res else "no result (syntax/runtime error)", stderr_tail=err, auto_score=round(5 * npass / total, 2)))
# ---------------- E) Danish professional email
if "da" in only:
    P = """Du er teamkoordinator i en kommunal sagsbehandlingsenhed. Skriv en kort, professionel e-mail på dansk (120-160 ord) til dine kolleger i teamet. Indhold:
1) Det ugentlige teammøde flyttes fra tirsdag kl. 9.00 til onsdag kl. 10.30 fra næste uge.
2) Tre beslutninger fra sidste møde: vi indfører en fast frist på fem hverdage for svar på borgerhenvendelser; vi samler sagsskabeloner i en fælles mappe; Maja og Kasper overtager koordineringen af vikardækning.
3) Alle bedes bekræfte deltagelse senest fredag kl. 12.00.
Skriv med emnelinje ("Emne:"), en naturlig hilsen og en afslutning med "Venlig hilsen" og navnet "Teamkoordinator". Tonen skal være saglig, venlig og klar, som en rigtig dansk kommunal mail, uden floskler og uden at oversætte direkte fra engelsk. Svar kun med mailen."""
    r = gen(P, 0.5, 900); t = r["text"]; wc = words(t)
    facts = [("onsdag", r"onsdag"), ("10.30", r"10[.:]30"), ("fem hverdage", r"(fem|5) hverdage"), ("skabeloner", r"skabelon"), ("fælles mappe", r"fælles mappe"), ("Maja", r"\bMaja\b"), ("Kasper", r"\bKasper\b"), ("vikardækning", r"vikardækning"), ("fredag 12", r"fredag.{0,20}12[.:]00|12[.:]00.{0,20}fredag"), ("tirsdag 9", r"tirsdag.{0,25}9[.:]?0?0?")]
    got = [n for n, p in facts if re.search(p, t, re.I | re.S)]
    leak = re.findall(r"\b(the|and|please|regards|with|will|meeting|best)\b", t, re.I)
    dk = len(re.findall(r"\b(og|at|til|der|vi|er|som|for|med|af|jeg|det|en|på)\b", t.lower()))
    s = 1.0 * (len(got) / len(facts)) * 2 + (0.5 if re.search(r"^\s*\**Emne:", t, re.M | re.I) else 0) + (0.5 if re.search(r"venlig hilsen", t, re.I) else 0) + (1.0 if 100 <= wc <= 185 else 0.5 if 80 <= wc <= 220 else 0) + (0.5 if not leak else 0) + (0.5 if dk / max(wc, 1) > 0.15 else 0)
    rec("da", r, dict(words=wc, facts=f"{len(got)}/{len(facts)}", missing=[n for n, _ in facts if n not in got], english_leak=leak[:5], auto_score=round(min(5, s), 2)))
# ---------------- unload
try: post("/api/generate", {"model": model, "prompt": "", "keep_alive": 0}, timeout=60).read()
except Exception as e: print("unload err", e)
for _ in range(40):
    if not get("/api/ps")["models"]: break
    time.sleep(1.5)
R["unloaded"] = not get("/api/ps")["models"]; R["finished"] = time.strftime("%Y-%m-%d %H:%M:%S"); save(); print(f"[{model}] done, unloaded={R['unloaded']}", flush=True)
