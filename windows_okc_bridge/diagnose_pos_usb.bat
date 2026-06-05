@echo off
setlocal EnableExtensions

set "PORT=8787"
set "OUT=%TEMP%\fastfoot_pos_usb_diag.txt"

echo FastFoot POS USB diagnostic > "%OUT%"
echo Generated: %DATE% %TIME% >> "%OUT%"
echo Computer: %COMPUTERNAME% >> "%OUT%"
echo User: %USERNAME% >> "%OUT%"
echo. >> "%OUT%"

echo === Bridge processes === >> "%OUT%"
tasklist /FI "IMAGENAME eq FastFootOkcBridge.exe" /V >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo === Port %PORT% owner === >> "%OUT%"
netstat -ano | findstr ":%PORT%" >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo === POS / Token / USB related processes === >> "%OUT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-Process | Where-Object { $_.ProcessName -match 'FastFoot|Token|Beko|Arcelik|Arcelik|ERP|OKC|POS|Ingenico|Integration|libusb|java' } | Select-Object Id,ProcessName,Path | Format-Table -AutoSize" >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo === POS / Token / USB related services === >> "%OUT%"
sc query type= service state= all | findstr /I "Token Beko Arcelik ERP OKC POS Ingenico Integration USB" >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo === USB / Android / POS PnP devices === >> "%OUT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_PnPEntity | Where-Object { ($_.Name -match 'Android|Beko|Arcelik|Token|POS|Ingenico|WinUSB|libusb|X30|USB') -or ($_.DeviceID -match 'VID_18D1|VID_13A1|VID_1A40|VID_04E8|VID_0BDA|VID_067B|VID_1133|VID_29B5|VID_18D1|VID_6353') } | Select-Object Status,ClassGuid,Name,Manufacturer,DeviceID | Format-List" >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo === Installed drivers matching POS keywords === >> "%OUT%"
pnputil /enum-drivers | findstr /I "Token Beko Arcelik POS Ingenico Android WinUSB libusb" >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo === Recent system errors mentioning USB/POS keywords === >> "%OUT%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=(Get-Date).AddHours(-6)} -ErrorAction SilentlyContinue | Where-Object { $_.Message -match 'USB|Android|WinUSB|libusb|Token|Beko|Arcelik|POS|Ingenico' } | Select-Object -First 30 TimeCreated,ProviderName,Id,Message | Format-List" >> "%OUT%" 2>&1
echo. >> "%OUT%"

echo Diagnostic file:
echo %OUT%
echo.
type "%OUT%"

endlocal
