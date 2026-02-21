import socket
import json
import threading
import time

def pos_simulator(port=5000):
    """Simulates a POS device with JSON protocol"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', port))
        s.listen(1)
        print(f"🚀 POS Simülatörü başladı: 127.0.0.1:{port}")
        
        while True:
            conn, addr = s.accept()
            with conn:
                print(f"📡 Bağlantı alındı: {addr}")
                data = conn.recv(1024)
                if not data:
                    break
                
                try:
                    request = json.loads(data.decode('utf-8'))
                    print(f"📥 İstek: {request}")
                    
                    amount = request.get('amount')
                    if amount:
                        print(f"💳 {amount/100 if 'beko' in str(request) else amount:.2f} TL ödeme işleniyor...")
                        time.sleep(3) # Simulate user interaction on POS
                        
                        response = {
                            "status": "success",
                            "resultCode": 0,
                            "message": "İşlem Başarılı",
                            "authCode": "123456",
                            "rrn": "987654321"
                        }
                    else:
                        response = {"status": "error", "message": "Geçersiz tutar"}
                        
                    conn.sendall(json.dumps(response).encode('utf-8'))
                    print(f"📤 Yanıt gönderildi: {response}")
                    
                except Exception as e:
                    print(f"❌ Hata: {e}")
                    conn.sendall(b"ERROR")

if __name__ == "__main__":
    pos_simulator()
