r"""summarize.py -> results.md + results.json (aggregate; no model text). Reads results\*.json, *.hw.json and judge.json (my 0-5 ratings for write/summ/da, blind)."""
import json, glob, os, statistics
D = os.path.dirname(os.path.abspath(__file__)); J = json.load(open(os.path.join(D, "judge.json"))) if os.path.exists(os.path.join(D, "judge.json")) else {}
QUANT = json.load(open(os.path.join(D, "meta_models.json"))) if os.path.exists(os.path.join(D, "meta_models.json")) else {}
rows = []
for f in sorted(glob.glob(os.path.join(D, "results", "*.json"))):
    if f.endswith(".hw.json"): continue
    R = json.load(open(f)); m = R["model"]; safe = os.path.basename(f)[:-5]; hw = json.load(open(f[:-5] + ".hw.json")) if os.path.exists(f[:-5] + ".hw.json") else {}
    T = R["tasks"]; sc = {}
    for t in ("write", "summ", "da"):
        if t in T:
            a = T[t].get("auto_score", 0); j = J.get(m, {}).get(t); sc[t] = round(0.5 * a + 0.5 * j, 2) if j is not None else a
    for t in ("json", "code"):
        if t in T: sc[t] = T[t].get("auto_score", 0)
    toks = [T[t]["tok_s"] for t in T if T[t].get("tok_s")]
    rows.append(dict(model=m, quant=QUANT.get(m, ""), size_gb=R.get("size_gb"), vram_gb=R.get("vram_gb"), gpu_pct=R.get("gpu_pct"), load_s=R.get("load_wall_s"), ttft_warm_s=R.get("ttft_warm_s"),
                     tok_s_write=T.get("write", {}).get("tok_s"), tok_s_median=round(statistics.median(toks), 1) if toks else None, ttft_write_s=T.get("write", {}).get("ttft"), prompt_tok_s=T.get("write", {}).get("prompt_tok_s"),
                     vram_peak_mb=hw.get("vram_peak_mb"), vram_base_mb=hw.get("vram_baseline_mb"), hotspot_max_c=hw.get("hotspot_max_c"), power_max_w=hw.get("power_max_w"), scores=sc, auto={t: T[t].get("auto_score") for t in T}, judge=J.get(m, {}),
                     total=round(sum(sc.values()), 2), words_write=T.get("write", {}).get("words"), json_valid=T.get("json", {}).get("strict_valid_json"), json_correct=T.get("json", {}).get("fully_correct"), code_pass=T.get("code", {}).get("tests_passed"), unloaded=R.get("unloaded")))
rows.sort(key=lambda r: -r["total"])
json.dump(rows, open(os.path.join(D, "results_aggregate.json"), "w"), indent=1)
L = ["# LLM shootout - results (aggregate, no model text)", "", "Hardware: RX 7900 XT 20 GB (ROCm via Ollama), Ryzen 5 7600X, 32 GB RAM. ctx 16384, seed 42, keep_alive 20m during tests then 0. Scores 0-5 per task; write/summ/da = 0.5 x automatic checks + 0.5 x Grok Bot's blind rating (NOT Thomas'); json/code fully automatic. Total /25.", "",
     "| # | Model | Quant | Size GB | GPU % | tok/s write (median all) | TTFT warm / write s | Peak VRAM GB (base) | Hotspot max C | write | summ | json | code | da | Total |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for i, r in enumerate(rows, 1):
    s = r["scores"]; L.append(f"| {i} | {r['model']} | {r['quant']} | {r['size_gb']} | {r['gpu_pct']} | {r['tok_s_write']} ({r['tok_s_median']}) | {r['ttft_warm_s']} / {r['ttft_write_s']} | {round((r['vram_peak_mb'] or 0)/1024,1)} ({round((r['vram_base_mb'] or 0)/1024,1)}) | {r['hotspot_max_c']} | {s.get('write')} | {s.get('summ')} | {s.get('json')} | {s.get('code')} | {s.get('da')} | **{r['total']}** |")
L += ["", "json = strict-valid / fully-correct of 10 trials; code = hidden unit tests passed of 20.", ""]
for r in rows: L.append(f"- {r['model']}: write words {r['words_write']}, json strict {r['json_valid']}/10 fully correct {r['json_correct']}/10, code {r['code_pass']}/20, load {r['load_s']} s, unloaded={r['unloaded']}")
ns = os.path.join(D, "notes_static.md"); L += [""] + (open(ns, encoding="utf-8-sig").read().splitlines() if os.path.exists(ns) else [])
open(os.path.join(D, "results.md"), "w", encoding="utf-8").write("\n".join(L) + "\n"); print("\n".join(L))
