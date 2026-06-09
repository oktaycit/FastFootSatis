@echo off
setlocal EnableExtensions

set "SERVER_USER=oktay"
set "SERVER_HOST=100.127.221.60"
set "REMOTE_DIR=/home/oktay/restoran/windows_printer_bridge"
set "LOCAL_DIR=C:\FastFootPrinterBridge"

if not "%~1"=="" set "SERVER_HOST=%~1"
if not "%~2"=="" set "SERVER_USER=%~2"
if not "%~3"=="" set "LOCAL_DIR=%~3"

echo.
echo FastFoot Thermal Printer Bridge setup
echo Server: %SERVER_USER%@%SERVER_HOST%:%REMOTE_DIR%
echo Local : %LOCAL_DIR%
echo.

where scp >nul 2>&1
if errorlevel 1 (
    echo ERROR: scp bulunamadi.
    echo Windows OpenSSH Client'i etkinlestirin veya Git for Windows kurun.
    exit /b 1
)

if not exist "%LOCAL_DIR%" mkdir "%LOCAL_DIR%"

echo Scriptler sunucudan cekiliyor...
scp "%SERVER_USER%@%SERVER_HOST%:%REMOTE_DIR%/install_printer_bridge.ps1" "%LOCAL_DIR%\install_printer_bridge.ps1" || exit /b 1
scp "%SERVER_USER%@%SERVER_HOST%:%REMOTE_DIR%/test_printer_bridge.ps1" "%LOCAL_DIR%\test_printer_bridge.ps1" || exit /b 1
scp "%SERVER_USER%@%SERVER_HOST%:%REMOTE_DIR%/remove_printer_bridge.ps1" "%LOCAL_DIR%\remove_printer_bridge.ps1" || exit /b 1
scp "%SERVER_USER%@%SERVER_HOST%:%REMOTE_DIR%/start_printer_bridge.bat" "%LOCAL_DIR%\start_printer_bridge.bat" || exit /b 1
scp "%SERVER_USER%@%SERVER_HOST%:%REMOTE_DIR%/create_desktop_shortcut.ps1" "%LOCAL_DIR%\create_desktop_shortcut.ps1" || exit /b 1
scp "%SERVER_USER%@%SERVER_HOST%:%REMOTE_DIR%/README.md" "%LOCAL_DIR%\README.md" >nul 2>&1

net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Bu dosyayi Yonetici olarak calistirin.
    echo PowerShell/CMD uzerinde "Run as administrator" kullanin.
    exit /b 2
)

echo.
echo Printer bridge kuruluyor...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%LOCAL_DIR%\install_printer_bridge.ps1"
if errorlevel 1 exit /b 3

echo.
echo Masaustu kisayolu hazirlaniyor...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%LOCAL_DIR%\create_desktop_shortcut.ps1" -InstallDir "%LOCAL_DIR%"
if errorlevel 1 (
    echo UYARI: Masaustu kisayolu olusturulamadi.
    echo Manuel komut:
    echo powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%LOCAL_DIR%\create_desktop_shortcut.ps1" -InstallDir "%LOCAL_DIR%" -CurrentUser
)

echo.
echo Test komutu:
echo powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%LOCAL_DIR%\test_printer_bridge.ps1"
echo.
echo Masaustu kisayolu:
echo FastFootPrinterBridge
echo.

endlocal
