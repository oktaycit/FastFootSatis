# -*- coding: utf-8 -*-
"""
Courier Integration Manager
Restoran
"""

import json
import logging
import requests

logger = logging.getLogger(__name__)

class CourierIntegration:
    def __init__(self, db):
        self.db = db

    def send_order_to_firm(self, firma_id, order_data):
        """
        Kurye firmasına sipariş bilgisini gönderir (API entegrasyonu)
        Yemeksepeti Mahalle, Banabi, Getir Kurye vb. için genişletilebilir.
        """
        # Firmanın API ayarlarını DB'den al
        with self.db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM kurye_firmalari WHERE id = %s", (firma_id,))
            firma = cursor.fetchone()
            
        if not firma:
            return False, "Firma bulunamadı"

        # Örn: Mock API entegrasyonu
        logger.info(f"🚚 Sipariş {firma['ad']} firmasına gönderiliyor: {order_data['masa']}")
        
        # Gerçek entegrasyonlar burada yapılacak
        # success = self._call_firm_api(firma, order_data)
        
        return True, "Sipariş firmaya başarıyla iletildi"

    def generate_courier_message(self, adisyon, customer_info):
        """
        Kurye için bilgilendirme mesajı oluşturur.
        """
        items_str = "\n".join([f"- {i['adet']}x {i['urun']}" for i in adisyon['items']])
        address = customer_info.get('adres', 'Adres bilgisi yok')
        maps_link = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
        
        message = f"🔔 *YENİ PAKET SİPARİŞİ*\n\n"
        message += f"📍 *Müşteri:* {customer_info.get('cari_isim', 'Bilinmiyor')}\n"
        message += f"📞 *Tel:* {customer_info.get('telefon', 'Bilinmiyor')}\n\n"
        message += f"📦 *Sipariş İçeriği:*\n{items_str}\n\n"
        message += f"💰 *Toplam:* {adisyon.get('total', 0):.2f} TL\n\n"
        message += f"🏠 *Adres:* {address}\n\n"
        message += f"🗺️ *Konum:* {maps_link}"
        
        return message, maps_link
