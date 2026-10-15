// hwmon.cs - own hardware monitor on LibreHardwareMonitorLib 0.9.6 (MPL-2.0). C# 5 (csc of .NET Framework 4.x), no SDK needed.
// hwmon.exe [--dir D] [--logs L] [--interval 5] [--tag hwmon] [--run-seconds N] [--no-network] [--no-full] [--report] [--storage-every 30]
using System; using System.Collections.Generic; using System.Diagnostics; using System.Globalization; using System.IO; using System.Linq; using System.Text; using System.Threading;
using System.Security.Principal; using Microsoft.Win32; using LibreHardwareMonitor.Hardware;

namespace HwMon {
class SRef { public ISensor S; public IHardware H; public string Col; public int Nulls; public int Reads; public double Min = double.MaxValue, Max = double.MinValue; public bool Zero = true; }
class Session { public string Name, Csv, Sum, SumFull; public int Parent; public double MaxHours = 72; public DateTime Start; public StreamWriter W; public int N;
  public double[] Sum13 = new double[13]; public double[] Max13 = new double[13]; public int[] Cnt13 = new int[13]; public double eG, eC; public DateTime Last; public int Hot95; public int Htc;
  public double[] FSum, FMin, FMax; public int[] FCnt; public bool[] Seen = new bool[13]; }
static class P {
  static string Dir = @"C:\grok\hwmon", Logs = @"C:\grok\podcast\hwlogs", Tag = "hwmon";
  static int RollAfter = 0; static int Interval = 5, RunSeconds = 0, StorageEvery = 30, KeepCompat = 30, KeepFull = 14;
  static bool Network = true, Full = true, Report = false;
  static Computer C; static List<SRef> All = new List<SRef>(); static string FullHeader = "";
  static readonly string[] Cols = { "GpuTemp_C","GpuHotspot_C","GpuMemJunc_C","GpuPower_W","GpuLoad_pct","GpuVram_MB","GpuFan_RPM","GpuHotLimit_pct","CpuTemp_C","CpuPower_W","CpuLoad_pct","CpuHTC","RamUsed_MB" };
  static ISensor[] Map = new ISensor[13]; static double[] Mul = { 1,1,1,1,1,1,1,1,1,1,1,1,1024 };
  static StreamWriter ContW, FullW; static string ContDay = "";
  static Dictionary<string, Session> Sess = new Dictionary<string, Session>();
  static Stopwatch SW = Stopwatch.StartNew(); static DateTime LastStorage = DateTime.MinValue; static int TickNo = 0; static bool CatalogDone = false;
  static CultureInfo IC = CultureInfo.InvariantCulture;
  static string F(double? v) { return v.HasValue && !double.IsNaN(v.Value) && !double.IsInfinity(v.Value) ? v.Value.ToString("0.###", IC) : ""; }
  static string Q(string s) { return (s.IndexOf(',') >= 0 || s.IndexOf('"') >= 0) ? "\"" + s.Replace("\"", "\"\"") + "\"" : s; }
  static void Log(string m) { try { File.AppendAllText(Path.Combine(Dir, "hwmon.log"), DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " " + m + "\r\n"); } catch { } }
  static bool IsAdmin() { return new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator); }
  static bool Pawn() { try { using (var k = Registry.LocalMachine.OpenSubKey(@"SYSTEM\CurrentControlSet\Services\PawnIO")) return k != null; } catch { return false; } }
  static int Main(string[] a) {
    for (int i = 0; i < a.Length; i++) {
      string x = a[i].ToLowerInvariant(); string v = i + 1 < a.Length ? a[i + 1] : "";
      if (x == "--dir") { Dir = v; i++; } else if (x == "--logs") { Logs = v; i++; } else if (x == "--tag") { Tag = v; i++; }
      else if (x == "--interval") { Interval = int.Parse(v); i++; } else if (x == "--run-seconds") { RunSeconds = int.Parse(v); i++; }
      else if (x == "--roll-after") { RollAfter = int.Parse(v); i++; } else if (x == "--storage-every") { StorageEvery = int.Parse(v); i++; } else if (x == "--no-network") Network = false; else if (x == "--no-full") Full = false; else if (x == "--report") Report = true;
    }
    Thread.CurrentThread.CurrentCulture = CultureInfo.InvariantCulture; CultureInfo.DefaultThreadCurrentCulture = CultureInfo.InvariantCulture;
    Directory.CreateDirectory(Dir); Directory.CreateDirectory(Logs); Directory.CreateDirectory(Path.Combine(Dir, "sessions"));
    bool created; var mtx = new Mutex(true, "Global\\HwMonDaemon_" + Tag, out created);
    if (!created) { Log("another instance running, exit"); return 3; }
    try { Process.GetCurrentProcess().PriorityClass = ProcessPriorityClass.BelowNormal; } catch { }
    Log("start pid=" + Process.GetCurrentProcess().Id + " admin=" + IsAdmin() + " pawnio=" + Pawn() + " interval=" + Interval + " tag=" + Tag);
    C = new Computer { IsCpuEnabled = true, IsGpuEnabled = true, IsMemoryEnabled = true, IsMotherboardEnabled = true, IsStorageEnabled = true, IsNetworkEnabled = Network, IsControllerEnabled = true, IsPsuEnabled = true, IsBatteryEnabled = true };
    C.Open();
    if (Report) { try { File.WriteAllText(Path.Combine(Dir, "lhm_report.txt"), C.GetReport()); } catch (Exception e) { Log("report: " + e.Message); } }
    Enumerate(); Cleanup();
    long next = 0; long end = RunSeconds > 0 ? RunSeconds * 1000L : long.MaxValue;
    while (true) {
      try { Tick(true); } catch (Exception e) { Log("tick error: " + e); }
      next += Interval * 1000L;
      while (SW.ElapsedMilliseconds < next) {
        Thread.Sleep(250);
        try { if (CheckSessions()) Tick(false); } catch (Exception e) { Log("session error: " + e.Message); }
        if (SW.ElapsedMilliseconds >= end) break;
      }
      if (SW.ElapsedMilliseconds >= end) break;
    }
    foreach (var s in Sess.Values.ToList()) Finish(s, "daemon exit");
    try { if (ContW != null) ContW.Dispose(); if (FullW != null) FullW.Dispose(); } catch { }
    C.Close(); Log("exit"); return 0;
  }
  static void Walk(IHardware h, List<IHardware> l) { l.Add(h); foreach (var s in h.SubHardware) Walk(s, l); }
  static void Enumerate() {
    All.Clear(); var hws = new List<IHardware>(); foreach (var h in C.Hardware) Walk(h, hws);
    foreach (var h in hws) h.Update();
    var seen = new Dictionary<string, int>();
    foreach (var h in hws) foreach (var s in h.Sensors) {
      string col = h.Name + " / " + s.Name + " [" + s.SensorType + "]";
      int n; if (seen.TryGetValue(col, out n)) { seen[col] = n + 1; col = col + " #" + (n + 1); } else seen[col] = 1;
      All.Add(new SRef { S = s, H = h, Col = col });
    }
    FullHeader = "Time," + string.Join(",", All.Select(r => Q(r.Col)).ToArray());
    BuildMap(hws); CatalogDone = false; TickNo = 0;
    Log("sensors: " + All.Count + " hardware: " + hws.Count);
  }
  static ISensor Find(IEnumerable<ISensor> ss, SensorType t, params string[] names) { foreach (var n in names) { var f = ss.FirstOrDefault(s => s.SensorType == t && s.Name == n); if (f != null) return f; } return null; }
  static void BuildMap(List<IHardware> hws) {
    Array.Clear(Map, 0, Map.Length);
    var gpus = hws.Where(h => h.HardwareType == HardwareType.GpuAmd || h.HardwareType == HardwareType.GpuNvidia || h.HardwareType == HardwareType.GpuIntel).ToList();
    var g = gpus.OrderByDescending(h => h.Sensors.Count(s => s.SensorType == SensorType.Temperature) * 1000 + h.Sensors.Length).FirstOrDefault();
    if (g != null) { var s = g.Sensors;
      Map[0] = Find(s, SensorType.Temperature, "GPU Core"); Map[1] = Find(s, SensorType.Temperature, "GPU Hot Spot");
      Map[2] = Find(s, SensorType.Temperature, "GPU Memory Junction", "GPU Memory"); Map[3] = Find(s, SensorType.Power, "GPU Package", "GPU Total Board Power");
      Map[4] = Find(s, SensorType.Load, "GPU Core"); Map[5] = Find(s, SensorType.SmallData, "D3D Dedicated Memory Used", "GPU Memory Used");
      Map[6] = Find(s, SensorType.Fan, "GPU Fan"); }
    var cpu = hws.FirstOrDefault(h => h.HardwareType == HardwareType.Cpu);
    if (cpu != null) { var s = cpu.Sensors; Map[8] = Find(s, SensorType.Temperature, "Core (Tctl/Tdie)", "CPU Package", "Core Max"); Map[9] = Find(s, SensorType.Power, "Package"); Map[10] = Find(s, SensorType.Load, "CPU Total"); }
    var mem = hws.FirstOrDefault(h => h.HardwareType == HardwareType.Memory && h.Name == "Total Memory");
    if (mem != null) Map[12] = Find(mem.Sensors, SensorType.Data, "Memory Used");
  }
  static void UpdateHw(bool storageDue) {
    var hws = new List<IHardware>(); foreach (var h in C.Hardware) Walk(h, hws);
    foreach (var h in hws) { if (h.HardwareType == HardwareType.Storage && !storageDue) continue; try { h.Update(); } catch { } }
  }
  static double? Val(ISensor s) { if (s == null) return null; float? v = s.Value; if (!v.HasValue) return null; return (double)v.Value; }
  static void Tick(bool scheduled) {
    DateTime now = DateTime.Now;
    bool storageDue = (now - LastStorage).TotalSeconds >= StorageEvery - 0.5; if (storageDue) LastStorage = now;
    string day = now.ToString("yyyyMMdd"); if (RollAfter > 0) day += "r" + (SW.ElapsedMilliseconds / 1000 / RollAfter);
    if (scheduled && day != ContDay) { if (ContDay != "") { C.Close(); C.Open(); Enumerate(); Cleanup(); } OpenCont(day); }
    UpdateHw(storageDue);
    var vals = new double?[All.Count]; for (int i = 0; i < All.Count; i++) { vals[i] = Val(All[i].S); }
    var cv = new double?[13]; for (int i = 0; i < 13; i++) { var v = Val(Map[i]); cv[i] = v.HasValue ? v * Mul[i] : null; }
    if (scheduled) {
      TickNo++;
      for (int i = 0; i < All.Count; i++) { var r = All[i]; r.Reads++; if (!vals[i].HasValue) r.Nulls++; else { double d = vals[i].Value; if (d < r.Min) r.Min = d; if (d > r.Max) r.Max = d; if (d != 0) r.Zero = false; } }
      string ts = now.ToString("yyyy-MM-dd HH:mm:ss");
      if (ContW != null) { ContW.WriteLine(ts + "," + string.Join(",", cv.Select(F).ToArray())); ContW.Flush(); ((FileStream)ContW.BaseStream).Flush(true); }
      if (FullW != null) { var sb = new StringBuilder(ts); for (int i = 0; i < vals.Length; i++) { sb.Append(','); sb.Append(F(vals[i])); } FullW.WriteLine(sb.ToString()); FullW.Flush(); ((FileStream)FullW.BaseStream).Flush(true); }
      if (TickNo == 6 && !CatalogDone) WriteCatalog();
      Heartbeat();
    }
    foreach (var s in Sess.Values.ToList()) SessRow(s, now, cv, vals);
    CheckSessions();
  }
  static void Heartbeat() {
    try { int rd = All.Count(r => r.Reads > 0 && r.Nulls < r.Reads);
      File.WriteAllText(Path.Combine(Dir, "heartbeat.txt"), "utc=" + DateTime.UtcNow.ToString("o") + "\r\nlocal=" + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "\r\npid=" + Process.GetCurrentProcess().Id + "\r\ninterval=" + Interval + "\r\nadmin=" + IsAdmin() + "\r\npawnio=" + Pawn() + "\r\nsensors=" + All.Count + "\r\nreadable=" + rd + "\r\nsessions=" + string.Join(";", Sess.Keys.ToArray()) + "\r\n"); } catch { }
  }
  static void WriteCatalog() {
    CatalogDone = true;
    try { var sb = new StringBuilder("Hardware,HardwareType,Sensor,SensorType,Identifier,Reads,NullReads,Min,Max,Status\r\n");
      foreach (var r in All) { string st = r.Nulls == r.Reads ? "UNREADABLE(null)" : (r.Zero ? "always 0" : "ok");
        sb.Append(Q(r.H.Name) + "," + r.H.HardwareType + "," + Q(r.S.Name) + "," + r.S.SensorType + "," + Q(r.S.Identifier.ToString()) + "," + r.Reads + "," + r.Nulls + "," + F(r.Reads > r.Nulls ? (double?)r.Min : null) + "," + F(r.Reads > r.Nulls ? (double?)r.Max : null) + "," + st + "\r\n"); }
      File.WriteAllText(Path.Combine(Dir, "sensors_catalog.csv"), sb.ToString(), new UTF8Encoding(false));
      Log("catalog written: " + All.Count + " sensors, null=" + All.Count(r => r.Nulls == r.Reads) + ", always0=" + All.Count(r => r.Nulls < r.Reads && r.Zero)); } catch (Exception e) { Log("catalog: " + e.Message); }
  }
  static StreamWriter Open(string prefix, string ext, string header, string day) {
    string p = Path.Combine(Logs, prefix + "_" + day + ext); int n = 1;
    while (File.Exists(p)) { string first; try { using (var fs = new FileStream(p, FileMode.Open, FileAccess.Read, FileShare.ReadWrite)) using (var sr = new StreamReader(fs)) first = sr.ReadLine(); } catch { first = null; } if (first == header) break; n++; p = Path.Combine(Logs, prefix + "_" + day + "_" + n + ext); }
    bool fresh = !File.Exists(p);
    var w = new StreamWriter(new FileStream(p, FileMode.Append, FileAccess.Write, FileShare.ReadWrite), new UTF8Encoding(false));
    if (fresh) { w.WriteLine(header); w.Flush(); }
    return w;
  }
  static void OpenCont(string day) {
    try { if (ContW != null) ContW.Dispose(); if (FullW != null) FullW.Dispose(); } catch { }
    ContDay = day; ContW = Open(Tag + "_cont", ".csv", "Time," + string.Join(",", Cols), day);
    FullW = Full ? Open(Tag + "_full", ".csv", FullHeader, day) : null;
  }
  static void Cleanup() {
    try { foreach (var f in new DirectoryInfo(Logs).GetFiles(Tag + "_cont_*.csv")) if (f.LastWriteTime < DateTime.Now.AddDays(-KeepCompat)) f.Delete();
          foreach (var f in new DirectoryInfo(Logs).GetFiles(Tag + "_full_*.csv")) if (f.LastWriteTime < DateTime.Now.AddDays(-KeepFull)) f.Delete(); } catch { }
  }
  static string SafeName(string n) { return new string(n.Select(ch => char.IsLetterOrDigit(ch) || ch == '-' || ch == '.' || ch == '_' ? ch : '_').ToArray()); }
  static bool CheckSessions() {
    bool started = false; string sd = Path.Combine(Dir, "sessions");
    foreach (var f in Directory.GetFiles(sd, "*.session")) {
      string name = Path.GetFileNameWithoutExtension(f);
      if (!Sess.ContainsKey(name)) {
        var s = new Session { Name = name, Start = DateTime.Now, FSum = new double[All.Count], FMin = new double[All.Count], FMax = new double[All.Count], FCnt = new int[All.Count] };
        for (int i = 0; i < All.Count; i++) { s.FMin[i] = double.MaxValue; s.FMax[i] = double.MinValue; }
        try { foreach (var line in File.ReadAllLines(f)) { var kv = line.Split(new[] { '=' }, 2); if (kv.Length == 2) { if (kv[0] == "parent") int.TryParse(kv[1], out s.Parent); else if (kv[0] == "maxhours") double.TryParse(kv[1], NumberStyles.Float, IC, out s.MaxHours); } } } catch { }
        string stamp = s.Start.ToString("yyyyMMdd_HHmmss"); s.Csv = Path.Combine(Logs, name + "_" + stamp + ".csv"); s.Sum = Path.ChangeExtension(s.Csv, ".summary.txt"); s.SumFull = Path.ChangeExtension(s.Csv, ".summary_full.txt");
        s.W = new StreamWriter(new FileStream(s.Csv, FileMode.CreateNew, FileAccess.Write, FileShare.ReadWrite), new UTF8Encoding(false)); s.W.WriteLine("Time," + string.Join(",", Cols)); s.W.Flush();
        try { File.WriteAllText(Path.Combine(sd, name + ".state"), s.Csv + "\r\n" + s.Sum + "\r\n"); File.Delete(Path.Combine(sd, name + ".done")); } catch { }
        Sess[name] = s; started = true; Log("session start " + name + " -> " + s.Csv);
      }
    }
    foreach (var s in Sess.Values.ToList()) {
      bool stop = File.Exists(Path.Combine(sd, s.Name + ".stop")) || !File.Exists(Path.Combine(sd, s.Name + ".session"));
      string why = stop ? "stop" : null;
      if (!stop && s.Parent > 0) { bool alive = true; try { Process.GetProcessById(s.Parent); } catch { alive = false; } if (!alive) { stop = true; why = "parent exited"; } }
      if (!stop && (DateTime.Now - s.Start).TotalHours >= s.MaxHours) { stop = true; why = "maxhours"; }
      if (stop) Finish(s, why);
    }
    return started;
  }
  static void SessRow(Session s, DateTime now, double?[] cv, double?[] vals) {
    double dt = s.N == 0 ? 0 : Math.Min(60, (now - s.Last).TotalSeconds); s.Last = now; s.N++;
    s.W.WriteLine(now.ToString("yyyy-MM-dd HH:mm:ss") + "," + string.Join(",", cv.Select(F).ToArray())); s.W.Flush();
    for (int i = 0; i < 13; i++) if (cv[i].HasValue) { s.Sum13[i] += cv[i].Value; s.Cnt13[i]++; if (s.Cnt13[i] == 1 || cv[i].Value > s.Max13[i]) s.Max13[i] = cv[i].Value; s.Seen[i] = true; }
    if (cv[3].HasValue) s.eG += cv[3].Value * dt; if (cv[9].HasValue) s.eC += cv[9].Value * dt;
    if (cv[1].HasValue && cv[1].Value > 95) s.Hot95++;
    for (int i = 0; i < vals.Length && i < s.FCnt.Length; i++) if (vals[i].HasValue) { double d = vals[i].Value; s.FSum[i] += d; s.FCnt[i]++; if (d < s.FMin[i]) s.FMin[i] = d; if (d > s.FMax[i]) s.FMax[i] = d; }
  }
  static void Finish(Session s, string why) {
    string sd = Path.Combine(Dir, "sessions"); Sess.Remove(s.Name);
    try { s.W.Dispose(); } catch { }
    try {
      var o = new List<string>(); var end = DateTime.Now;
      o.Add("Run: " + s.Name); o.Add("Start: " + s.Start.ToString("yyyy-MM-dd HH:mm:ss") + "  End: " + end.ToString("yyyy-MM-dd HH:mm:ss") + "  Duration: " + Math.Round((end - s.Start).TotalMinutes, 1, MidpointRounding.AwayFromZero).ToString("0.0", IC) + " min  Samples: " + s.N + "  (source: own hwmon / LibreHardwareMonitorLib 0.9.6, ended: " + why + ")"); o.Add("");
      o.Add(string.Format("{0,-14}{1,10}{2,10}", "Sensor", "Max", "Avg"));
      var missing = new List<string>();
      for (int i = 0; i < 13; i++) { if (s.Cnt13[i] > 0) o.Add(string.Format("{0,-14}{1,10:n1}{2,10:n1}", Cols[i], s.Max13[i], s.Sum13[i] / s.Cnt13[i])); else { o.Add(string.Format("{0,-14}{1,10}{2,10}", Cols[i], "n/a", "n/a")); missing.Add(Cols[i]); } }
      o.Add(""); o.Add("HTC throttling samples: n/a (no LHM equivalent)"); o.Add("Hotspot >95 C samples: " + (s.Cnt13[1] > 0 ? s.Hot95.ToString() : "n/a (sensor missing)"));
      o.Add("Energy GPU: " + (s.Cnt13[3] > 0 ? (s.eG / 3.6e6).ToString("n4", IC) + " kWh" : "n/a") + "   CPU: " + (s.Cnt13[9] > 0 ? (s.eC / 3.6e6).ToString("n4", IC) + " kWh" : "n/a") + "   Total: " + ((s.eG + s.eC) / 3.6e6).ToString("n4", IC) + " kWh");
      if (missing.Count > 0) o.Add("Not available from LHM: " + string.Join(", ", missing.ToArray()));
      o.Add("All sensors (min/max/avg): " + Path.GetFileName(s.SumFull));
      File.WriteAllLines(s.Sum, o.ToArray(), new UTF8Encoding(false));
      var f = new List<string>(); f.Add("Run: " + s.Name + "  Samples: " + s.N + "  all sensors"); f.Add(string.Format("{0,-70}{1,12}{2,12}{3,12}", "Sensor", "Min", "Max", "Avg"));
      for (int i = 0; i < All.Count && i < s.FCnt.Length; i++) if (s.FCnt[i] > 0) f.Add(string.Format("{0,-70}{1,12}{2,12}{3,12}", All[i].Col.Length > 69 ? All[i].Col.Substring(0, 69) : All[i].Col, F(s.FMin[i]), F(s.FMax[i]), F(s.FSum[i] / s.FCnt[i])));
      File.WriteAllLines(s.SumFull, f.ToArray(), new UTF8Encoding(false));
      File.WriteAllText(Path.Combine(sd, s.Name + ".done"), s.Csv + "\r\n" + s.Sum + "\r\n");
    } catch (Exception e) { Log("finish error: " + e); }
    try { File.Delete(Path.Combine(sd, s.Name + ".session")); File.Delete(Path.Combine(sd, s.Name + ".stop")); } catch { }
    Log("session end " + s.Name + " (" + why + ") samples=" + s.N);
  }
}
}