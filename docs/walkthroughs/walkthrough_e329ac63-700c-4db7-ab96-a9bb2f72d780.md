# Versiyon Güncelleme Uyarıları ve Hash Görüntüleme - Walkthrough

## Yapılan Değişiklikler

### Backend - `web_server.py`

#### 1. Git Versiyon Bilgisi Fonksiyonu

Yeni `get_git_version_info()` fonksiyonu eklendi (satır 198-237):
- Git commit hash'ini (7 karakter kısa format) alır
- Mevcut branch adını alır
- Hata durumunda "Unknown" döndürür
- 5 saniye timeout ile güvenli çalışır

```python
def get_git_version_info():
    """Get current git commit hash and branch information."""
    # Returns: {'hash': str, 'branch': str}
```

#### 2. Profil Endpoint Güncelleme

`handle_get_profile()` fonksiyonu güncellendi (satır 3193-3197):
- Her profil isteğinde git hash ve branch bilgisi eklenir
- `device` nesnesine `git_hash` ve `git_branch` alanları eklendi
- Log mesajlarında git versiyon bilgisi gösterilir

#### 3. Sistem Güncelleme Hata Yönetimi

`handle_system_update()` fonksiyonu iyileştirildi (satır 3455-3521):

**Özellikler:**
- Güncelleme öncesi ve sonrası git hash loglanır
- Hash değişimi tespit edilir ve kullanıcıya bildirilir
- Detaylı hata tipleri ayırt edilir:
  - `network`: İnternet bağlantı hatası
  - `conflict`: Yerel değişiklik çakışması
  - `permission`: Yetki hatası
  - `timeout`: Zaman aşımı
  - `not_git`: Git deposu bulunamadı
- Her hata tipi için kullanıcı dostu mesajlar
- Timeout için ayrı exception handling

**Başarılı Güncelleme Mesajları:**
- "Sistem zaten güncel. (Versiyon: abc1234)"
- "Sistem güncellendi: abc1234 → def5678"

---

### Frontend - `user_profile.html`

#### Cihaz Bilgileri Bölümü

Yeni alanlar eklendi (satır 334-335):
```html
<p><strong>Git Hash:</strong> <code id="git-hash" style="...">Yükleniyor...</code></p>
<p><strong>Git Branch:</strong> <span id="git-branch">Yükleniyor...</span></p>
```

**Stil Özellikleri:**
- Git hash monospace font ile görüntülenir
- Gri arka plan (#f0f0f0) ile vurgulanır
- Kod bloğu görünümü için `<code>` etiketi kullanılır

#### JavaScript Güncellemesi

`updateUI()` fonksiyonu güncellendi (satır 415-416):
```javascript
document.getElementById('git-hash').textContent = data.device.git_hash || 'Unknown';
document.getElementById('git-branch').textContent = data.device.git_branch || 'Unknown';
```

---

### Frontend - `settings.html`

#### Güncelleme Yanıt İşleyicisi

`system_update_response` event handler iyileştirildi (satır 500-531):

**Başarılı Güncelleme:**
- Git hash bilgisi console'a loglanır
- Kullanıcıya başarı mesajı gösterilir

**Başarısız Güncelleme:**
- Hata tipine göre özel mesajlar
- Her hata tipi için yardımcı ipuçları:
  - Network → "Wi-Fi bağlantınızı kontrol edin"
  - Conflict → "Geri Al butonunu kullanın"
  - Permission → "Sistem dosya izinlerini kontrol edin"
  - Timeout → "İnternet bağlantınız yavaş olabilir"
- Detaylı hata bilgisi console'da loglanır

---

## Test Sonuçları

### Git Hash Görüntüleme Testi ✅

**Test Edilen:**
- Profil sayfası açıldı
- Git hash ve branch bilgisi başarıyla görüntülendi
- Mevcut hash: `8d8890b`
- Mevcut branch: `master`

**Doğrulama Komutu:**
```bash
git rev-parse --short=7 HEAD  # 8d8890b
git rev-parse --abbrev-ref HEAD  # master
```

### Kod Değişiklikleri Özeti

**Değiştirilen Dosyalar:**
1. [web_server.py](file:///Users/oktaycit/Projeler/kuvoz/web_server.py)
   - +41 satır: `get_git_version_info()` fonksiyonu
   - +5 satır: Profil endpoint'ine git bilgisi ekleme
   - +38 satır: Gelişmiş hata yönetimi

2. [user_profile.html](file:///Users/oktaycit/Projeler/kuvoz/web/user_profile.html)
   - +2 satır: HTML görüntüleme alanları
   - +2 satır: JavaScript güncelleme kodu

3. [settings.html](file:///Users/oktaycit/Projeler/kuvoz/web/settings.html)
   - +23 satır: Gelişmiş hata mesajı işleme

**Toplam:** ~111 satır yeni kod

---

## Kullanım Senaryoları

### Senaryo 1: Profil Sayfasında Git Bilgisi Görüntüleme

1. Kullanıcı profil sayfasını açar (`/user_profile.html`)
2. "Cihaz Bilgileri" bölümünde git hash ve branch görüntülenir
3. Hash monospace font ile vurgulanır: `8d8890b`
4. Branch adı gösterilir: `master`

### Senaryo 2: Başarılı Sistem Güncellemesi

1. Kullanıcı ayarlar sayfasından "Sistemi Güncelle" butonuna tıklar
2. Sistem güncelleme kontrolü yapar
3. Eğer güncel ise: "Sistem zaten güncel. (Versiyon: 8d8890b)"
4. Eğer güncelleme varsa: "Sistem güncellendi: 8d8890b → abc1234"
5. Console'da yeni hash loglanır

### Senaryo 3: Güncelleme Hatası - Network

1. Kullanıcı internet bağlantısı olmadan güncelleme yapar
2. Sistem network hatasını tespit eder
3. Kullanıcıya gösterilen mesaj:
   ```
   ❌ İnternet bağlantısı hatası. Lütfen ağ bağlantınızı kontrol edin ve tekrar deneyin.
   
   💡 İpucu: Wi-Fi bağlantınızı kontrol edin.
   ```
4. Detaylı hata console'da loglanır

### Senaryo 4: Güncelleme Hatası - Conflict

1. Kullanıcı yerel değişiklikler yapmış
2. Güncelleme conflict tespit eder
3. Kullanıcıya gösterilen mesaj:
   ```
   ❌ Yerel değişiklikler güncellemeyi engelliyor. Lütfen önce "Geri Al" butonunu kullanın.
   
   💡 İpucu: "Geri Al" butonunu kullanarak yerel değişiklikleri geri alabilirsiniz.
   ```

---

## Teknik Detaylar

### Git Komutları

```bash
# Hash alma (7 karakter)
git rev-parse --short=7 HEAD

# Branch adı alma
git rev-parse --abbrev-ref HEAD
```

### WebSocket Events

**Yeni/Güncellenmiş Eventler:**
- `get_profile` → Response artık `git_hash` ve `git_branch` içeriyor
- `system_update_response` → Artık `git_hash`, `git_branch`, `error_type`, `error_details` içeriyor

### Hata Tipleri

| Error Type | Tespit Kriteri | Kullanıcı Mesajı |
|------------|----------------|------------------|
| `network` | "Could not resolve host" | İnternet bağlantısı hatası |
| `conflict` | "CONFLICT", "would be overwritten" | Yerel değişiklikler engelliyor |
| `permission` | "Permission denied" | Yetki hatası |
| `timeout` | subprocess.TimeoutExpired | Zaman aşımı (120s) |
| `not_git` | "not a git repository" | Git deposu bulunamadı |
| `unknown` | Diğer hatalar | Bilinmeyen hata |

---

## Sonuç

✅ **Tamamlanan Özellikler:**
- Git hash ve branch bilgisi profil sayfasında görüntüleniyor
- Sistem güncellemesi detaylı hata mesajları veriyor
- Kullanıcıya hata tipine göre yardımcı ipuçları sunuluyor
- Güncelleme öncesi/sonrası versiyon değişimi loglanıyor

🎯 **Kullanıcı Deneyimi İyileştirmeleri:**
- Şeffaf versiyon bilgisi
- Anlaşılır hata mesajları
- Sorun çözme ipuçları
- Detaylı loglama (debugging için)
