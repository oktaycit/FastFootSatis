import socket
import json
import logging
import time
import threading
import uuid

try:
    import requests
except ImportError:
    class _MissingRequests:
        class RequestException(Exception):
            pass

        @staticmethod
        def post(*args, **kwargs):
            raise _MissingRequests.RequestException(
                "requests modülü yüklü değil; POS/ÖKC bridge için requirements.txt kurulmalı"
            )

        @staticmethod
        def get(*args, **kwargs):
            raise _MissingRequests.RequestException(
                "requests modülü yüklü değil; POS/ÖKC bridge için requirements.txt kurulmalı"
            )

    requests = _MissingRequests

logger = logging.getLogger(__name__)

class POSManager:
    TOKEN_BRIDGE_TYPES = {"token-bridge", "beko-token", "beko-yn-okc"}
    TOKEN_BRIDGE_STARTUP_GRACE_SECONDS = 180
    TOKEN_BRIDGE_STARTUP_WAIT_SECONDS = 45
    TOKEN_BRIDGE_HEALTH_POLL_SECONDS = 3
    PAYMENT_TYPE_CODES = {
        "nakit": 1,
        "kredi kartı": 3,
        "kredi karti": 3,
        "kart": 3,
        "yemek kartı": 7,
        "yemek karti": 7,
        "açık hesap": 17,
        "acik hesap": 17,
    }

    def __init__(self, enabled=False, ip="", port=0, pos_type="demo"):
        self.enabled = enabled
        self.ip = ip
        self.port = port
        self.pos_type = pos_type # "demo", "beko-json", "hugin", "generic", "token-bridge"
        self._sale_lock = threading.Lock()
        
    def sale(self, amount, table_name="", items=None, payments=None, order_id=None,
             invoice_pending=False, invoice_info=None):
        """
        Send a sale request to the POS device.
        :param amount: Float amount in TL
        :param table_name: String table identifier
        :param items: Optional adisyon items for fiscal OKC basket payloads
        :param payments: Optional payment list for fiscal OKC basket payloads
        :param order_id: Optional stable basket id
        :param invoice_pending: Send Token bridge basket as invoice info receipt
        :param invoice_info: Dict with document_type, tax_id, serial_no and note
        :return: (bool success, str message)
        """
        if not self.enabled:
            return True, "POS entegrasyonu kapalı, nakit/kart işlemi veri tabanına kaydedildi."
            
        if self.pos_type == "demo":
            logger.info(f"POS DEMO: Masa {table_name} için {amount:.2f} TL ödeme alınıyor...")
            time.sleep(2) # Simulate processing
            return True, "İşlem Başarılı (DEMO)"

        # Eşzamanlı ÖKC isteklerini engelle — cihaz aynı anda tek işlem yapabilir
        if not self._sale_lock.acquire(timeout=10):
            logger.warning("POS Lock: Başka bir ÖKC işlemi devam ediyor, istek reddedildi.")
            return False, "Başka bir ÖKC işlemi devam ediyor, lütfen bekleyin"

        try:
            if self.pos_type in self.TOKEN_BRIDGE_TYPES:
                # Bridge sağlık kontrolü — cihaz bağlı mı ve bekleyen işlem var mı?
                bridge_ok, bridge_msg = self._check_bridge_health()
                if not bridge_ok:
                    return False, bridge_msg

                payload = self._create_token_bridge_payload(
                    table_name=table_name,
                    items=items or [],
                    payments=payments or [{"type": "Kredi Kartı", "amount": amount}],
                    order_id=order_id,
                    invoice_pending=invoice_pending,
                    invoice_info=invoice_info,
                )
                response = self._send_token_bridge_request(payload)
                return self._parse_token_bridge_response(response, invoice_pending=invoice_pending)

            payload = self._create_payload(amount, table_name)
            response = self._send_request(payload)
            return self._parse_response(response)
            
        except ConnectionRefusedError:
            logger.error(f"POS Bağlantı Hatası: {self.ip}:{self.port} bağlantısı reddedildi.")
            return False, f"POS cihazına bağlanılamadı ({self.ip}:{self.port})"
        except socket.timeout:
            logger.error(f"POS Zaman Aşımı: {self.ip}:{self.port} yanıt vermedi.")
            return False, "POS cihazından yanıt alınamadı (Zaman aşımı)"
        except requests.RequestException as e:
            logger.error(f"ÖKC Bridge Bağlantı Hatası: {str(e)}")
            return False, f"ÖKC bridge bağlantı hatası: {str(e)}"
        except Exception as e:
            logger.error(f"POS Beklenmedik Hata: {str(e)}")
            return False, f"POS Hatası: {str(e)}"
        finally:
            self._sale_lock.release()

    def _create_payload(self, amount, table_name):
        """Prepare payload based on pos_type"""
        if self.pos_type == "beko-json":
            return json.dumps({
                "command": "SALE",
                "amount": int(amount * 100), # Para birimi genelde kuruş cinsinden istenir
                "currency": "TRY",
                "extOrderNum": table_name[:20],
                "printReceipt": True
            }).encode('utf-8')
        
        # Generic JSON or default
        return json.dumps({
            "type": "sale",
            "amount": amount,
            "table": table_name
        }).encode('utf-8')

    def _create_token_bridge_payload(self, table_name, items, payments, order_id=None,
                                     invoice_pending=False, invoice_info=None):
        """Build the Token IntegrationHub basket JSON sent to the Windows bridge."""
        token_items = [self._create_token_item(item) for item in items]
        token_items = [item for item in token_items if item is not None]
        token_payments = [self._create_token_payment(payment) for payment in payments]
        token_payments = [payment for payment in token_payments if payment is not None]

        if not token_items:
            raise ValueError("ÖKC sepeti için ürün satırı bulunamadı")
        if not token_payments:
            raise ValueError("ÖKC sepeti için ödeme satırı bulunamadı")

        items_total = sum(item["price"] * item["quantity"] for item in token_items)
        payments_total = sum(payment["amount"] * 1000 for payment in token_payments)
        if abs(items_total - payments_total) > 10:
            raise ValueError(
                "ÖKC sepet toplamı ile ödeme toplamı eşleşmiyor "
                f"({items_total / 100000:.2f} TL / {payments_total / 100000:.2f} TL)"
            )

        payload = {
            "basketID": order_id or str(uuid.uuid4()),
            "createInvoice": False,
            "documentType": 0,
            "isVoid": False,
            "items": token_items,
            "paymentItems": token_payments,
            "customerInfo": None,
            "adjust": None,
            "infoReceiptInfo": None,
            "isWayBill": False,
            "note": table_name[:64] if table_name else None,
        }

        if invoice_pending:
            invoice_info = invoice_info or {}
            document_type = int(invoice_info.get("document_type") or 9006)
            tax_id = str(invoice_info.get("tax_id") or "").strip()
            serial_no = str(invoice_info.get("serial_no") or "").strip()
            if document_type not in (9005, 9006, 9007):
                document_type = 9006
            if len(tax_id) not in (10, 11):
                raise ValueError("Fatura bilgi fişi için geçerli VKN/TCKN gerekli")
            if not serial_no:
                raise ValueError("Fatura bilgi fişi için seri no gerekli")

            payload["documentType"] = document_type
            payload["customerInfo"] = {"taxID": tax_id}
            payload["infoReceiptInfo"] = {"serialNo": serial_no[:32]}
            note_parts = [table_name[:32] if table_name else "", invoice_info.get("note") or ""]
            payload["note"] = " | ".join(part for part in note_parts if part)[:64] or None

        return payload

    def _create_token_item(self, item):
        name = str(item.get("urun") or item.get("name") or "").strip()
        if not name:
            return None

        price = self._to_minor_units(item.get("fiyat", item.get("price", 0)))
        quantity = self._to_quantity_units(item.get("adet", item.get("quantity", 1)))
        if price < 0 or quantity <= 0:
            return None

        return {
            "barcode": str(item.get("barcode") or item.get("barkod") or "")[:32],
            "name": name[:64],
            "pluNo": int(item.get("pluNo") or item.get("plu_no") or 0),
            "price": price,
            "sectionNo": int(item.get("sectionNo") or item.get("section_no") or 1),
            "taxPercent": int(item.get("taxPercent") or item.get("tax_percent") or 1000),
            "type": int(item.get("type") or 0),
            "unit": item.get("unit") or "Adet",
            "vatID": int(item.get("vatID") or item.get("vat_id") or 0),
            "limit": int(item.get("limit") or 0),
            "quantity": quantity,
            "paymentType": int(item.get("paymentType") or 0),
            "total": price * quantity,
        }

    def _create_token_payment(self, payment):
        amount = self._to_minor_units(payment.get("amount", 0))
        if amount <= 0:
            return None

        payment_type_name = str(payment.get("type") or "Kredi Kartı").strip()
        payment_name = str(payment.get("description") or payment_type_name).strip()
        token_type = payment.get("token_type")
        if token_type is None:
            token_type = self.PAYMENT_TYPE_CODES.get(payment_type_name.lower(), 3)

        return {
            "description": payment_name,
            "amount": amount,
            "type": int(token_type),
            "batchNo": 0,
            "currencyId": 0,
            "operatorId": int(payment.get("operatorId") or payment.get("operator_id") or 0),
            "status": 0,
            "txnNo": 0,
        }

    def _to_minor_units(self, amount):
        return int(round(float(amount) * 100))

    def _to_quantity_units(self, quantity):
        return int(round(float(quantity) * 1000))

    def _check_bridge_health(self):
        """Bridge sağlık kontrolü — cihaz bağlı mı ve bekleyen işlem var mı?"""
        try:
            url = f"http://{self.ip}:{self.port}/health"
            resp = requests.get(url, timeout=5)
            data = resp.json()
            data = self._wait_for_token_bridge_startup(url, data)
            device_connected = data.get("deviceConnected")
            device_state_known = data.get("deviceStateKnown")
            bridge_uptime = self._safe_int(data.get("uptimeSeconds"))
            if device_connected is False and device_state_known is True:
                logger.error("ÖKC Bridge: Cihaz bağlı değil")
                return False, "ÖKC cihazı bağlı değil, lütfen USB bağlantısını kontrol edin"
            if device_state_known is False and 0 <= bridge_uptime < self.TOKEN_BRIDGE_STARTUP_GRACE_SECONDS:
                logger.warning(
                    "ÖKC Bridge yeni açılmış ve cihaz durumu henüz bilinmiyor; satış isteği bekletildi"
                )
                return False, "ÖKC bridge başlatılıyor, cihaz bağlantısı bekleniyor. Lütfen biraz sonra tekrar deneyin"
            if device_connected is False:
                logger.warning(
                    "ÖKC Bridge cihaz durumu henüz kesin değil, satış isteği bridge'e iletilecek"
                )
            pending = data.get("pendingSales", 0)
            if pending > 0:
                logger.warning(f"ÖKC Bridge: {pending} bekleyen işlem var, yeni istek bekleniyor...")
                # Bekleyen işlemin bitmesini bekle (maks 15 saniye)
                for _ in range(15):
                    time.sleep(1)
                    try:
                        resp2 = requests.get(url, timeout=5)
                        if resp2.json().get("pendingSales", 0) == 0:
                            break
                    except Exception:
                        pass
                else:
                    return False, "ÖKC cihazında tamamlanmamış bir işlem var, lütfen biraz bekleyin"
            return True, ""
        except requests.RequestException:
            # Health endpoint'e ulaşılamıyorsa bridge çalışmıyor olabilir
            logger.warning("ÖKC Bridge health endpoint'e ulaşılamadı, satış yine de deneniyor")
            return True, ""

    def _wait_for_token_bridge_startup(self, url, data):
        """Yeni açılan bridge cihaz state callback'ini bekliyorsa kısa süre poll et."""
        device_state_known = data.get("deviceStateKnown")
        bridge_uptime = self._safe_int(data.get("uptimeSeconds"), fallback=-1)
        if device_state_known is True:
            return data
        if bridge_uptime < 0 or bridge_uptime >= self.TOKEN_BRIDGE_STARTUP_GRACE_SECONDS:
            return data

        wait_seconds = min(
            self.TOKEN_BRIDGE_STARTUP_WAIT_SECONDS,
            max(0, self.TOKEN_BRIDGE_STARTUP_GRACE_SECONDS - bridge_uptime),
        )
        if wait_seconds <= 0:
            return data

        logger.info(
            "ÖKC Bridge yeni açılmış; cihaz state callback'i için %.0f sn bekleniyor",
            wait_seconds,
        )
        deadline = time.monotonic() + wait_seconds
        latest = data
        while time.monotonic() < deadline:
            time.sleep(self.TOKEN_BRIDGE_HEALTH_POLL_SECONDS)
            try:
                resp = requests.get(url, timeout=5)
                latest = resp.json()
            except requests.RequestException:
                continue

            if latest.get("deviceStateKnown") is True:
                return latest
            latest_uptime = self._safe_int(latest.get("uptimeSeconds"), fallback=bridge_uptime)
            if latest_uptime >= self.TOKEN_BRIDGE_STARTUP_GRACE_SECONDS:
                return latest

        return latest

    @staticmethod
    def _safe_int(value, fallback=0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def _send_token_bridge_request(self, payload):
        """Send a Token basket payload to the Windows terminal OKC bridge."""
        url = f"http://{self.ip}:{self.port}/api/sale"
        response = requests.post(url, json=payload, timeout=130)
        try:
            result = response.json()
        except ValueError:
            response.raise_for_status()
            return {"success": False, "message": response.text[:200]}

        # Hata/iptal durumunda Bridge'in DLL ACK döngüsünü tamamlaması için bekle.
        # Bu olmadan kullanıcı hemen "tekrar dene" dediğinde eski işlemle çakışabilir.
        if result.get("status") == -1 or not result.get("success"):
            logger.info("ÖKC işlemi başarısız, DLL ACK döngüsü için 2s bekleniyor...")
            time.sleep(2)

        return result

    def _send_request(self, payload):
        """Low level TCP socket communication"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(60) # POS processes can take time
            s.connect((self.ip, self.port))
            s.sendall(payload)
            
            # Simple buffer read - in real world you might need to handle EOF or length prefix
            data = s.recv(1024)
            return data.decode('utf-8')

    def _parse_token_bridge_response(self, response, invoice_pending=False):
        """Parse response from the Windows OKC bridge."""
        payment_error = self._get_token_payment_error(response)
        if payment_error:
            return False, f"ÖKC Red: {payment_error}"

        if response.get("success") is True or response.get("status") in (0, "success"):
            receipt_no = response.get("receiptNo") or response.get("receipt_no")
            z_no = response.get("zNo") or response.get("z_no")
            document_type = response.get("documentType") or response.get("document_type")
            if invoice_pending or document_type in (9005, 9006, 9007, "9005", "9006", "9007"):
                return True, f"ÖKC fatura bilgi fişi tamamlandı (Fiş: {receipt_no or '-'}, Z: {z_no or '-'})"
            if receipt_no or z_no:
                return True, f"ÖKC fişi tamamlandı (Fiş: {receipt_no or '-'}, Z: {z_no or '-'})"
            return True, response.get("message") or "ÖKC fişi tamamlandı"

        message = response.get("message") or response.get("error") or "ÖKC bridge işlemi reddetti"
        return False, f"ÖKC Red: {message}"

    def _get_token_payment_error(self, response):
        """Return a cashier-friendly message if any OKC payment item reports failure."""
        sale_info = response
        raw_sale_info = response.get("rawSaleInfo") or response.get("raw_sale_info")
        if isinstance(raw_sale_info, str) and raw_sale_info.strip():
            try:
                sale_info = json.loads(raw_sale_info)
            except json.JSONDecodeError:
                sale_info = response

        payment_items = (
            sale_info.get("paymentItems")
            or sale_info.get("payments")
            or response.get("paymentItems")
            or response.get("payments")
            or []
        )
        if not isinstance(payment_items, list):
            return ""

        failed = []
        successful_total = 0
        for index, payment in enumerate(payment_items, start=1):
            if not isinstance(payment, dict):
                continue

            if self._is_token_payment_failed(payment):
                label = payment.get("description") or payment.get("name") or f"Ödeme {index}"
                failed.append(str(label))
            else:
                successful_total += self._token_payment_total_units(payment)

        if not failed:
            return ""

        # A declined card can be followed by cash/current-account payment on the OKC.
        # If the successful payment lines cover the fiscal basket total, keep it closed.
        if self._token_response_success(response):
            sale_total = self._token_sale_total_units(sale_info)
            if sale_total <= 0 or successful_total >= sale_total - 10:
                return ""

        detail = ", ".join(failed)
        return f"{detail} başarısız. Adisyon kapatılmadı; ödeme tutarlarını kontrol edip tekrar deneyin"

    def _token_response_success(self, response):
        if response.get("success") is True or response.get("status") == "success":
            return True
        try:
            return int(response.get("status")) == 0
        except (TypeError, ValueError):
            return False

    def _is_token_payment_failed(self, payment):
        status_text = " ".join(str(payment.get(key) or "") for key in (
            "message", "error", "errorMessage", "statusMessage"
        ))
        normalized_text = status_text.casefold()
        has_decline_text = any(token in normalized_text for token in (
            "redd", "declin", "fail", "hata", "yetersiz", "bakiye", "iptal"
        ))

        try:
            status_code = int(payment.get("status"))
        except (TypeError, ValueError):
            status_code = 0

        return status_code < 0 or has_decline_text

    def _token_sale_total_units(self, sale_info):
        items = sale_info.get("items") or sale_info.get("basketItems") or []
        if isinstance(items, list):
            total = 0
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_total = self._safe_number(
                    item.get("total") or item.get("lineTotal") or item.get("line_total")
                )
                if item_total > 0:
                    total += int(round(item_total))
                    continue

                price = self._safe_number(item.get("price"))
                quantity = self._safe_number(item.get("quantity"))
                if price > 0 and quantity > 0:
                    total += int(round(price * quantity))
            if total > 0:
                return total

        total = self._safe_number(
            sale_info.get("total") or sale_info.get("totalAmount") or sale_info.get("amount")
        )
        return int(round(total * 1000)) if total > 0 else 0

    def _token_payment_total_units(self, payment):
        amount = self._safe_number(payment.get("amount"))
        return int(round(amount * 1000)) if amount > 0 else 0

    @staticmethod
    def _safe_number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _parse_response(self, response_str):
        """Parse the response from POS device"""
        try:
            resp = json.loads(response_str)
            
            # This logic depends heavily on the specific POS protocol
            # Assuming a generic success field for now
            if resp.get("status") == "success" or resp.get("resultCode") == 0:
                return True, "İşlem Başarılı"
            
            error_msg = resp.get("message") or resp.get("errorDescription") or "Bilinmeyen hata"
            return False, f"POS Red: {error_msg}"
            
        except json.JSONDecodeError:
            # Fallback if response is not JSON
            if "OK" in response_str.upper():
                return True, "İşlem Başarılı"
            return False, f"Geçersiz yanıt: {response_str[:50]}"
