# Restoran Web Sunucusu - Başlangıç Rehberi

## 🚀 Hızlı Başlangıç

### 1. Sunucuyu Başlatma

```bash
cd /path/to/restoran
python3 web_server.py
```

### 2. Web Arayüzüne Erişim

Tarayıcınızda açın:
- **Yerel bilgisayardan**: http://localhost:8000
- **Ağdaki diğer cihazlardan**: http://<IP_ADRESI>:8000

> IP adresiniz sunucu başlatıldığında konsola yazdırılır.

---

## 📋 Özellikler

### ✅ Çalışan Özellikler

- Web tabanlı modern arayüz
- Real-time sipariş güncellemeleri
- Masa/paket yönetimi
- Dinamik menü sistemi
- Nakit/Kart/Açık hesap ödemeleri
- Uzaktan terminal desteği
- PostgreSQL veritabanı (opsiyonel)
- Responsive tasarım

### 🔧 Yapılandırma

`config.txt` dosyasından ayarları değiştirebilirsiniz:
- Firma ismi
- Masa sayısı
- Paket sayısı
- Admin şifresi
- Terminal ID

---

## 💡 Kullanım İpuçları

1. **Masa Seçimi**: Orta panelden masa/paket seçin
2. **Sipariş Ekle**: Sol menüden ürüne tıklayın
3. **Sipariş Sil**: Sağ paneldeki siparişe tıklayın
4. **Ödeme Al**: Ödeme butonlarından birini seçin

---

## 🐛 Sorun Giderme

### PostgreSQL Bağlantı Hatası
Normal! Sistem otomatik olarak dosya tabanlı moda geçer.

### Port Kullanımda
8000 portu kullanımdaysa başka port deneyin:
```python
socketio.run(app, host='0.0.0.0', port=8080)
```

---

## 📞 Destek

Detaylı bilgi için [walkthrough.md](file:///Users/oktaycit/.gemini/antigravity/brain/10dd0dfe-cddd-44a4-a9b6-57ebc8b80ef3/walkthrough.md) dosyasına bakın.
