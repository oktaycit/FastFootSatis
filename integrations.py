# -*- coding: utf-8 -*-
"""
Delivery Platform Integration Manager
Restoran
"""

import json
import os
import datetime
import logging
import copy

try:
    import requests
except ImportError:
    requests = None

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
        elif platform == "mysoft":
            return MysoftProvider(acc_settings.get("mysoft", {}))
        return None

    def load_settings(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return self._merge_default_settings(json.load(f))
            except Exception as e:
                logger.error(f"Error loading integration settings: {e}")
        return self._default_settings()

    def _default_settings(self):
        return {
            "yemeksepeti": {"enabled": False, "api_key": "", "store_id": ""},
            "trendyol": {"enabled": False, "api_key": "", "api_secret": "", "supplier_id": ""},
            "getir": {"enabled": False, "app_token": "", "restaurant_id": ""},
            "migros": {"enabled": False, "api_key": "", "store_id": ""},
            "whatsapp": {"enabled": False, "api_key": "", "service_name": ""},
            "accounting": {
                "active_platform": "none", # "none", "parasut", "kolaybi", "mysoft"
                "parasut": {"client_id": "", "client_secret": "", "username": "", "password": "", "company_id": ""},
                "kolaybi": {"api_key": "", "api_secret": ""},
                "mysoft": {
                    "enabled": False,
                    "environment": "test",
                    "base_url": "",
                    "auth_endpoint": "",
                    "invoice_endpoint": "",
                    "username": "",
                    "password": "",
                    "api_key": "",
                    "bearer_token": "",
                    "company_tax_id": "",
                    "tenant_identifier_number": "",
                    "invoice_series": "",
                    "numbering_unit": "",
                    "sender_alias": "",
                    "receiver_alias": "",
                    "xslt_code": "",
                    "draft": True
                }
            }
        }

    def _merge_default_settings(self, raw):
        defaults = self._default_settings()
        merged = copy.deepcopy(defaults)
        for key, value in (raw or {}).items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            else:
                merged[key] = value
        acc = merged.setdefault("accounting", defaults["accounting"])
        default_acc = defaults["accounting"]
        for key, value in default_acc.items():
            if isinstance(value, dict):
                acc.setdefault(key, {})
                acc[key] = {**value, **acc.get(key, {})}
            else:
                acc.setdefault(key, value)
        return merged

    def save_settings(self, new_settings):
        self.settings = self._merge_default_settings(new_settings)
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


class MysoftProvider(BaseAccountingProvider):
    DOCUMENT_TYPE_MAP = {
        9005: "MATBU",
        9006: "EFATURA",
        9007: "EARSIV",
    }

    def __init__(self, config):
        super().__init__(config)
        self.session = requests.Session() if requests else None

    def authenticate(self):
        if not self.config.get("enabled", True):
            raise ValueError("Mysoft entegrasyonu kapalı")
        if not requests:
            raise RuntimeError("requests modülü yüklü değil")

        bearer_token = (self.config.get("bearer_token") or "").strip()
        api_key = (self.config.get("api_key") or "").strip()
        if bearer_token:
            self.access_token = bearer_token
            return
        if api_key:
            self.access_token = None
            return

        auth_endpoint = (self.config.get("auth_endpoint") or "").strip()
        username = (self.config.get("username") or "").strip()
        password = (self.config.get("password") or "").strip()
        if not auth_endpoint:
            raise ValueError("Mysoft auth endpoint veya token/API key girilmeli")
        if not username or not password:
            raise ValueError("Mysoft kullanıcı adı ve şifre girilmeli")

        url = self._build_url(auth_endpoint)
        response = self.session.post(url, json={
            "username": username,
            "password": password
        }, timeout=30)
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token") or data.get("token") or data.get("Token")
        if not token:
            raise ValueError("Mysoft auth yanıtında token bulunamadı")
        self.access_token = token

    def send_invoice(self, order_data):
        if not order_data.get("invoice_pending"):
            logger.info("Mysoft: fatura beklemeyen satış atlandı")
            return {"skipped": True}

        invoice_endpoint = (self.config.get("invoice_endpoint") or "").strip()
        if not invoice_endpoint:
            raise ValueError("Mysoft fatura endpoint'i girilmeli")

        payload = self.build_invoice_payload(order_data)
        headers = self._headers()
        url = self._build_url(invoice_endpoint)
        response = self.session.post(url, json=payload, headers=headers, timeout=45)
        response.raise_for_status()
        try:
            result = response.json()
        except ValueError:
            result = {"raw": response.text[:500]}
        logger.info(f"Mysoft fatura gönderildi: {payload.get('external_id')}")
        return result

    def build_invoice_payload(self, order_data):
        document_type = int(order_data.get("invoice_document_type") or 9006)
        invoice_kind = self.DOCUMENT_TYPE_MAP.get(document_type, "EFATURA")
        tax_id = str(order_data.get("invoice_tax_id") or "").strip()
        serial_no = str(order_data.get("invoice_serial_no") or "").strip()
        if len(tax_id) not in (10, 11):
            raise ValueError("Mysoft faturası için VKN/TCKN gerekli")
        if not serial_no:
            raise ValueError("Mysoft faturası için fatura seri no gerekli")

        default_vat_rate = self._sanitize_vat_rate(
            order_data.get("default_tax_rate", self.config.get("default_tax_rate", 10))
        )
        items = []
        for item in order_data.get("items", []):
            quantity = float(item.get("adet") or 1)
            unit_price = float(item.get("fiyat") or 0)
            items.append({
                "name": item.get("urun") or "Ürün",
                "quantity": quantity,
                "unit_price": unit_price,
                "vat_rate": int(item.get("tax_percent") or item.get("kdv") or default_vat_rate),
                "line_total": round(quantity * unit_price, 2)
            })

        return {
            "source": "FastFootSatis",
            "draft": bool(self.config.get("draft", True)),
            "external_id": f"{order_data.get('masa', 'SATIS')}-{order_data.get('timestamp')}",
            "invoice_kind": invoice_kind,
            "document_type": document_type,
            "serial_no": serial_no,
            "issue_datetime": str(order_data.get("timestamp") or datetime.datetime.now()),
            "seller_tax_id": self.config.get("company_tax_id", ""),
            "customer": {
                "name": order_data.get("customer") or "Genel Müşteri",
                "tax_id": tax_id,
                "note": order_data.get("invoice_note") or ""
            },
            "payment": {
                "type": order_data.get("payment_type") or "",
                "total": float(order_data.get("total") or 0)
            },
            "items": items,
            "totals": {
                "payable": float(order_data.get("total") or 0),
                "complimentary": float(order_data.get("ikram_total") or 0)
            }
        }

    @staticmethod
    def _sanitize_vat_rate(value):
        try:
            rate = float(value)
        except (TypeError, ValueError):
            rate = 10.0
        return max(0.0, min(rate, 100.0))

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        api_key = (self.config.get("api_key") or "").strip()
        bearer_token = self.access_token or (self.config.get("bearer_token") or "").strip()
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        if api_key:
            headers["X-API-Key"] = api_key
        return headers

    def _build_url(self, endpoint):
        endpoint = endpoint.strip()
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        base_url = (self.config.get("base_url") or "").strip().rstrip("/")
        if not base_url:
            raise ValueError("Mysoft base URL girilmeli")
        return f"{base_url}/{endpoint.lstrip('/')}"

    def check_stock(self, item_name):
        return None
