<#  tools\make_ref_v2.ps1 (template v1.12, 2026-10-21) - build a VERSIONED Drama 3 clone reference (default Elliot_v2) from one generated, QC-passed
Drama 3 chunk of an earlier render: continuous conversational speech, exact punctuated transcript (the script text of that chunk), then cleaned.
Why (fl1b\analysis\TEMPO_PAUSES.md): drama3_refs\Elliot.wav = 4 unrelated read VCTK p227 sentences, no punctuation, ~102 wpm, noise floor only
~37-41 dB below speech -> Drama 3 cloned a slow (raw 150 wpm), pause-heavy, flat (F0 std 2.9 st) Elliot. The only source recordings of this voice
are VCTK read sentences, so the reference is taken from Drama 3's own Elliot output (same voice identity, passed the ECAPA voice gate):
default fl1b\seg01.raw.wav.chunks\c006.wav = 19.8 s, 57 words, raw 173 wpm, F0 std 4.1 st (range 16.8 st), longest pause 0.65 s, no tags
(best of the 50 Elliot chunks for wpm + pitch variation + few pauses at ~20 s).
Chain: highpass 70 Hz -> afftdn (nr 12, nf -42) -> lead/tail silence trimmed -> 24 kHz mono 16-bit. Writes <Name>.wav, <Name>.txt (UTF-8, no BOM),
<Name>.json (provenance + metrics). Never overwrites an existing <Name> (use -Force) and never touches the original <Voice>.wav.
Licence/credit: derived from the Elliot voice (CSTR VCTK speaker p227, CC BY 4.0) - same credit as Elliot in voices.json. Never a clone of Thomas.
Usage: powershell -File tools\make_ref_v2.ps1 [-Name Elliot_v2] [-Chunks fl1b\seg01.raw.wav.chunks] [-Index 6] [-Force]  #>
param([string]$Root = "C:\grok\podcast", [string]$Voice = "Elliot", [string]$Name = "Elliot_v2", [string]$Chunks = "fl1b\seg01.raw.wav.chunks", [int]$Index = 6, [switch]$Force)
$ErrorActionPreference = 'Stop'; cd $Root
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
if ($Name -match '^(thomas|alice|mary|maya|declan)' -or $Voice -match '^(thomas|alice|mary|maya|declan)$') { throw "blocked voice" }
if ($Name -eq $Voice) { throw "refusing: -Name must differ from the original reference $Voice" }
$D = "$Root\drama3_refs"; $wav = "$D\$Name.wav"
if ((Test-Path $wav) -and -not $Force) { "REFV2 $Name exists - kept (use -Force to rebuild)"; exit 0 }
$src = Join-Path $Root ("$Chunks\c{0:000}.wav" -f $Index); if (-not (Test-Path $src)) { throw "missing $src" }
& ffmpeg -v error -y -i $src -af "highpass=f=70,afftdn=nr=12:nf=-42:tn=1,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.05,areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.12,areverse" -ar 24000 -ac 1 -c:a pcm_s16le $wav
if ($LASTEXITCODE -or -not (Test-Path $wav)) { throw "ffmpeg failed" }
$py = @'
import json, sys, numpy as np, soundfile as sf
src, wav, cj, idx, name, voice = sys.argv[1:7]; idx = int(idx)
c = [x for x in json.load(open(cj, encoding="utf-8"))["chunks"] if x["i"] == idx][0]
if set(c["speakers"]) != {"Guest"} and len(set(c["speakers"])) != 1: sys.exit("chunk is not a single-speaker chunk")
txt = c["text"].strip(); open(wav[:-4] + ".txt", "w", encoding="utf-8").write(txt)
def m(p):
    y, sr = sf.read(p, dtype="float32"); y = y.mean(1) if y.ndim > 1 else y; h = int(sr * 0.01); n = len(y) // h
    e = 20 * np.log10(np.sqrt((y[:n * h].reshape(n, h) ** 2).mean(1)) + 1e-9); sp = float(np.median(e[e > -45]))
    return {"dur_s": round(len(y) / sr, 2), "speech_db": round(sp, 1), "floor_rel_db": round(float(np.percentile(e, 5)) - sp, 1)}
ms, mo = m(src), m(wav); w = len(txt.split())
meta = {"name": name, "voice": voice, "source": src, "chunk": idx, "seed": c.get("seed"), "words": w, "wpm": round(w / mo["dur_s"] * 60, 1), "src_metrics": ms, "ref_metrics": mo,
        "chain": "highpass=70, afftdn nr=12 nf=-42 tn=1, lead/tail silenceremove -55 dB, 24 kHz mono s16", "transcript": txt,
        "credit": "derived from the Elliot voice (CSTR VCTK p227, CC BY 4.0) via Fish Audio Drama 3 output", "made": "tools\\make_ref_v2.ps1 (template v1.12)"}
json.dump(meta, open(wav[:-4] + ".json", "w", encoding="utf-8"), indent=1)
print(f"REFV2 {name}: {mo['dur_s']} s, {w} words, {meta['wpm']} wpm, floor {ms['floor_rel_db']} -> {mo['floor_rel_db']} dB rel. speech; text: {txt[:70]}...")
'@
$tmp = "$env:TEMP\make_ref_v2.py"; [IO.File]::WriteAllText($tmp, $py)
& "$Root\venv_vv\Scripts\python.exe" $tmp $src $wav (Join-Path $Root "$Chunks\chunks.json") $Index $Name $Voice
Remove-Item $tmp -EA 0
