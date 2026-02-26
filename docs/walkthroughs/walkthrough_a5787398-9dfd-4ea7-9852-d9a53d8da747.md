# Ayarlar Sayfası — Tamamlandı

## Yapılan Değişiklikler

### Yeni Dosya — `web/settings.html`
Tam özellikli ayarlar sayfası; 4 seksiyon:
- **🏢 Firma Bilgileri** — Firma adı, Terminal ID
- **🪑 Salon Ayarları** — Masa sayısı, Paket sayısı
- **🔐 Güvenlik** — Mevcut şifre doğrulama + yeni şifre değiştirme
- **🖨️ Yazıcı & Sistem** — Direkt baskı toggle, DB/PDF/IP/Masa durumu kartları

### Güncellenen — `web_server.py`
- `GET /api/settings` → mevcut ayarları JSON döndürür
- `POST /api/settings` → şifre doğrular, ayarları kaydeder, masa sayısı değiştiyse adisyonları yeniler ve socket'e `system_update` yayar
- `/settings` route

### Güncellenen — `web/index.html`
"AYARLAR" butonu `/settings` sayfasına yönlendirildi.

## Test Videosu

![Ayarlar sayfası — kuvoz.local:8000/settings](file:///Users/oktaycit/.gemini/antigravity/brain/a5787398-9dfd-4ea7-9852-d9a53d8da747/settings_kuvoz_test_1771509978619.webp)

## Doğrulama Sonuçları

| Kontrol | Sonuç |
|---|---|
| Sayfa yüklendi (404 yok) | ✅ |
| 4 seksiyon görünüyor | ✅ |
| Form alanları dolu (RESTORAN OTOMASYON / 30 masa / 5 paket) | ✅ |
| IP adresi yüklendi (192.168.1.197) | ✅ |
| Kaydet / Yenile / Ana Sayfa butonları | ✅ |
| `vet@kuvoz.local` cihazında çalışıyor | ✅ |
