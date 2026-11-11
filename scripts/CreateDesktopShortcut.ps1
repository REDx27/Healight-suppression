$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $projectRoot "dist\GlareTracker-v1.3.exe"
$icon = $target
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPaths = @(
    (Join-Path $projectRoot "Launch_GlareTracker.lnk"),
    (Join-Path $desktop "GlareTracker.lnk")
)

if (-not (Test-Path $target)) {
    throw "dist\GlareTracker-v1.3.exe was not found. Build the application first."
}

$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in $shortcutPaths) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $target
    $shortcut.WorkingDirectory = Split-Path -Parent $target
    $shortcut.IconLocation = "$icon,0"
    $shortcut.Description = "Launch GlareTracker"
    $shortcut.Save()
    Write-Host "Created: $shortcutPath" -ForegroundColor Green
}
