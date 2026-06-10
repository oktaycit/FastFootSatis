#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$ListenAddress = "100.76.106.39",
    [string]$AllowedRemoteAddress = "100.127.221.60",
    [int]$KasaPort = 9201,
    [int]$IzgaraPort = 9202,
    [int]$MutfakPort = 9203,
    [int]$PrinterPort = 9100,
    [bool]$RegisterStartupTask = $true,
    [int]$StartupDelaySeconds = 0,
    [int]$NetworkWaitSeconds = 90,
    [string]$LogPath = "$env:ProgramData\FastFootPrinterBridge\printer_bridge.log"
)

$ErrorActionPreference = "Stop"
$firewallRuleName = "FastFoot Thermal Printer Bridge"
$taskName = "FastFoot Thermal Printer Bridge"

if ($LogPath) {
    $logDir = Split-Path -Parent $LogPath
    if ($logDir) {
        New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    }
}

function Write-BridgeLog {
    param(
        [string]$Message,
        [string]$ForegroundColor
    )

    if ($ForegroundColor) {
        Write-Host $Message -ForegroundColor $ForegroundColor
    } else {
        Write-Host $Message
    }

    if ($LogPath) {
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $LogPath -Value "[$timestamp] $Message" -Encoding UTF8
    }
}

function Test-ListenAddressReady {
    if ($ListenAddress -in @("0.0.0.0", "*", "+")) {
        return $true
    }

    $ip = Get-NetIPAddress -AddressFamily IPv4 -IPAddress $ListenAddress -ErrorAction SilentlyContinue
    return $null -ne $ip
}

function Wait-ForListenAddress {
    if (Test-ListenAddressReady) {
        return $true
    }

    $deadline = (Get-Date).AddSeconds([Math]::Max(0, $NetworkWaitSeconds))
    while ((Get-Date) -lt $deadline) {
        Write-BridgeLog "Dinleme IP henuz hazir degil: $ListenAddress. Bekleniyor..."
        Start-Sleep -Seconds 5
        if (Test-ListenAddressReady) {
            return $true
        }
    }

    Write-BridgeLog "UYARI: Dinleme IP Windows uzerinde gorunmedi: $ListenAddress. Kurallar yine de yenilenecek." "Yellow"
    return $false
}

$bridgeRules = @(
    [pscustomobject]@{
        Name = "kasa-tatli-icecek"
        ListenPort = $KasaPort
        TargetAddress = "192.168.1.201"
        TargetPort = $PrinterPort
    },
    [pscustomobject]@{
        Name = "izgara"
        ListenPort = $IzgaraPort
        TargetAddress = "192.168.1.202"
        TargetPort = $PrinterPort
    },
    [pscustomobject]@{
        Name = "mutfak"
        ListenPort = $MutfakPort
        TargetAddress = "192.168.1.203"
        TargetPort = $PrinterPort
    }
)

Write-BridgeLog "FastFoot termal yazici bridge kuruluyor..." "Cyan"
Write-BridgeLog "Dinleme IP: $ListenAddress"
Write-BridgeLog "Izinli uzak sunucu: $AllowedRemoteAddress"

if ($StartupDelaySeconds -gt 0) {
    Write-BridgeLog "Baslangic gecikmesi: $StartupDelaySeconds saniye"
    Start-Sleep -Seconds $StartupDelaySeconds
}

Wait-ForListenAddress | Out-Null

Set-Service -Name iphlpsvc -StartupType Automatic
Start-Service -Name iphlpsvc

foreach ($rule in $bridgeRules) {
    Write-BridgeLog "Portproxy: $ListenAddress`:$($rule.ListenPort) -> $($rule.TargetAddress)`:$($rule.TargetPort)"
    netsh interface portproxy delete v4tov4 `
        listenaddress=$ListenAddress `
        listenport=$($rule.ListenPort) 2>$null | Out-Null

    netsh interface portproxy add v4tov4 `
        listenaddress=$ListenAddress `
        listenport=$($rule.ListenPort) `
        connectaddress=$($rule.TargetAddress) `
        connectport=$($rule.TargetPort) | Out-Null
}

Get-NetFirewallRule -DisplayName $firewallRuleName -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule

New-NetFirewallRule `
    -DisplayName $firewallRuleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalAddress $ListenAddress `
    -LocalPort $KasaPort,$IzgaraPort,$MutfakPort `
    -RemoteAddress $AllowedRemoteAddress | Out-Null

if ($RegisterStartupTask) {
    $scriptPath = $PSCommandPath
    $taskArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$scriptPath`"",
        "-ListenAddress", $ListenAddress,
        "-AllowedRemoteAddress", $AllowedRemoteAddress,
        "-KasaPort", $KasaPort,
        "-IzgaraPort", $IzgaraPort,
        "-MutfakPort", $MutfakPort,
        "-PrinterPort", $PrinterPort,
        "-StartupDelaySeconds", 45,
        "-NetworkWaitSeconds", $NetworkWaitSeconds,
        "-LogPath", "`"$LogPath`"",
        "-RegisterStartupTask:`$false"
    ) -join " "

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $taskArgs
    $triggerStartup = New-ScheduledTaskTrigger -AtStartup
    $triggerLogon = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -StartWhenAvailable

    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $triggerStartup,$triggerLogon `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null
}

Write-BridgeLog ""
Write-BridgeLog "Kurulum tamamlandi." "Green"
if ($RegisterStartupTask) {
    Write-BridgeLog "Baslangic gorevi kuruldu: $taskName" "Green"
}
Write-BridgeLog "Aktif portproxy kurallari:"
netsh interface portproxy show v4tov4

Write-BridgeLog ""
Write-BridgeLog "Log dosyasi: $LogPath"
Write-BridgeLog "Yazicilari test etmek icin:"
Write-BridgeLog ".\test_printer_bridge.ps1 -Retries 6 -RetryDelaySeconds 10"
