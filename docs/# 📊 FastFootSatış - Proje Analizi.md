# 📊 FastFootSatış - Proje Analizi

## 🏗️ Proje Mimarisi

### Genel Bakış
**FastFootSatış**, Flask tabanlı kapsamlı bir restoran yönetim sistemidir. Gerçek zamanlı sipariş yönetimi, çoklu platform entegrasyonları ve modern web arayüzü sunar.

---

## 📁 Dosya Yapısı

```
FastFootSatıs/
├── web_server.py          # Ana Flask sunucusu (Socket.IO + REST API)
├── database.py            # PostgreSQL veritabanı yönetimi
├── integrations.py        # Teslimat platformu entegrasyonları
├── courier_integration.py # Kurye yönetimi
├── pos_integration.py     # POS ödeme entegrasyonu
├── voice_agent_tools.py   # Sesli asistan araçları
├── db_config.py           # DB bağlantı ayarları
├── menu.txt               # Menü verileri
├── waiters.json           # Garson listesi
├── salons.json            # Salon düzeni
├── integrations.json      # Entegrasyon ayarları
├── config.txt             # Sistem ayarları
└── web/                   # Frontend dosyaları
    ├── index.html         # Ana kasa ekranı
    ├── mutfak.html        # Mutfak ekranı
    ├── waiter.html        # Garson arayüzü
    ├── kasa_yonetimi.html # Kasa yönetimi
    ├── cari.html          # Cari hesaplar
    ├── settings.html      # Ayarlar
    ├── script.js          # Ortak JavaScript
    └── styles.css         # Stil dosyası
```

---

## 🛠️ Teknoloji Stack

| Katman | Teknoloji |
|--------|-----------|
| Backend | Python 3 + Flask |
| Real-time | Socket.IO (Flask-SocketIO) |
| Database | PostgreSQL (opsiyonel) + JSON dosyaları |
| Frontend | HTML5 + CSS3 + Vanilla JS |
| PDF | ReportLab |
| Serial | PySerial (Caller ID için) |

---

## 🎯 Ana Modüller

### 1. **Sipariş Yönetimi**
- Masa ve paket siparişleri
- Gerçek zamanlı adisyon güncellemeleri
- Kısmi ödeme desteği
- Masa transferi

### 2. **Kasa ve Vardiya**
- Çoklu kasa desteği
- Vardiya açma/kapama
- Gün sonu raporları
- Nakit/Kart/Açık hesap ödemeleri

### 3. **Cari Hesaplar**
- Müşteri bakiye takibi
- Telefon numarası ile arama
- Geçmiş sipariş görüntüleme

### 4. **Personel Yönetimi**
- Garson/Kasiyer/Mutfak personeli
- PIN ile giriş sistemi
- Puantaj takibi

### 5. **Mutfak Ekranı**
- Sipariş hazır bildirimi
- Garson bildirimi
- Durum takibi

---

## 🔌 Entegrasyonlar

### Teslimat Platformları
| Platform | Durum | Özellik |
|----------|-------|---------|
| Yemeksepeti | ✅ | Webhook, fiyat mapping |
| Trendyol | ✅ | Webhook, fiyat mapping |
| Getir | ✅ | Webhook, fiyat mapping |
| Migros | ✅ | Webhook, fiyat mapping |
| WhatsApp | ✅ | Mesaj parse, sipariş oluşturma |

### Muhasebe
| Platform | Durum |
|----------|-------|
| Paraşüt | 🔧 Altyapı hazır |
| KolayBi | 🔧 Altyapı hazır |

### Diğer
- **POS Entegrasyonu**: TCP/IP üzerinden POS cihazı ile ödeme
- **Caller ID**: Signal 7 standardı (TCP/Serial)
- **QR Menü**: Dinamik QR token + NFC doğrulama

---

## 🔐 Güvenlik Özellikleri

1. **QR Menü Doğrulama**:
   - Dinamik QR token sistemi
   - Replay attack koruması (nonce)
   - Session expiry ve sliding window

2. **Sesli Asistan**:
   - Karaliste sistemi
   - Rate limiting
   - Mutfak onay mekanizması

3. **Genel**:
   - Admin şifre koruması
   - Garson PIN doğrulama

---

## 📊 Veritabanı Şeması

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  satislar   │     │ cari_hesaplar│     │  vardiyalar │
├─────────────┤     ├─────────────┤     ├─────────────┤
│ id          │     │ id          │     │ id          │
│ urun        │     │ cari_isim   │     │ kasa_id     │
│ adet        │     │ telefon     │     │ kasiyer     │
│ fiyat       │     │ adres       │     │ acilis_...  │
│ odeme       │     │ bakiye      │     │ durum       │
│ masa        │     └─────────────┘     └─────────────┘
│ vardiya_id  │            │
└─────────────┘            ▼
                   ┌─────────────┐
                   │cari_hareketler│
                   ├─────────────┤
                   │ cari_id     │
                   │ islem       │
                   │ tutar       │
                   └─────────────┘
```

**Diğer Tablolar**: `menu`, `kasalar`, `kuryeler`, `puantaj`, `online_orders`, `public_table_sessions`, `voice_agent_blacklist`

---

## 🚀 Çalıştırma

```bash
# Geliştirme
python3 web_server.py

# Production (Makefile)
make run

# Deploy
make deploy
```

**Erişim**: `http://<IP>:8000`

---

## 💡 Öne Çıkan Özellikler

1. **Real-time Güncelleme**: Socket.IO ile anlık sipariş bildirimi
2. **Çoklu Terminal**: Ağ üzerinden birden fazla terminal desteği
3. **Esnek Ödeme**: Nakit, Kart, Açık Hesap ve Parçalı ödeme
4. **Platform Farkı**: Her teslimat platformu için ayrı fiyatlandırma
5. **Offline Destek**: DB olmadan dosya tabanlı çalışabilme
6. **Caller ID**: Gelen aramada müşteri tanıma ve geçmiş sipariş gösterimi

---

## 📝 Geliştirilebilir Alanlar

1. Muhasebe entegrasyonları (Paraşüt, KolayBi) tam implementasyon
2. Sesli asistan için daha fazla AI entegrasyonu
3. Mobil uygulama desteği
4. Raporlama dashboard'u zenginleştirme

---

Bu analiz projenin mevcut durumunu özetlemektedir. Daha detaylı inceleme veya belirli bir modül hakkında bilgi almak ister misiniz?