@echo off
setlocal
cd /d "%~dp0.."

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-windows-exe.ps1" -InstallIfMissing
if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo EmailManagement.exe is ready in the project root.
pause
endlocal
