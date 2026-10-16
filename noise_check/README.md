# noise_check (2026-10-16)
Offline analysis of the QC noise detector (qc_vv.py) on Mike Ma ep1 / UI ep1 / das Man v2 - see templates\technical_v1.7.md.
- noise_cache.py / noise_cache_rev.py / noise_cache_takes.py: cache whisper word times of the final chunks and non-final takes (words*\ is git-ignored: contains script text).
- noise_diag.py: replicates the event detection (asserts same count as qc_vv.metrics) -> diag.json, events.json (per-event level/spectrum/distance to words).
- noise_eval.py: old vs new (v2.2) flags per final chunk -> before_after.json. take_eval.py: same for all takes -> take_eval.json.
- p3.py / p4.py: map chunk times to episode times and cut the listening clips (clips are not committed).