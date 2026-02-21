import urllib.request
import json
import time

BASE_URL = "http://localhost:8000/api/integration/webhook"

def send_request(platform, payload):
    url = f"{BASE_URL}/{platform}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as f:
            print(f"[{platform}] Response: {f.status}, {f.read().decode('utf-8')}")
    except Exception as e:
        print(f"[{platform}] Error: {e}")

def test_yemeksepeti():
    print("Testing Yemeksepeti...")
    payload = {
        "id": "YS-12345678",
        "items": [
            {"name": "Adana Kebap", "quantity": 1, "price": 250.0},
            {"name": "Ayran", "quantity": 1, "price": 40.0}
        ],
        "customer": {"first_name": "Ahmet"}
    }
    send_request("yemeksepeti", payload)

def test_trendyol():
    print("\nTesting Trendyol...")
    payload = {
        "orderNumber": "TY-98765432",
        "lines": [
            {"productName": "Lahmacun", "quantity": 3, "price": 90.0},
            {"productName": "Kola", "quantity": 1, "price": 50.0}
        ],
        "customerFirstName": "Mehmet",
        "customerLastName": "Yılmaz"
    }
    send_request("trendyol", payload)

def test_getir():
    print("\nTesting Getir...")
    payload = {
        "id": "GT-11223344",
        "products": [
            {"name": "Kıymalı Pide", "count": 1, "price": 180.0},
            {"name": "Sütlaç", "count": 2, "price": 75.0}
        ],
        "client": {"name": "Ayşe Demir"}
    }
    send_request("getir", payload)

def test_migros():
    print("\nTesting Migros...")
    payload = {
        "orderNumber": "MG-55667788",
        "orderItems": [
            {"productName": "Et Döner Dürüm", "quantity": 1, "unitPrice": 220.0},
            {"productName": "Şalgam", "quantity": 1, "unitPrice": 35.0}
        ],
        "customerName": "Fatma Şahin"
    }
    send_request("migros", payload)

if __name__ == "__main__":
    test_yemeksepeti()
    test_trendyol()
    test_getir()
    test_migros()
