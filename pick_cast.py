"""pick_cast.py (template v1.3, 2026-10-15) - choose the guest voices for an episode. No default cast: only the HOST is fixed (Carter unless told otherwise).
Guests are drawn at RANDOM (seeded, reproducible) from the allowed pool in voices.json.
Usage: python pick_cast.py --out <Dir>\\cast.json [--host Carter] [--roles Guest,Guest2] [--genders M,F] [--seed N] [--guests Marcus,Isla] [--min_gap 12] [--script-dir <Dir>]
  --genders  gender the script requires for each role in order (M/F/any), e.g. "M,F" = Guest male, Guest2 female. Also read from <Dir>\\cast_request.json {"Guest":"M","Guest2":"F"} if present.
  --guests   explicit override (validated, never accepts blocked voices; F0/gender problems are only warnings).
  --seed     pick seed; omitted -> a fresh random seed, which is WRITTEN to cast.json so the pick can be reproduced with --seed.
Rules: pool = voices.json "pool" (Frank, Clara, Isla, Marcus, Declan; Maya excluded 15 Oct, override only with a warning) + low-priority Samuel (weight 0.25); never Alice, Mary, Thomas, never the host.
 - gender per role respected when the script says so
 - |F0 guest - F0 host| >= min_gap (12 Hz) and |F0 guest - F0 other guest| >= min_gap, F0 from voice_f0.json (measured 7B, 3-speaker)
   -> with host Carter (132 Hz): Frank (131) and Samuel (132) are excluded, so male guests are Marcus (152) / Declan (95); Maya (202) is excluded from the pool (override only).
 - candidates = all valid (guest, guest2) pairs; weighted random choice with the seed (low-priority voices weigh 0.25); if nothing satisfies the F0 gap the pair with the largest minimum gap is used and a WARNING is written."""
import argparse, json, os, random, sys, time, itertools
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True); ap.add_argument("--host", default="Carter"); ap.add_argument("--roles", default="Guest,Guest2")
ap.add_argument("--genders", default=""); ap.add_argument("--seed", type=int, default=None); ap.add_argument("--guests", default="")
ap.add_argument("--min_gap", type=float, default=12.0); ap.add_argument("--script-dir", dest="sdir", default="")
ap.add_argument("--root", default=os.environ.get("PODCAST_ROOT", r"C:\grok\podcast")); ap.add_argument("--force", action="store_true")
a = ap.parse_args()
reg = json.load(open(os.path.join(a.root, "voices.json"), encoding="utf-8-sig")); F0 = json.load(open(os.path.join(a.root, "voice_f0.json"), encoding="utf-8-sig"))
V = reg["voices"]; blocked = {k.lower() for k in reg.get("blocked", {})}
roles = [r for r in a.roles.split(",") if r]; gen = {r: "any" for r in roles}
req = os.path.join(a.sdir or os.path.dirname(os.path.abspath(a.out)), "cast_request.json")
if os.path.exists(req):
    for r, g in json.load(open(req, encoding="utf-8-sig")).items():
        if r in gen: gen[r] = g.upper()[:1] if g.lower() != "any" else "any"
for r, g in zip(roles, [x.strip() for x in a.genders.split(",")] if a.genders else []):
    gen[r] = g.upper()[:1] if g.lower() != "any" else "any"
host = a.host
if host.lower() in blocked: sys.exit(f"Error: host {host} is blocked")
if os.path.exists(a.out) and not a.force: sys.exit(f"Error: {a.out} exists (cast already fixed for this episode; use --force to re-pick)")
seed = a.seed if a.seed is not None else random.SystemRandom().randrange(1, 2**31)
hf = F0.get(host)
def okg(v, r): return gen[r] == "any" or V[v]["gender"].upper()[:1] == gen[r]
def f0(v): return F0.get(v)
pool = [v for v in reg["pool"]["guests"] + reg["pool"].get("low_priority", []) if v in V and v != host and v.lower() not in blocked]
w = {v: (0.25 if v in reg["pool"].get("low_priority", []) else 1.0) for v in pool}
warn = []; mode = "random"
if a.guests:
    mode = "override"; g = [x.strip() for x in a.guests.split(",") if x.strip()]
    if len(g) != len(roles): sys.exit(f"Error: --guests needs {len(roles)} names for roles {roles}")
    for r, v in zip(roles, g):
        if v.lower() in blocked: sys.exit(f"Error: {v} is blocked: {reg['blocked'].get(v.capitalize(), '')}")
        if v not in V: sys.exit(f"Error: unknown voice {v}")
        if v in reg["pool"].get("excluded", {}) : warn.append(f"{v} is excluded from the random pool: {reg['pool']['excluded'][v]}")
        elif v not in pool and v != host: warn.append(f"{v} is not in the random pool")
        if not okg(v, r): warn.append(f"{r}={v} is {V[v]['gender']} but the script wants {gen[r]}")
    pick = g
else:
    cands = []
    for combo in itertools.permutations(pool, len(roles)):
        if not all(okg(v, r) for v, r in zip(combo, roles)): continue
        fs = [f0(v) for v in combo]
        gaps = [abs(x - hf) for x in fs if x is not None and hf is not None] + [abs(x - y) for x, y in itertools.combinations([x for x in fs if x is not None], 2)]
        cands.append((combo, min(gaps) if gaps else 999.0))
    if not cands: sys.exit(f"Error: no pool voices satisfy genders {gen}")
    ok = [c for c in cands if c[1] >= a.min_gap]
    if not ok:
        best = max(c[1] for c in cands); ok = [c for c in cands if c[1] == best]
        warn.append(f"no pair keeps the F0 gap >= {a.min_gap} Hz; using the largest minimum gap ({best:.1f} Hz)")
    ok.sort(key=lambda c: c[0]); rng = random.Random(seed)
    wt = [1.0 for _ in ok]
    for i, (combo, _) in enumerate(ok):
        for v in combo: wt[i] *= w[v]
    pick = list(rng.choices(ok, weights=wt, k=1)[0][0])
cast = {"Host": host}; cast.update({r: v for r, v in zip(roles, pick)})
fs = {k: f0(v) for k, v in cast.items()}
gaps = {f"{x}-{y}": round(abs(fs[x] - fs[y]), 1) for x, y in itertools.combinations(cast, 2) if fs[x] is not None and fs[y] is not None}
for k, g in gaps.items():
    if g < a.min_gap: warn.append(f"F0 gap {k} = {g} Hz < {a.min_gap}")
res = {"host": host, "guest": cast.get("Guest", ""), "guest2": cast.get("Guest2", ""), "mode": mode, "seed": seed if mode == "random" else None, "genders_required": gen,
       "f0": fs, "f0_gaps_hz": gaps, "pool": pool, "min_gap": a.min_gap, "warnings": warn, "picked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
       "reproduce": f"python pick_cast.py --out cast.json --host {host} --roles {a.roles} --genders {','.join(gen[r] for r in roles)} --seed {seed} --force" if mode == "random" else "override: " + a.guests}
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True); json.dump(res, open(a.out, "w"), indent=1)
print(f"CAST host={host} guest={res['guest']} guest2={res['guest2']} mode={mode} seed={res['seed']} gaps={gaps}" + ("  WARN: " + "; ".join(warn) if warn else ""))
