# FastFood OKC Bridge

Bu küçük Windows console uygulaması, `oktayraspian` üzerindeki FastFood sunucusu ile USB bağlı Beko YN ÖKC arasında köprü görevi görür.

## Akış

1. FastFood ödeme sırasında `http://WINDOWS_IP:8787/api/sale` adresine Token sepet JSON'u gönderir.
2. Bridge bu JSON'u `IntegrationHub.POSCommunication.sendBasket()` ile ÖKC'ye iletir.
3. ÖKC satış callback'i (`type == 3`) dönene kadar HTTP cevabı bekletilir.
4. Başarılı callback gelirse FastFood adisyonu kapatır; hata veya timeout olursa adisyon açık kalır.

Tek ödeme için varsayılan callback bekleme süresi 180 saniyedir. FastFood
parçalı ödeme sepetlerinde `saleTimeoutSeconds: 300` gönderir; bridge bu değeri
300 saniye üst sınırıyla kullanır.

## Kurulum

1. Token/Arçelik sürücüsünü Windows'a kurun.
2. ERP12 klasöründeki gerekli DLL dosyalarını `windows_okc_bridge\lib\` klasörüne koyun. En az `IntegrationHub.dll` gerekir; üretici kurulumuna göre aynı klasöre diğer bağımlı DLL'ler de gerekebilir.
3. Projeyi Visual Studio'da `x86` hedefiyle derleyin.
4. Windows terminalde yönetici olarak HTTP dinleme izni verin:

```powershell
netsh http add urlacl url=http://+:8787/ user=Everyone
netsh advfirewall firewall add rule name="FastFood OKC Bridge 8787" dir=in action=allow protocol=TCP localport=8787
```

5. Bridge'i çalıştırın:

```powershell
.\FastFootOkcBridge.exe 8787
```

6. FastFood ayarlarında:

- POS Servisi: açık
- Cihaz Tipi: `Beko YN ÖKC (Windows Bridge)`
- IP Adresi: Windows terminalin yerel IP adresi
- Port: `8787`

## Test

Windows makineden:

```powershell
curl http://localhost:8787/health
curl http://localhost:8787/api/fiscal-info
```

`/health` yanitinda `deviceStateKnown:false` gorunurse bridge aciktir ancak OKC
baglanti callback'i henuz gelmemistir. Bridge ilk 5 dakika icinde callback
kaydini periyodik olarak yeniler; FastFood sunucusu da bridge yeni acilmissa
satis istegini hemen gondermeden once kisa sure cihaz state callback'ini bekler.
Bu pencere dolduktan sonra, eski kurulumlarla uyum icin satis istegi yine
bridge'e iletilir; cihaz gercekten hazir degilse hata `sendBasket` cevabindan
gelir.

Sabah Windows acilisinda sorun yakalamak icin `/health` alanlarina bakin:

- `uptimeSeconds`: Bridge'in kac saniyedir calistigi.
- `callbackRecoveryActive`: Startup callback recovery halen deniyor mu?
- `callbackRegistrationAttempts`: Callback kaydi kac kez yenilendi?
- `lastCallbackRegistrationError`: IntegrationHub hazir degilse son hata.
- `lastSerialCallbackAt`: OKC'den en son satis/seri callback zamani.

`/api/fiscal-info` yanıtındaki kısım numaraları ve KDV oranları, FastFood ürün eşleştirmesi için referans alınmalıdır.
