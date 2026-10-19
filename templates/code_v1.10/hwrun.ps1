<# hwrun.ps1 - run any command with the hardware monitor active.
Usage: .\hwrun.ps1 [-Name label] <command> [args...]
  e.g. .\hwrun.ps1 venv\Scripts\python.exe gen_backgrounds.py ...   |  .\hwrun.ps1 -Name test Start-Sleep 30 #>
param([string]$Name = "", [Parameter(Mandatory, Position = 0, ValueFromRemainingArguments)][string[]]$Cmd)
$hl = 'C:\grok\hwmon\hwmon_lib.ps1'; if (-not (Test-Path $hl)) { $hl = "$PSScriptRoot\hwmon_lib.ps1" }  # v1.3: own LibreHardwareMonitor monitor, falls back to HWiNFO
. $hl
if (-not $Name) { $t = $Cmd | Where-Object { $_ -match '\.(py|ps1)$' } | Select-Object -First 1; if (-not $t) { $t = $Cmd[0] }; $Name = [IO.Path]::GetFileNameWithoutExtension($t) }
$h = Start-HwMonitor $Name
$code = 0
try { $exe = $Cmd[0]; $rest = @($Cmd | Select-Object -Skip 1); & $exe @rest; if ($LASTEXITCODE) { $code = $LASTEXITCODE } elseif (-not $?) { $code = 1 } }
finally { Stop-HwMonitor $h }
exit $code

