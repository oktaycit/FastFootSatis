@echo off
setlocal EnableExtensions

set "PORT=8787"
set "BASE_DIR=C:\FastFootOkcBridge\windows_okc_bridge"
set "EXE=%BASE_DIR%\bin\Release\FastFootOkcBridge.exe"

if not "%~1"=="" set "PORT=%~1"

echo.
echo FastFoot OKC Bridge runner
echo EXE : %EXE%
echo PORT: %PORT%
echo.

if not exist "%EXE%" (
    echo ERROR: Bridge exe bulunamadi.
    echo Once su komutu calistirin:
    echo C:\FastFootOkcBridge\build_from_server.bat
    exit /b 1
)

net session >nul 2>&1
if errorlevel 1 (
    echo Not: Yonetici degil. URL/firewall izinleri zaten ekli degilse bridge acilmayabilir.
) else (
    netsh http show urlacl url=http://+:%PORT%/ >nul 2>&1
    if errorlevel 1 netsh http add urlacl url=http://+:%PORT%/ user=Everyone

    netsh advfirewall firewall show rule name="FastFoot OKC Bridge %PORT%" >nul 2>&1
    if errorlevel 1 netsh advfirewall firewall add rule name="FastFoot OKC Bridge %PORT%" dir=in action=allow protocol=TCP localport=%PORT%
)

echo.
echo Bridge baslatiliyor. Bu pencere acik kalmali.
echo Test icin ikinci PowerShell:
echo curl.exe http://localhost:%PORT%/health
echo.

"%EXE%" %PORT%
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo Bridge kapandi. Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%
