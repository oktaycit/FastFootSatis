# OnlyOffice AI Assistant - Alibaba Cloud Qwen Entegrasyonu

Bu doküman, OnlyOffice 9.3.1'e Alibaba Cloud Qwen AI modelini entegre etmek için gerekli adımları açıklar.

## Genel Bakış

OnlyOffice AI Assistant, üçüncü taraf AI sağlayıcılarını destekler. Bu entegrasyon, Alibaba Cloud'un Qwen modellerini OnlyOffice içinde kullanmanızı sağlar.

### Özellikler

- ✏️ **Metin Tamamlama** - Yazarken otomatik tamamlama
- 📝 **Özetleme** - Uzun metinleri özetleme
- 🌐 **Çeviri** - Diller arası çeviri
- ✨ **Dilbilgisi Düzeltme** - Yazım hatalarını düzeltme
- 📋 **Metin Genişletme/Kısaltma** - İçeriği düzenleme
- 💬 **Sohbet** - AI ile interaktif konuşma

## Gereksinimler

1. **OnlyOffice Document Server 9.x** (AI Assistant desteği ile)
2. **Alibaba Cloud API Anahtarı** (DashScope)
3. **Python 3.8+** (Proxy sunucusu için)
4. **Flask** ve **requests** kütüphaneleri

## Kurulum Adımları

### 1. OnlyOffice AI Assistant'ı Etkinleştirme

OnlyOffice Document Server ayarlarında AI Assistant'ı etkinleştirin:

```bash
# Docker kullanıyorsanız
docker exec -it <container_id> bash
# onlyoffice-document-server ayarlarını düzenleyin
```

OnlyOffice Control Panel üzerinden:
1. **Settings** → **AI Settings** bölümüne gidin
2. **AI Assistant**'ı etkinleştirin
3. **Custom AI Provider** seçeneğini seçin

### 2. Proxy Sunucusunu Kurma

#### 2.1 Bağımlılıkları Yükleyin

```bash
cd /path/to/FastFootSatis
pip install -r requirements.txt
```

#### 2.2 API Anahtarını Yapılandırın

`.env` dosyası oluşturun (`.env.example`'ı kopyalayın):

```bash
cp .env.example .env
```

`.env` dosyasını düzenleyin:

```env
# OnlyOffice AI Proxy Ayarları
ONLYOFFICE_AI_PORT=5557
ALIBABA_API_KEY=sk-sizin_api_anahtariniz
ALIBABA_MODEL=qwen-turbo
```

**Mevcut Qwen Modelleri:**
- `qwen-turbo` - Hızlı ve ekonomik
- `qwen-plus` - Dengeli performans
- `qwen-max` - En güçlü model
- `qwen2.5-72b-instruct` - En son model

### 3. Proxy Sunucusunu Başlatma

```bash
python3 onlyoffice_ai.py
```

Sunucu `http://0.0.0.0:5557` adresinde çalışacaktır.

### 4. OnlyOffice'e Proxy'yi Tanıtma

OnlyOffice Document Server ayarlarında **Custom AI Endpoint** yapılandırması:

#### 4.1 OnlyOffice Control Panel (Web)

1. OnlyOffice Control Panel'e giriş yapın
2. **Settings** → **AI Settings** → **Custom Provider**
3. Aşağıdaki bilgileri girin:

| Alan | Değer |
|------|-------|
| **API Endpoint** | `http://<sunucu_ip>:5557/api/v1/ai` |
| **Chat Endpoint** | `/chat` |
| **Complete Endpoint** | `/complete` |
| **Translate Endpoint** | `/translate` |
| **Command Endpoint** | `/command` |
| **Models Endpoint** | `/models` |
| **Authentication** | Bearer Token (opsiyonel) |

#### 4.2 local.json ile Yapılandırma (Alternatif)

OnlyOffice Document Server kurulumunuzda `local.json` dosyasını düzenleyin:

```json
{
  "services": {
    "CoAuthoring": {
      "ai": {
        "enabled": true,
        "provider": "custom",
        "endpoint": "http://<sunucu_ip>:5557/api/v1/ai",
        "endpoints": {
          "chat": "/chat",
          "complete": "/complete",
          "translate": "/translate",
          "command": "/command",
          "models": "/models"
        },
        "model": "qwen-turbo"
      }
    }
  }
}
```

### 5. Test Etme

#### 5.1 Sağlık Kontrolü

```bash
curl http://localhost:5557/health
```

Beklenen yanıt:
```json
{
  "status": "ok",
  "model": "qwen-turbo",
  "configured": true
}
```

#### 5.2 Model Listesi

```bash
curl http://localhost:5557/api/v1/ai/models
```

#### 5.3 Doğrudan API Testi

```bash
curl -X POST http://localhost:5557/api/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Merhaba, nasılsın?",
    "command": "chat",
    "maxTokens": 100
  }'
```

### 6. Production Ortamında Çalıştırma

#### Systemd Servisi Oluşturma

`/etc/systemd/system/onlyoffice-ai.service` dosyası oluşturun:

```ini
[Unit]
Description=OnlyOffice AI Proxy Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/FastFootSatis
Environment="ALIBABA_API_KEY=sk-sizin_anahtariniz"
Environment="ALIBABA_MODEL=qwen-turbo"
Environment="ONLYOFFICE_AI_PORT=5557"
ExecStart=/usr/bin/python3 /path/to/FastFootSatis/onlyoffice_ai.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Servisi başlatın:

```bash
sudo systemctl daemon-reload
sudo systemctl enable onlyoffice-ai
sudo systemctl start onlyoffice-ai
sudo systemctl status onlyoffice-ai
```

## OnlyOffice'te Kullanım

1. OnlyOffice Docs (Document/Spreadsheet/Presentation) açın
2. Sağ üst köşedeki **AI Assistant** (✨) ikonuna tıklayın
3. Aşağıdaki işlemleri yapabilirsiniz:
   - **Continue writing** - Metni devam ettir
   - **Summarize** - Seçili metni özetle
   - **Translate** - Çeviri yap
   - **Fix grammar** - Dilbilgisi düzelt
   - **Change tone** - Ton değiştir
   - **Chat** - AI ile konuş

## Sorun Giderme

### API Anahtarı Hatası

```
Error: API anahtarı yapılandırılmamış
```

**Çözüm:** `.env` dosyasında `ALIBABA_API_KEY` değerini ayarlayın.

### Bağlantı Hatası

```
Error: Connection refused
```

**Çözüm:** 
- Proxy sunucusunun çalıştığından emin olun
- Firewall ayarlarını kontrol edin (port 5557 açık olmalı)
- OnlyOffice ile aynı ağda olduğundan emin olun

### CORS Hatası

OnlyOffice tarayıcıdan erişiyorsa CORS hatası alabilirsiniz.

**Çözüm:** `onlyoffice_ai.py` dosyasına CORS desteği ekleyin:

```python
from flask_cors import CORS
app = Flask(__name__)
CORS(app)
```

Ve `flask-cors` yükleyin:
```bash
pip install flask-cors
```

## Güvenlik Önerileri

1. **API Anahtarını Koruyun**: `.env` dosyasını `.gitignore`'a ekleyin
2. **HTTPS Kullanın**: Production'da reverse proxy (nginx) ile HTTPS kullanın
3. **Erişim Kontrolü**: OnlyOffice'ten gelen istekleri doğrulayın
4. **Rate Limiting**: API limitlerini aşmamak için request throttling ekleyin

## Performans İpuçları

1. **Model Seçimi**: Hızlı işlemler için `qwen-turbo`, karmaşık işlemler için `qwen-max` kullanın
2. **Token Limitleri**: `maxTokens` değerini ihtiyaca göre ayarlayın
3. **Connection Pooling**: `requests` kütüphanesi otomatik yapar

## Desteklenen Endpoint'ler

| Endpoint | Metod | Açıklama |
|----------|-------|----------|
| `/health` | GET | Sağlık kontrolü |
| `/api/v1/ai/models` | GET | Kullanılabilir modeller |
| `/api/v1/ai/status` | GET | AI durumu |
| `/api/v1/ai/chat` | POST | Sohbet |
| `/api/v1/ai/complete` | POST | Metin tamamlama |
| `/api/v1/ai/translate` | POST | Çeviri |
| `/api/v1/ai/command` | POST | Komut işleme |

## Referanslar

- [OnlyOffice AI Documentation](https://api.onlyoffice.com/)
- [Alibaba Cloud DashScope](https://help.aliyun.com/zh/dashscope/)
- [Qwen Model Documentation](https://help.aliyun.com/zh/dashscope/developer-reference/quick-start)