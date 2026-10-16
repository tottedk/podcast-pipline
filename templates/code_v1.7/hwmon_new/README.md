# hwmon - own hardware monitor (replaces HWiNFO-based logging)   [built 2026-10-15]

Engine: **LibreHardwareMonitorLib 0.9.6** (NuGet, MPL-2.0; sha512 verified against NuGet's catalog, the same release zip sha256 verified against GitHub's digest).
Program: `hwmon.exe` (C#, built from `src\hwmon.cs` with the .NET Framework 4 `csc.exe`; no SDK needed). DLLs in `lib\`, `hwmon.exe.config` points the probing path at `lib\`.
Driver: LHM 0.9.6 has **no WinRing0** (replaced by **PawnIO** since 0.9.5; the string WinRing0 is not in the DLL). PawnIO 2.2.0 (namazso, Authenticode-valid, sha256 1F519A22...A3032) is installed as service `PawnIO`
(driver C:\WINDOWS\system32\DriverStore\FileRepository\pawnio.inf_amd64_*\PawnIO.sys, start type Manual). Uninstall: `"C:\Program Files\PawnIO\uninstall.exe" -uninstall -silent` (admin), or Apps > PawnIO.
A restore point "Pre-PawnIO-hwmon 2026-10-15" was created before the install.

## What runs
Scheduled Task **HwMon** (at logon, user TJ, highest privileges, no time limit, restart on failure, BelowNormal priority) -> `hwmon.exe` (hidden, single instance via mutex).
Every 5 s it reads ALL LHM sensors (CPU, Super I/O Nuvoton NCT6799D, GPU 7900 XT + iGPU, RAM + DIMM SPD/PMIC, NVMe, network, PSU/controllers/battery if present). Storage is polled every 30 s.
Measured: 0.044 % of total CPU (about 0.5 % of one core), ~58 MB RAM, ~490 handles.

## Output (C:\grok\podcast\hwlogs\)
| File | Content |
|---|---|
| `hwmon_cont_YYYYMMDD.csv` | continuous log, **same columns as the old hw_monitor CSVs** (Time,GpuTemp_C,GpuHotspot_C,GpuMemJunc_C,GpuPower_W,GpuLoad_pct,GpuVram_MB,GpuFan_RPM,GpuHotLimit_pct,CpuTemp_C,CpuPower_W,CpuLoad_pct,CpuHTC,RamUsed_MB); GpuHotLimit_pct and CpuHTC are blank (no LHM sensor) |
| `hwmon_full_YYYYMMDD.csv` | continuous log of ALL sensors, wide: `Time` + one column per sensor named `<Hardware> / <Sensor> [<Type>]` (257 sensors now, ~10 MB/day) |
| `<run>_<yyyyMMdd_HHmmss>.csv` + `.summary.txt` + `.summary_full.txt` | **session** log (old compat columns) with the old-style summary (max/avg, energy kWh, hotspot>95 count) and a max/min/avg table of every sensor |
Daily rotation at midnight (new file per day; the sensor list is re-read at rollover; a changed sensor set gets `_2`). Every row is flushed to disk (FlushFileBuffers) so a crash/BSOD loses at most the current 5 s sample.
Retention: cont 30 days, full 14 days. `sensors_catalog.csv` (here) lists every sensor, identifier, min/max, status ok / always 0 / UNREADABLE(null). `heartbeat.txt` is touched every 5 s. `hwmon.log` = daemon log.

## Use from pipeline scripts (same API as podcast\hwmon_lib.ps1)
```
. C:\grok\hwmon\hwmon_lib.ps1
$h = Start-HwMonitor "ui2_render"      # writes sessions\ui2_render.session; daemon starts <run>_<ts>.csv within ~1 s
...
Stop-HwMonitor $h                       # daemon writes the summaries, prints the path
```
Session ends by itself if the parent process dies (parent=$PID) or after 72 h. If the daemon is not alive the lib runs `schtasks /run /tn HwMon`; if that fails it falls back to the old HWiNFO `hw_monitor.ps1`.
**Switching podcast.ps1 / run_episode.ps1 over** = change the dot-source line from `C:\grok\podcast\hwmon_lib.ps1` to `C:\grok\hwmon\hwmon_lib.ps1` (not done yet: old monitor untouched until Thomas says so).

## Control
`powershell -File C:\grok\hwmon\hwmon_ctl.ps1 status|start|stop|restart` (works without UAC).  
After a crash/BSOD: `powershell -File C:\grok\hwmon\last_before.ps1 [-At "2026-10-15 14:03"] [-Minutes 10] [-Full]` prints the last samples before the crash / before the current boot.  
Compare with HWiNFO: `compare_hwinfo.ps1` (reads HWiNFO VSB registry vs the full CSV).  
Re-install / repair (needs ONE UAC approval): `Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File C:\grok\hwmon\install_admin.ps1'` (`-SkipPawnIO` for the task only).
Rebuild: `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe /nologo /target:winexe /platform:x64 /optimize+ /out:hwmon.exe /reference:lib\LibreHardwareMonitorLib.dll /lib:lib src\hwmon.cs` (stop the task first).
Options of hwmon.exe: `--interval 5 --tag hwmon --dir --logs --no-network --no-full --report (writes lhm_report.txt) --storage-every 30 --run-seconds N --roll-after N (test)`.

## Known gaps vs HWiNFO (LHM limits, not bugs of hwmon)
- **Vcore (Super I/O) reads about 1.8x too high** (LHM 1.9-2.6 V vs HWiNFO 1.1-1.4 V): board-specific scaling missing in LHM. **CPU Core VID reads 0.16-0.25 V (wrong; HWiNFO 1.29-1.37 V).** Do not trust these two.
- Not exposed by LHM at all: Ryzen SVI3 VRM telemetry (VDDCR_VDD/SOC/MISC voltage, current, VRM temps), per-core temperatures, IOD temps, PPT/TDC/EDC and thermal limits, HTC/PROCHOT flags, GPU VR/GCD/MCD/memory-chip temps, GPU currents and TBP/TGP split, GPU throttle reasons, GPU thermal limit %, chipset (xHCI) temps, DRAM bandwidth.
- NVMe read/write activity stays 0 (LHM polls it only per storage update). Fan #3-#7 headers are empty (always 0). iGPU D3D load sensors are 0 (idle). Network sensors are 0 when idle.
- GPU power: LHM "GPU Package" tracks HWiNFO TBP within ~2 W (not identical).