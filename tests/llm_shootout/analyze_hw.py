r"""analyze_hw.py <session.csv> <safe> <start> <end>: peak VRAM (D3D dedicated, hwmon GpuVram_MB), hotspot max etc. for the RX 7900 XT -> results\<safe>.hw.json"""
import sys, csv, json, os, statistics
f, safe, t0, t1 = sys.argv[1:5]; D = os.path.dirname(os.path.abspath(__file__))
rows = list(csv.reader(open(f, encoding="utf-8-sig"))); h = rows[0]; ix = {n: h.index(n) for n in h}
def g(r, n):
    try: return float(r[ix[n]])
    except Exception: return 0.0
allr = rows[1:]; data = [r for r in allr if t0 <= r[0][:19] <= t1]; pre = [r for r in allr if r[0][:19] < t0][-4:] or data[:3]
base = statistics.median(g(r, "GpuVram_MB") for r in pre) if pre else 0
res = dict(samples=len(data), vram_baseline_mb=round(base), vram_peak_mb=round(max(g(r, "GpuVram_MB") for r in data)) if data else None,
           hotspot_max_c=max(g(r, "GpuHotspot_C") for r in data) if data else None, hotspot_avg_c=round(statistics.mean(g(r, "GpuHotspot_C") for r in data), 1) if data else None,
           core_max_c=max(g(r, "GpuTemp_C") for r in data) if data else None, memjunction_max_c=max(g(r, "GpuMemJunc_C") for r in data) if data else None,
           power_max_w=round(max(g(r, "GpuPower_W") for r in data), 1) if data else None, power_avg_w=round(statistics.mean(g(r, "GpuPower_W") for r in data), 1) if data else None,
           load_avg_pct=round(statistics.mean(g(r, "GpuLoad_pct") for r in data), 1) if data else None, cpu_load_avg_pct=round(statistics.mean(g(r, "CpuLoad_pct") for r in data), 1) if data else None, csv=f)
if data: res["vram_peak_delta_mb"] = res["vram_peak_mb"] - res["vram_baseline_mb"]
json.dump(res, open(os.path.join(D, "results", safe + ".hw.json"), "w"), indent=1); print("hw", safe, {k: v for k, v in res.items() if k != "csv"})
