import json, collections
ev=json.load(open(r"noise_check\events.json")); print(len(ev)); print(ev[0])
ba=json.load(open(r"noise_check\before_after.json"))
mm=[e for e in ev if e["ep"]=="mm"]
print(collections.Counter(e["voice"] for e in mm))
s=json.load(open(r"mm\seg01.json")); print(type(s), (list(s.keys()) if isinstance(s,dict) else len(s)))
