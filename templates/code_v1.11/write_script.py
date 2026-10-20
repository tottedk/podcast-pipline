"""write_script.py - notes/summary text file -> podcast script JSON via Ollama (Gemma).
Usage: python write_script.py notes.txt script.json [--model gemma4:26b-a4b-it-qat] [--lines 12] [--topic "..."]
The model is unloaded afterwards (keep_alive=0) so VRAM is freed for gaming.
"""
import argparse, json, re, sys, time, urllib.request
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from md_clean import clean_lines   # v1.4: strip markdown marks (*x*, **x**, _x_, `x`, leading #/-/>) from the TEXT only

ap = argparse.ArgumentParser()
ap.add_argument("notes"); ap.add_argument("out")
ap.add_argument("--model", default="gemma4:26b-a4b-it-qat")
ap.add_argument("--lines", type=int, default=12)
ap.add_argument("--topic", default="")
ap.add_argument("--ctx", type=int, default=8192)
ap.add_argument("--host", default="http://localhost:11434")
a = ap.parse_args()

notes = open(a.notes, encoding="utf-8-sig").read()
prompt = f"""Write a lively, natural two-person English podcast dialogue{(' about ' + a.topic) if a.topic else ''}, based on the notes below.
Speakers: "Host" (curious, warm, keeps things moving) and "Guest" (knowledgeable, opinionated, uses concrete examples).
Rules:
- About {a.lines} turns, alternating, starting and ending with Host.
- Sound like real people talking: contractions, short reactions, the occasional interruption or joke, varied sentence length. No lecture paragraphs, no "Great question!".
- Give serious counter-arguments their own strong voice, not a strawman.
- Plain spoken text only: no stage directions, markdown, emojis or speaker names inside the text.
- Output ONLY a JSON array like [{{"speaker":"Host","text":"..."}}, ...].

NOTES:
{notes}
"""
body = {"model": a.model, "prompt": prompt, "stream": False, "format": "json", "think": False,
        "keep_alive": 0, "options": {"temperature": 0.8, "num_ctx": a.ctx}}
t = time.time()
def ask():
    req = urllib.request.Request(a.host + "/api/generate", json.dumps(body).encode(), {"Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=1800))
    raw = r["response"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = json.loads(re.search(r"\[.*\]", raw, re.S).group(0))
    if isinstance(data, dict):  # model wrapped the list in an object (or returned one turn)
        lst = [v for v in data.values() if isinstance(v, list)]
        data = lst[0] if lst else [data]
    if len(data) < max(4, a.lines // 2): raise ValueError(f"only {len(data)} turns")
    return r, data
for attempt in range(3):
    try:
        r, data = ask(); break
    except Exception as e:
        print(f"attempt {attempt+1} failed: {e}", file=sys.stderr)
        if attempt == 2: raise
lines = [{"speaker": "Guest" if str(d.get("speaker","")).lower().startswith("g") else "Host", "text": d["text"].strip()} for d in data if d.get("text")]
lines, nmd = clean_lines(lines)   # v1.4: markdown marks out of the spoken text
if nmd: print(f"md_clean: {nmd} line(s) had markdown marks removed")
json.dump(lines, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
tps = r.get("eval_count", 0) / max(r.get("eval_duration", 1) / 1e9, 1e-9)
print(f"Wrote {len(lines)} lines to {a.out} | {r.get('eval_count')} tokens @ {tps:.1f} tok/s | total {time.time()-t:.1f}s | model unloaded")

