"""pick_traits.py (content_style v2.4, 2026-10-19) - randomly assign human traits to the GUESTS of an episode. NEVER the Host (Carter has a fixed personality, see content_style_v2.4).
Usage: python pick_traits.py --cast <Dir>\\cast.json --out <Dir>\\cast_traits.json [--sides Guest=right,Guest2=left] [--seed N]
       [--counts quirks=1-2,debate_tactics=2,emotional=1-2,blind_spots=1,backstory_hooks=1] [--library templates\\guest_traits_v1.json] [--force]
Rules: seeded + reproducible (seed written to the output); no contradictory tag combos within one guest (exclusive_tags in the library, e.g. volatile vs calm,
stubborn vs yielding, data vs anti_data); blind spots / backstory hooks must match the guest's side (or be 'any'); the two guests never share a trait;
'rare' traits (e.g. storming off) weigh 0.3. The output's prompt_block is pasted into the script prompt."""
import argparse, json, os, random, sys, time
ap = argparse.ArgumentParser()
ap.add_argument("--cast", required=True); ap.add_argument("--out", required=True); ap.add_argument("--sides", default="Guest=right,Guest2=left")
ap.add_argument("--seed", type=int, default=None); ap.add_argument("--counts", default="quirks=1-2,debate_tactics=2,emotional=1-2,blind_spots=1,backstory_hooks=1")
ap.add_argument("--library", default=os.path.join(os.environ.get("PODCAST_ROOT", r"C:\grok\podcast"), "templates", "guest_traits_v1.json")); ap.add_argument("--force", action="store_true")
a = ap.parse_args()
lib = json.load(open(a.library, encoding="utf-8-sig")); cast = json.load(open(a.cast, encoding="utf-8-sig"))
host = cast.get("host", "Carter"); roles = {r: cast.get(k, "") for r, k in (("Guest", "guest"), ("Guest2", "guest2")) if cast.get(k)}
sides = dict(x.split("=", 1) for x in a.sides.split(",") if "=" in x)
if any(r.lower() == "host" for r in sides) or any(v == host for v in roles.values()): sys.exit("Error: traits are never assigned to the Host")
if os.path.exists(a.out) and not a.force: sys.exit(f"Error: {a.out} exists (use --force to re-pick)")
counts = {}
for x in a.counts.split(","):
    k, v = x.split("="); lo, hi = (v.split("-") + [v])[:2]; counts[k] = (int(lo), int(hi))
excl = [tuple(p) for p in lib.get("exclusive_tags", [])]
def clash(A, B): return any((x in A and y in B) or (y in A and x in B) for x, y in excl) or any((x in B and y in B) for x, y in excl)
seed = a.seed if a.seed is not None else random.SystemRandom().randrange(1, 2**31); rng = random.Random(seed)
used = set(); out = {}
for role, voice in roles.items():
    side = sides.get(role, "any"); tags = set(); got = {}
    for cat, (lo, hi) in counts.items():
        n = rng.randint(lo, hi); got[cat] = []
        for _ in range(n):
            cand = [i for i in lib["categories"][cat]["items"] if i["id"] not in used and i.get("side", "any") in ("any", side) and not clash(tags, set(i.get("tags", [])))]
            if not cand: break
            p = rng.choices(cand, weights=[0.3 if i.get("rare") else 1.0 for i in cand], k=1)[0]
            used.add(p["id"]); tags |= set(p.get("tags", [])); got[cat].append({k: p[k] for k in ("id", "text", "tags") if k in p})
    out[role] = {"voice": voice, "side": side, "tags": sorted(tags), "traits": got}
def block(r, g):
    lines = [f"{r} ({g['voice']}, {g['side']}):"]
    for cat, items in g["traits"].items():
        for i in items: lines.append(f"  - [{cat}] {i['text']}")
    return "\n".join(lines)
res = {"host": host, "host_traits": "NONE - fixed personality (content_style_v2.4, 'Carter')", "seed": seed, "counts": a.counts, "library": lib.get("version"),
       "guests": out, "picked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
       "prompt_block": "GUEST TRAITS (use naturally, not all at once; show them, never announce them):\n" + "\n".join(block(r, g) for r, g in out.items()),
       "reproduce": f"python pick_traits.py --cast {a.cast} --out {a.out} --sides {a.sides} --counts {a.counts} --seed {seed} --force"}
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True); json.dump(res, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(f"TRAITS seed={seed} " + "; ".join(f"{r}={g['voice']}/{g['side']}:{sum(len(v) for v in g['traits'].values())}" for r, g in out.items()))
