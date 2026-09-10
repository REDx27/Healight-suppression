$ErrorActionPreference = "Continue"

python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m PyInstaller --clean --noconfirm glare_tracker.spec 2>&1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Copy-Item .\dist\GlareTracker.exe .\GlareTracker.exe -Force

if (Get-Command iscc -ErrorAction SilentlyContinue) {
	iscc installer.iss
	if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host ""
Write-Host "Build complete: dist\GlareTracker.exe" -ForegroundColor Green
if (Test-Path .\installer-output\GlareTracker-Setup.exe) {
	Write-Host "Installer complete: installer-output\GlareTracker-Setup.exe" -ForegroundColor Green
}