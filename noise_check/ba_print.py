import json
o=json.load(open(r"noise_check\before_after.json"))
for ep in ("mm","ui1","dm_v2"):
    R={k:v for k,v in o.items() if v["ep"]==ep}
    print(ep,"flagged any: old",sum(bool(r["old_flags"]) for r in R.values()),"new",sum(bool(r["new_flags"]) for r in R.values()),
      "| noise-ONLY old",sum(r["old_flags"]==["noise"] for r in R.values()), "| hard-other old",sum(bool([f for f in r["old_flags"] if f not in("noise","f0_drift")]) for r in R.values()))
    for k,v in R.items():
        if v["new_hard"] or "noise" in v["new_flags"] or (v["old_hard"] and v["old_hard"]!=["noise"]): print("  ",k,"old",v["old_flags"],"new",v["new_flags"],"ne/nv/nr",v["ne"],v["nv"],v["nr"],"dur",v["dur"])
