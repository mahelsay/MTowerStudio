<#
.SYNOPSIS
  Center-crop an image to the target aspect ratio and resize it (default 1280x720, the keyframe size).
  Used by 'mtower import' for images made outside the engine (e.g. ChatGPT). PNG/JPEG/BMP input.
#>
param(
    [Parameter(Mandatory)] [string] $In,
    [Parameter(Mandatory)] [string] $Out,
    [int] $Width = 1280,
    [int] $Height = 720
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Image]::FromFile((Resolve-Path $In).Path)
try {
    $target = $Width / $Height
    if ($src.Width / $src.Height -gt $target) {
        $h = $src.Height; $w = [int][math]::Round($h * $target); $x = [int](($src.Width - $w) / 2); $y = 0
    } else {
        $w = $src.Width; $h = [int][math]::Round($w / $target); $x = 0; $y = [int](($src.Height - $h) / 2)
    }
    $bmp = New-Object System.Drawing.Bitmap $Width, $Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.DrawImage($src, (New-Object System.Drawing.Rectangle 0, 0, $Width, $Height), (New-Object System.Drawing.Rectangle $x, $y, $w, $h), [System.Drawing.GraphicsUnit]::Pixel)
    $g.Dispose()
    $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    "{0}x{1} -> {2}x{3} (crop {4}x{5} at {6},{7})" -f $src.Width, $src.Height, $Width, $Height, $w, $h, $x, $y
} finally {
    $src.Dispose()
}
