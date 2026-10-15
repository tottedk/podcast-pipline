r"""judge_prep.py: build blind packets (labels A,B,C... shuffled, seed 7) for write / summ / da; mapping in blind_key.json (do not open before rating). Local only."""
import os, json, random, glob, string
D = os.path.dirname(os.path.abspath(__file__)); models = [json.load(open(f))["model"] for f in sorted(glob.glob(D + r"\results\*.json")) if not f.endswith(".hw.json")]
random.Random(7).shuffle(models); key = {}
for task, fn in (("write", "write_plain.txt"), ("summ", "summ.txt"), ("da", "da.txt")):
    safe = lambda m: "".join(c if c.isalnum() or c in "._-" else "_" for c in m); parts = []
    for i, m in enumerate(models):
        p = os.path.join(D, "results", safe(m), fn); L = string.ascii_uppercase[i]; key.setdefault(task, {})[L] = m
        parts.append(f"===== {L} =====\n" + (open(p, encoding="utf-8").read() if os.path.exists(p) else "(no output)") + "\n")
    open(os.path.join(D, f"blind_{task}.md"), "w", encoding="utf-8").write("\n".join(parts))
json.dump(key, open(os.path.join(D, "blind_key.json"), "w"), indent=1); print("ok", len(models))
