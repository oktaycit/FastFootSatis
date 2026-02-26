# Muhasebe Entegrasyonu Tamamlandı

Restoran otomasyon sistemine **Paraşüt** ve **KolayBi** muhasebe platformları için esnek bir entegrasyon katmanı eklendi. Bu entegrasyon sayesinde ödeme tamamlandığında adisyon verileri otomatik olarak seçilen muhasebe platformuna gönderilir.

## Yapılan Değişiklikler

### 1. Backend Altyapısı (`integrations.py`)
- `BaseAccountingProvider` soyut sınıfı oluşturuldu.
- `ParasutProvider` ve `KolayBiProvider` iskelet sınıfları tanımlandı.
- `IntegrationManager` güncellenerek aktif muhasebe sağlayıcısını yönetme ve veri gönderme yeteneği kazandı.

### 2. Ödeme Akışı Entegrasyonu (`web_server.py`)
- `handle_payment` (finalize_payment) olayı güncellendi.
- Ödeme başarılı olduğunda, arka planda (`threading.Thread`) sipariş verileri muhasebe sağlayıcısına gönderilecek şekilde ayarlandı.
- Arayüz performansı etkilenmemesi için gönderim işlemi asenkron olarak gerçekleştirilir.

### 3. Ayarlar Arayüzü (`web/settings.html`)
- Ayarlar sayfasına "Muhasebe Entegrasyonu" bölümü eklendi.
- Kullanıcılar aktif platformu (Paraşüt/KolayBi) seçebilir ve gerekli API bilgilerini (Client ID, Secret, Username vb.) girebilir.

## Doğrulama ve Test

### Manuel Kontrol Adımları
1. **Ayarlar Girişi:**
   - Ayarlar sayfasına gidin.
   - Muhasebe Entegrasyonu bölümünden "Paraşüt" seçin.
   - Bilgileri girip kaydedin.
2. **Ödeme Testi:**
   - Bir masadan sipariş alıp ödemeyi sonlandırın.
   - Sunucu loglarında `Sending invoice to Paraşüt for customer: ...` mesajını kontrol edin.

> [!NOTE]
> Mevcut uygulama iskelet (skeleton) aşamasındadır. Gerçek API isteği gönderimi için Paraşüt/KolayBi tarafında "Uygulama" oluşturulup API bilgilerinin alınması gerekmektedir.

## Gelecek Planı
- [ ] Paraşüt OAuth2 akışının tam implementasyonu.
- [ ] KolayBi API Key doğrulanması.
- [ ] Stok takibi entegrasyonu (İsteğe bağlı).
