import json, collections
rows=json.load(open(r"noise_check\take_eval.json")); ba=json.load(open(r"noise_check\before_after.json"))
S={"f0_drift","noise"}
def nf(r): return [f for f in r["old"] if f!="noise"]+(["noise"] if r["new_noise"] else [])
by=collections.defaultdict(list)
for r in rows: by[(r["ep"],r["seg"],r["c"])].append(r)
for ep in ("mm","ui1","dm_v2"):
    o=n=0
    for k,v in by.items():
        if k[0]!=ep: continue
        v.sort(key=lambda r:r["p"]); o+=len(v)
        for i,r in enumerate(v,1):
            if not set(nf(r))-S: break
        n+=i
    print(ep,"takes",o,"->",n)
for ep in ("mm","ui1","dm_v2"):
    R=[v for v in ba.values() if v["ep"]==ep]
    print(ep,"final chunks",len(R),"any flag old",sum(bool(r["old_flags"]) for r in R),"new",sum(bool(r["new_flags"]) for r in R),"| hard old",sum(bool(r["old_hard"]) for r in R),"new",sum(bool(r["new_hard"]) for r in R),"| noise flag old",sum("noise" in r["old_flags"] for r in R),"new",sum("noise" in r["new_flags"] for r in R),"| f0_drift only/with",sum("f0_drift" in r["new_flags"] for r in R))
print("total finals", len(ba), "any old", sum(bool(r["old_flags"]) for r in ba.values()), "new", sum(bool(r["new_flags"]) for r in ba.values()), "hard old", sum(bool(r["old_hard"]) for r in ba.values()), "new", sum(bool(r["new_hard"]) for r in ba.values()))
