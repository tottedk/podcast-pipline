// hwmon_ui.cs - HwMon UI widget v1.0 (2026-10-16). Small always-on-top status widget for LLM use, gaming and hardware health.
// Reads the latest rows of the existing hwmon log (C:\grok\podcast\hwlogs\hwmon_cont_YYYYMMDD.csv, 14 columns, written every 5 s by hwmon.exe); changes nothing in hwmon.
// C# 5 (csc.exe of .NET Framework 4), WinForms, no external dependencies. Build: build.ps1
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.Globalization;
using System.IO;
using System.Management;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

namespace HwUi
{
    static class Native
    {
        [DllImport("user32.dll")] public static extern bool RegisterHotKey(IntPtr h, int id, uint mod, uint vk);
        [DllImport("user32.dll")] public static extern bool UnregisterHotKey(IntPtr h, int id);
        [DllImport("user32.dll")] public static extern bool DestroyIcon(IntPtr h);
        [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
        public class MEMSTAT
        {
            public uint dwLength = (uint)Marshal.SizeOf(typeof(MEMSTAT));
            public uint dwMemoryLoad; public ulong ullTotalPhys, ullAvailPhys, ullTotalPageFile, ullAvailPageFile, ullTotalVirtual, ullAvailVirtual, ullAvailExtendedVirtual;
        }
        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)] public static extern bool GlobalMemoryStatusEx([In, Out] MEMSTAT s);
    }

    class Sample { public DateTime T; public double GpuT, Hot, Mem, Pwr, Load, VramMB, Fan, CpuT, CpuP, CpuL, RamMB; }
    class Alert { public int Level; public string Text; public Alert(int l, string t) { Level = l; Text = t; } }
    class Snap
    {
        public Sample Last; public double AgeSec = 9999; public List<Alert> Alerts = new List<Alert>(); public int Level;
        public double RamTotalMB; public string Job = "idle (no LLM/render job)"; public int JobLevel;
    }

    static class Cfg
    {
        public const string LogDir = @"C:\grok\podcast\hwlogs";
        public const double VramTotalMB = 20421;        // RX 7900 XT D3D Dedicated Memory Total
        public const double VramAmber = 17408, VramRed = 19456;   // 17 GB / 19 GB used
        public const double EdgeAmber = 75, EdgeRed = 85;
        public const double HotAmber = 95, HotRed = 100, HotLimit = 108;
        public const double MemAmber = 90, MemRed = 100;
        public const double CpuAmber = 80, CpuRed = 90;
        public const double RamAmberPct = 80, RamRedPct = 92;
        public const int HotSustainedSec = 30, StaleSec = 30;
    }

    static class Data
    {
        static double P(string[] c, int i)
        {
            double v; if (i < c.Length && c[i].Length > 0 && double.TryParse(c[i], NumberStyles.Float, CultureInfo.InvariantCulture, out v)) return v; return double.NaN;
        }
        static List<Sample> ReadFile(string f)
        {
            var res = new List<Sample>();
            using (var fs = new FileStream(f, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            {
                long n = Math.Min(fs.Length, 8192); fs.Seek(-n, SeekOrigin.End); var buf = new byte[n]; int got = 0;
                while (got < n) { int r = fs.Read(buf, got, (int)n - got); if (r <= 0) break; got += r; }
                string[] lines = Encoding.ASCII.GetString(buf, 0, got).Split('\n');
                for (int i = (n < fs.Length ? 1 : 0); i < lines.Length; i++)
                {
                    string ln = lines[i].Trim(); if (ln.Length == 0 || ln.StartsWith("Time,")) continue;
                    string[] c = ln.Split(','); if (c.Length < 14) continue; DateTime t;
                    if (!DateTime.TryParseExact(c[0], "yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture, DateTimeStyles.None, out t)) continue;
                    res.Add(new Sample { T = t, GpuT = P(c, 1), Hot = P(c, 2), Mem = P(c, 3), Pwr = P(c, 4), Load = P(c, 5), VramMB = P(c, 6), Fan = P(c, 7), CpuT = P(c, 9), CpuP = P(c, 10), CpuL = P(c, 11), RamMB = P(c, 13) });
                }
            }
            return res;
        }
        public static List<Sample> ReadTail()
        {
            try
            {
                string[] files = Directory.GetFiles(Cfg.LogDir, "hwmon_cont_*.csv"); Array.Sort(files);
                for (int k = files.Length - 1; k >= 0 && k >= files.Length - 2; k--) { var s = ReadFile(files[k]); if (s.Count > 0) return s; }
            }
            catch { }
            return new List<Sample>();
        }
        public static double RamTotalMB()
        {
            var m = new Native.MEMSTAT(); return Native.GlobalMemoryStatusEx(m) ? m.ullTotalPhys / 1048576.0 : 0;
        }
        static bool Ok(double v) { return !double.IsNaN(v); }
        public static Snap Evaluate() { return Evaluate(null); }
        public static Snap Evaluate(List<Sample> demo)
        {
            var sn = new Snap(); var rows = demo != null ? demo : ReadTail(); sn.RamTotalMB = RamTotalMB();
            sn.Job = Jobs.Text; sn.JobLevel = Jobs.Level;
            if (rows.Count == 0) { sn.Alerts.Add(new Alert(2, "no hwmon data (is the HwMon task running?)")); sn.Level = 2; return sn; }
            var l = rows[rows.Count - 1]; sn.Last = l; sn.AgeSec = (DateTime.Now - l.T).TotalSeconds;
            if (sn.AgeSec > Cfg.StaleSec) sn.Alerts.Add(new Alert(2, "hwmon data stale (" + (int)sn.AgeSec + " s) - HwMon task not running?"));
            // hotspot sustained > 100 C
            if (Ok(l.Hot) && l.Hot > Cfg.HotRed)
            {
                double span = 0; bool all = true;
                for (int i = rows.Count - 1; i >= 0 && (l.T - rows[i].T).TotalSeconds <= Cfg.HotSustainedSec + 2; i--) { span = (l.T - rows[i].T).TotalSeconds; if (!(rows[i].Hot > Cfg.HotRed)) { all = false; break; } }
                if (all && span >= Cfg.HotSustainedSec - 5) sn.Alerts.Add(new Alert(2, "GPU hotspot > 100 C for " + (int)span + " s+"));
            }
            if (Ok(l.Hot) && l.Hot >= Cfg.HotLimit) sn.Alerts.Add(new Alert(2, "GPU at thermal limit (hotspot " + (int)l.Hot + " C) - throttling likely"));
            else if (Ok(l.Hot) && l.Hot >= Cfg.HotAmber) sn.Alerts.Add(new Alert(l.Hot >= Cfg.HotRed ? 2 : 1, "GPU hotspot " + (int)l.Hot + " C"));
            if (Ok(l.Mem) && l.Mem >= Cfg.MemRed) sn.Alerts.Add(new Alert(2, "GPU memory junction " + (int)l.Mem + " C"));
            if (Ok(l.VramMB) && l.VramMB >= Cfg.VramRed) sn.Alerts.Add(new Alert(2, "VRAM nearly full: " + (l.VramMB / 1024).ToString("0.0", CultureInfo.InvariantCulture) + " / 20 GB"));
            else if (Ok(l.VramMB) && l.VramMB >= Cfg.VramAmber) sn.Alerts.Add(new Alert(1, "VRAM " + (l.VramMB / 1024).ToString("0.0", CultureInfo.InvariantCulture) + " GB used - little room for an LLM"));
            if (Ok(l.CpuT) && l.CpuT >= Cfg.CpuRed) sn.Alerts.Add(new Alert(2, "CPU " + (int)l.CpuT + " C"));
            if (Ok(l.Fan) && l.Fan < 50 && Ok(l.Hot) && l.Hot >= 85) sn.Alerts.Add(new Alert(2, "GPU fan stopped while hotspot " + (int)l.Hot + " C"));
            if (sn.RamTotalMB > 0 && Ok(l.RamMB) && l.RamMB / sn.RamTotalMB * 100 >= Cfg.RamRedPct) sn.Alerts.Add(new Alert(2, "RAM nearly full"));
            foreach (var a in sn.Alerts) if (a.Level > sn.Level) sn.Level = a.Level;
            return sn;
        }
    }

    static class Jobs
    {
        public static volatile string Text = "idle (no LLM/render job)"; public static volatile int Level = 0;
        static string pipeline = "";
        static string OllamaPs()
        {
            if (Process.GetProcessesByName("ollama").Length == 0) return "";
            try
            {
                var rq = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:11434/api/ps"); rq.Timeout = 600; rq.ReadWriteTimeout = 600; rq.Proxy = null;
                using (var rs = rq.GetResponse()) using (var sr = new StreamReader(rs.GetResponseStream()))
                {
                    string j = sr.ReadToEnd(); var names = new List<string>();
                    foreach (Match m in Regex.Matches(j, "\"name\"\\s*:\\s*\"([^\"]+)\"[^}]*?\"size_vram\"\\s*:\\s*(\\d+)"))
                        names.Add(m.Groups[1].Value + " (" + (double.Parse(m.Groups[2].Value, CultureInfo.InvariantCulture) / 1073741824.0).ToString("0.0", CultureInfo.InvariantCulture) + " GB VRAM)");
                    if (names.Count == 0) foreach (Match m in Regex.Matches(j, "\"name\"\\s*:\\s*\"([^\"]+)\"")) names.Add(m.Groups[1].Value);
                    return string.Join(", ", names.ToArray());
                }
            }
            catch { return ""; }
        }
        static string Pipeline()
        {
            var tags = new List<string>();
            try
            {
                using (var s = new ManagementObjectSearcher("SELECT CommandLine FROM Win32_Process WHERE Name='python.exe' OR Name='powershell.exe' OR Name='pwsh.exe'"))
                    foreach (ManagementObject o in s.Get())
                    {
                        string c = o["CommandLine"] as string; if (c == null) continue;
                        if (c.IndexOf("hwmon_ui", StringComparison.OrdinalIgnoreCase) >= 0) continue;
                        string t = null;
                        if (Regex.IsMatch(c, "run_episode|start_.*_ep1", RegexOptions.IgnoreCase)) t = "podcast pipeline";
                        else if (Regex.IsMatch(c, "render7b|vv7b_generate|vv_generate|qc_vv|qc_takes", RegexOptions.IgnoreCase)) t = "TTS render/QC";
                        else if (Regex.IsMatch(c, "make_video|post_episode|post_segment|align\\.py|qc_mix", RegexOptions.IgnoreCase)) t = "podcast post/video";
                        else if (Regex.IsMatch(c, "gen_backgrounds", RegexOptions.IgnoreCase)) t = "FLUX backgrounds";
                        if (t != null && !tags.Contains(t)) tags.Add(t);
                    }
            }
            catch { }
            return string.Join(", ", tags.ToArray());
        }
        public static void Poll(bool deep)
        {
            if (deep) pipeline = Pipeline();
            var parts = new List<string>();
            string ol = OllamaPs(); if (ol.Length > 0) parts.Add("Ollama: " + ol);
            if (Process.GetProcessesByName("audiocpp_cli").Length > 0) parts.Add("audio.cpp TTS");
            if (pipeline.Length > 0) parts.Add(pipeline);
            if (parts.Count > 0) { Text = "LLM/render job running: " + string.Join(" | ", parts.ToArray()); Level = 3; }
            else { Text = "idle (no LLM/render job)"; Level = 0; }
        }
    }

    static class Painter
    {
        static readonly Color Bg = Color.FromArgb(22, 24, 30), Border = Color.FromArgb(60, 66, 80), Dim = Color.FromArgb(125, 133, 148), Txt = Color.FromArgb(214, 219, 228);
        static readonly Color Green = Color.FromArgb(90, 205, 130), Amber = Color.FromArgb(255, 190, 70), Red = Color.FromArgb(255, 90, 90), Blue = Color.FromArgb(110, 170, 255);
        public static Color LevelColor(int lv) { return lv >= 3 ? Blue : lv == 2 ? Red : lv == 1 ? Amber : Green; }
        static Color Hi(double v, double amber, double red) { if (double.IsNaN(v)) return Dim; return v >= red ? Red : v >= amber ? Amber : Green; }
        static string F(double v, string fmt) { return double.IsNaN(v) ? "-" : v.ToString(fmt, CultureInfo.InvariantCulture); }
        static Font fn = new Font("Segoe UI", 12f, FontStyle.Regular, GraphicsUnit.Pixel), fb = new Font("Segoe UI Semibold", 12f, FontStyle.Regular, GraphicsUnit.Pixel), fs = new Font("Segoe UI", 10f, FontStyle.Regular, GraphicsUnit.Pixel);
        static StringFormat sf = MkSf(); static StringFormat MkSf() { var f = (StringFormat)StringFormat.GenericTypographic.Clone(); f.FormatFlags |= StringFormatFlags.MeasureTrailingSpaces | StringFormatFlags.NoWrap; return f; }
        static float W(Graphics g, string t, Font f) { return g.MeasureString(t, f, 10000, sf).Width; }
        static float T(Graphics g, string t, Font f, Color c, float x, float y, bool draw) { if (draw) using (var b = new SolidBrush(c)) g.DrawString(t, f, b, x, y, sf); return W(g, t, f); }
        static void Bar(Graphics g, float x, float y, float w, float h, double frac, Color c)
        {
            using (var b = new SolidBrush(Color.FromArgb(48, 53, 66))) g.FillRectangle(b, x, y, w, h);
            if (!double.IsNaN(frac)) using (var b = new SolidBrush(c)) g.FillRectangle(b, x, y, (float)(Math.Max(0, Math.Min(1, frac)) * w), h);
        }
        static string Gb(double mb) { return double.IsNaN(mb) ? "-" : (mb / 1024).ToString("0.0", CultureInfo.InvariantCulture); }

        public static float Scale = 1f;
        public static Size Paint(Graphics g, Snap s, bool expanded, bool draw, int mode)
        {
            if (draw) g.ScaleTransform(Scale, Scale);
            Size z = PaintU(g, s, expanded, draw);
            return new Size((int)Math.Ceiling(z.Width * Scale), (int)Math.Ceiling(z.Height * Scale));
        }
        static Size PaintU(Graphics g, Snap s, bool expanded, bool draw)
        {
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit; var l = s.Last; double nan = double.NaN;
            double gt = l != null ? l.GpuT : nan, hot = l != null ? l.Hot : nan, mem = l != null ? l.Mem : nan, ld = l != null ? l.Load : nan, vr = l != null ? l.VramMB : nan, pw = l != null ? l.Pwr : nan, fan = l != null ? l.Fan : nan;
            double ct = l != null ? l.CpuT : nan, cl = l != null ? l.CpuL : nan, cp = l != null ? l.CpuP : nan, ram = l != null ? l.RamMB : nan;
            Color cG = Hi(gt, Cfg.EdgeAmber, Cfg.EdgeRed), cH = Hi(hot, Cfg.HotAmber, Cfg.HotRed), cM = Hi(mem, Cfg.MemAmber, Cfg.MemRed), cV = Hi(vr, Cfg.VramAmber, Cfg.VramRed), cC = Hi(ct, Cfg.CpuAmber, Cfg.CpuRed);
            double ramPct = (s.RamTotalMB > 0 && !double.IsNaN(ram)) ? ram / s.RamTotalMB * 100 : nan; Color cR = Hi(ramPct, Cfg.RamAmberPct, Cfg.RamRedPct);
            int w, h;
            if (!expanded)
            {
                float x = 10, y = 6; var Q = new List<KeyValuePair<string, Color>>();
                Action<string, Color> a = delegate(string t, Color c) { Q.Add(new KeyValuePair<string, Color>(t, c)); };
                a("\u25CF", LevelColor(s.Level)); a(" ", Dim);
                a("GPU ", Dim); a(F(gt, "0") + "\u00B0", cG); a("/", Dim); a(F(hot, "0") + "\u00B0", cH); a("/", Dim); a(F(mem, "0") + "\u00B0", cM); a("  ", Dim);
                a(F(ld, "0") + "%", Txt); a("  ", Dim); a("VRAM ", Dim); a(Gb(vr) + "/20", cV); a("  ", Dim); a(F(pw, "0") + "W", Txt); a("  ", Dim);
                a("CPU ", Dim); a(F(ct, "0") + "\u00B0", cC); a(" ", Dim); a(F(cl, "0") + "%", Txt); a("  ", Dim); a("RAM ", Dim); a(Gb(ram), cR); a("  ", Dim);
                if (s.JobLevel >= 3) a("LLM/render", Blue); else a("idle", Dim);
                if (s.Alerts.Count > 0) { a("  ", Dim); a(s.Alerts[0].Text, LevelColor(s.Alerts[0].Level)); }
                float tot = 0; foreach (var q in Q) tot += W(g, q.Key, fb);
                w = (int)tot + 20; h = 28;
                if (draw) { g.Clear(Bg); using (var p = new Pen(Border)) g.DrawRectangle(p, 0, 0, w - 1, h - 1); foreach (var q in Q) x += T(g, q.Key, fb, q.Value, x, y, true); }
                return new Size(w, h);
            }
            w = 410; int ny = 0;
            if (draw) { g.Clear(Bg); }
            float yy = 8;
            // header
            float hx = 12; hx += T(g, "HwMon", fb, Txt, hx, yy, draw); T(g, l != null ? "  " + l.T.ToString("HH:mm:ss", CultureInfo.InvariantCulture) : "  no data", fn, Dim, hx, yy, draw);
            string live = s.AgeSec > Cfg.StaleSec ? "stale" : "live"; float lw = W(g, live, fn); T(g, "\u25CF " + live, fn, s.AgeSec > Cfg.StaleSec ? Red : Green, w - 12 - lw - 14, yy, draw);
            yy += 26;
            // GPU temps
            T(g, "GPU 7900 XT", fb, Txt, 12, yy, draw); float c1 = 112, c2 = 212, c3 = 312;
            T(g, "Edge ", fs, Dim, c1, yy + 2, draw); T(g, F(gt, "0") + "\u00B0C", fb, cG, c1 + 28, yy, draw);
            T(g, "Hotspot ", fs, Dim, c2 - 12, yy + 2, draw); T(g, F(hot, "0") + "\u00B0C", fb, cH, c2 + 34, yy, draw);
            yy += 20;
            T(g, "Mem junction ", fs, Dim, c1, yy + 2, draw); T(g, F(mem, "0") + "\u00B0C", fb, cM, c1 + 82, yy, draw);
            T(g, "Fan ", fs, Dim, c3 - 12, yy + 2, draw); T(g, F(fan, "0") + " rpm", fb, (!double.IsNaN(fan) && fan < 50 && hot >= 85) ? Red : Txt, c3 + 10, yy, draw);
            yy += 22;
            T(g, "Load / power", fn, Dim, 12, yy, draw); Bar(g, c1, yy + 6, 120, 8, ld / 100.0, Blue); T(g, F(ld, "0") + "%", fb, Txt, c1 + 128, yy, draw); T(g, F(pw, "0") + " W", fb, Txt, c3 - 12, yy, draw);
            yy += 24;
            T(g, "VRAM (D3D)", fn, Dim, 12, yy, draw); Bar(g, c1, yy + 6, 120, 8, vr / Cfg.VramTotalMB, cV); T(g, Gb(vr) + " / 20 GB", fb, cV, c1 + 128, yy, draw);
            yy += 20; double free = double.IsNaN(vr) ? nan : Math.Max(0, Cfg.VramTotalMB - vr);
            T(g, "Free for LLM", fn, Dim, 12, yy, draw); T(g, Gb(free) + " GB", fb, cV, c1, yy, draw);
            yy += 26;
            T(g, "CPU", fb, Txt, 12, yy, draw); T(g, F(ct, "0") + "\u00B0C", fb, cC, c1, yy, draw); T(g, F(cl, "0") + "%", fb, Txt, c2 - 12, yy, draw); T(g, F(cp, "0") + " W", fb, Txt, c3 - 12, yy, draw);
            yy += 22;
            T(g, "RAM", fn, Dim, 12, yy, draw); Bar(g, c1, yy + 6, 120, 8, ramPct / 100.0, cR); T(g, Gb(ram) + " / " + (s.RamTotalMB / 1024).ToString("0.0", CultureInfo.InvariantCulture) + " GB", fb, cR, c1 + 128, yy, draw);
            yy += 22;
            double pc = (double.IsNaN(pw) || double.IsNaN(cp)) ? nan : pw + cp;
            T(g, "CPU+GPU power", fn, Dim, 12, yy, draw); T(g, "~" + F(pc, "0") + " W", fb, Txt, c1, yy, draw); T(g, "(no wall meter)", fs, Dim, c2 - 12, yy + 2, draw);
            yy += 26;
            if (draw) using (var p = new Pen(Border)) g.DrawLine(p, 10, yy - 6, w - 10, yy - 6);
            string jt = s.Job; while (jt.Length > 8 && W(g, jt, fb) > w - 24) jt = jt.Substring(0, jt.Length - 2).TrimEnd() + "\u2026"; if (jt != s.Job) { while (jt.EndsWith("\u2026\u2026")) jt = jt.Substring(0, jt.Length - 1); }
            T(g, jt, fb, LevelColor(s.JobLevel), 12, yy, draw); yy += 22;
            if (s.Alerts.Count == 0) { T(g, "\u2714 all OK (hotspot " + F(hot, "0") + "\u00B0, VRAM " + Gb(vr) + " GB)", fn, Green, 12, yy, draw); yy += 20; }
            else foreach (var al in s.Alerts) { if (ny >= 4) break; T(g, "\u25B2 " + al.Text, fb, LevelColor(al.Level), 12, yy, draw); yy += 20; ny++; }
            yy += 4; T(g, "click: compact  |  right-click: menu  |  Ctrl+Alt+H: hide/show", fs, Dim, 12, yy, draw); yy += 18;
            h = (int)yy + 4;
            if (draw) using (var p = new Pen(Border)) g.DrawRectangle(p, 0, 0, w - 1, h - 1);
            return new Size(w, h);
        }
    }

    class Widget : Form
    {
        const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run", RunName = "HwMonUI";
        NotifyIcon tray; ContextMenuStrip menu; ToolStripMenuItem miShow, miMode, miAuto; System.Windows.Forms.Timer timer;
        Snap snap = new Snap(); bool expanded; int lastSig; IntPtr iconH = IntPtr.Zero; int iconLevel = -1;
        Point down; Point formAtDown; bool dragging, mouseDown; string settingsPath; bool hotkeyOk; int tick;
        System.Threading.Timer jobTimer; int jobTick;

        protected override CreateParams CreateParams { get { var cp = base.CreateParams; cp.ExStyle |= 0x08000000 | 0x80; return cp; } }   // WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        protected override bool ShowWithoutActivation { get { return true; } }

        public Widget()
        {
            Text = "HwMonUI"; FormBorderStyle = FormBorderStyle.None; ShowInTaskbar = false; TopMost = true; StartPosition = FormStartPosition.Manual; Opacity = 0.97;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.UserPaint, true);
            settingsPath = Path.Combine(Path.GetDirectoryName(Application.ExecutablePath), "hwmon_ui.settings");
            int sx = int.MinValue, sy = int.MinValue; LoadSettings(out sx, out sy);
            menu = new ContextMenuStrip();
            miShow = new ToolStripMenuItem("Hide (Ctrl+Alt+H)", null, delegate { ToggleVisible(); });
            miMode = new ToolStripMenuItem("Expanded", null, delegate { SetExpanded(!expanded); });
            miAuto = new ToolStripMenuItem("Start with Windows", null, delegate { SetAutostart(!GetAutostart()); });
            menu.Items.Add(miShow); menu.Items.Add(miMode); menu.Items.Add(miAuto); menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add(new ToolStripMenuItem("Exit", null, delegate { Quit(); }));
            menu.Opening += delegate { miShow.Text = (Visible ? "Hide" : "Show") + " (Ctrl+Alt+H)"; miMode.Text = expanded ? "Compact bar" : "Expanded panel"; miAuto.Checked = GetAutostart(); };
            tray = new NotifyIcon(); tray.ContextMenuStrip = menu; tray.Text = "HwMon UI"; tray.Visible = true;
            tray.MouseClick += delegate(object o, MouseEventArgs e) { if (e.Button == MouseButtons.Left) ToggleVisible(); };
            tray.DoubleClick += delegate { SetExpanded(!expanded); };
            using (var g0 = CreateGraphics()) Painter.Scale = g0.DpiX / 96f;
            Refresh2(true);
            ClientSize = Painter.Paint(CreateGraphics(), snap, expanded, false, 0);
            var wa = Screen.PrimaryScreen.WorkingArea;
            if (sx == int.MinValue || !Screen.AllScreens.Any2(sx, sy)) { sx = wa.Right - Width - 12; sy = wa.Top + 12; }
            Location = new Point(sx, sy); ClampToScreen();
            timer = new System.Windows.Forms.Timer(); timer.Interval = 3000; timer.Tick += delegate { Refresh2(false); }; timer.Start();
            jobTimer = new System.Threading.Timer(delegate { try { Jobs.Poll(jobTick++ % 3 == 0); } catch { } }, null, 500, 5000);
            var exitWait = new Thread(delegate()
            {
                try { var ev = new EventWaitHandle(false, EventResetMode.AutoReset, @"Local\HwMonUI_Exit"); ev.WaitOne(); BeginInvoke(new Action(Quit)); } catch { }
            }); exitWait.IsBackground = true; exitWait.Start();
        }

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e); hotkeyOk = Native.RegisterHotKey(Handle, 1, 0x0002 | 0x0001 | 0x4000, (uint)Keys.H);   // Ctrl+Alt+H (MOD_CONTROL|MOD_ALT|MOD_NOREPEAT)
            if (!hotkeyOk) tray.ShowBalloonTip(4000, "HwMon UI", "Hotkey Ctrl+Alt+H is taken by another program; use the tray icon.", ToolTipIcon.Warning);
        }
        protected override void WndProc(ref Message m) { if (m.Msg == 0x0312 && m.WParam.ToInt32() == 1) ToggleVisible(); else base.WndProc(ref m); }

        void Refresh2(bool first)
        {
            snap = Data.Evaluate(); tick++;
            int sig = (snap.Last == null ? 0 : snap.Last.T.GetHashCode()) ^ snap.Job.GetHashCode() ^ (snap.Level << 3) ^ ((int)snap.AgeSec > Cfg.StaleSec ? 99 : 0) ^ (expanded ? 1 : 0);
            if (!first && sig == lastSig) return; lastSig = sig;
            if (snap.Level != iconLevel) SetTrayIcon(snap.Level);
            var l = snap.Last; tray.Text = l == null ? "HwMon UI: no data" : "HwMon UI  GPU " + (int)l.GpuT + "/" + (int)l.Hot + " C  VRAM " + (l.VramMB / 1024).ToString("0.0", CultureInfo.InvariantCulture) + " GB";
            if (!first && IsHandleCreated) { var sz = Painter.Paint(CreateGraphics(), snap, expanded, false, 0); if (sz != ClientSize) { ClientSize = sz; ClampToScreen(); } Invalidate(); }
        }
        void SetTrayIcon(int lv)
        {
            using (var bmp = new Bitmap(16, 16)) using (var g = Graphics.FromImage(bmp))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias; using (var b = new SolidBrush(Painter.LevelColor(lv))) g.FillEllipse(b, 1, 1, 13, 13); using (var p = new Pen(Color.FromArgb(30, 30, 36), 1.5f)) g.DrawEllipse(p, 1, 1, 13, 13);
                IntPtr h = bmp.GetHicon(); tray.Icon = Icon.FromHandle(h); if (iconH != IntPtr.Zero) Native.DestroyIcon(iconH); iconH = h; iconLevel = lv;
            }
        }
        protected override void OnPaint(PaintEventArgs e) { Painter.Paint(e.Graphics, snap, expanded, true, 0); }

        void ClampToScreen()
        {
            var wa = Screen.FromPoint(Location).WorkingArea; int x = Math.Min(Math.Max(Left, wa.Left), Math.Max(wa.Left, wa.Right - Width)), y = Math.Min(Math.Max(Top, wa.Top), Math.Max(wa.Top, wa.Bottom - Height));
            if (x != Left || y != Top) Location = new Point(x, y);
        }
        public void SetExpanded(bool ex) { expanded = ex; lastSig = 0; Refresh2(false); if (IsHandleCreated) { ClientSize = Painter.Paint(CreateGraphics(), snap, expanded, false, 0); ClampToScreen(); Invalidate(); } SaveSettings(); }
        void ToggleVisible() { if (Visible) Hide(); else { Show(); ClampToScreen(); Invalidate(); } }
        void Quit() { SaveSettings(); tray.Visible = false; Application.Exit(); }
        protected override void OnFormClosed(FormClosedEventArgs e)
        {
            try { Native.UnregisterHotKey(Handle, 1); } catch { }
            tray.Visible = false; tray.Dispose(); if (iconH != IntPtr.Zero) Native.DestroyIcon(iconH); base.OnFormClosed(e);
        }

        protected override void OnMouseDown(MouseEventArgs e) { if (e.Button == MouseButtons.Left) { mouseDown = true; dragging = false; down = Cursor.Position; formAtDown = Location; Capture = true; } }
        protected override void OnMouseMove(MouseEventArgs e)
        {
            if (!mouseDown) return; var c = Cursor.Position; int dx = c.X - down.X, dy = c.Y - down.Y;
            if (!dragging && Math.Abs(dx) + Math.Abs(dy) > 4) dragging = true; if (dragging) Location = new Point(formAtDown.X + dx, formAtDown.Y + dy);
        }
        protected override void OnMouseUp(MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left && mouseDown) { mouseDown = false; Capture = false; if (dragging) { ClampToScreen(); SaveSettings(); } else SetExpanded(!expanded); }
            else if (e.Button == MouseButtons.Right) menu.Show(Cursor.Position);
        }

        bool GetAutostart() { try { using (var k = Registry.CurrentUser.OpenSubKey(RunKey)) return k != null && k.GetValue(RunName) != null; } catch { return false; } }
        void SetAutostart(bool on)
        {
            try { using (var k = Registry.CurrentUser.OpenSubKey(RunKey, true)) { if (on) k.SetValue(RunName, "\"" + Application.ExecutablePath + "\""); else k.DeleteValue(RunName, false); } } catch { }
        }
        void LoadSettings(out int x, out int y)
        {
            x = int.MinValue; y = int.MinValue;
            try { foreach (var ln in File.ReadAllLines(settingsPath)) { var kv = ln.Split('='); if (kv.Length != 2) continue; int v; if (!int.TryParse(kv[1], out v)) continue; if (kv[0] == "x") x = v; else if (kv[0] == "y") y = v; else if (kv[0] == "expanded") expanded = v == 1; } } catch { }
        }
        void SaveSettings() { try { File.WriteAllText(settingsPath, "x=" + Left + "\r\ny=" + Top + "\r\nexpanded=" + (expanded ? 1 : 0) + "\r\n"); } catch { } }
    }

    static class Ext
    {
        public static bool Any2(this Screen[] sc, int x, int y) { foreach (var s in sc) if (s.WorkingArea.Contains(x + 20, y + 10)) return true; return false; }
    }

    static class Program
    {
        [STAThread]
        static int Main(string[] args)
        {
            if (args.Length >= 2 && args[0] == "--snapshot")
            {
                Jobs.Poll(true); Snap sn;
                if (args.Length >= 3 && args[2] == "--demo")   // synthetic hot/full-VRAM scenario to check the colours and alerts
                {
                    var rows = new List<Sample>(); for (int i = 0; i < 8; i++) rows.Add(new Sample { T = DateTime.Now.AddSeconds(-5 * (7 - i)), GpuT = 82, Hot = 103, Mem = 97, Pwr = 285, Load = 99, VramMB = 19800, Fan = 2100, CpuT = 71, CpuP = 88, CpuL = 63, RamMB = 27500 });
                    sn = Data.Evaluate(rows); sn.Job = "LLM/render job running: Ollama: qwen3:32b (17.9 GB VRAM) | TTS render/QC"; sn.JobLevel = 3;
                }
                else sn = Data.Evaluate();
                int ok = 0;
                foreach (bool ex in new bool[] { false, true })
                {
                    using (var m = new Bitmap(1, 1)) using (var g0 = Graphics.FromImage(m))
                    {
                        var sz = Painter.Paint(g0, sn, ex, false, 0);
                        using (var bmp = new Bitmap(sz.Width, sz.Height)) using (var g = Graphics.FromImage(bmp)) { Painter.Paint(g, sn, ex, true, 0); bmp.Save(args[1] + (ex ? "_expanded.png" : "_compact.png"), ImageFormat.Png); ok++; }
                    }
                }
                Console.WriteLine("snapshot ok: " + ok + " files, level " + sn.Level + ", job: " + sn.Job); return 0;
            }
            Native.SetProcessDPIAware();   // per-pixel layout; the widget scales its own drawing by DPI/96 (4K @ 300% stays sharp)
            bool created; using (var mx = new Mutex(true, @"Local\HwMonUI", out created))
            {
                if (!created) return 0;
                Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false); Application.Run(new Widget()); return 0;
            }
        }
    }
}