import requests
import json
import time

def simulate_whatsapp_order(text, from_phone="905320001122", name="Oktay"):
    url = "http://localhost:8000/api/integration/webhook/whatsapp"
    payload = {
        "from": from_phone,
        "text": text,
        "name": name
    }
    
    print(f"🚀 Sending mock WhatsApp message: '{text}' from {name} ({from_phone})...")
    try:
        response = requests.post(url, json=payload)
        print(f"✅ Response Status: {response.status_code}")
        print(f"📝 Response Body: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Test cases
    test_messages = [
        "2 Burger, 1 Ayran",
        "3 adet Lahmacun, 2 Kola",
        "Pizza 1, Tatlı 1",
        "1 Adet Tavuk Döner"
    ]
    
    for msg in test_messages:
        simulate_whatsapp_order(msg)
        print("-" * 30)
        time.sleep(1)
