@echo off
setlocal EnableExtensions

set "BASE_DIR=%~dp0"
set "INSTALL_SCRIPT=%BASE_DIR%install_printer_bridge.ps1"
set "TEST_SCRIPT=%BASE_DIR%test_printer_bridge.ps1"

echo.
echo FastFootPrinterBridge
echo Klasor: %BASE_DIR%
echo.

net session >nul 2>&1
if errorlevel 1 (
    echo Yonetici izni isteniyor...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -WorkingDirectory '%~dp0' -Verb RunAs"
    exit /b
)

if not exist "%INSTALL_SCRIPT%" (
    echo ERROR: install_printer_bridge.ps1 bulunamadi.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%INSTALL_SCRIPT%"
if errorlevel 1 (
    echo.
    echo ERROR: Bridge kurulumu/baslatma basarisiz.
    pause
    exit /b 2
)

echo.
if exist "%TEST_SCRIPT%" (
    echo Bridge test ediliyor...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TEST_SCRIPT%"
) else (
    echo test_printer_bridge.ps1 bulunamadi, test atlandi.
)

echo.
echo FastFootPrinterBridge hazir. Bu pencereyi kapatabilirsiniz.
pause
endlocal
