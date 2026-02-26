import sys
import os
import json
from voice_agent_tools import search_menu, place_order, get_customer_context, get_full_menu

def print_separator():
    print("-" * 50)

def simulate_test_scenario():
    print("\n🚀 RESTORAN SESLİ ASİSTAN TEST SİMÜLASYONU")
    print_separator()

    # Senaryo 1: Müşteri Tanıma (Veritabanı kapalı olduğu için mock dönecek)
    test_phone = "5551234567"
    print(f"📡 Adım 1: Arayan Numara Tanıma ({test_phone})")
    context = get_customer_context(test_phone)
    print(f"Asistan Bilgisi:\n{context}")
    print_separator()

    # Senaryo 2: Menü Sorgulama
    print("📡 Adım 2: Menü Sorgulama ('Kebap var mı?')")
    search_res = search_menu("Kebap")
    print(f"Asistan Cevabı:\n{search_res}")
    print_separator()

    # Senaryo 3: Ürün Özelleştirme ve Sipariş
    print("📡 Adım 3: Sipariş Verme (Tavuk Döner - Ketçapsız)")
    customer_name = "Test Müşteri"
    items = [
        {"urun": "Tavuk Döner", "adet": 1, "fiyat": 120.0, "not": "Ketçapsız, bol yeşillik"}
    ]
    order_res = place_order(customer_name, items, address="Atatürk Mah. No:5", note="Zil bozuk")
    print(f"Sistem Kaydı:\n{order_res}")
    print_separator()

    print("\n✅ Test tamamlandı. Bu araçlar gerçek telefon hattı bağlandığında aynı mantıkla çalışacaktır.")

if __name__ == "__main__":
    simulate_test_scenario()
