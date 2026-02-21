import socket
import json
import logging
import time

logger = logging.getLogger(__name__)

class POSManager:
    def __init__(self, enabled=False, ip="", port=0, pos_type="demo"):
        self.enabled = enabled
        self.ip = ip
        self.port = port
        self.pos_type = pos_type # "demo", "beko-json", "hugin", "generic"
        
    def sale(self, amount, table_name=""):
        """
        Send a sale request to the POS device.
        :param amount: Float amount in TL
        :param table_name: String table identifier
        :return: (bool success, str message)
        """
        if not self.enabled:
            return True, "POS entegrasyonu kapalı, nakit/kart işlemi veri tabanına kaydedildi."
            
        if self.pos_type == "demo":
            logger.info(f"POS DEMO: Masa {table_name} için {amount:.2f} TL ödeme alınıyor...")
            time.sleep(2) # Simulate processing
            return True, "İşlem Başarılı (DEMO)"
            
        try:
            # Create the payload based on device type
            payload = self._create_payload(amount, table_name)
            
            # Send request via TCP
            response = self._send_request(payload)
            
            return self._parse_response(response)
            
        except ConnectionRefusedError:
            logger.error(f"POS Bağlantı Hatası: {self.ip}:{self.port} bağlantısı reddedildi.")
            return False, f"POS cihazına bağlanılamadı ({self.ip}:{self.port})"
        except socket.timeout:
            logger.error(f"POS Zaman Aşımı: {self.ip}:{self.port} yanıt vermedi.")
            return False, "POS cihazından yanıt alınamadı (Zaman aşımı)"
        except Exception as e:
            logger.error(f"POS Beklenmedik Hata: {str(e)}")
            return False, f"POS Hatası: {str(e)}"

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

    def _send_request(self, payload):
        """Low level TCP socket communication"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(60) # POS processes can take time
            s.connect((self.ip, self.port))
            s.sendall(payload)
            
            # Simple buffer read - in real world you might need to handle EOF or length prefix
            data = s.recv(1024)
            return data.decode('utf-8')

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
