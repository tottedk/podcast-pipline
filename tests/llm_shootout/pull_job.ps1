$ErrorActionPreference='Continue'; $d=$PSScriptRoot
$models='qwen3.8:27b-q4_K_M','gpt-oss:20b','mistral-small3.2:24b','muse-glimmer:30b-q4_K_M','gemma4:31b-it-qat','qwen3.6:35b-a3b-q4_K_M'
foreach($m in $models){ "START $m $(Get-Date -f HH:mm:ss)" | Add-Content $d\pull_status.txt; $p=Start-Process ollama -ArgumentList 'pull',$m -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$d\pull_cur.log" -RedirectStandardError "$d\pull_cur.err"; "END $m exit $($p.ExitCode) $(Get-Date -f HH:mm:ss)" | Add-Content $d\pull_status.txt }
"ALLDONE" | Add-Content $d\pull_status.txt
