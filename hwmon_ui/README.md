# HwMon UI widget (v1.0, 2026-10-16)

Small always-on-top, dark, non-focus-stealing status widget for LLM use, gaming and hardware health.
It only READS the existing hwmon log (`C:\grok\podcast\hwlogs\hwmon_cont_YYYYMMDD.csv`, 14 columns, written every 5 s by hwmon.exe / scheduled task HwMon). hwmon itself is unchanged (no JSON file needed), so logging and the task are unaffected.

## Start / stop
- Desktop shortcut **HwMon UI toggle** (or `hwmon_ui_toggle.bat`, or `powershell -File hwmon_ui_toggle.ps1 [toggle|start|stop|status]`): starts it if not running, closes it (gracefully, via a named event) if running.
- Tray icon (dot = worst current alert level: green/amber/red, blue is not used there): left-click = show/hide, double-click = compact/expanded, right-click menu = Show/Hide, Compact/Expanded, Start with Windows (on/off, default OFF), Exit.
- Global hotkey **Ctrl+Alt+H** = hide/show (if another program owns it you get a tray balloon; use the tray icon).
- Click the widget = compact bar <-> expanded panel. Drag it to move (position and mode are remembered in `hwmon_ui.settings`).
- Autostart is OFF. Turn on from the tray menu, or: `reg add HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v HwMonUI /t REG_SZ /d "C:\grok\hwmon\ui\hwmon_ui.exe" /f` (off: `reg delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v HwMonUI /f`).

## What it shows
GPU edge / hotspot / memory-junction temp, GPU load, **D3D Dedicated VRAM used / 20 GB** (column GpuVram_MB = D3D dedicated, not the bogus "GPU Memory Usage") and free-for-LLM, GPU power and fan RPM, CPU temp / load / power, RAM used / total, estimated CPU+GPU power (no wall-power sensor exists), job status line, alert lines.
Job status: Ollama loaded models (`/api/ps`, 0.6 s timeout, only if ollama.exe runs), `audiocpp_cli` process, python/powershell command lines matching the podcast pipeline (run_episode, render7b, QC, make_video, post_episode, gen_backgrounds; checked every 15 s via WMI).

## Thresholds (Cfg class in hwmon_ui.cs)
| value | amber | red |
|---|---|---|
| GPU edge | 75 | 85 |
| GPU hotspot | 95 | 100 (alert if >100 for 30 s+; "thermal limit/throttling likely" at 108) |
| GPU memory junction | 90 | 100 |
| VRAM (D3D) used | 17 GB | 19 GB ("VRAM nearly full") |
| CPU temp | 80 | 90 |
| RAM used | 80 % | 92 % |
Also red: GPU fan <50 rpm with hotspot >=85, hwmon data older than 30 s (HwMon task not running).

## Limits
- Overlay only shows over windowed / borderless-windowed games. Exclusive-fullscreen games cover it (and the widget never forces itself on top of them). Hide it with Ctrl+Alt+H if you do not want it in a game.
- LibreHardwareMonitor exposes no GPU throttle-reason sensor, so "throttling" is a heuristic (hotspot >=108 C). No PC total power sensor: shown value is CPU+GPU package power only.
- Needs no admin and no install (.NET Framework 4 that ships with Windows). DPI aware (sharp at 4K/300 %).
- Cost: ~0.2 % of ONE core (0.02 % of the machine), ~45 MB RAM; redraws only when data changes (3 s timer, 8 KB file tail read).

## Build / files
`build.ps1` compiles `hwmon_ui.cs` with `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe` (refuses while running; `-Force` closes it first). `hwmon_ui.exe --snapshot <prefix> [--demo]` writes `<prefix>_compact.png` / `_expanded.png` (demo = synthetic hot/full-VRAM scenario). `capture_window.ps1 -Out x.png` screenshots the live window. `create_shortcut.ps1` recreates the Desktop shortcut.
Source is mirrored (without the exe) in the podcast git repo under `hwmon_ui\`.
