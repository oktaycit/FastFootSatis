[CmdletBinding()]
param(
    [string]$ListenAddress = "100.76.106.39",
    [int]$KasaPort = 9201,
    [int]$IzgaraPort = 9202,
    [int]$MutfakPort = 9203,
    [int]$PrinterPort = 9100
)

$targets = @(
    [pscustomobject]@{ Name = "kasa-tatli-icecek"; Address = "192.168.1.201"; Port = $PrinterPort; BridgePort = $KasaPort },
    [pscustomobject]@{ Name = "izgara"; Address = "192.168.1.202"; Port = $PrinterPort; BridgePort = $IzgaraPort },
    [pscustomobject]@{ Name = "mutfak"; Address = "192.168.1.203"; Port = $PrinterPort; BridgePort = $MutfakPort }
)

Write-Host "Lokal yazici portlari test ediliyor..." -ForegroundColor Cyan
foreach ($target in $targets) {
    $result = Test-NetConnection -ComputerName $target.Address -Port $target.Port -InformationLevel Quiet
    $status = if ($result) { "OK" } else { "FAIL" }
    Write-Host "$($target.Name): $($target.Address):$($target.Port) $status"
}

Write-Host ""
Write-Host "Windows bridge dinleme portlari test ediliyor..." -ForegroundColor Cyan
foreach ($target in $targets) {
    $result = Test-NetConnection -ComputerName $ListenAddress -Port $target.BridgePort -InformationLevel Quiet
    $status = if ($result) { "OK" } else { "FAIL" }
    Write-Host "$($target.Name): $ListenAddress`:$($target.BridgePort) $status"
}

Write-Host ""
Write-Host "Portproxy kurallari:"
netsh interface portproxy show v4tov4
