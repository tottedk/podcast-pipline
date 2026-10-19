"""gen_faultlines.py - generate Fault Lines #1 script draft in sequential parts with gemma4 via Ollama (reasoning off). Draft only; edited afterwards."""
import json, os, sys, time, urllib.request, urllib.error, re
D = sys.argv[1]; B = json.load(open(os.path.join(D, "gen", "bundle.json"), encoding="utf-8"))
CT = json.load(open(os.path.join(D, "cast_traits.json"), encoding="utf-8-sig"))
MODEL = "gemma4:26b-a4b-it-qat"; HOST = "http://127.0.0.1:11434"
SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
    "speaker": {"type": "string", "enum": ["Host", "Guest", "Guest2"]}, "text": {"type": "string"}}, "required": ["speaker", "text"]}},
    "summary": {"type": "string"}}, "required": ["lines", "summary"]}
def log(m): print(time.strftime("%H:%M:%S"), m, flush=True)
def call(prompt):
    for think in (False, None):
        d = {"model": MODEL, "prompt": prompt, "stream": False, "format": SCHEMA, "keep_alive": "10m",
             "options": {"temperature": 0.85, "top_p": 0.95, "num_ctx": 16384, "num_predict": 4500, "repeat_penalty": 1.08}}
        if think is not None: d["think"] = think
        try: r = json.load(urllib.request.urlopen(urllib.request.Request(HOST + "/api/generate", data=json.dumps(d).encode(), headers={"Content-Type": "application/json"}), timeout=900))
        except urllib.error.HTTPError:
            if think is not None: continue
            raise
        return json.loads(r["response"])
allL, summ = [], []
os.makedirs(os.path.join(D, "gen"), exist_ok=True)
for i, p in enumerate(B["parts"], 1):
    tail = "\n".join(f'{l["speaker"]}: {l["text"]}' for l in allL[-10:])
    prompt = (B["system"] + "\n\nGUEST TRAITS (guests only; Carter has NO random traits):\n" + CT["prompt_block"] +
              "\n\nALLOWED VERBATIM QUOTES (only these may be quoted word for word; attribute to author/book; never invent others):\n" + B["quotes"] +
              "\n\nFACTS YOU MAY USE (and constraints):\n" + B["facts"] + "\n\nCARTER'S PREPARED QUESTIONS:\n" + B["questions"] +
              "\n\nSTORY SO FAR (summaries of earlier parts):\n" + ("\n".join(f"Part {k+1}: {s}" for k, s in enumerate(summ)) or "(this is the start)") +
              "\n\nLAST LINES SO FAR:\n" + (tail or "(none)") +
              f"\n\nNOW WRITE PART {i} of {len(B['parts'])}: {p['brief']}\nLength: about {p['words']} words in total across all lines (this matters). "
              "Continue seamlessly from the last lines; do not restart or re-introduce. Return JSON {\"lines\":[{\"speaker\":\"Host|Guest|Guest2\",\"text\":...}],\"summary\":\"3-5 sentences of what happened in this part, incl. any running jokes, wounds or callbacks\"}.")
    best = None
    for att in range(2):
        t0 = time.time()
        try: r = call(prompt)
        except Exception as e: log(f"part {i} att {att} ERROR {e}"); continue
        w = sum(len(l["text"].split()) for l in r.get("lines", []))
        log(f"part {i} att {att}: {len(r.get('lines', []))} lines {w} words {time.time()-t0:.0f}s")
        if best is None or w > best[0]: best = (w, r)
        if w >= 0.8 * p["words"]: break
    if not best: log(f"part {i} FAILED"); continue
    r = best[1]; json.dump(r, open(os.path.join(D, "gen", f"part{i}.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    allL += [l for l in r["lines"] if l.get("text", "").strip()]; summ.append(r.get("summary", ""))
json.dump(allL, open(os.path.join(D, "gen", "draft_raw.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
log(f"DONE lines={len(allL)} words={sum(len(l['text'].split()) for l in allL)}")
