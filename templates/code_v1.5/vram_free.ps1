<#  vram_free.ps1 (v1.5, 2026-10-15) - free GPU VRAM for the nightly podcast render (LLM / TTS / FLUX) by closing configured GPU-hungry desktop apps GRACEFULLY.
Modes (default = -Report, which changes nothing):
  -Report            per-process dedicated GPU memory (adapter = the RX 7900 XT), config status of each process, idle/foreground/audio/fullscreen state
  -Free              close the apps in vram_free.json "apps" (WM_CLOSE to all their windows, or the app's own shutdown command), wait, log VRAM before/after.
                     Only runs when the gate allows it (see below). Add -WhatIf (alias -DryRun) to list what WOULD be closed, closing nothing.
                     -Force: after the wait, kill ONLY the processes of apps that were selected and did not exit (default: never kill)
  -Restore           relaunch the apps the last -Free closed (hwlogs\vram_free_closed.json); -WhatIf lists them
  -Check             is a render / LLM job running or about to run? (exit code 3 = yes, 0 = no) and would -Free be allowed right now?
Gate for -Free (all of it is bypassed ONLY by -WhatIf, which closes nothing):
  night run:      user idle >= idle_minutes (20) AND local time inside night_window (00:30-07:00)
  -Scheduled (or env PODCAST_SCHEDULED=1, set by the render wrappers for scheduled runs): scheduled_enabled AND user idle >= scheduled_min_idle_minutes (10)
  -IgnoreIdle:    skips the idle/time-window condition (explicit manual override) - the safety guards below still apply
Guards that ALWAYS apply (even with -IgnoreIdle/-Force): fullscreen app/game in the foreground or Windows "busy/presentation/D3D fullscreen" state -> close nothing; a game running from a game path -> close nothing;
  per app: skipped if it owns the foreground window, or has an ACTIVE audio session (any process of the app, incl. browser child processes), or is in the protected list.
Never touched: the protected list in vram_free.json (Grok Bot app + agent connection tools, explorer/dwm/csrss, hwmon/HWiNFO, ollama, python/audio.cpp, Battle.net, drivers/services, ...).
Log: hwlogs\vram_free_<date>.log (before/after dedicated VRAM, what was closed, what was skipped and why). Needs Windows PowerShell 5.1, no admin.  #>
param([switch]$Report, [switch]$Free, [switch]$Restore, [switch]$Check, [switch]$Force, [Alias('DryRun')][switch]$WhatIf, [switch]$IgnoreIdle, [switch]$Scheduled, [string]$Config = "", [int]$IdleMinutes = -1)
$ErrorActionPreference = 'Continue'
$here = Split-Path $MyInvocation.MyCommand.Path
if (-not $Config) { $Config = Join-Path $here 'vram_free.json' }
if ($env:PODCAST_SCHEDULED -eq '1') { $Scheduled = $true }
if (-not ($Report -or $Free -or $Restore -or $Check)) { $Report = $true }
$cfg = Get-Content $Config -Raw | ConvertFrom-Json
$logDir = if ($cfg.log_dir) { $cfg.log_dir } else { Join-Path $here 'hwlogs' }; if (-not (Test-Path $logDir)) { New-Item -ItemType Directory $logDir -Force | Out-Null }
$logFile = Join-Path $logDir ("vram_free_{0}.log" -f (Get-Date -f 'yyyy-MM-dd')); $stateFile = Join-Path $logDir 'vram_free_closed.json'
function Log($m) { $l = "{0} {1}" -f (Get-Date -f 'HH:mm:ss'), $m; Write-Host $l; Add-Content -Path $logFile -Value $l }

if (-not ('VF.Native' -as [type])) { Add-Type -TypeDefinition @'
using System; using System.Collections.Generic; using System.Runtime.InteropServices; using System.Text;
namespace VF {
  [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] class MMDevEnumCls {}
  [ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IMMDeviceEnumerator { [PreserveSig] int EnumAudioEndpoints(int flow, int mask, out IMMDeviceCollection c); [PreserveSig] int GetDefaultAudioEndpoint(int flow, int role, out IMMDevice d); }
  [ComImport, Guid("0BD7A1BE-7A1A-44DB-8397-CC5392387B5E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IMMDeviceCollection { [PreserveSig] int GetCount(out uint n); [PreserveSig] int Item(uint i, out IMMDevice d); }
  [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IMMDevice { [PreserveSig] int Activate(ref Guid iid, int ctx, IntPtr p, [MarshalAs(UnmanagedType.IUnknown)] out object o); }
  [ComImport, Guid("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IAudioSessionManager2 { [PreserveSig] int N1(); [PreserveSig] int N2(); [PreserveSig] int GetSessionEnumerator(out IAudioSessionEnumerator e); }
  [ComImport, Guid("E2F5BB11-0570-40CA-ACDD-3AA01277DEE8"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IAudioSessionEnumerator { [PreserveSig] int GetCount(out int n); [PreserveSig] int GetSession(int i, out IAudioSessionControl2 s); }
  [ComImport, Guid("BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
  interface IAudioSessionControl2 { [PreserveSig] int GetState(out int st); [PreserveSig] int B1(); [PreserveSig] int B2(); [PreserveSig] int B3(); [PreserveSig] int B4(); [PreserveSig] int B5(); [PreserveSig] int B6(); [PreserveSig] int B7(); [PreserveSig] int B8(); [PreserveSig] int B9(); [PreserveSig] int B10(); [PreserveSig] int GetProcessId(out uint pid); }
  public static class Native {
    [StructLayout(LayoutKind.Sequential)] struct LII { public uint cb; public uint t; }
    [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }
    [StructLayout(LayoutKind.Sequential)] struct MONINFO { public int cb; public RECT mon; public RECT work; public uint flags; }
    delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LII l);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h, uint cmd);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] static extern IntPtr MonitorFromWindow(IntPtr h, uint f);
    [DllImport("user32.dll")] static extern bool GetMonitorInfo(IntPtr m, ref MONINFO i);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder sb, int n);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder sb, int n);
    [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h, int i);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    [DllImport("shell32.dll")] static extern int SHQueryUserNotificationState(out int s);
    public static double IdleSeconds() { LII l = new LII(); l.cb = 8; if (!GetLastInputInfo(ref l)) return -1; return (double)unchecked((uint)Environment.TickCount - l.t) / 1000.0; }
    public static uint ForegroundPid() { uint p = 0; IntPtr h = GetForegroundWindow(); if (h == IntPtr.Zero) return 0; GetWindowThreadProcessId(h, out p); return p; }
    public static string Title(IntPtr h) { StringBuilder sb = new StringBuilder(256); GetWindowText(h, sb, 256); return sb.ToString(); }
    public static string ForegroundTitle() { IntPtr h = GetForegroundWindow(); return h == IntPtr.Zero ? "" : Title(h); }
    public static bool ForegroundFullscreen() {
      IntPtr h = GetForegroundWindow(); if (h == IntPtr.Zero) return false;
      StringBuilder sb = new StringBuilder(256); GetClassName(h, sb, 256); string c = sb.ToString(); if (c == "Progman" || c == "WorkerW" || c == "Shell_TrayWnd") return false;
      RECT r; GetWindowRect(h, out r); MONINFO mi = new MONINFO(); mi.cb = Marshal.SizeOf(typeof(MONINFO)); IntPtr m = MonitorFromWindow(h, 2); if (!GetMonitorInfo(m, ref mi)) return false;
      bool covers = r.L <= mi.mon.L && r.T <= mi.mon.T && r.R >= mi.mon.R && r.B >= mi.mon.B; int style = GetWindowLong(h, -16); bool caption = (style & 0xC00000) == 0xC00000; return covers && !caption;
    }
    public static int NotificationState() { int s; if (SHQueryUserNotificationState(out s) != 0) return -1; return s; }
    public static IntPtr[] WindowsOf(uint pid) { List<IntPtr> res = new List<IntPtr>(); EnumWindows(delegate(IntPtr h, IntPtr l) { uint p; GetWindowThreadProcessId(h, out p); if (p == pid && IsWindowVisible(h) && GetWindow(h, 4) == IntPtr.Zero) res.Add(h); return true; }, IntPtr.Zero); return res.ToArray(); }
    public static bool CloseWindow(IntPtr h) { return PostMessage(h, 0x0010, IntPtr.Zero, IntPtr.Zero); }
    public static uint[] ActiveAudioPids() {
      List<uint> res = new List<uint>();
      try {
        IMMDeviceEnumerator en = (IMMDeviceEnumerator)new MMDevEnumCls(); IMMDeviceCollection col; if (en.EnumAudioEndpoints(0, 1, out col) != 0) return null; uint n; col.GetCount(out n);
        for (uint i = 0; i < n; i++) {
          IMMDevice d; if (col.Item(i, out d) != 0) continue; Guid iid = new Guid("77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F"); object o; if (d.Activate(ref iid, 23, IntPtr.Zero, out o) != 0) continue;
          IAudioSessionManager2 mgr = (IAudioSessionManager2)o; IAudioSessionEnumerator se; if (mgr.GetSessionEnumerator(out se) != 0) continue; int c; se.GetCount(out c);
          for (int j = 0; j < c; j++) { IAudioSessionControl2 s; if (se.GetSession(j, out s) != 0) continue; int st; s.GetState(out st); if (st == 1) { uint pid; s.GetProcessId(out pid); res.Add(pid); } }
        }
        return res.ToArray();
      } catch (Exception) { return null; }
    }
  }
}
'@ }

# ---------- helpers ----------
function Get-ProcTable { $t = @{}; Get-CimInstance Win32_Process | ForEach-Object { $t[[int]$_.ProcessId] = $_ }; $t }
function Norm($n) { ([string]$n -replace '\.exe$', '').ToLower() }
$protSet = @{}; foreach ($p in $cfg.protected) { $protSet[(Norm $p)] = $true }
function Chain-Names($procId, $tbl) { $r = @(); $cur = [int]$procId; for ($i = 0; $i -lt 8 -and $cur -and $tbl.ContainsKey($cur); $i++) { $r += (Norm $tbl[$cur].Name); $cur = [int]$tbl[$cur].ParentProcessId }; $r }
function Get-Idle { $s = [VF.Native]::IdleSeconds(); if ($s -lt 0) { return $null }; [math]::Round($s / 60, 1) }
function In-Window { $now = Get-Date; $s = [datetime]::ParseExact($cfg.night_window.start, 'HH:mm', $null); $e = [datetime]::ParseExact($cfg.night_window.end, 'HH:mm', $null)
  $n = $now.TimeOfDay; if ($s.TimeOfDay -le $e.TimeOfDay) { ($n -ge $s.TimeOfDay -and $n -lt $e.TimeOfDay) } else { ($n -ge $s.TimeOfDay -or $n -lt $e.TimeOfDay) } }
function Get-Vram {
  $c = Get-Counter '\GPU Adapter Memory(*)\Dedicated Usage', '\GPU Adapter Memory(*)\Shared Usage' -EA SilentlyContinue; $a = @{}
  foreach ($s in $c.CounterSamples) { if ($s.InstanceName -match 'luid_(0x\w+_0x\w+)_phys') { $k = $matches[1]; if (-not $a[$k]) { $a[$k] = @{ Ded = 0; Sh = 0 } }; if ($s.Path -match 'dedicated usage') { $a[$k].Ded = $s.CookedValue } else { $a[$k].Sh = $s.CookedValue } } }
  $best = $a.Keys | Sort-Object { $a[$_].Ded } -Descending | Select-Object -First 1
  if (-not $best) { return $null }; [pscustomobject]@{ Luid = $best; DedGB = [math]::Round($a[$best].Ded / 1GB, 2); SharedGB = [math]::Round($a[$best].Sh / 1GB, 2) }
}
function Get-PerProc($luid, $tbl) {
  $c = Get-Counter '\GPU Process Memory(*)\Dedicated Usage' -EA SilentlyContinue
  $rows = foreach ($s in $c.CounterSamples) { if ($s.InstanceName -match "^pid_(\d+)_luid_$luid") { $p = [int]$matches[1]; [pscustomobject]@{ Pid = $p; Name = $(if ($tbl.ContainsKey($p)) { $tbl[$p].Name -replace '\.exe$', '' } else { "pid$p(gone)" }); GB = $s.CookedValue / 1GB } } }
  $rows | Group-Object Name | ForEach-Object { [pscustomobject]@{ Name = $_.Name; Procs = $_.Count; DedGB = [math]::Round(($_.Group | Measure-Object GB -Sum).Sum, 2) } } | Sort-Object DedGB -Descending
}
function App-Of($name) { $n = Norm $name; foreach ($a in $cfg.apps) { foreach ($p in $a.processes) { if ((Norm $p) -eq $n) { return $a } } }; $null }
function Get-State($tbl) {
  $st = [ordered]@{}
  $st.idleMin = Get-Idle; $st.nowWindow = In-Window
  $fp = [VF.Native]::ForegroundPid(); $st.fgPid = $fp; $st.fgChain = $(if ($fp) { Chain-Names $fp $tbl } else { @() }); $st.fgTitle = [VF.Native]::ForegroundTitle()
  $st.fgFullscreen = [VF.Native]::ForegroundFullscreen(); $st.notifState = [VF.Native]::NotificationState()   # 2=busy (fullscreen/presentation), 3=D3D fullscreen, 4=presentation, 5=normal
  $ap = [VF.Native]::ActiveAudioPids(); $st.audioKnown = ($null -ne $ap); $st.audioPids = $(if ($ap) { @($ap) } else { @() })
  $g = @(); foreach ($pr in $tbl.Values) { if ($pr.ExecutablePath) { foreach ($pat in $cfg.game_path_patterns) { if ($pat -and ($pr.ExecutablePath -like $pat)) { $g += $pr.Name; break } } } }; $st.games = @($g | Select-Object -Unique)
  $st
}

# ---------- -Report ----------
function Do-Report {
  $tbl = Get-ProcTable; $v = Get-Vram; $st = Get-State $tbl
  Log ("REPORT adapter luid={0}: dedicated {1} GB, shared {2} GB" -f $v.Luid, $v.DedGB, $v.SharedGB)
  $rows = Get-PerProc $v.Luid $tbl | ForEach-Object { $s = if ($protSet[(Norm $_.Name)]) { 'PROTECTED (never touched)' } elseif ($a = App-Of $_.Name) { if ($a.enabled) { "closable: $($a.name) [$($a.close)]" } else { "listed but disabled: $($a.name)" } } else { 'not listed (never touched)' }
    if ($_.DedGB -gt $v.DedGB + 0.5) { $s += '  (counter unreliable, > adapter total)' }; $_ | Add-Member Status $s -PassThru }
  Log ("per-process dedicated GB (top 20):`r`n" + (($rows | Select-Object -First 20 | Format-Table Name, Procs, DedGB, Status -Auto | Out-String -Width 200).TrimEnd()))
  Log ("state: idle={0} min, in night window={1}, scheduled={2}, foreground='{3}' [{4}] fullscreen={5}, notification state={6}, audio sessions active pids={7} (known={8}), games running={9}" -f $st.idleMin, $st.nowWindow, [bool]$Scheduled, $st.fgTitle, ($st.fgChain -join '<'), $st.fgFullscreen, $st.notifState, ($st.audioPids -join ','), $st.audioKnown, ($st.games -join ','))
}

# ---------- gate ----------
function Get-Gate($st) {
  $blk = @(); $minIdle = if ($IdleMinutes -ge 0) { $IdleMinutes } elseif ($Scheduled) { [double]$cfg.scheduled_min_idle_minutes } else { [double]$cfg.idle_minutes }
  if ($st.idleMin -eq $null) { $blk += 'idle time unknown' }
  $idleOk = ($st.idleMin -ne $null -and $st.idleMin -ge $minIdle)
  if ($IgnoreIdle) { } elseif ($Scheduled) { if (-not $cfg.scheduled_enabled) { $blk += 'scheduled_enabled=false in config' } elseif (-not $idleOk) { $blk += ("user active (idle {0} min < {1} required for scheduled runs)" -f $st.idleMin, $minIdle) } }
  else { if (-not $st.nowWindow) { $blk += ("outside night window {0}-{1} (use -Scheduled from the render wrapper, or -IgnoreIdle)" -f $cfg.night_window.start, $cfg.night_window.end) }; if (-not $idleOk) { $blk += ("user active (idle {0} min < {1} required)" -f $st.idleMin, $minIdle) } }
  if ($st.fgFullscreen) { $blk += 'fullscreen window in the foreground' }
  if ($st.notifState -in 2, 3, 4) { $blk += ("Windows reports fullscreen/busy/presentation state ({0})" -f $st.notifState) }
  if ($st.games.Count) { $blk += ("game running: " + ($st.games -join ',')) }
  if (-not $st.audioKnown) { $blk += 'audio session state unavailable (fail-safe)' }
  , $blk
}

# ---------- -Free ----------
function Do-Free {
  $tbl = Get-ProcTable; $st = Get-State $tbl; $v0 = Get-Vram
  $mode = if ($WhatIf) { 'DRY-RUN (-WhatIf)' } else { 'LIVE' }
  Log ("FREE {0}{1}{2}: dedicated before = {3} GB (shared {4}); idle={5} min, window={6}, foreground='{7}'" -f $mode, $(if ($Scheduled) { ' scheduled' }), $(if ($Force) { ' +Force' }), $v0.DedGB, $v0.SharedGB, $st.idleMin, $st.nowWindow, $st.fgTitle)
  $blk = Get-Gate $st
  if ($blk.Count) { if ($WhatIf) { Log ("  gate would currently BLOCK a live run: " + ($blk -join '; ') + "  (listing candidates anyway)") } else { Log ("  BLOCKED, closed nothing: " + ($blk -join '; ')); return } } else { Log '  gate: open' }
  $plan = @()
  foreach ($a in $cfg.apps) {
    if (-not $a.enabled) { continue }
    $names = @($a.processes | ForEach-Object { Norm $_ }); $mine = @($tbl.Values | Where-Object { $names -contains (Norm $_.Name) -and $_.ProcessId -ne $PID })
    if (-not $mine.Count) { continue }
    $why = $null
    if ($names | Where-Object { $protSet[$_] }) { $why = 'protected' }
    elseif ($st.fgChain | Where-Object { $names -contains $_ }) { if (-not ([double]$cfg.foreground_guard_unless_idle_minutes -gt 0 -and $st.idleMin -ge [double]$cfg.foreground_guard_unless_idle_minutes)) { $why = "in the foreground ('$($st.fgTitle)')" } }
    if (-not $why) { foreach ($ap in $st.audioPids) { if ((Chain-Names $ap $tbl) | Where-Object { $names -contains $_ }) { $why = "active audio session (pid $ap)"; break } } }
    if (-not $why -and $a.close -eq 'force_only' -and -not $Force) { $why = 'no window to close gracefully; needs -Force' }
    if ($why) { Log ("  SKIP {0}: {1}" -f $a.name, $why); continue }
    $wins = @(); foreach ($pr in $mine) { $wins += [VF.Native]::WindowsOf([uint32]$pr.ProcessId) }
    if ($a.close -eq 'window' -and $wins.Count -eq 0 -and -not $Force) { Log ("  SKIP {0}: no visible window (background/tray process, cannot be closed gracefully; needs -Force)" -f $a.name); continue }
    $plan += [pscustomobject]@{ App = $a; Procs = $mine; Wins = $wins }
  }
  if (-not $plan.Count) { Log '  nothing to close'; return }
  $closedState = @()
  foreach ($p in $plan) {
    $a = $p.App; $first = Norm $a.processes[0]; $main = @($p.Procs | Where-Object { $_.ExecutablePath -and (Norm $_.Name) -eq $first })[0]; if (-not $main) { $main = @($p.Procs | Where-Object { $_.ExecutablePath })[0] }
    $wins = $p.Wins
    $desc = "{0}: {1} process(es), {2} window(s), ~exe {3}" -f $a.name, $p.Procs.Count, $wins.Count, $main.ExecutablePath
    if ($WhatIf) { Log ("  WOULD CLOSE " + $desc + " via " + $a.close); continue }
    Log ("  CLOSE " + $desc + " via " + $a.close)
    $closedState += [pscustomobject]@{ ts = (Get-Date -f 's'); name = $a.name; exe = $main.ExecutablePath; args = [string]$a.restart_args }
    if ($a.close -eq 'command' -and $main.ExecutablePath) { Start-Process -FilePath $main.ExecutablePath -ArgumentList $a.command_args -WindowStyle Hidden }
    elseif ($a.close -eq 'window') { foreach ($w in $wins) { [void][VF.Native]::CloseWindow($w) } }
    elseif ($a.close -eq 'force_only') { }
  }
  if ($WhatIf) { Log ("  DRY-RUN: nothing closed, no state written."); return }
  $deadline = (Get-Date).AddSeconds([int]$cfg.wait_seconds)
  do { Start-Sleep 2; $left = @($plan | ForEach-Object { $nm = @($_.App.processes | ForEach-Object { Norm $_ }); Get-Process -EA 0 | Where-Object { $nm -contains (Norm $_.ProcessName) } }) } while ($left.Count -and (Get-Date) -lt $deadline)
  foreach ($p in $plan) { $nm = @($p.App.processes | ForEach-Object { Norm $_ }); $r = @(Get-Process -EA 0 | Where-Object { $nm -contains (Norm $_.ProcessName) })
    if ($r.Count) { if ($Force -or $p.App.close -eq 'force_only') { if ($Force) { Log ("  FORCE-KILL {0}: {1} process(es) still running after {2}s" -f $p.App.name, $r.Count, $cfg.wait_seconds); $r | Stop-Process -Force -EA 0 } } else { Log ("  {0}: still running after {1}s (did not close gracefully; left alone, no -Force)" -f $p.App.name, $cfg.wait_seconds) } }
    else { Log ("  {0}: closed" -f $p.App.name) } }
  if ($closedState.Count) { ConvertTo-Json -InputObject @($closedState) | Set-Content $stateFile -Encoding UTF8 }
  Start-Sleep ([int]$cfg.settle_seconds); $v1 = Get-Vram
  Log ("FREE done: dedicated {0} GB -> {1} GB (freed {2} GB)" -f $v0.DedGB, $v1.DedGB, [math]::Round($v0.DedGB - $v1.DedGB, 2))
}

# ---------- -Restore ----------
function Do-Restore {
  if (-not (Test-Path $stateFile)) { Log 'RESTORE: no closed-apps state file (nothing was closed by the last -Free)'; return }
  $items = @(Get-Content $stateFile -Raw | ConvertFrom-Json)
  Log ("RESTORE{0}: {1} app(s) from {2}" -f $(if ($WhatIf) { ' (dry-run)' }), $items.Count, $stateFile)
  foreach ($i in $items) {
    $exeName = Norm ([IO.Path]::GetFileNameWithoutExtension($i.exe))
    if (Get-Process -EA 0 | Where-Object { (Norm $_.ProcessName) -eq $exeName }) { Log ("  {0}: already running, skipped" -f $i.name); continue }
    if (-not (Test-Path $i.exe)) { Log ("  {0}: exe not found {1}" -f $i.name, $i.exe); continue }
    if ($WhatIf) { Log ("  WOULD START {0}: {1} {2}" -f $i.name, $i.exe, $i.args); continue }
    if ($i.args) { Start-Process -FilePath $i.exe -ArgumentList $i.args } else { Start-Process -FilePath $i.exe }; Log ("  started {0}" -f $i.name)
  }
  if (-not $WhatIf) { Move-Item $stateFile ($stateFile -replace '\.json$', ('.restored_{0}.json' -f (Get-Date -f 'yyyyMMdd_HHmmss'))) -Force }
}

# ---------- -Check ----------
function Do-Check {
  $tbl = Get-ProcTable; $why = @()
  try { $m = (Invoke-RestMethod http://localhost:11434/api/ps -TimeoutSec 3).models; if ($m) { $why += ("ollama model loaded: " + ($m.name -join ',')) } } catch { }
  foreach ($p in $tbl.Values) { $cl = [string]$p.CommandLine
    if ($p.Name -match '^audiocpp') { $why += "audio.cpp running (pid $($p.ProcessId))" }
    elseif ($p.Name -match '^(python|pythonw|powershell|pwsh)\.exe$' -and $p.ProcessId -ne $PID -and $cl -match 'run_episode\.ps1|podcast\.ps1|render7b\.ps1|post_episode\.ps1|vv7b_generate|vv_generate|write_script|gen_backgrounds|hwrun\.ps1|llm_shootout') { $why += ("{0} pid {1}: {2}" -f $p.Name, $p.ProcessId, ($cl -replace '\s+', ' ').Substring(0, [Math]::Min(110, $cl.Length))) } }
  $recent = Get-ChildItem 'C:\grok\podcast\*\STATUS.txt' -EA 0 | Where-Object { $_.LastWriteTime -gt (Get-Date).AddMinutes(-15) -and ((Get-Content $_ -Raw) -notmatch 'ALL DONE|ABORT') }
  foreach ($r in $recent) { $why += ("fresh STATUS file (<15 min, not finished): " + $r.FullName) }
  $active = $why.Count -gt 0
  Log ("CHECK: job active/imminent = {0}" -f $active); foreach ($w in $why) { Log ("  - " + $w) }
  $st = Get-State $tbl; $blk = Get-Gate $st
  Log ("CHECK: a live -Free{0} right now would be {1}" -f $(if ($Scheduled) { ' -Scheduled' }), $(if ($blk.Count) { 'BLOCKED: ' + ($blk -join '; ') } else { 'ALLOWED' }))
  if ($active) { exit 3 }
}

if ($Report) { Do-Report }
if ($Check) { Do-Check }
if ($Free) { Do-Free }
if ($Restore) { Do-Restore }
