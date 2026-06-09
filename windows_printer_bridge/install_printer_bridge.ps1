#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$ListenAddress = "100.76.106.39",
    [string]$AllowedRemoteAddress = "100.127.221.60",
    [int]$KasaPort = 9201,
    [int]$IzgaraPort = 9202,
    [int]$MutfakPort = 9203,
    [int]$PrinterPort = 9100,
    [bool]$RegisterStartupTask = $true
)

$ErrorActionPreference = "Stop"
$firewallRuleName = "FastFoot Thermal Printer Bridge"
$taskName = "FastFoot Thermal Printer Bridge"

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

Write-Host "FastFoot termal yazici bridge kuruluyor..." -ForegroundColor Cyan
Write-Host "Dinleme IP: $ListenAddress"
Write-Host "Izinli uzak sunucu: $AllowedRemoteAddress"

Set-Service -Name iphlpsvc -StartupType Automatic
Start-Service -Name iphlpsvc

foreach ($rule in $bridgeRules) {
    Write-Host "Portproxy: $ListenAddress`:$($rule.ListenPort) -> $($rule.TargetAddress)`:$($rule.TargetPort)"
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
        "-RegisterStartupTask:`$false"
    ) -join " "

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $taskArgs
    $triggerStartup = New-ScheduledTaskTrigger -AtStartup
    $triggerLogon = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $triggerStartup,$triggerLogon `
        -Principal $principal `
        -Settings $settings `
        -Force | Out-Null
}

Write-Host ""
Write-Host "Kurulum tamamlandi." -ForegroundColor Green
if ($RegisterStartupTask) {
    Write-Host "Baslangic gorevi kuruldu: $taskName" -ForegroundColor Green
}
Write-Host "Aktif portproxy kurallari:"
netsh interface portproxy show v4tov4

Write-Host ""
Write-Host "Yazicilari test etmek icin:"
Write-Host ".\test_printer_bridge.ps1"
