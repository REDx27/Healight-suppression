$ErrorActionPreference = "Continue"

python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m PyInstaller --clean --noconfirm glare_tracker.spec 2>&1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Build complete: dist\GlareTracker.exe" -ForegroundColor Green