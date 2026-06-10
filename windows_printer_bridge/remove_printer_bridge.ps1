#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$ListenAddress = "0.0.0.0",
    [string]$WindowsTailscaleAddress = "100.76.106.39",
    [int[]]$ListenPorts = @(9201, 9202, 9203)
)

$ErrorActionPreference = "Stop"
$firewallRuleName = "FastFoot Thermal Printer Bridge"
$cleanupListenAddresses = @($ListenAddress, $WindowsTailscaleAddress, "0.0.0.0") |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
    Select-Object -Unique

foreach ($port in $ListenPorts) {
    foreach ($cleanupAddress in $cleanupListenAddresses) {
        Write-Host "Portproxy siliniyor: $cleanupAddress`:$port"
        netsh interface portproxy delete v4tov4 `
            listenaddress=$cleanupAddress `
            listenport=$port 2>$null | Out-Null
    }
}

Get-NetFirewallRule -DisplayName $firewallRuleName -ErrorAction SilentlyContinue |
    Remove-NetFirewallRule

Write-Host "FastFoot termal yazici bridge kaldirildi." -ForegroundColor Green
