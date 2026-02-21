import socket
import time
import sys

def simulate_call(phone="05321234567"):
    """Signal 7 formatında bir çağrı simüle eder"""
    try:
        # Web sunucu Port 101'i dinliyor olmalı
        host = '127.0.0.1'
        port = 101
        
        print(f"🚀 Simülasyon başlatılıyor: {phone} numaralı çağrı gönderilecek...")
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            try:
                s.connect((host, port))
            except ConnectionRefusedError:
                print(f"❌ Hata: {host}:{port} bağlantısı reddedildi. Sunucunun açık olduğundan emin olun.")
                return

            # Signal 7 formatı: ID=1,NO=05321234567,DATE=...
            payload = f"ID=1,NO={phone},DATE={time.strftime('%d/%m/%Y')},TIME={time.strftime('%H:%M')}\r\n"
            s.sendall(payload.encode('utf-8'))
            print(f"✅ Veri gönderildi: {payload.strip()}")
            
    except Exception as e:
        print(f"❌ Beklenmedik hata: {e}")

if __name__ == "__main__":
    phone_num = sys.argv[1] if len(sys.argv) > 1 else "05321234567"
    simulate_call(phone_num)
