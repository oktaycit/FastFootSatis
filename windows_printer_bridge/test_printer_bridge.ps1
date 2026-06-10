[CmdletBinding()]
param(
    [string]$ListenAddress = "100.76.106.39",
    [int]$KasaPort = 9201,
    [int]$IzgaraPort = 9202,
    [int]$MutfakPort = 9203,
    [int]$PrinterPort = 9100,
    [int]$Retries = 1,
    [int]$RetryDelaySeconds = 5
)

$targets = @(
    [pscustomobject]@{ Name = "kasa-tatli-icecek"; Address = "192.168.1.201"; Port = $PrinterPort; BridgePort = $KasaPort },
    [pscustomobject]@{ Name = "izgara"; Address = "192.168.1.202"; Port = $PrinterPort; BridgePort = $IzgaraPort },
    [pscustomobject]@{ Name = "mutfak"; Address = "192.168.1.203"; Port = $PrinterPort; BridgePort = $MutfakPort }
)

function Test-PortWithRetry {
    param(
        [string]$ComputerName,
        [int]$Port
    )

    $attempts = [Math]::Max(1, $Retries)
    for ($attempt = 1; $attempt -le $attempts; $attempt++) {
        if (Test-NetConnection -ComputerName $ComputerName -Port $Port -InformationLevel Quiet) {
            return $true
        }

        if ($attempt -lt $attempts) {
            Start-Sleep -Seconds $RetryDelaySeconds
        }
    }

    return $false
}

Write-Host "Lokal yazici portlari test ediliyor..." -ForegroundColor Cyan
foreach ($target in $targets) {
    $result = Test-PortWithRetry -ComputerName $target.Address -Port $target.Port
    $status = if ($result) { "OK" } else { "FAIL" }
    Write-Host "$($target.Name): $($target.Address):$($target.Port) $status"
}

Write-Host ""
Write-Host "Windows bridge dinleme portlari test ediliyor..." -ForegroundColor Cyan
foreach ($target in $targets) {
    $result = Test-PortWithRetry -ComputerName $ListenAddress -Port $target.BridgePort
    $status = if ($result) { "OK" } else { "FAIL" }
    Write-Host "$($target.Name): $ListenAddress`:$($target.BridgePort) $status"
}

Write-Host ""
Write-Host "Portproxy kurallari:"
netsh interface portproxy show v4tov4
