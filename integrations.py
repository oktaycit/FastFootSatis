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
        self.accounting_provider = self._init_accounting_provider()
        
    def _init_accounting_provider(self):
        acc_settings = self.settings.get("accounting", {})
        platform = acc_settings.get("active_platform", "none")
        
        if platform == "parasut":
            return ParasutProvider(acc_settings.get("parasut", {}))
        elif platform == "kolaybi":
            return KolayBiProvider(acc_settings.get("kolaybi", {}))
        return None
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
            "migros": {"enabled": False, "api_key": "", "store_id": ""},
            "whatsapp": {"enabled": False, "api_key": "", "service_name": ""},
            "accounting": {
                "active_platform": "none", # "none", "parasut", "kolaybi"
                "parasut": {"client_id": "", "client_secret": "", "username": "", "password": "", "company_id": ""},
                "kolaybi": {"api_key": "", "api_secret": ""}
            }
        }

    def save_settings(self, new_settings):
        self.settings = new_settings
        self.accounting_provider = self._init_accounting_provider() # Re-init on save
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving integration settings: {e}")
            return False

    def process_webhook(self, platform, data, menu_data=None):
        """
        Process incoming webhook data from platforms and convert to internal order format.
        """
        self.menu_data = menu_data # Store temporarily for mapping
        if platform == "yemeksepeti":
            return self._map_yemeksepeti(data)
        elif platform == "trendyol":
            return self._map_trendyol(data)
        elif platform == "getir":
            return self._map_getir(data)
        elif platform == "migros":
            return self._map_migros(data)
        elif platform == "whatsapp":
            return self._map_whatsapp(data)
        else:
            logger.warning(f"Unknown platform: {platform}")
            return None

    def send_to_accounting(self, order_data):
        """
        Send mapped order data to the active accounting provider.
        """
        if not self.accounting_provider:
            return False, "No active accounting provider"
        
        try:
            self.accounting_provider.authenticate()
            self.accounting_provider.send_invoice(order_data)
            return True, "Success"
        except Exception as e:
            logger.error(f"Accounting Integration Error: {e}")
            return False, str(e)

    def _get_item_price(self, urun_adi, platform, webhook_price):
        """
        Calculate the platform-specific price based on menu data and percentages.
        """
        if not self.menu_data:
            return webhook_price

        # Search for item in menu_data
        base_price = None
        item_markup = 0
        
        found = False
        for cat in self.menu_data:
            for item in self.menu_data[cat]:
                if item[0].lower() == urun_adi.lower():
                    base_price = item[1]
                    # Map platform to index
                    platform_idx = {"yemeksepeti": 2, "trendyol": 3, "getir": 4, "migros": 5}.get(platform)
                    if platform_idx and len(item) > platform_idx:
                        item_markup = item[platform_idx]
                    found = True
                    break
            if found: break
        
        if not found:
            return webhook_price

        # Use platform global markup if item markup is 0
        global_markup = self.settings.get(platform, {}).get('markup', 0)
        markup = item_markup if item_markup != 0 else global_markup
        
        if markup != 0:
            return base_price * (1 + markup / 100)
        
        # If no markup, but we have a base price and webhook_price is 0, use base_price
        if webhook_price == 0:
            return base_price
            
        return webhook_price

    def _map_yemeksepeti(self, data):
        # Placeholder for Yemeksepeti mapping logic
        # Expecting data format based on DeliveryHero/Yemeksepeti API
        try:
            order_id = data.get('id')
            items = []
            for entry in data.get('items', []):
                name = entry.get('name')
                price = self._get_item_price(name, "yemeksepeti", float(entry.get('price', 0)))
                items.append({
                    "urun": name,
                    "adet": entry.get('quantity', 1),
                    "fiyat": price,
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
                name = line.get('productName')
                price = self._get_item_price(name, "trendyol", float(line.get('price', 0)))
                items.append({
                    "urun": name,
                    "adet": line.get('quantity', 1),
                    "fiyat": price,
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
                name = product.get('name')
                price = self._get_item_price(name, "getir", float(product.get('price', 0)))
                items.append({
                    "urun": name,
                    "adet": product.get('count', 1),
                    "fiyat": price,
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
                name = item.get('productName')
                price = self._get_item_price(name, "migros", float(item.get('unitPrice', 0)))
                items.append({
                    "urun": name,
                    "adet": item.get('quantity', 1),
                    "fiyat": price,
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

    def _map_whatsapp(self, data):
        """
        Map WhatsApp message to internal order format.
        Expecting data like: {'from': '905321234567', 'text': '2 Burger, 1 Kola', 'name': 'Ahmet'}
        """
        try:
            phone = data.get('from', 'Unknown')
            text = data.get('text', '')
            customer = data.get('name', 'WhatsApp Müşteri')
            
            items = self._parse_whatsapp_message(text)
            
            if not items:
                logger.warning(f"Could not parse WhatsApp message: {text}")
                return None
                
            return {
                "masa": f"WP-{phone[-4:]}",
                "items": items,
                "platform": "WhatsApp",
                "external_id": f"WP-{datetime.datetime.now().strftime('%H%M%S')}",
                "customer": f"{customer} ({phone})"
            }
        except Exception as e:
            logger.error(f"Error mapping WhatsApp: {e}")
            return None

    def _parse_whatsapp_message(self, text):
        """
        Simple parser for WhatsApp messages.
        Recognizes formats like:
        - "2 Burger, 1 Kola"
        - "3 Adet Lahmacun"
        - "Pizza 2, Ayran 1"
        """
        import re
        items = []
        # Split by comma or newline
        lines = re.split(r'[,|\n]', text)
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            # Pattern 1: "2 Burger" or "2 adet Burger"
            match1 = re.search(r'(\d+)\s*(?:adet|x|u00d7)?\s*(.+)', line, re.IGNORECASE)
            # Pattern 2: "Burger 2"
            match2 = re.search(r'(.+?)\s*(\d+)', line)
            
            if match1:
                adet = int(match1.group(1))
                urun = match1.group(2).strip()
                price = self._get_item_price(urun, "whatsapp", 0)
                items.append({"urun": urun, "adet": adet, "fiyat": price, "tip": "whatsapp"})
            elif match2:
                urun = match2.group(1).strip()
                adet = int(match2.group(2))
                price = self._get_item_price(urun, "whatsapp", 0)
                items.append({"urun": urun, "adet": adet, "fiyat": price, "tip": "whatsapp"})
                
        return items

class BaseAccountingProvider:
    """Base class for accounting platforms like Paraşüt and KolayBi"""
    def __init__(self, config):
        self.config = config
        self.access_token = None

    def authenticate(self):
        raise NotImplementedError

    def send_invoice(self, order_data):
        """Map order data to invoice format and send to platform"""
        raise NotImplementedError

    def check_stock(self, item_name):
        """Check stock levels in the accounting platform"""
        raise NotImplementedError

class ParasutProvider(BaseAccountingProvider):
    def authenticate(self):
        # Implementation for Paraşüt OAuth2 flow
        logger.info("Authenticating with Paraşüt API...")
        pass

    def send_invoice(self, order_data):
        # Implementation for Paraşüt Invoice Creation
        logger.info(f"Sending invoice to Paraşüt for customer: {order_data.get('customer')}")
        pass

    def check_stock(self, item_name):
        pass

class KolayBiProvider(BaseAccountingProvider):
    def authenticate(self):
        # Implementation for KolayBi API Key flow
        logger.info("Authenticating with KolayBi API...")
        pass

    def send_invoice(self, order_data):
        # Implementation for KolayBi Invoice Creation
        logger.info(f"Sending invoice to KolayBi for customer: {order_data.get('customer')}")
        pass

    def check_stock(self, item_name):
        pass
