# capture_window.ps1 - screenshot of the widget window (BitBlt with CAPTUREBLT, needed because the widget is a layered/translucent window).
param([string]$Out)
Add-Type -AssemblyName System.Drawing
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public class W32 { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); [DllImport("user32.dll")] public static extern IntPtr FindWindow(string c, string t); [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern IntPtr GetDC(IntPtr h); [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr h, IntPtr dc);
 [DllImport("gdi32.dll")] public static extern bool BitBlt(IntPtr d, int x, int y, int w, int h, IntPtr s, int sx, int sy, int rop);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; } }
"@
[void][W32]::SetProcessDPIAware(); $h=[W32]::FindWindow([NullString]::Value,'HwMonUI'); if($h -eq [IntPtr]::Zero){ Write-Host 'window not found'; exit 1 }
$r=New-Object W32+RECT; [void][W32]::GetWindowRect($h,[ref]$r); $w=$r.R-$r.L; $ht=$r.B-$r.T
$bmp=New-Object Drawing.Bitmap $w,$ht; $g=[Drawing.Graphics]::FromImage($bmp); $hd=$g.GetHdc(); $sd=[W32]::GetDC([IntPtr]::Zero)
[void][W32]::BitBlt($hd,0,0,$w,$ht,$sd,$r.L,$r.T,0x40CC0020); [void][W32]::ReleaseDC([IntPtr]::Zero,$sd); $g.ReleaseHdc($hd); $g.Dispose()
$bmp.Save($Out,[Drawing.Imaging.ImageFormat]::Png); Write-Host "captured ${w}x${ht} at $($r.L),$($r.T)"

