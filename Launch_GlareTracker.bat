@echo off
set "APP=%~dp0dist\GlareTracker.exe"

if not exist "%APP%" (
    echo GlareTracker.exe was not found in the dist folder.
    pause
    exit /b 1
)

start "" "%APP%"