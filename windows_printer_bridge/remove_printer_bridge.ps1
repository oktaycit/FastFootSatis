#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$ListenAddress = "100.76.106.39",
    [int[]]$ListenPorts = @(9201, 9202, 9203)
)

$ErrorActionPreference = "Stop"
$firewallRuleName = "FastFoot Thermal Printer Bridge"

foreach ($port in $ListenPorts) {
    Write-Host "Portproxy siliniyor: $ListenAddress`:$port"
    netsh interface portproxy delete v4tov4 `
        listenaddress=$ListenAddress `
        listenport=$port 2>$null | Out-Null
}

Get-NetFirewallRule -DisplayName $firewallRuleName -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule

Write-Host "FastFoot termal yazici bridge kaldirildi." -ForegroundColor Green
