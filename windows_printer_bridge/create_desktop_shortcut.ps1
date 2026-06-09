[CmdletBinding()]
param(
    [string]$InstallDir = "C:\FastFootPrinterBridge",
    [string]$ShortcutName = "FastFootPrinterBridge.lnk",
    [switch]$CurrentUser
)

$ErrorActionPreference = "Stop"

$targetPath = Join-Path $InstallDir "start_printer_bridge.bat"
if (-not (Test-Path $targetPath)) {
    throw "Shortcut target bulunamadi: $targetPath"
}

$desktopPath = if ($CurrentUser) {
    [Environment]::GetFolderPath("Desktop")
} else {
    [Environment]::GetFolderPath("CommonDesktopDirectory")
}

if ([string]::IsNullOrWhiteSpace($desktopPath)) {
    $desktopPath = [Environment]::GetFolderPath("Desktop")
}

$shortcutPath = Join-Path $desktopPath $ShortcutName

try {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $targetPath
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.Description = "FastFoot termal yazici bridge baslat/test et"
    $shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,16"
    $shortcut.Save()
} catch {
    if (-not $CurrentUser) {
        Write-Warning "Ortak masaustune kisayol olusturulamadi, kullanici masaustu deneniyor: $($_.Exception.Message)"
        & $PSCommandPath -InstallDir $InstallDir -ShortcutName $ShortcutName -CurrentUser
        return
    }

    throw
}

Write-Host "Masaustu kisayolu hazir: $shortcutPath" -ForegroundColor Green
