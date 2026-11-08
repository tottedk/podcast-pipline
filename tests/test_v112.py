"""tests\\test_v112.py (template v1.12, 2026-10-21) - unit tests for the v1.12 changes (no GPU, no audio files, nothing outside a temp dir is written).
  venv_vv\\Scripts\\python.exe tests\\test_v112.py [C:\\grok\\podcast]
Covers: d3_pace.clamp (relative silence threshold vs the v1.11 32 dB rule, [whispers] guard, short pauses untouched), d3_pace.plan_tempo (map,
auto-calibration + lock, clamp 0.85-1.10, fallback), md_clean.strip_lead_sighs, episodes_index import guard + update subcommand (temp index)."""
import json, os, subprocess, sys, tempfile
import numpy as np
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import d3_pace, md_clean
fails = 0; n = 0
def check(c, msg):
    global fails, n
    n += 1; fails += (not c); print(("PASS " if c else "FAIL ") + msg)
sr = 24000; rng = np.random.default_rng(0); amp = 0.3; sp_db = 20 * np.log10(amp / np.sqrt(2))
def tone(s): t = np.arange(int(sr * s)) / sr; return amp * np.sin(2 * np.pi * 150 * t) * (1 + 0.3 * np.sin(2 * np.pi * 3 * t))
def noise(s, rel): return rng.normal(0, 1, int(sr * s)) * 10 ** ((sp_db + rel) / 20)
w = np.concatenate([tone(2) + noise(2, -27), noise(1.5, -27), tone(2) + noise(2, -27)]).astype(np.float32)   # Elliot-like pause: noise/breath 27 dB below speech (between the -32 and -20 dB rules)
o, info = d3_pace.clamp(w, sr, 0.4, 0.4, 20)
check(abs(len(o) / sr - 4.4) < 0.1, f"clamp v2: 1.5 s pause over a noisy floor (-27 dB) -> 0.4 s (total {len(o)/sr:.2f} s, expect ~4.4; {info.get('clamped')})")
o2, _ = d3_pace.clamp(w, sr, 0.4, 0.4, 32)
check(len(o2) / sr > 5.4, f"v1.11 rule (32 dB) misses the same pause ({len(o2)/sr:.2f} s) - the Fault Lines #1 root cause")
oq, _ = d3_pace.clamp(w, sr, 0.4, 0.4, 20, quiet=True)
check(len(oq) / sr > 5.4, "[whispers] chunk keeps the 32 dB rule (soft speech is never treated as silence)")
s3 = np.concatenate([tone(1), noise(0.3, -60), tone(1)]).astype(np.float32); o3, _ = d3_pace.clamp(s3, sr, 0.4, 0.4, 20)
check(abs(len(o3) - len(s3)) < sr * 0.01, "0.3 s pause (< cap) untouched")
s4 = np.concatenate([noise(0.8, -60), tone(1), noise(0.9, -60)]).astype(np.float32); o4, i4 = d3_pace.clamp(s4, sr, 0.4, 0.4, 20)
check(abs(i4["lead_cut_s"] - 0.75) < 0.03 and abs(i4["tail_cut_s"] - 0.78) < 0.03, f"lead -> 0.05 s, tail -> 0.12 s ({i4['lead_cut_s']}, {i4['tail_cut_s']})")
cfg = d3_pace.load_cfg(os.path.join(ROOT, "drama3_tempo.json")); lock = {}
tb = d3_pace.plan_tempo(cfg, {"Host": "Carter", "Guest": "Elliot_v2", "Guest2": "Clara"}, {"Carter": [200, 60.0], "Elliot_v2": [100, 40.0], "Clara": [100, 36.0]}, lock, 0.90)
check(tb["Host"] == {"tempo": 0.86, "src": "map", "raw_wpm": 200.0}, f"Carter fixed 0.86 from the map ({tb['Host']})")
check(tb["Guest2"]["tempo"] == 0.95 and tb["Guest2"]["src"] == "map", "Clara fixed 0.95")
cfg_ps = dict(cfg); cfg_ps["voices"] = dict(cfg["voices"])
cfg_ps["voices"]["Carter"] = {"mode": "per_segment", "target_wpm": 156, "min_tempo": 0.72, "max_tempo": 0.95, "fallback": 0.86}
tbps = d3_pace.plan_tempo(cfg_ps, {"Host": "Carter"}, {"Carter": [300, 300 * 60 / 210]}, {}, 0.90)
check(tbps["Host"]["src"] == "per_segment" and abs(tbps["Host"]["tempo"] - 0.743) < 1e-9, f"per_segment Carter 156/210 wpm -> 0.743 ({tbps['Host']})")
lock_ps = {}
d3_pace.plan_tempo(cfg_ps, {"Host": "Carter"}, {"Carter": [300, 300 * 60 / 210]}, lock_ps, 0.90)
check("Carter" not in lock_ps, "per_segment tempo is not written to the lock")
tbfb = d3_pace.plan_tempo(cfg_ps, {"Host": "Carter"}, {"Carter": [10, 3.0]}, {}, 0.90)["Host"]
check(tbfb["src"] == "voice-fallback" and tbfb["tempo"] == 0.86, f"per_segment with too few words uses the voice fallback ({tbfb})")
check(tb["Guest"]["src"] == "auto" and abs(tb["Guest"]["tempo"] - 160 / 150) < 0.002 and "Elliot_v2" in lock, f"unmapped Elliot_v2 at raw 150 wpm -> auto {tb['Guest']['tempo']} and locked")
tb2 = d3_pace.plan_tempo(cfg, {"Guest": "Elliot_v2"}, {"Elliot_v2": [100, 30.0]}, lock, 0.90)
check(tb2["Guest"]["src"] == "locked" and tb2["Guest"]["tempo"] == tb["Guest"]["tempo"], "a later segment reuses the locked tempo")
check(d3_pace.plan_tempo(cfg, {"Guest": "Elliot"}, {"Elliot": [100, 40.0]}, {}, 0.9)["Guest"]["tempo"] == 1.00, "old Elliot ref -> 1.00 (map)")
check(d3_pace.plan_tempo(cfg, {"Guest": "X"}, {"X": [100, 100.0]}, {}, 0.90)["Guest"]["tempo"] == 1.10, "auto clamped at 1.10 (raw 60 wpm)")
check(d3_pace.plan_tempo(cfg, {"Guest": "X"}, {"X": [100, 25.0]}, {}, 0.90)["Guest"]["tempo"] == 0.85, "auto clamped at 0.85 (raw 240 wpm)")
t5 = d3_pace.plan_tempo(cfg, {"Guest": "Y"}, {"Y": [10, 3.0]}, {}, 0.90)["Guest"]; check(t5["src"] == "fallback" and t5["tempo"] == 0.90, "too few words -> fallback tempo")
t6 = d3_pace.plan_tempo(dict(cfg, auto_all=True), {"Host": "Carter"}, {"Carter": [186, 60.0]}, {}, 0.9)["Host"]; check(t6["src"] == "auto" and t6["tempo"] == 0.86, f"auto_all: Carter raw 186 wpm -> {t6['tempo']}")
L = [{"speaker": "Guest", "text": "[sighs] Sick. I felt sick."}, {"speaker": "Host", "text": "[sighs] Okay."}, {"speaker": "Guest2", "text": "I [sighs] see."}, {"speaker": "Guest", "text": "[sighs]"}, {"speaker": "Guest2", "text": "[Sighs] Fine."}]
o, k = md_clean.strip_lead_sighs(L)
check(k == 2 and o[0]["text"] == "Sick. I felt sick." and o[1]["text"] == "[sighs] Okay." and o[2]["text"] == "I [sighs] see." and o[3]["text"] == "[sighs]" and o[4]["text"] == "Fine.", "strip_lead_sighs: guests only, leading tag only, tag-only line kept")
r = subprocess.run([sys.executable, "-c", f"import sys;sys.argv=['x'];sys.path.insert(0,r'{ROOT}');import episodes_index as E;print('IMPORT_OK',callable(E.main))"], capture_output=True, text=True)
check("IMPORT_OK True" in r.stdout, "episodes_index imports without running argparse (__main__ guard)")
tmp = tempfile.mkdtemp(); ix = os.path.join(tmp, "ix.json")
json.dump({"episodes": [{"ep": "t1", "number": 1, "version": 1, "series": "S", "multi": False, "series_no": None, "display_title": "T", "subject": "T", "label": "x", "date": "2026-01-01", "duration_s": 100}], "series": {}}, open(ix, "w"))
r = subprocess.run([sys.executable, os.path.join(ROOT, "episodes_index.py"), "update", "--ep", "t1", "--dur", "2593.4378", "--date", "2026-10-21", "--note", "n", "--index", ix], capture_output=True, text=True)
e = json.load(open(ix))["episodes"][0]
check(e["duration_s"] == 2593.4378 and e["date"] == "2026-10-21" and e["note"] == "n" and "43:13" in r.stdout and "43:13" in open(ix[:-5] + ".md").read(), f"update subcommand on a temp index ({r.stdout.strip()})")
print(f"TESTS {n - fails}/{n} passed")
sys.exit(1 if fails else 0)
