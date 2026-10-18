<#
.SYNOPSIS
  Face pass helper (Windows: System.Drawing). Two modes:
    crop  - cut the square X,Y,Size out of -In and enlarge it to -Res x -Res (the inpainter then works on a close-up).
    paste - shrink -Patch back to Size x Size and blend it into -In at X,Y through a soft ellipse
            (centre -Cx,-Cy and radii -Rx,-Ry in pixels relative to the square): fully the patch inside
            -Inner of the radius, fading to the original picture at the ellipse edge. Writes -Out.
#>
param(
    [Parameter(Mandatory)] [ValidateSet('crop', 'paste')] [string] $Mode,
    [Parameter(Mandatory)] [string] $In,
    [Parameter(Mandatory)] [string] $Out,
    [Parameter(Mandatory)] [int] $X,
    [Parameter(Mandatory)] [int] $Y,
    [Parameter(Mandatory)] [int] $Size,
    [int] $Res = 960,
    [string] $Patch,
    [double] $Cx, [double] $Cy, [double] $Rx, [double] $Ry,
    [double] $Inner = 0.7
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

function Resize([System.Drawing.Image] $img, [System.Drawing.Rectangle] $from, [int] $w, [int] $h) {
    $bmp = New-Object System.Drawing.Bitmap $w, $h, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $attr = New-Object System.Drawing.Imaging.ImageAttributes
    $attr.SetWrapMode([System.Drawing.Drawing2D.WrapMode]::TileFlipXY)  # no dark fringe at the edges
    $g.DrawImage($img, (New-Object System.Drawing.Rectangle 0, 0, $w, $h), $from.X, $from.Y, $from.Width, $from.Height,
        [System.Drawing.GraphicsUnit]::Pixel, $attr)
    $g.Dispose()
    return $bmp
}

function Load([string] $path) {
    # From memory, not FromFile: FromFile keeps the file locked, so -Out could not overwrite -In
    $stream = New-Object System.IO.MemoryStream (, [System.IO.File]::ReadAllBytes((Resolve-Path $path).Path))
    return [System.Drawing.Image]::FromStream($stream)
}

$src = Load $In
try {
    if ($Mode -eq 'crop') {
        $bmp = Resize $src (New-Object System.Drawing.Rectangle $X, $Y, $Size, $Size) $Res $Res
        $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
        "crop {0}x{0} at {1},{2} -> {3}x{3}" -f $Size, $X, $Y, $Res
        return
    }
    if (-not ('FacePatch.Blend' -as [type])) {
        Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System; using System.Drawing; using System.Drawing.Imaging; using System.Runtime.InteropServices;
namespace FacePatch {
  public static class Blend {
    public static void Ellipse(Bitmap dst, Bitmap patch, int x0, int y0, double cx, double cy, double rx, double ry, double inner) {
      var rd = new Rectangle(x0, y0, patch.Width, patch.Height);
      var d = dst.LockBits(rd, ImageLockMode.ReadWrite, PixelFormat.Format32bppArgb);
      var p = patch.LockBits(new Rectangle(0, 0, patch.Width, patch.Height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
      var db = new byte[d.Stride * patch.Height]; var pb = new byte[p.Stride * patch.Height];
      Marshal.Copy(d.Scan0, db, 0, db.Length); Marshal.Copy(p.Scan0, pb, 0, pb.Length);
      for (int y = 0; y < patch.Height; y++) for (int x = 0; x < patch.Width; x++) {
        double dx = (x + 0.5 - cx) / rx, dy = (y + 0.5 - cy) / ry, r = Math.Sqrt(dx * dx + dy * dy);
        double a = r <= inner ? 1.0 : (r >= 1.0 ? 0.0 : (1.0 - r) / (1.0 - inner));
        if (a <= 0) continue;
        a = a * a * (3 - 2 * a);  // smoothstep: no visible ring
        int i = y * d.Stride + x * 4, j = y * p.Stride + x * 4;
        for (int c = 0; c < 3; c++) db[i + c] = (byte)Math.Round(db[i + c] * (1 - a) + pb[j + c] * a);
      }
      Marshal.Copy(db, 0, d.Scan0, db.Length);
      dst.UnlockBits(d); patch.UnlockBits(p);
    }
  }
}
'@
    }
    $base = ([System.Drawing.Bitmap]$src).Clone((New-Object System.Drawing.Rectangle 0, 0, $src.Width, $src.Height),
        [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)  # exact pixel copy (a redraw would re-apply gamma)
    $pimg = Load $Patch
    try { $small = Resize $pimg (New-Object System.Drawing.Rectangle 0, 0, $pimg.Width, $pimg.Height) $Size $Size } finally { $pimg.Dispose() }
    [FacePatch.Blend]::Ellipse($base, $small, $X, $Y, $Cx, $Cy, $Rx, $Ry, $Inner)
    $small.Dispose()
    $src.Dispose(); $src = $null
    $base.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png); $base.Dispose()
    "paste {0}x{0} at {1},{2}" -f $Size, $X, $Y
} finally {
    if ($src) { $src.Dispose() }
}
