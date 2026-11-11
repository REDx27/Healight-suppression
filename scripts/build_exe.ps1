param(
    [switch]$SkipDependencies,
    [switch]$SkipSmokeTest
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$artifactName = "GlareTracker-v1.3.exe"
$artifactPath = Join-Path $projectRoot "dist\$artifactName"
$checksumPath = "$artifactPath.sha256"

Push-Location $projectRoot
try {
    if (-not $SkipDependencies) {
        py -3.13 -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    py -3.13 -m PyInstaller --clean --noconfirm scripts/glare_tracker.spec
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if (-not (Test-Path -LiteralPath $artifactPath)) {
        throw "Expected build artifact was not created: $artifactPath"
    }

    if (-not $SkipSmokeTest) {
        $process = Start-Process -FilePath $artifactPath `
            -ArgumentList "--release-smoke-test" -PassThru -WindowStyle Hidden
        if (-not $process.WaitForExit(20000)) {
            Stop-Process -Id $process.Id -Force
            throw "Standalone smoke test timed out after 20 seconds."
        }
        if ($process.ExitCode -ne 0) {
            throw "Standalone smoke test failed with exit code $($process.ExitCode)."
        }
    }

    $hash = Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256
    "$($hash.Hash.ToLowerInvariant())  $artifactName" |
        Set-Content -LiteralPath $checksumPath -Encoding ascii

    if (Get-Command iscc -ErrorAction SilentlyContinue) {
        iscc scripts/installer.iss
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    $sizeMb = [math]::Round((Get-Item -LiteralPath $artifactPath).Length / 1MB, 1)
    Write-Host ""
    Write-Host "Build complete: dist\$artifactName ($sizeMb MB)" -ForegroundColor Green
    if ($SkipSmokeTest) {
        Write-Host "Smoke test: skipped" -ForegroundColor Yellow
    }
    else {
        Write-Host "Smoke test: passed" -ForegroundColor Green
    }
    Write-Host "SHA-256: $($hash.Hash.ToLowerInvariant())" -ForegroundColor Green
    if (Test-Path .\installer-output\GlareTracker-v1.3-Setup.exe) {
        Write-Host "Installer complete: installer-output\GlareTracker-v1.3-Setup.exe" -ForegroundColor Green
    }
}
finally {
    Pop-Location
}
