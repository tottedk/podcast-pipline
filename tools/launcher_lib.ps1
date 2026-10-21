<#  tools\launcher_lib.ps1 (template v1.12, 2026-10-21) - shared helpers for unattended episode launchers (tools\start_<ep>.ps1). Dot-source it:
      . "$Root\tools\launcher_lib.ps1"
Update-EpisodeIndex: registers a FINISHED episode or updates an existing registry entry via the episodes_index.py CLI (subcommands add / update).
  Fault Lines #1 (v1.11 launcher, start_faultlines_01b.ps1:55) imported episodes_index from an inline `python -c`; the module ran argparse on import
  ("the following arguments are required: cmd") and the re-render was never re-registered. Never import it inline again - always call the CLI.
Get-PostExitText: human-readable STATUS text for post_episode.ps1 exit codes (v1.12: 7 = blocking mix QC failed -> no swap / publish).  #>
function Update-EpisodeIndex([string]$Py, [string]$Root, [string]$Ep, [double]$Dur = 0, [string]$Date = "", [string]$Note = $null, [string]$Cast = "",
                             [string]$Series = "", [string]$Title = "", [switch]$Multi, [switch]$OneOff) {
  $ix = "$Root\episodes_index.py"
  $known = & $Py -c "import json,sys;ix=json.load(open(r'$Root\episodes_index.json',encoding='utf-8-sig'));print(any(e['ep']==sys.argv[1] for e in ix['episodes']))" $Ep 2>&1 | Out-String
  if ($known.Trim() -eq 'True') {
    $a = @('update', '--ep', $Ep); if ($Dur) { $a += '--dur', ("{0:0.####}" -f $Dur).Replace(',', '.') }; if ($Date) { $a += '--date', $Date }; if ($null -ne $Note -and $Note -ne '') { $a += '--note', $Note }; if ($Cast) { $a += '--cast', $Cast }
  } else {
    $a = @('add', '--ep', $Ep); if ($Series) { $a += '--series', $Series }; if ($Title) { $a += '--title', $Title }; if ($Multi) { $a += '--multi' }; if ($OneOff) { $a += '--oneoff' }
    if ($Date) { $a += '--date', $Date }; if ($Dur) { $a += '--dur', ("{0:0.####}" -f $Dur).Replace(',', '.') }; if ($Cast) { $a += '--cast', $Cast }
  }
  $o = & $Py $ix @a 2>&1 | Out-String
  return "$($o.Trim()) (exit $LASTEXITCODE)"
}
function Get-PostExitText([int]$Code) {
  switch ($Code) { 0 { 'post ok' } 2 { 'post ABORT: output exists (never overwrite)' } 3 { 'duration gate failed (38-48 min)' } 4 { 'no cast' } 5 { 'missing segment mp3 / mix failed' }
    7 { 'BLOCKING mix QC failed (speaker wpm outside 145-175 or intra-line pause > 1.5 s) - nothing published, see mixqc.txt' } default { "post failed (exit $Code)" } }
}
