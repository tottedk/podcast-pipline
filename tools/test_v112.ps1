<#  tools\test_v112.ps1 (template v1.12, 2026-10-21) - v1.12 validation render + Elliot reference A/B. Output ONLY in tests\v112_ab\ (+ a copy of the two A/B
mp3s in -Out); never touches episodes\, fl1b\ or C:\grok\drama3 (read-only use of the CLI/model).
  old\seg00 = 4 Elliot lines of Fault Lines #1 (fl1b\faultlines_01.json lines 63, 103, 114, 132) with the OLD reference drama3_refs\Elliot.wav (ref map {} -> tempo map 1.00)
  new\seg00 = the same 4 lines with drama3_refs\Elliot_v2.wav (drama3_ref_map.json -> auto tempo to 160 wpm)
  new\seg01 = FL1 lines 13-18 (Carter / Elliot / Clara mix) = 2nd short v1.12 segment (per-speaker tempo, voice gate, clamp v2)
Both arms use the full v1.12 chain (render_drama3.ps1: generator + QC + voice gate + post_segment -Tempo 1). Then: whisper words (venv_whisper) ->
wpm / longest pause; pyin F0 std (venv_vv); spk_check of new\seg00 against the ORIGINAL refs (voice identity kept?). RESULT.txt + result.json, DONE.txt.  #>
param([string]$Root = "C:\grok\podcast", [string]$Out = "", [switch]$SkipRender, [string]$Arms = "old,new")
if (-not $Out) { $Out = Join-Path $env:TEMP 'v112_ab' }
$ErrorActionPreference = 'Continue'; cd $Root; (Get-Process -Id $PID).PriorityClass = 'Idle'
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
$T = "$Root\tests\v112_ab"; if ($T -match '\\(episodes|fl1b)(\\|$)') { throw "refusing to write into $T" }
$py_t = "$Root\venv_vv\Scripts\python.exe"; $py_w = "$Root\venv_whisper\Scripts\python.exe"; $py_s = "$Root\venv_spk\Scripts\python.exe"
function L($m) { Add-Content "$T\test.log" "$(Get-Date -f 'HH:mm:ss') $m" }
if (-not $SkipRender) {
  $AL = $Arms -split ','; if ($AL.Count -ge 2) { if (Test-Path $T) { Remove-Item -Recurse -Force $T } } else { foreach ($x in $AL) { if (Test-Path "$T\$x") { Remove-Item -Recurse -Force "$T\$x" } } }
  New-Item -ItemType Directory -Force "$T\old", "$T\new", $Out | Out-Null
  $mk = @'
import json, sys
root, T = sys.argv[1], sys.argv[2]
S = json.load(open(root + r"\fl1b\faultlines_01.json", encoding="utf-8-sig"))
ab = [S[i] for i in (63, 103, 114, 132)]; assert all(l["speaker"] == "Guest" for l in ab), [l["speaker"] for l in ab]
for d in ("old", "new"): json.dump(ab, open(T + "\\" + d + r"\seg00.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
json.dump(S[13:19], open(T + r"\new\seg01.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
json.dump({"map": {}}, open(T + r"\old\refmap_old.json", "w"))
print("A/B lines 63,103,114,132:", sum(len(l["text"].split()) for l in ab), "words; seg01 lines 13-18:", [l["speaker"] for l in S[13:19]])
'@
  [IO.File]::WriteAllText("$T\_mk.py", $mk); L (& $py_t "$T\_mk.py" $Root $T 2>&1 | Out-String).Trim()
  Copy-Item "$Root\fl1b\cast.json" "$T\old\cast.json"; Copy-Item "$Root\fl1b\cast.json" "$T\new\cast.json"
  foreach ($arm in $AL) {
    $wo = 0; while ((((Invoke-RestMethod http://localhost:11434/api/ps -EA SilentlyContinue).models).Count -gt 0) -and $wo -lt 20) { L 'ollama busy, waiting'; Start-Sleep 15; $wo++ }
    $t0 = Get-Date; $segs = if ($arm -eq 'old') { "'00'" } else { "'00','01'" }; $rm = if ($arm -eq 'old') { " -RefMap '$T\old\refmap_old.json'" } else { "" }
    L "render $arm segs $segs"   # quoted seg ids: a bare 00,01 inside -Command binds as the integers 0,1 (-> seg0.json, GENFAIL)
    & powershell -NoProfile -ExecutionPolicy Bypass -Command "& '$Root\render_drama3.ps1' -Dir '$T\$arm' -Segs $segs -NoResume$rm *> '$T\$arm\render.log'"
    L "render $arm exit $LASTEXITCODE in $([int]((Get-Date)-$t0).TotalSeconds) s; $((gc "$T\$arm\render.log" -EA 0 | sls 'SEGDONE|STOPPED|ALLDONE|GENFAIL|SPKFAIL|^TEMPO' | % { $_.Line }) -join ' | ')"
  }
}
$ms = @'
import json, sys, re, os
from faster_whisper import WhisperModel
import numpy as np, subprocess
T = sys.argv[1]; M = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=6); R = {}
for k in ("old\\seg00", "new\\seg00", "new\\seg01"):
    f = os.path.join(T, k + ".mp3")
    if not os.path.exists(f): continue
    x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout, np.float32)
    segs, _ = M.transcribe(x, language="en", word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    R[k] = [[w.word, round(w.start, 2), round(w.end, 2)] for s in segs for w in s.words]
json.dump(R, open(os.path.join(T, "whisper_ab.json"), "w"), indent=1)
'@
[IO.File]::WriteAllText("$T\_wh.py", $ms); & $py_w "$T\_wh.py" $T 2>&1 | ? { $_ -match 'Error|Traceback' } | % { L "whisper: $_" }
$an = @'
import json, sys, os, re, subprocess, numpy as np, librosa
T = sys.argv[1]; W = json.load(open(os.path.join(T, "whisper_ab.json"))); TAG = re.compile(r"\[[^\]]*\]"); SR = 16000; out = {}; P = []
def env(x, h=160): n = len(x) // h; return 20 * np.log10(np.sqrt((x[:n * h].reshape(n, h).astype(np.float64) ** 2).mean(1)) + 1e-9)
for k, ws in W.items():
    d = os.path.join(T, k.split("\\")[0]); sj = os.path.join(d, k.split("\\")[1] + ".json"); S = json.load(open(sj, encoding="utf-8"))
    cj = json.load(open(os.path.join(d, k.split("\\")[1] + ".raw.wav.chunks", "chunks.json")))
    x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", os.path.join(T, k + ".mp3"), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout, np.float32)
    nw = sum(len(TAG.sub(" ", l["text"]).split()) for l in S); a, b = ws[0][1], ws[-1][2]; nch = len(cj["chunks"])
    e = env(x)[int(a * 100):int(b * 100)]; sp = np.percentile(e, 70); q = e < sp - 30
    d_ = np.diff(np.concatenate([[0], q.astype(np.int8), [0]])); runs = sorted([(int(j - i) / 100, round(a + i / 100, 2)) for i, j in zip(np.where(d_ == 1)[0], np.where(d_ == -1)[0])], reverse=True)
    f, v, _ = librosa.pyin(x[int(a * SR):int(b * SR)], fmin=55, fmax=400, sr=SR, frame_length=1024, hop_length=320); f = f[v & np.isfinite(f)]
    st = 12 * np.log2(f / np.median(f)); st = st[np.abs(st) < 12]
    spk = {}
    for c in cj["chunks"]:
        r = c["speakers"][0]; s_ = spk.setdefault(r, {"words": 0, "dur": 0.0, "pace": 0.0, "tempo": c.get("tempo"), "src": c.get("tempo_src"), "ref": (c.get("refs") or [None])[0], "clamped": 0})
        s_["words"] += c["words"]; s_["dur"] += c["dur_s"]; s_["pace"] += c.get("pace_dur_s", c["dur_s"]); s_["clamped"] += len(c.get("clamp", {}).get("clamped", []))
    for r, s_ in spk.items(): s_["raw_wpm"] = round(s_["words"] / s_["pace"] * 60, 1); s_["final_chunk_wpm"] = round(s_["words"] / s_["dur"] * 60, 1)
    span = b - a - 0.35 * (nch - 1)
    o = {"words": nw, "whisper_words": len(ws), "span_s": round(b - a, 2), "wpm": round(nw / span * 60, 1), "longest_pause_s": runs[0][0] if runs else 0, "longest_at_s": runs[0][1] if runs else None,
         "pauses_gt_0.5": sum(1 for r in runs if r[0] > 0.5), "pauses_gt_1.0": sum(1 for r in runs if r[0] > 1.0), "f0_median_hz": round(float(np.median(f)), 1), "f0_std_st": round(float(np.std(st)), 2),
         "f0_p5_p95_st": round(float(np.percentile(st, 95) - np.percentile(st, 5)), 1), "per_speaker": spk, "chunks": nch}
    out[k] = o; P.append(f"AB {k}: {nw} words, wpm {o['wpm']}, longest pause {o['longest_pause_s']} s, pauses>0.5 {o['pauses_gt_0.5']}, >1.0 {o['pauses_gt_1.0']}, F0 {o['f0_median_hz']} Hz std {o['f0_std_st']} st (P5-95 {o['f0_p5_p95_st']}); " + "; ".join(f"{r} ref {s_['ref']} tempo {s_['tempo']} ({s_['src']}) raw {s_['raw_wpm']} wpm -> chunk {s_['final_chunk_wpm']} wpm, {s_['clamped']} clamps" for r, s_ in spk.items()))
json.dump(out, open(os.path.join(T, "result.json"), "w"), indent=1); print("\n".join(P))
'@
[IO.File]::WriteAllText("$T\_an.py", $an); $res = & $py_t "$T\_an.py" $T 2>&1 | ? { $_ -match '^AB|Error|Traceback|line \d' } | % { "$_" }
$idv = @(); if (Test-Path "$T\new\seg00.raw.wav.chunks\chunks.json") {   # identity: new-ref Elliot chunks vs the ORIGINAL refs (Carter, Elliot.wav, Clara)
  $idv = cmd /c "`"$py_s`" `"$Root\spk_check.py`" --chunks `"$T\new\seg00.raw.wav.chunks`" --cast Host=Carter,Guest=Elliot,Guest2=Clara --ref_map `"$T\old\refmap_old.json`" --root `"$Root`" --json `"$T\new\spk_vs_original.json`" 2>&1" | % { "$_" } | ? { $_ -match '^SPK' } }
$copied = @(); foreach ($p in @(@("$T\old\seg00.mp3", "elliot_AB_old_ref_Elliot.mp3"), @("$T\new\seg00.mp3", "elliot_AB_new_ref_Elliot_v2.mp3"), @("$T\new\seg01.mp3", "v112_seg01_mixed_Carter_Elliot_Clara.mp3"))) { if (Test-Path $p[0]) { Copy-Item $p[0] "$Out\$($p[1])" -Force; $copied += $p[1] } }
$gpu = "ollama: $(((& ollama ps 2>&1 | Out-String).Trim() -split "`n").Count - 1) model(s); audiocpp: $(@(Get-Process audiocpp_cli, audiocpp_server -EA 0).Count)"
$all = @("v112 A/B $(Get-Date -f 'yyyy-MM-dd HH:mm')") + (gc "$T\test.log" -EA 0) + $res + "== new-ref Elliot vs ORIGINAL refs (spk_check)" + $idv + "copied to ${Out}: $($copied -join ', ')" + $gpu
Set-Content "$T\RESULT.txt" $all; Copy-Item "$T\RESULT.txt" "$Out\RESULT.txt" -Force; Set-Content "$T\DONE.txt" (Get-Date -f 'yyyy-MM-dd HH:mm:ss')
