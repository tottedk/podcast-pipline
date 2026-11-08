r"""qc_eval.py (desk tools, 2026-11-01) - offline eval of the episode QC checks. One command, no models, no LLM, no audio:
    venv_vv\Scripts\python.exe tools\qc_eval.py [--rebuild] [--root C:\grok\podcast]
Builds <root>\qc_eval\fixtures\ from <root>\qc_eval\base\ (deterministic, seed 7) unless it exists (--rebuild = rebuild), runs
tools\episode_qc.py pre + post on every fixture, the brief_gen.py label strip and fact-check guard on their cases, and writes
<root>\qc_eval\results.md + results.json: precision / recall per check, plus every miss and false alarm. Exit 0 = all expected, 1 = any miss/false alarm.
Fixture = segNN.json (script text = what TTS gets), ep_script.json, ep.whisper.json (what the audio says, simulated from the script with
whisper-like noise), ep.timings.json, ep.srt, expect.json {"pre": [[check, line]], "post": [[check, line]]}. Real fixtures (real_*) are the rendered
episodes' own files."""
import argparse, copy, glob, json, os, random, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = {"label": "label", "spoken_label": "label", "stage": "stage", "markdown": "markdown", "duplicate": "duplicate",
         "repeat": "repeat", "dropped": "dropped", "truncated_end": "dropped", "extra": "extra", "empty": "empty"}
NAMES = "Carter,Clara,Lachlan"
EP = "fx"

# ---------------- fixture building ----------------
def tokens_for_audio(text, rnd, noise):
    """whisper-like words of a script line: punctuation kept on words, some 'Alright'->'All right', digits, and a few ASR slips"""
    t = re.sub(r"\[(?:laughs|sighs)\]", " ", text).replace("Alright", "All right")
    w = t.split(); out = []
    for x in w:
        if noise and rnd.random() < 0.02: x = rnd.choice(["the", "a", "uh", x + "s"])   # ~2 % ASR slips
        out.append(x)
    return out

def build_audio(lines_audio, wps=2.7, gap=0.4):
    """lines_audio: list of (script_line_index or None, [words]) in spoken order -> whisper words + timings lines"""
    W = []; T = {}; t = 1.0
    for li, ws in lines_audio:
        st = t
        for x in ws: W.append([x, round(t, 2), round(t + 1 / wps - 0.05, 2)]); t += 1 / wps
        if li is not None and li not in T: T[li] = {"start": round(st, 2), "end": round(t, 2)}
        t += gap
    return W, T, t

def srt_of(lines, T):
    cues = []; n = 1
    def ts(s): return f"{int(s//3600):02d}:{int(s%3600//60):02d}:{int(s%60):02d},{int(round((s%1)*1000)):03d}"
    for i, l in enumerate(lines):
        if i not in T: continue
        w = l["text"].split(); st, en = T[i]["start"], T[i]["end"]; step = (en - st) / max(1, len(w))
        for k in range(0, len(w), 12):
            a = st + k * step; b = st + min(len(w), k + 12) * step
            cues.append(f"{n}\n{ts(a)} --> {ts(b)}\n{' '.join(w[k:k+12])}\n"); n += 1
    return "\n".join(cues)

def write_fixture(fd, name, lines, audio=None, srt_edit=None, expect=None, seg_sizes=(12, 12, 12)):
    d = os.path.join(fd, name); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    rnd = random.Random(7)
    if audio is None: audio = [(i, tokens_for_audio(l["text"], rnd, True)) for i, l in enumerate(lines)]
    W, T, dur = build_audio(audio)
    k = 0; sizes = list(seg_sizes); sizes[-1] = len(lines) - sum(sizes[:-1])
    for s, n in enumerate(sizes):
        json.dump(lines[k:k + n], open(os.path.join(d, f"seg{s:02d}.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False); k += n
    json.dump(lines, open(os.path.join(d, f"{EP}_script.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump({"model": "simulated", "duration": dur, "words": W}, open(os.path.join(d, f"{EP}.whisper.json"), "w", encoding="utf-8"))
    TL = [{"speaker": l["speaker"], "text": l["text"], **T.get(i, {"start": None, "end": None})} for i, l in enumerate(lines)]
    json.dump({"duration": dur, "lines": TL}, open(os.path.join(d, f"{EP}.timings.json"), "w", encoding="utf-8"))
    srt = srt_of(lines, T)
    if srt_edit: srt = srt_edit(srt)
    open(os.path.join(d, f"{EP}.srt"), "w", encoding="utf-8").write(srt)
    json.dump(expect or {"pre": [], "post": []}, open(os.path.join(d, "expect.json"), "w", encoding="utf-8"), indent=1)

def build(root):
    base = json.load(open(os.path.join(root, "qc_eval", "base", "base_script.json"), encoding="utf-8-sig"))
    fd = os.path.join(root, "qc_eval", "fixtures"); shutil.rmtree(fd, ignore_errors=True); os.makedirs(fd)
    B = lambda: copy.deepcopy(base)
    def text_defect(name, i, fn, check):   # a script text defect: pre and post must both see it (post via script + srt)
        L = B(); L[i]["text"] = fn(L[i]["text"]); write_fixture(fd, name, L, expect={"pre": [[check, i]], "post": [[check, i]]})
    # --- planted script text defects (pre-TTS)
    text_defect("lbl_guest1_colon", 5, lambda t: "Guest 1: " + t, "label")
    text_defect("lbl_caps_dash", 9, lambda t: "GUEST 1 - " + t, "label")
    text_defect("lbl_bold_name", 13, lambda t: "**Clara:** " + t, "label")
    text_defect("lbl_host", 20, lambda t: "Host: " + t, "label")
    text_defect("lbl_speaker2_midtext", 22, lambda t: re.sub(r"([.!?]) ", r"\1 Speaker 2: ", t, count=1), "label")
    text_defect("lbl_name_after_sentence", 26, lambda t: re.sub(r"([.!?]) ", r"\1 Lachlan: ", t, count=1), "label")
    text_defect("stage_bracket", 7, lambda t: "[pauses] " + t, "stage")
    text_defect("stage_paren", 11, lambda t: re.sub(r"([.!?]) ", r"\1 (leans in) ", t, count=1), "stage")
    text_defect("stage_asterisk", 15, lambda t: "*smiles* " + t, "stage")
    text_defect("md_heading", 30, lambda t: "## Takeaways\n" + t, "markdown")
    text_defect("md_bold", 17, lambda t: t.replace(" the ", " **the** ", 1), "markdown")
    # duplicates in the script (each one is also heard twice; long ones also trip the audio repeat check)
    L = B(); L.insert(19, copy.deepcopy(L[18])); L[19]["speaker"] = "Host" if L[18]["speaker"] != "Host" else "Guest"
    write_fixture(fd, "dup_exact_next_line", L, expect={"pre": [["duplicate", 19]], "post": [["duplicate", 19], ["repeat", 19]]})
    L = B(); L[1] = copy.deepcopy(L[0]); L[1]["text"] = L[0]["text"].replace("Carter", "Clara").replace(" not ", " never ", 1) if " not " in L[0]["text"] else L[0]["text"].replace("Carter", "Clara")
    write_fixture(fd, "dup_near_factcheck_shift", L, expect={"pre": [["duplicate", 1]], "post": [["duplicate", 1], ["repeat", 1]]})   # 40-word line said twice = 15 s heard repeat
    L = B(); w = L[24]["text"].split(); L[25]["text"] = " ".join(w[10:42]) + " " + L[25]["text"]
    write_fixture(fd, "dup_partial_30_words", L, expect={"pre": [["duplicate", 25]], "post": [["duplicate", 25]]})
    # --- audio-only defects (post-TTS): script clean, the audio differs
    rnd = random.Random(7); A0 = [(i, tokens_for_audio(l["text"], rnd, True)) for i, l in enumerate(base)]
    def aud(name, mod, exp):
        A = copy.deepcopy(A0); A = mod(A); write_fixture(fd, name, B(), audio=A, expect={"pre": [], "post": exp})
    def rep(nw, at):
        def m(A):
            src = A[at][1]; A.insert(at + 1, (None, src[:nw])); return A
        return m
    aud("audio_repeat_5s", rep(13, 10), [])
    aud("audio_repeat_12s", rep(32, 10), [])            # 8-15 s = warning only (gate threshold 15 s)
    aud("audio_repeat_20s", rep(54, 10), [["repeat", 11]])
    aud("audio_repeat_40s", rep(108, 15), [["repeat", 16]])
    aud("audio_dropped_line", lambda A: A[:14] + A[15:], [["dropped", 14]])
    aud("audio_dropped_short_line", lambda A: A[:4] + A[5:], [["dropped", 4]])
    aud("audio_truncated_end", lambda A: A[:-3] + [(33, A[-3][1][:10])], [["dropped", 33], ["dropped", 34], ["dropped", 35]])
    aud("audio_spoken_label", lambda A: A[:8] + [(None, ["Guest", "one."])] + A[8:], [["label", 8]])
    aud("audio_extra_speech", lambda A: A[:20] + [(None, "and so the garden is wet because rain comes from clouds that drift over the green hills every spring while my neighbour waters his roses twice a day anyway for no reason at all".split())] + A[20:], [["extra", 20]])
    write_fixture(fd, "srt_label_only", B(), srt_edit=lambda s: s.replace("\n" + base[3]["text"].split()[0] + " ", "\nGuest 2: " + base[3]["text"].split()[0] + " ", 1),
                  expect={"pre": [], "post": [["label", None]]})
    # --- clean edge cases: nothing may be flagged
    write_fixture(fd, "ok_clean", B())
    L = B(); L[6]["text"] = "I was Guest 1 on that panel, and the host never let me finish. " + L[6]["text"]; L[12]["text"] += " As guest two on a radio show once said, it is all about the speaker one trusts."
    write_fixture(fd, "ok_guest1_mid_sentence", L)
    L = B(); L[3]["text"] = "Here's the thing: the ratio was 3:1 at 10:30 in the morning. " + L[3]["text"]; L[8]["text"] = "[laughs] " + L[8]["text"] + " [sighs]"; L[10]["text"] += " In code you write snake_case names, and 3 * 4 is still twelve."
    write_fixture(fd, "ok_colons_tags_math", L)
    L = B()
    for i in (4, 12, 21, 29): L[i]["text"] += " Call it the Lachlan disclaimer: trust, but verify."
    write_fixture(fd, "ok_callbacks_short_repeats", L)
    L = B(); q = "\"the creation of an identity implies the establishment of a difference, difference which is often constructed on the basis of a hierarchy\""
    L[2]["text"] += " As Mouffe puts it, " + q + "."; L[31]["text"] += " Remember Mouffe: " + q + "."
    write_fixture(fd, "ok_distant_quote_callback", L)
    L = B(); L[16]["text"] = L[16]["text"] + " Alright, alright."
    write_fixture(fd, "ok_asr_variants", L, audio=[(i, tokens_for_audio(l["text"], random.Random(i), True)) for i, l in enumerate(L)])
    # --- the two real rendered episodes (their own files)
    for nm, ep, exp in [("real_ep13_agent_orchestration", "agent_orchestration_debate_ep1",
                         {"pre": [["label", 31], ["duplicate", 68]], "post": [["label", 31], ["label", None], ["duplicate", 68], ["repeat", 68]]}),
                        ("real_ep14_algorithmic_sin", "algorithmic_sin_ep1", {"pre": [["duplicate", 1], ["duplicate", 49]], "post": [["duplicate", 1], ["duplicate", 49]]})]:
        d = os.path.join(fd, nm); shutil.copytree(os.path.join(root, "qc_eval", "base", nm), d)
        exp["ep"] = ep; json.dump(exp, open(os.path.join(d, "expect.json"), "w", encoding="utf-8"), indent=1)

# ---------------- running ----------------
def run_qc(root, d, mode, ep):
    out = os.path.join(d, f"_epqc_{mode}.json")
    cmd = [sys.executable, os.path.join(HERE, "episode_qc.py"), mode, d, "--names", NAMES, "--out", out]
    if mode == "post": cmd += ["--ep", ep, "--srt", os.path.join(d, f"{ep}.srt")]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    r = json.load(open(out, encoding="utf-8")); os.remove(out)
    return p.returncode, p.stdout.strip(), r

def hit_line(h, segs):
    if h.get("line") is not None: return h["line"]
    if h.get("at") and "#" in h["at"]:   # pre: segNN.json#k -> global line
        f, k = h["at"].split("#"); return segs[f] + int(k)
    return None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", default=os.path.dirname(HERE)); ap.add_argument("--rebuild", action="store_true")
    a = ap.parse_args(); root = a.root; fd = os.path.join(root, "qc_eval", "fixtures")
    if a.rebuild or not os.path.isdir(fd): build(root)
    stats = {}; rows = []; bad = []
    def tally(stage, chk, kind): stats.setdefault((stage, chk), {"tp": 0, "fp": 0, "fn": 0, "tn": 0})[kind] += 1
    for d in sorted(glob.glob(os.path.join(fd, "*", ""))):
        name = os.path.basename(os.path.dirname(d)); E = json.load(open(os.path.join(d, "expect.json"), encoding="utf-8")); ep = E.get("ep", EP)
        segs = {}; n = 0
        for f in sorted(glob.glob(os.path.join(d, "seg??.json"))): segs[os.path.basename(f)] = n; n += len(json.load(open(f, encoding="utf-8-sig")))
        for mode in ("pre", "post"):
            rc, msg, r = run_qc(root, d, mode, ep)
            got = [(CHECK.get(h["kind"], h["kind"]), hit_line(h, segs)) for h in r["hits"]]
            exp = [(c, l) for c, l in E[mode]]
            used = set(); ok_case = True
            for c, l in exp:   # an expected defect is found if a hit of the same check is at that line (+-1), or anywhere for line None
                m = [k for k, (gc, gl) in enumerate(got) if gc == c and k not in used and (l is None or gl is None or abs(gl - l) <= 1)]
                if m: used.add(m[0]); tally(mode, c, "tp")
                else: tally(mode, c, "fn"); ok_case = False; bad.append(f"MISS {name} {mode}: {c} at line {l}")
            for k, (gc, gl) in enumerate(got):
                if k in used: continue
                if any(gc == c and (l is None or gl is None or abs(gl - l) <= 1) for c, l in exp): continue   # extra hit on the same planted defect (e.g. script + srt)
                tally(mode, gc, "fp"); ok_case = False; bad.append(f"FALSE ALARM {name} {mode}: {gc} at line {gl}: {r['hits'][k]['what'][:120]}")
            if mode == "post" and E[mode] and rc == 0: ok_case = False; bad.append(f"GATE OPEN {name}: post exit 0 despite expected hits")
            if not E[mode] and rc != 0: ok_case = False
            rows.append((name, mode, "ok" if ok_case else "WRONG", rc, msg.split(" | plan")[0][:150], [p for p in r.get("plan", [])]))
    # pre --fix: label / stage / markdown fixtures must pass after the deterministic sanitize; clean fixtures must stay byte-identical
    import tempfile
    for d in sorted(glob.glob(os.path.join(fd, "*", ""))):
        name = os.path.basename(os.path.dirname(d)); E = json.load(open(os.path.join(d, "expect.json"), encoding="utf-8"))
        kinds = {c for c, _ in E["pre"]}
        if not (kinds and kinds <= {"label", "stage", "markdown"}) and not name.startswith("ok_"): continue
        with tempfile.TemporaryDirectory() as td:
            for f in glob.glob(os.path.join(d, "seg??.json")): shutil.copy(f, td)
            before = {f: open(f, encoding="utf-8").read() for f in glob.glob(os.path.join(td, "seg??.json"))}
            p = subprocess.run([sys.executable, os.path.join(HERE, "episode_qc.py"), "pre", td, "--names", NAMES, "--fix"], capture_output=True, text=True, encoding="utf-8")
            changed = sum(open(f, encoding="utf-8").read() != t for f, t in before.items())
            wb = sum(len(json.load(open(os.path.join(d, os.path.basename(f)), encoding="utf-8"))[k]["text"].split()) for f in before for k in range(len(json.load(open(f, encoding="utf-8")))))
            wa = sum(len(l["text"].split()) for f in before for l in json.load(open(f, encoding="utf-8")))
        if name.startswith("ok_"):
            if changed: tally("pre --fix", "sanitize(no change on clean)", "fp"); bad.append(f"SANITIZE CHANGED clean fixture {name}")
            else: tally("pre --fix", "sanitize(no change on clean)", "tn")
        else:
            good = p.returncode == 0 and changed == 1 and wa >= 0.97 * wb
            tally("pre --fix", "sanitize", "tp" if good else "fn")
            if not good: bad.append(f"SANITIZE {name}: exit {p.returncode}, {changed} file(s) changed, words {wb}->{wa}: {p.stdout.strip()[:150]}")
    # brief_gen: label strip + fact-check guard
    sys.path.insert(0, HERE); import brief_gen as bg
    LS = [("Guest 1: You do not trust it.", "You do not trust it."), ("GUEST 1 - Right.", "Right."), ("**Clara:** No way!", "No way!"), ("Host: Welcome back.", "Welcome back."),
          ("Speaker 2: Fine.", "Fine."), ("Lachlan: Wrong.", "Wrong."), ("Clara, you are wrong.", "Clara, you are wrong."), ("I was Guest 1 on that panel.", "I was Guest 1 on that panel."),
          ("Here's the thing: it works.", "Here's the thing: it works."), ("The host: a role nobody wants.", "The host: a role nobody wants.")]
    for src, want in LS:
        got = bg.strip_label(src, ["Carter", "Clara", "Lachlan"]); is_lbl = src != want
        if got == want: tally("brief_gen", "label_strip", "tp" if is_lbl else "tn")
        else: tally("brief_gen", "label_strip", "fn" if is_lbl else "fp"); bad.append(f"label_strip {src!r} -> {got!r} (want {want!r})")
    FC = json.load(open(os.path.join(root, "qc_eval", "base", "factcheck_cases.json"), encoding="utf-8"))
    for c in FC:
        ft = bg.strip_label(c["fixed_text"], ["Carter", "Clara", "Lachlan"]); ok, rs, ro = bg.fc_fix_ok(c["seg"], c["j"], ft); rej = not ok; want = c["expect"] == "reject"
        k = ("tp" if want else "fp") if rej else ("fn" if want else "tn")
        tally("brief_gen", "factcheck_guard(reject)", k)
        if k in ("fp", "fn"): bad.append(f"factcheck_guard {c['episode']} line {c['line']}: {'rejected' if rej else 'applied'} (self {rs:.2f}, other {ro:.2f}), expected {c['expect']}")
    # report
    lines = ["# QC eval results", "", f"fixtures: {fd} ({len(rows)//2} cases), checks: tools\\episode_qc.py pre/post + brief_gen strip_label / fact-check guard", "",
             "| stage | check | TP | FP | FN | precision | recall |", "|---|---|---|---|---|---|---|"]
    for (st, ch), v in sorted(stats.items()):
        tp, fp, fn = v.get("tp", 0), v.get("fp", 0), v.get("fn", 0)
        pr = f"{tp/(tp+fp):.2f}" if tp + fp else "n/a"; rc = f"{tp/(tp+fn):.2f}" if tp + fn else "n/a"
        lines.append(f"| {st} | {ch} | {tp} | {fp} | {fn} | {pr} | {rc} |" + (f" (+{v['tn']} correct negatives)" if v.get("tn") else ""))
    lines += ["", "## cases", "", "| fixture | mode | result | exit | summary | fix plan |", "|---|---|---|---|---|---|"]
    lines += [f"| {n} | {m} | {o} | {rc} | {s} | {', '.join(p.get('segment', p.get('file', '')) + '=' + p['action'] for p in pl)} |" for n, m, o, rc, s, pl in rows]
    lines += ["", "## misses / false alarms", ""] + ([f"- {b}" for b in bad] or ["- none"])
    open(os.path.join(root, "qc_eval", "results.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    json.dump({"stats": {f"{k[0]}/{k[1]}": v for k, v in stats.items()}, "problems": bad}, open(os.path.join(root, "qc_eval", "results.json"), "w", encoding="utf-8"), indent=1)
    print("\n".join(lines[:5 + len(stats) + 1])); print(f"\n{len(bad)} miss/false alarm(s)" + ("".join(f"\n  {b}" for b in bad[:20]))); print(f"-> {os.path.join(root, 'qc_eval', 'results.md')}")
    return 1 if bad else 0

if __name__ == "__main__": sys.exit(main())
