<#  tools\test_drama3_pipeline.ps1 (template v1.9, 2026-10-19) - ONE short Drama 3 pipeline test: first -Lines lines of chapter -Chapter of agentic_ai_ep1
(Host Carter, Guest Clara, Guest2 Lachlan; one [laughs] tag added to test tag handling) -> render_drama3.ps1 (QC + post) -> align.py -> RESULT.txt.
Output ONLY in C:\grok\podcast\tests\drama3_pipeline\ (never episodes\ or ag\; ag\ is only read). Run detached; poll <T>\DONE.txt.  #>
param([int]$Chapter = 9, [int]$Lines = 10, [string]$Root = "C:\grok\podcast", [string]$T = "C:\grok\podcast\tests\drama3_pipeline", [int]$QcRetries = 1)
$ErrorActionPreference = 'Continue'; (Get-Process -Id $PID).PriorityClass = 'Idle'
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
if ($T -match '\\(episodes|ag)(\\|$)') { throw "refusing to write into $T" }
New-Item -ItemType Directory -Force $T | Out-Null; Remove-Item "$T\DONE.txt", "$T\RESULT.txt" -EA 0
$py_t = "$Root\venv_vv\Scripts\python.exe"; $py_w = "$Root\venv_whisper\Scripts\python.exe"
function L($m) { Add-Content "$T\test.log" "$(Get-Date -f 'HH:mm:ss') $m" }
L "start chapter=$Chapter lines=$Lines"
$mk = @'
import json, sys
root, T, ch, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
S = json.load(open(root + r"\agentic_ai_ep1_script.json", encoding="utf-8-sig"))
C = json.load(open(root + r"\ag\agentic_ai_ep1.chapters.in.json", encoding="utf-8-sig"))["sections"]
st = C[ch]["start"]; seg = [dict(l) for l in S[st:st + n]]
for l in seg:
    if l["text"].startswith("I said it with confidence"): l["text"] = "[laughs] " + l["text"]
json.dump(seg, open(T + r"\seg00.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"host": "Carter", "guest": "Clara", "guest2": "Lachlan", "mode": "override", "seed": None, "reproduce": "override: Clara,Lachlan (drama3 pipeline test)"}, open(T + r"\cast.json", "w"), indent=1)
print("chapter", ch, repr(C[ch]["title"]), "script lines", st, "-", st + n - 1, "words", sum(len(l["text"].split()) for l in seg), "speakers", sorted(set(l["speaker"] for l in seg)))
'@
Set-Content "$T\_mk.py" $mk -Encoding ascii; $o = & $py_t "$T\_mk.py" $Root $T $Chapter $Lines 2>&1; L "$o"
$t0 = Get-Date; $wo = 0
while ((((Invoke-RestMethod http://localhost:11434/api/ps -EA SilentlyContinue).models).Count -gt 0) -and $wo -lt 20) { L 'ollama has a model loaded, waiting'; Start-Sleep 15; $wo++ }
& powershell -NoProfile -ExecutionPolicy Bypass -File "$Root\render_drama3.ps1" -Dir $T -Segs 00 -QcRetries $QcRetries -NoResume *> "$T\render.log"
$rt = [int]((Get-Date) - $t0).TotalSeconds; L "render done in $rt s"
$left = Get-Process audiocpp_cli, audiocpp_server -EA 0; $om = ((Invoke-RestMethod http://localhost:11434/api/ps -EA SilentlyContinue).models)
L "after: audiocpp processes=$(@($left).Count) ollama models=$(@($om).Count)"
if (Test-Path "$T\seg00.mp3") { $ta = Get-Date; & $py_w "$Root\align.py" "$T\seg00.mp3" "$T\seg00.json" -o "$T\seg00.timings.json" *> "$T\align.log"; L "align exit $LASTEXITCODE in $([int]((Get-Date)-$ta).TotalSeconds) s" }
$st = @'
import json, sys, os, re, soundfile as sf
T = sys.argv[1]; R = []
seg = json.load(open(T + r"\seg00.json", encoding="utf-8"))
TAG = re.compile(r"\[[A-Za-z][A-Za-z' -]{0,30}\]")
words = sum(len(TAG.sub(" ", l["text"]).split()) for l in seg)
raw = sf.info(T + r"\seg00.raw.wav").duration if os.path.exists(T + r"\seg00.raw.wav") else 0
mp3 = float(sys.argv[2]) if sys.argv[2] else 0
cj = T + r"\seg00.raw.wav.chunks"
M = json.load(open(cj + r"\drama3_metrics.json")) if os.path.exists(cj + r"\drama3_metrics.json") else []
for m in M: R.append(f"run {m['time']} todo {m['todo']}: wall {m['wall_s']}s audio {m['audio_s']}s rtf_wall {m['rtf_wall']} rtf_gen {m['rtf_gen']} vram_peak {m['vram_peak_mb']} MB (base {m['vram_base_mb']}) commit_peak {m['commit_peak_mb']} MB rss_peak {m['rss_peak_mb']} MB sys_free_min {m['sys_free_min_mb']} MB reached_limit {m['reached_limit']}")
q = json.load(open(T + r"\seg00.qc.json")) if os.path.exists(T + r"\seg00.qc.json") else {}
for c in q.get("chunks", []): R.append(f"QC chunk {c['i']} seed {c['seed']} score {c['score']} wer {c['wer']} flags {c['flags']} (soft {c.get('soft_flags')}) rates {[r.get('rate') for r in c['lines']]}")
R.append(f"QC final redo={q.get('redo')} file_wer={q.get('wer')}")
tk = cj + r"\takes\takes.json"
if os.path.exists(tk): R.append("takes: " + "; ".join(f"{k}: " + ",".join(f"p{t['pass']}/s{t['seed']}={t['score']}" for t in v) for k, v in json.load(open(tk)).items()))
R.append(f"words {words} raw {raw:.1f}s -> {words/raw if raw else 0:.2f} w/s raw; mp3 {mp3:.1f}s -> {words/mp3 if mp3 else 0:.2f} w/s ({60*words/mp3 if mp3 else 0:.0f} wpm) final; target 2.6 w/s (155 wpm)")
if mp3: R.append(f"tempo for 2.6 w/s: {1.05*2.6/(words/mp3):.3f} (current 1.05)")
tj = T + r"\seg00.timings.json"
if os.path.exists(tj):
    L = json.load(open(tj))["lines"]; sp = sum(l["end"] - l["start"] for l in L); R.append(f"align: {len(L)} lines, speech-only {sp:.1f}s -> {words/sp:.2f} w/s inside lines; per-line w/s " + ", ".join(f"{l['speaker'][0]}{l['speaker'][-1] if l['speaker'][-1]=='2' else ''}:{len(TAG.sub(' ', l['text']).split())/max(0.1,l['end']-l['start']):.1f}" for l in L))
print("\n".join(R))
'@
Set-Content "$T\_stats.py" $st -Encoding ascii
$md = if (Test-Path "$T\seg00.mp3") { (& ffprobe -v error -show_entries format=duration -of csv=p=0 "$T\seg00.mp3") } else { '' }
$res = & $py_t "$T\_stats.py" $T "$md" 2>&1 | % { "$_" }
$hdr = @("Drama 3 pipeline test $(Get-Date -f 'yyyy-MM-dd HH:mm') render+QC+post $rt s; out: $T\seg00.mp3 (raw $T\seg00.raw.wav)", "$o",
  "render.log: " + ((gc "$T\render.log" -EA 0 | ? { $_ -match '^REF|^chunk \d+/|D3RUN|\[QC\]|SEGDONE|ALLDONE|Error|GENFAIL|Exception|killing|REACHED' }) -join ' | '))
Set-Content "$T\RESULT.txt" ($hdr + $res + "after: audiocpp processes=$(@($left).Count) ollama models=$(@($om).Count)")
Set-Content "$T\DONE.txt" (Get-Date -f 'yyyy-MM-dd HH:mm:ss')
