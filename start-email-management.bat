@echo off
setlocal

cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local.ps1"
if errorlevel 1 (
    echo.
    echo Service exited with an error. Press any key to close.
    pause >nul
    exit /b 1
)

echo.
echo Email Management has stopped.
pause
endlocal
