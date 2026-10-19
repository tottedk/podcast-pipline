"""expand_traits.py (content_style v2.4, 2026-10-19) - expand the hand-written guest trait seed library with the local LLM via Ollama.
Usage: python tools\\expand_traits.py --seed templates\\guest_traits_seed_v1.json --out templates\\guest_traits_v1.json [--model gemma4:26b-a4b-it-qat] [--target 35] [--max 40] [--no-llm]
Asks for STRICT JSON (Ollama structured output), validates tags against tag_vocab, dedupes (normalised text + difflib ratio >= 0.72), merges, caps at --max per category.
Run `ollama stop <model>` afterwards (Thomas games on this PC)."""
import argparse, json, re, difflib, urllib.request, time
ap = argparse.ArgumentParser(); ap.add_argument("--seed", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--model", default="gemma4:26b-a4b-it-qat"); ap.add_argument("--target", type=int, default=35); ap.add_argument("--max", type=int, default=40)
ap.add_argument("--host", default="http://127.0.0.1:11434"); ap.add_argument("--no-llm", action="store_true"); ap.add_argument("--rounds", type=int, default=2)
a = ap.parse_args()
lib = json.load(open(a.seed, encoding="utf-8-sig")); vocab = set(lib["tag_vocab"])
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
    "text": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}, "side": {"type": "string", "enum": ["right", "left", "any"]},
    "rare": {"type": "boolean"}}, "required": ["text", "tags", "side", "rare"]}}}, "required": ["items"]}
def norm(s): return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()
def dup(t, items): n = norm(t); return any(n == norm(x["text"]) or difflib.SequenceMatcher(None, n, norm(x["text"])).ratio() >= 0.72 for x in items)
def ask(cat, c, need):
    ex = "\n".join("- " + x["text"] for x in c["items"])
    side_rule = ("Set side to 'right' for blind spots typical of the far right, 'left' for the far left, 'any' if universal; aim for roughly equal right and left." if cat == "blind_spots"
                 else "Set side to 'any' unless the item only fits one political side.")
    p = (f"You are helping write fictional, very human guests for a heated political debate podcast (one far-right and one far-left expert guest).\n"
         f"Category: {cat} = {c['desc']}\nExisting items:\n{ex}\n\n"
         f"Write {need} NEW items for this category. Each must be clearly different from the existing ones and from each other, concrete, usable by a scriptwriter, "
         f"max 22 words, English, audio-only (no visual-only gestures). Vary tone: funny, petty, sad, proud, stubborn. "
         f"tags: choose 0-2 from this exact list only: {sorted(vocab)}. {side_rule} rare: true only for dramatic, seldom-used behaviour (e.g. walking out). "
         f"Return strict JSON: {{\"items\":[{{\"text\":...,\"tags\":[...],\"side\":...,\"rare\":false}}]}}")
    body = json.dumps({"model": a.model, "prompt": p, "stream": False, "format": SCHEMA, "keep_alive": "10m",
                       "options": {"temperature": 0.9, "num_ctx": 8192, "num_predict": 4096}}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request(a.host + "/api/generate", data=body, headers={"Content-Type": "application/json"}), timeout=420))
    return json.loads(r["response"]).get("items", [])
stats = {}
for cat, c in lib["categories"].items():
    added = rej = 0
    for rnd in range(a.rounds if not a.no_llm else 0):
        need = a.target - len(c["items"])
        if need <= 0: break
        t0 = time.time()
        try: new = ask(cat, c, need + 6)
        except Exception as e: print(f"{cat} round {rnd}: LLM error {e}"); continue
        for x in new:
            t = " ".join(str(x.get("text", "")).split())
            if not t or len(t.split()) > 30 or dup(t, c["items"]) or len(c["items"]) >= a.max: rej += 1; continue
            side = x.get("side", "any") if cat in ("blind_spots", "backstory_hooks") else "any"
            c["items"].append({"text": t, "tags": [g for g in x.get("tags", []) if g in vocab][:2], "side": side if side in ("right", "left", "any") else "any",
                               "rare": bool(x.get("rare", False)) and cat == "emotional", "source": "llm:" + a.model})
            added += 1
        print(f"{cat} round {rnd}: got {len(new)} in {time.time()-t0:.0f}s")
    for i, x in enumerate(c["items"]): x["id"] = f"{cat[:2]}{i+1:02d}"
    stats[cat] = {"total": len(c["items"]), "llm_added": added, "rejected_dupes_or_invalid": rej}
lib["version"] = "v1"; lib["expanded_with"] = a.model if not a.no_llm else None; lib["stats"] = stats
json.dump(lib, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("TRAITS", json.dumps({k: v["total"] for k, v in stats.items()}), "added", sum(v["llm_added"] for v in stats.values()))
