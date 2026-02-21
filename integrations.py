# -*- coding: utf-8 -*-
"""
Delivery Platform Integration Manager
FastFootSatış
"""

import json
import os
import datetime
import logging

logger = logging.getLogger(__name__)

class IntegrationManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.settings = self.load_settings()
        
    def load_settings(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading integration settings: {e}")
        return {
            "yemeksepeti": {"enabled": False, "api_key": "", "store_id": ""},
            "trendyol": {"enabled": False, "api_key": "", "api_secret": "", "supplier_id": ""},
            "getir": {"enabled": False, "app_token": "", "restaurant_id": ""},
            "migros": {"enabled": False, "api_key": "", "store_id": ""}
        }

    def save_settings(self, new_settings):
        self.settings = new_settings
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving integration settings: {e}")
            return False

    def process_webhook(self, platform, data):
        """
        Process incoming webhook data from platforms and convert to internal order format.
        """
        if platform == "yemeksepeti":
            return self._map_yemeksepeti(data)
        elif platform == "trendyol":
            return self._map_trendyol(data)
        elif platform == "getir":
            return self._map_getir(data)
        elif platform == "migros":
            return self._map_migros(data)
        else:
            logger.warning(f"Unknown platform: {platform}")
            return None

    def _map_yemeksepeti(self, data):
        # Placeholder for Yemeksepeti mapping logic
        # Expecting data format based on DeliveryHero/Yemeksepeti API
        try:
            order_id = data.get('id')
            items = []
            for entry in data.get('items', []):
                items.append({
                    "urun": entry.get('name'),
                    "adet": entry.get('quantity', 1),
                    "fiyat": float(entry.get('price', 0)),
                    "tip": "yemeksepeti"
                })
            return {
                "masa": f"YS-{order_id[-4:] if order_id else 'NEW'}",
                "items": items,
                "platform": "Yemeksepeti",
                "external_id": order_id,
                "customer": data.get('customer', {}).get('first_name', 'Müşteri')
            }
        except Exception as e:
            logger.error(f"Error mapping Yemeksepeti: {e}")
            return None

    def _map_trendyol(self, data):
        try:
            order_number = data.get('orderNumber')
            items = []
            for line in data.get('lines', []):
                items.append({
                    "urun": line.get('productName'),
                    "adet": line.get('quantity', 1),
                    "fiyat": float(line.get('price', 0)),
                    "tip": "trendyol"
                })
            return {
                "masa": f"TY-{order_number[-4:] if order_number else 'NEW'}",
                "items": items,
                "platform": "Trendyol",
                "external_id": order_number,
                "customer": f"{data.get('customerFirstName', '')} {data.get('customerLastName', '')}".strip()
            }
        except Exception as e:
            logger.error(f"Error mapping Trendyol: {e}")
            return None

    def _map_getir(self, data):
        try:
            order_id = data.get('id')
            items = []
            for product in data.get('products', []):
                items.append({
                    "urun": product.get('name'),
                    "adet": product.get('count', 1),
                    "fiyat": float(product.get('price', 0)),
                    "tip": "getir"
                })
            return {
                "masa": f"GT-{order_id[-4:] if order_id else 'NEW'}",
                "items": items,
                "platform": "Getir",
                "external_id": order_id,
                "customer": data.get('client', {}).get('name', 'Müşteri')
            }
        except Exception as e:
            logger.error(f"Error mapping Getir: {e}")
            return None

    def _map_migros(self, data):
        try:
            order_number = data.get('orderNumber')
            items = []
            for item in data.get('orderItems', []):
                items.append({
                    "urun": item.get('productName'),
                    "adet": item.get('quantity', 1),
                    "fiyat": float(item.get('unitPrice', 0)),
                    "tip": "migros"
                })
            return {
                "masa": f"MG-{order_number[-4:] if order_number else 'NEW'}",
                "items": items,
                "platform": "Migros",
                "external_id": order_number,
                "customer": data.get('customerName', 'Müşteri')
            }
        except Exception as e:
            logger.error(f"Error mapping Migros: {e}")
            return None
