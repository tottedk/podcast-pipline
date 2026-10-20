<#  test_fl1_v111.ps1 (2026-10-20, template v1.11) - short Drama 3 test render of the exact Fault Lines #1 lines Thomas flagged, with the v1.11 pipeline.
  tests\fl1_v111\seg00.json = script lines 0-4  (cold open; line 3 = 0:53 cut word "assassination", Clara lines 0/2 were voiced by Elliot)
  tests\fl1_v111\seg01.json = script lines 13-18 (3:33 pause after "Elliot.", 3:40 Elliot line 14 + 4:20 Clara line 17 were voiced by Carter)
  -Start : prepare + start render_drama3.ps1 detached (log tests\fl1_v111\render.log, STATUS.txt)      -Verify : checks after the render (verify.txt)
Verify = voice gate results (spk_check per chunk), cut-word check (gate_cut_check raw vs mp3), whisper word check (every line's last word, 'assassination'),
longest pause in the mp3, words per minute, and GPU/model state (ollama ps, audiocpp, python GPU jobs).  #>
param([switch]$Start, [switch]$Verify, [string]$Root = "C:\grok\podcast")
$ErrorActionPreference = 'Continue'; cd $Root; $T = "$Root\tests\fl1_v111"
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
if ($Start) {
  if (Test-Path $T) { Remove-Item -Recurse -Force $T }; New-Item -ItemType Directory $T | Out-Null
  & "$Root\venv_vv\Scripts\python.exe" -c "import json;S=json.load(open(r'$Root\episodes\faultlines_01\faultlines_01_script.json',encoding='utf-8-sig'));json.dump(S[0:5],open(r'$T\seg00.json','w',encoding='utf-8'),indent=1,ensure_ascii=False);json.dump(S[13:19],open(r'$T\seg01.json','w',encoding='utf-8'),indent=1,ensure_ascii=False);print('test lines',len(S[0:5]),len(S[13:19]),'words',sum(len(l['text'].split()) for l in S[0:5]+S[13:19]))"
  Copy-Item "$Root\episodes\faultlines_01\cast.json" "$T\cast.json"
  $p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-Command',"& '$Root\render_drama3.ps1' -Dir '$T' *> '$T\render.log'" -WindowStyle Hidden -PassThru
  "STARTED test render pid $($p.Id) at $(Get-Date -f HH:mm:ss)"; exit 0 }
if ($Verify) {
  $o = @(); $o += "== render.log key lines"; $o += (gc "$T\render.log" | sls '^(=== seg|chunk \d+|D3RUN|\[QC\]|\[VOICE\]|\[gate\]|SEGDONE|GENFAIL|SPKFAIL|STOPPED|ALLDONE|POST|WARNING|Error|Traceback|.*regenerate)' | % { $_.Line })
  foreach ($s in '00', '01') {
    $o += "== seg$s voice gate (independent re-run)"
    $o += (cmd /c "`"$Root\venv_spk\Scripts\python.exe`" `"$Root\spk_check.py`" --chunks `"$T\seg$s.raw.wav.chunks`" --cast Host=Carter,Guest=Elliot,Guest2=Clara --root `"$Root`" --json `"$T\seg$s.spk_verify.json`" 2>&1" | % { "$_" } | ? { $_ -match '^SPK' })
    $o += "== seg$s cut-word check raw vs mp3 (tempo 0.90)"
    $o += (cmd /c "`"$Root\venv_whisper\Scripts\python.exe`" `"$Root\gate_cut_check.py`" `"$T\seg$s.raw.wav`" `"$T\seg$s.mp3`" --tempo 0.90 2>&1" | % { "$_" })
  }
  $o += "== whisper word check + pauses + wpm"
  $o += (cmd /c "`"$Root\venv_whisper\Scripts\python.exe`" `"$Root\tools\verify_words.py`" `"$T`" 2>&1" | % { "$_" } | ? { $_ -notmatch 'Warning|warn\(' })
  $o += "== GPU / models"; $o += "ollama ps: " + ((& ollama ps 2>&1 | Out-String).Trim() -replace '\s+', ' ')
  $o += "audiocpp processes: $(@(Get-Process audiocpp_cli, audiocpp_server -EA 0).Count)"
  $o += "python GPU/TTS jobs: $(@(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.CommandLine -match 'drama3_|qc_vv|spk_check|gen_backgrounds|align\.py|make_video' }).Count)"
  $o | Set-Content "$T\verify.txt"; $o; exit 0 }
