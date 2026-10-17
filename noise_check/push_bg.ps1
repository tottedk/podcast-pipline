$env:GIT_TERMINAL_PROMPT='0'; Set-Location C:\grok\podcast
$p = Start-Process -FilePath 'C:\Users\TJ\tools\git\cmd\git.exe' -ArgumentList '-c','safe.directory=*','push' -NoNewWindow -PassThru -RedirectStandardOutput noise_check\push.out -RedirectStandardError noise_check\push.err
if (-not $p.WaitForExit(120000)) { $p.Kill(); 'TIMEOUT' | Set-Content noise_check\push.status } else { "exit $($p.ExitCode)" | Set-Content noise_check\push.status }
