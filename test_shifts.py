import requests
import time
import json

BASE_URL = "http://localhost:8000/api"

def test_shift_flow():
    print("🚀 Starting Shift Flow Test...")
    
    # 1. Kasa Listele / Ekle
    print("\n1. Kasa İşlemleri")
    res = requests.get(f"{BASE_URL}/kasa/liste")
    kasalar = res.json()
    print(f"Mevcut Kasalar: {kasalar}")
    
    kasa_adi = f"Test Kasa {int(time.time())}"
    res = requests.post(f"{BASE_URL}/kasa/ekle", json={"ad": kasa_adi})
    kasa_id = res.json().get('id')
    print(f"Yeni Kasa Eklendi: {kasa_adi} (ID: {kasa_id})")

    # 2. Vardiya Aç
    print("\n2. Vardiya Açma")
    res = requests.post(f"{BASE_URL}/vardiya/ac", json={
        "kasa_id": kasa_id,
        "kasiyer": "Test Kasiyer",
        "acilis_bakiyesi": 100.0
    })
    shift_id = res.json().get('id')
    print(f"Vardiya Açıldı: ID {shift_id}")

    # 3. Satış Simülasyonu (SocketIO üzerinden olması daha iyi ama API testi yapıyoruz)
    # Backend'de handle_payment vardiya_id kullanıyor.
    # Burada manuel test zordur çünkü sid_kasa_map lazım.
    # Ancak vardiya_id ile direkt save_sale test edebiliriz database.py üzerinden.
    
    # 4. Vardiya Durum Sorgula
    print("\n3. Vardiya Durum")
    res = requests.get(f"{BASE_URL}/vardiya/durum?kasa_id={kasa_id}")
    print(f"Aktif Vardiya: {res.json()}")

    # 5. Vardiya Kapat
    print("\n4. Vardiya Kapatma")
    res = requests.post(f"{BASE_URL}/vardiya/kapat", json={
        "shift_id": shift_id,
        "nakit": 500.0,
        "kart": 200.0
    })
    print(f"Vardiya Kapatıldı: {res.json()}")

    # 6. Özet Görüntüle
    print("\n5. Vardiya Özeti")
    res = requests.get(f"{BASE_URL}/vardiya/ozet/{shift_id}")
    print(f"Vardiya Özeti: {json.dumps(res.json(), indent=2)}")

if __name__ == "__main__":
    try:
        test_shift_flow()
        print("\n✅ Backend Shift Flow Test Completed Successfully!")
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
