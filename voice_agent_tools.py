import sys
import os
import json
import logging
from typing import List, Optional

# FastFootSatis dizinini path'e ekle (importlar için)
PROJECT_ROOT = "/Users/oktaycit/Projeler/FastFootSatıs"
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from database import db
    USE_DATABASE = True
except Exception as e:
    USE_DATABASE = False
    db = None
    print(f"⚠ Veri tabanı bağlantısı yapılamadı: {e}")

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_agent_tools")

def get_mock_menu():
    return {
        "Kebaplar": [["Adana Kebap", 250.0], ["Urfa Kebap", 240.0]],
        "İçecekler": [["Ayran", 40.0], ["Kola", 50.0]],
        "Tatlılar": [["Künefe", 120.0], ["Baklava", 150.0]]
    }

def get_customer_context(phone_number: str) -> str:
    """
    Telefon numarasından müşteri bilgilerini ve son siparişlerini getirir.
    """
    if not USE_DATABASE or not db:
        return "Müşteri tanıma devredışı (DB Yok)."

    try:
        # Karaliste Kontrolü
        if hasattr(db, 'is_blacklisted') and db.is_blacklisted(phone_number):
            return "DİKKAT: Bu numara KARALİSTEDEDİR. Sipariş almayın."

        # Günlük Çağrı Sınırı Kontrolü (Rate Limiting)
        # Basit bir sayaç veya db üzerinden kontrol eklenebilir
        # Şimdilik prensip olarak yerini hazırlıyoruz
        
        # database.py: get_cari_by_phone(self, telefon)
        customer = db.get_cari_by_phone(phone_number)
        if not customer:
            return "Yeni müşteri. Kayıt bulunamadı."

        customer_name = customer['cari_isim']
        # database.py: get_customer_order_history(self, cari_isim, limit=5)
        history = db.get_customer_order_history(customer_name, limit=3)
        
        context = f"Müşteri Adı: {customer_name}\n"
        if history:
            last_items = ", ".join(set([h['urun'] for h in history]))
            context += f"Son Siparişleri: {last_items}\n"
            context += "Öneri: 'Yine her zamankinden mi istersiniz?' veya 'En son [ürün] almıştınız, yine ondan mı hazırlayalım?' diyebilirsin."
        else:
            context += "Geçmiş sipariş bulunamadı."
            
        return context
    except Exception as e:
        logger.error(f"Müşteri tanıma hatası: {e}")
        return "Müşteri bilgisi alınamadı."

def search_menu(query: str) -> str:
    """
    Restoran menüsünde ürün araması yapar.
    Müşteri bir yemeğin olup olmadığını veya fiyatını sorduğunda kullanılır.
    """
    try:
        if USE_DATABASE and db:
            menu_data = db.get_menu_by_category()
        else:
            menu_data = get_mock_menu()
            
        found_items = []
        query_lower = query.lower()
        
        for category, items in menu_data.items():
            for item in items:
                name = item[0]
                price = item[1]
                if query_lower in name.lower() or query_lower in category.lower():
                    found_items.append(f"{name}: {price} TL (Kategori: {category})")
        
        if not found_items:
            return f"Maalesef '{query}' ile eşleşen bir ürün bulamadım."
        
        return "Bulunan ürünler:\n" + "\n".join(found_items[:5])
    except Exception as e:
        logger.error(f"Menu arama hatası: {e}")
        return "Menüde arama yaparken bir teknik hata oluştu."

def place_order(customer_name: str, items: List[dict], address: str = "", note: str = "") -> str:
    """
    Müşterinin siparişini sisteme kaydeder.
    items listesi [{'urun': 'Tavuk Döner', 'adet': 1, 'fiyat': 120.0, 'not': 'Ketçapsız, bol yeşillik'}] formatında olmalıdır.
    """
    try:
        if not USE_DATABASE or not db:
            logger.info(f"MOCK: Sipariş kaydedildi. Kalemler: {items}")
            return f"Siparişiniz (MOCK) başarıyla alındı {customer_name}."

        # Karaliste Kontrolü (Son Dakika)
        if hasattr(db, 'is_blacklisted') and db.is_blacklisted(items[0].get('telefon', '')):
             return "Maalesef şu an sipariş alamıyoruz."

        # Sunucu ayarlarından onay durumunu al (varsayılan bekliyor)
        # web_server nesnesine erişim yoksa manuel kontrol
        default_status = 'onay_bekliyor' # Varsayılan olarak onaya düşsün
        
        adisyon_adi = f"Sesli_Siparis_{customer_name}"
        order_id = db.save_online_order(
            musteri_adi=customer_name,
            telefon="", # Arayan numarayı vapi aktarmalı
            adres=address,
            not_bilgisi=note,
            items=items,
            adisyon_adi=adisyon_adi,
            odeme_tipi='kapida_nakit'
        )
        # Durumu güncelle (Mutfak onayı kapalıysa doğrudan 'bekliyor' (mutfak görür))
        # 'bekliyor' -> Mutfak ekranında görünür
        # 'onay_bekliyor' -> Sadece kasiyer onaylarsa görünür
        
        return f"Siparişiniz başarıyla alındı {customer_name}. En kısa sürede ulaştırılacaktır."
    except Exception as e:
        logger.error(f"Sipariş kaydetme hatası: {e}")
        return "Siparişinizi kaydederken bir hata oluştu."

def get_full_menu() -> str:
    """Tüm menüyü özet olarak döner."""
    try:
        if USE_DATABASE and db:
            menu_data = db.get_menu_by_category()
        else:
            menu_data = get_mock_menu()
            
        summary = []
        for category, items in menu_data.items():
            item_names = [it[0] for it in items]
            summary.append(f"{category}: {', '.join(item_names)}")
        return "\n".join(summary)
    except Exception as e:
        return f"Menü alınamadı: {e}"

if __name__ == "__main__":
    # Test kodları
    print("--- Menü Özeti ---")
    print(get_full_menu())
    print("\n--- Arama Testi (Kebap) ---")
    print(search_menu("Kebap"))
