@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SERVER_USER=oktay"
set "SERVER_HOST=100.127.221.60"
set "REMOTE_DIR=/home/oktay/restoran/windows_okc_bridge"
set "LOCAL_DIR=C:\FastFootOkcBridge"
set "PORT=8787"

if not "%~1"=="" set "SERVER_HOST=%~1"
if not "%~2"=="" set "SERVER_USER=%~2"
if not "%~3"=="" set "LOCAL_DIR=%~3"

set "SRC_DIR=%LOCAL_DIR%\windows_okc_bridge"

echo.
echo FastFoot OKC Bridge build helper
echo Server: %SERVER_USER%@%SERVER_HOST%:%REMOTE_DIR%
echo Local : %SRC_DIR%
echo.

where scp >nul 2>&1
if errorlevel 1 (
    echo ERROR: scp bulunamadi.
    echo Windows 10 OpenSSH Client'i etkinlestirin veya Git for Windows kurun.
    echo Ayarlar ^> Apps ^> Optional features ^> OpenSSH Client
    exit /b 1
)

if not exist "%LOCAL_DIR%" mkdir "%LOCAL_DIR%"
if not exist "%SRC_DIR%" mkdir "%SRC_DIR%"
if not exist "%SRC_DIR%\lib" mkdir "%SRC_DIR%\lib"

echo Kaynak dosyalari sunucudan cekiliyor...
scp "%SERVER_USER%@%SERVER_HOST%:%REMOTE_DIR%/OkcBridgeServer.cs" "%SRC_DIR%\OkcBridgeServer.cs" || exit /b 1
scp "%SERVER_USER%@%SERVER_HOST%:%REMOTE_DIR%/OkcBridgeServer.csproj" "%SRC_DIR%\OkcBridgeServer.csproj" || exit /b 1
scp "%SERVER_USER%@%SERVER_HOST%:%REMOTE_DIR%/README.md" "%SRC_DIR%\README.md" >nul 2>&1

if not exist "%SRC_DIR%\lib\IntegrationHub.dll" (
    echo IntegrationHub.dll araniyor...
    if defined INTEGRATIONHUB_DLL (
        if exist "%INTEGRATIONHUB_DLL%" copy /Y "%INTEGRATIONHUB_DLL%" "%SRC_DIR%\lib\IntegrationHub.dll" >nul
    )
)

if not exist "%SRC_DIR%\lib\IntegrationHub.dll" (
    for %%D in (
        "C:\ERP12\IntegrationHub.dll"
        "C:\Program Files (x86)\Token\ERP12\IntegrationHub.dll"
        "C:\Program Files\Token\ERP12\IntegrationHub.dll"
        "C:\Program Files (x86)\Arcelik\ERP12\IntegrationHub.dll"
        "C:\Program Files\Arcelik\ERP12\IntegrationHub.dll"
        "C:\Program Files (x86)\Beko\ERP12\IntegrationHub.dll"
        "C:\Program Files\Beko\ERP12\IntegrationHub.dll"
    ) do (
        if exist "%%~D" copy /Y "%%~D" "%SRC_DIR%\lib\IntegrationHub.dll" >nul
    )
)

if not exist "%SRC_DIR%\lib\IntegrationHub.dll" (
    echo.
    echo ERROR: IntegrationHub.dll bulunamadi.
    echo Bu DLL'i POS/Token kurulum klasorunden su konuma koyun:
    echo %SRC_DIR%\lib\IntegrationHub.dll
    echo.
    echo Alternatif:
    echo set INTEGRATIONHUB_DLL=C:\ERP12\IntegrationHub.dll
    echo %~nx0
    exit /b 2
)

set "MSBUILD="
if defined MSBUILD_EXE if exist "%MSBUILD_EXE%" set "MSBUILD=%MSBUILD_EXE%"

if not defined MSBUILD (
    set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
    if exist "!VSWHERE!" (
        for /f "usebackq delims=" %%M in (`"!VSWHERE!" -latest -requires Microsoft.Component.MSBuild -find "MSBuild\**\Bin\MSBuild.exe" 2^>nul`) do (
            if not defined MSBUILD set "MSBUILD=%%M"
        )
    )
)

if not defined MSBUILD (
    for %%M in (
        "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe"
        "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe"
        "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\Professional\MSBuild\Current\Bin\MSBuild.exe"
        "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\Enterprise\MSBuild\Current\Bin\MSBuild.exe"
        "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\BuildTools\MSBuild\Current\Bin\MSBuild.exe"
        "%ProgramFiles(x86)%\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\MSBuild.exe"
        "%WINDIR%\Microsoft.NET\Framework\v4.0.30319\MSBuild.exe"
    ) do (
        if exist "%%~M" if not defined MSBUILD set "MSBUILD=%%~M"
    )
)

if not defined MSBUILD (
    echo.
    echo ERROR: MSBuild bulunamadi.
    echo Visual Studio Build Tools yukleyin ve ".NET desktop build tools" secin.
    echo https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
    exit /b 3
)

echo.
echo MSBuild: %MSBUILD%
echo Derleme basliyor...
"%MSBUILD%" "%SRC_DIR%\OkcBridgeServer.csproj" /t:Build /p:Configuration=Release /p:Platform=x86 /p:PlatformTarget=x86 /verbosity:minimal
if errorlevel 1 exit /b 4

set "EXE=%SRC_DIR%\bin\Release\FastFootOkcBridge.exe"
if not exist "%EXE%" (
    echo ERROR: Derleme bitti ama exe bulunamadi: %EXE%
    exit /b 5
)

copy /Y "%SRC_DIR%\lib\*.dll" "%SRC_DIR%\bin\Release\" >nul 2>&1

echo.
echo Derleme tamam:
echo %EXE%
echo.

net session >nul 2>&1
if errorlevel 1 (
    echo 8787 izinleri icin bu dosyayi Yonetici olarak calistirin veya su komutlari Admin PowerShell'de calistirin:
    echo netsh http add urlacl url=http://+:%PORT%/ user=Everyone
    echo netsh advfirewall firewall add rule name="FastFoot OKC Bridge %PORT%" dir=in action=allow protocol=TCP localport=%PORT%
) else (
    netsh http show urlacl url=http://+:%PORT%/ >nul 2>&1
    if errorlevel 1 netsh http add urlacl url=http://+:%PORT%/ user=Everyone

    netsh advfirewall firewall show rule name="FastFoot OKC Bridge %PORT%" >nul 2>&1
    if errorlevel 1 netsh advfirewall firewall add rule name="FastFoot OKC Bridge %PORT%" dir=in action=allow protocol=TCP localport=%PORT%
)

echo.
echo Calistirma komutu:
echo "%EXE%" %PORT%
echo.
echo Test:
echo curl http://localhost:%PORT%/health
echo.
endlocal
