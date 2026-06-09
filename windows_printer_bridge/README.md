# FastFoot Termal Yazici Bridge

Bu klasordeki PowerShell scriptleri Windows makineyi termal yazici TCP koprusu olarak kullanir.
FastFoot sunucusu Tailscale uzerinden Windows makineye baglanir, Windows da lokal agdaki termal
yazicilara `9100` portundan ham ESC/POS verisini iletir.

## Eslesme

- `100.76.106.39:9201` -> `192.168.1.201:9100` kasa, tatli, icecek
- `100.76.106.39:9202` -> `192.168.1.202:9100` izgara
- `100.76.106.39:9203` -> `192.168.1.203:9100` mutfak

FastFoot sunucusu Tailscale IP'si: `100.127.221.60`
Windows Tailscale IP'si: `100.76.106.39`

## Kurulum

Windows makinede PowerShell'i Yonetici olarak acin ve bu klasorde calistirin:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
.\install_printer_bridge.ps1
```

Kurulum `netsh interface portproxy` kullanir ve kalicidir. Windows yeniden baslasa bile
kurallar durur; IP Helper servisi otomatik baslatilir.

## Test

```powershell
.\test_printer_bridge.ps1
```

Lokal yazici portlari `OK`, bridge portlari da `OK` gorunmelidir.

## Kaldirma

```powershell
.\remove_printer_bridge.ps1
```

## Sunucu Ayari

FastFoot ayarlarinda IP termal yazicilar dogrudan `192.168.1.x` yerine Windows Tailscale IP'sine
yonlendirilmelidir:

- kasa/hesap, tatli, icecek: `100.76.106.39`, port `9201`
- izgara: `100.76.106.39`, port `9202`
- mutfak: `100.76.106.39`, port `9203`
