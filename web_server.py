#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastFootSatış - Web Server
Flask tabanlı restoran yönetim sistemi
"""

from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import threading
import time
import datetime
import json
import os
import sys
import logging
import socket
import subprocess
import platform
import uuid
import serial
import serial.tools.list_ports
import urllib.parse
from collections import defaultdict
from integrations import IntegrationManager
from pos_integration import POSManager

# Database modülünü yükle
try:
    from database import db
    from courier_integration import CourierIntegration
    USE_DATABASE = True
    print("✓ PostgreSQL veri tabanı modülü yüklendi")
except Exception as e:
    USE_DATABASE = False
    print(f"⚠ Veri tabanı bağlantısı yapılamadı: {e}")

# PDF desteği
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    
    LOCAL_FONT_PATH = "arial.ttf"
    WIN_FONT_PATH = "C:/Windows/Fonts/arial.ttf"
    
    if os.path.exists(LOCAL_FONT_PATH):
        pdfmetrics.registerFont(TTFont('Arial-Turkce', LOCAL_FONT_PATH))
        PDF_FONT = 'Arial-Turkce'
    elif os.path.exists(WIN_FONT_PATH):
        pdfmetrics.registerFont(TTFont('Arial-Turkce', WIN_FONT_PATH))
        PDF_FONT = 'Arial-Turkce'
    else:
        PDF_FONT = 'Helvetica'
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("⚠ PDF desteği yok")

# Sabit değerler
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(SCRIPT_DIR, "config.txt")
MENU_FILE = os.path.join(SCRIPT_DIR, "menu.txt")
FIS_KLASORU = os.path.join(SCRIPT_DIR, "Fisler")
COUNTER_FILE = os.path.join(SCRIPT_DIR, "sira_no.txt")
WAITERS_FILE = os.path.join(SCRIPT_DIR, "waiters.json")
INTEGRATION_CONFIG = os.path.join(SCRIPT_DIR, "integrations.json")
SALONS_FILE = os.path.join(SCRIPT_DIR, "salons.json")
CASHIERS_FILE = os.path.join(SCRIPT_DIR, "cashiers.json")
ACTIVE_ADISYONLAR_FILE = os.path.join(SCRIPT_DIR, "active_adisyonlar.json")
SERVER_PORT = 5555

# Klasörleri oluştur
if not os.path.exists(FIS_KLASORU):
    os.makedirs(FIS_KLASORU)

# Flask app setup
app = Flask(__name__, static_folder='web', static_url_path='')
app.config['SECRET_KEY'] = 'fastfoot_secret_key_2026'
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='threading',
                   max_http_buffer_size=1000000,
                   ping_timeout=60000,
                   ping_interval=25000)

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_local_ip():
    """Yerel IP adresini al"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

class RestaurantServer:
    """Ana restoran yönetim sınıfı"""
    
    def __init__(self):
        # Sistem ayarları
        self.company_name = "RESTORAN"
        self.terminal_id = "1"
        self.admin_password = "1234"
        self.paket_sayisi = 5
        self.direct_print = False
        self.salons = []
        
        # Entegrasyonlar
        self.integration_manager = IntegrationManager(INTEGRATION_CONFIG)
        if USE_DATABASE:
            try:
                self.courier_manager = CourierIntegration(db)
            except NameError:
                self.courier_manager = None
        else:
            self.courier_manager = None
        self.pos_manager = POSManager()

        self.cid_port = 101 # Caller ID Port (Signal 7 standardı)
        self.cid_type = 'tcp' # 'tcp' veya 'serial'
        self.cid_serial_port = 'COM3'
        self.cid_enabled = True
        
        # Adisyon durumları
        self.adisyonlar = {}
        self.current_selections = {}  # {sid: masa_adi}
        
        # Menu
        self.menu_data = {}
        
        # Garsonlar ve Kasiyerler
        self.waiters = [] # [{"name": "Ahmet", "pin": "1234"}]
        self.cashiers = [] # [{"name": "Kasa 1"}]
        
        # Aktif bağlantılar
        self.active_connections = {}
        self.waiter_sessions = defaultdict(set) # waiter_name -> set(sids)
        
        # Terminal sunucusu
        self.terminal_thread = None
        self.running = False
        
        # Ayarları yükle
        self.load_settings()
        self.load_salons()
        self.load_waiters()
        self.load_cashiers()
        self.refresh_adisyonlar()
        self.load_active_adisyonlar() # Aktif adisyonları geri yükle
        self.load_menu_data()
        
        # Sid -> Kasa ID haritalaması (Vardiya işlemleri için)
        self.sid_kasa_map = {} # {sid: kasa_id}
        
        logger.info("🚀 RestaurantServer initialized")
        logger.info(f"📊 Masa: {self.masa_sayisi}, Paket: {self.paket_sayisi}")
        logger.info(f"📡 IP: {get_local_ip()}")
    
    def load_settings(self):
        """Ayarları dosyadan yükle"""
        defaults = {
            "password": "1234",
            "direct_print": "HAYIR",
            "masa_sayisi": "30",
            "paket_sayisi": "5",
            "firma_ismi": "RESTORAN OTOMASYON",
            "terminal_id": "1",
            "cid_port": "101",
            "cid_type": "tcp",
            "cid_serial_port": "COM3",
            "cid_enabled": "EVET",
            "pos_enabled": "HAYIR",
            "pos_ip": "127.0.0.1",
            "pos_port": "5000",
            "pos_type": "demo"
        }
        
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        if ":" in line:
                            key, value = line.strip().split(":", 1)
                            defaults[key] = value
            except Exception as e:
                logger.error(f"Ayar yükleme hatası: {e}")
        
        self.admin_password = defaults["password"]
        self.direct_print = (defaults["direct_print"] == "EVET")
        self.masa_sayisi = int(defaults["masa_sayisi"])
        self.paket_sayisi = int(defaults["paket_sayisi"])
        self.company_name = defaults["firma_ismi"]
        self.terminal_id = defaults["terminal_id"]
        self.cid_port = int(defaults["cid_port"])
        self.cid_type = defaults["cid_type"]
        self.cid_serial_port = defaults["cid_serial_port"]
        self.cid_enabled = (defaults["cid_enabled"] == "EVET")
        
        # POS Ayarları
        self.pos_enabled = (defaults["pos_enabled"] == "EVET")
        self.pos_ip = defaults["pos_ip"]
        self.pos_port = int(defaults["pos_port"])
        self.pos_type = defaults["pos_type"]
        self.pos_manager = POSManager(self.pos_enabled, self.pos_ip, self.pos_port, self.pos_type)
    
    def save_settings(self):
        """Ayarları dosyaya kaydet"""
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                f.write(f"password:{self.admin_password}\n")
                f.write(f"direct_print:{'EVET' if self.direct_print else 'HAYIR'}\n")
                f.write(f"masa_sayisi:{self.masa_sayisi}\n")
                f.write(f"paket_sayisi:{self.paket_sayisi}\n")
                f.write(f"firma_ismi:{self.company_name}\n")
                f.write(f"terminal_id:{self.terminal_id}\n")
                f.write(f"cid_port:{self.cid_port}\n")
                f.write(f"cid_type:{self.cid_type}\n")
                f.write(f"cid_serial_port:{self.cid_serial_port}\n")
                f.write(f"cid_enabled:{'EVET' if self.cid_enabled else 'HAYIR'}\n")
                f.write(f"pos_enabled:{'EVET' if self.pos_enabled else 'HAYIR'}\n")
                f.write(f"pos_ip:{self.pos_ip}\n")
                f.write(f"pos_port:{self.pos_port}\n")
                f.write(f"pos_type:{self.pos_type}\n")
            return True
        except Exception as e:
            logger.error(f"Ayar kaydetme hatası: {e}")
            return False

    def get_system_info(self):
        """Sistem bilgilerini döndür"""
        return {
            'company_name': self.company_name,
            'terminal_id': self.terminal_id,
            'ip': get_local_ip(),
            'masa_sayisi': self.masa_sayisi,
            'paket_sayisi': self.paket_sayisi,
            'salons': self.salons,
            'database': USE_DATABASE,
            'pdf': PDF_SUPPORT,
            'cid_enabled': self.cid_enabled,
            'pos_enabled': self.pos_enabled
        }

    def get_sid_active_shift(self, sid):
        """Socket SID'ine bağlı aktif vardiyayı getir"""
        if not USE_DATABASE:
            # DB yoksa Mac/Demo modu için her zaman açık bir vardiya varmış gibi davran
            return {
                'id': 0,
                'kasiyer': 'Demo Kasiyer',
                'kasa_id': 1,
                'durum': 'acik',
                'acilis_zamani': datetime.datetime.now().isoformat()
            }
        
        kasa_id = self.sid_kasa_map.get(sid)
        if not kasa_id: return None
        
        from decimal import Decimal
        shift = db.get_active_shift_by_kasa(kasa_id)
        if shift:
            shift_dict = dict(shift)
            if 'acilis_zamani' in shift_dict and hasattr(shift_dict['acilis_zamani'], 'isoformat'):
                shift_dict['acilis_zamani'] = shift_dict['acilis_zamani'].isoformat()
            if 'kapanis_zamani' in shift_dict and hasattr(shift_dict['kapanis_zamani'], 'isoformat'):
                shift_dict['kapanis_zamani'] = shift_dict['kapanis_zamani'].isoformat()
            
            # Decimal değerleri float'a çevir
            for key in ['acilis_bakiyesi', 'kapanis_nakit', 'kapanis_kart']:
                if key in shift_dict and isinstance(shift_dict[key], Decimal):
                    shift_dict[key] = float(shift_dict[key])
                    
            return shift_dict
            
        return None

    def load_waiters(self):
        """Garson listesini yükle"""
        if os.path.exists(WAITERS_FILE):
            try:
                with open(WAITERS_FILE, "r", encoding="utf-8") as f:
                    self.waiters = json.load(f)
                logger.info(f"✓ {len(self.waiters)} garson yüklendi")
            except Exception as e:
                logger.error(f"Garson yükleme hatası: {e}")
                self.waiters = []
        else:
            self.waiters = []

    def save_waiters(self):
        """Garsonları dosyaya kaydet"""
        try:
            with open(WAITERS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.waiters, f, ensure_ascii=False, indent=2)
            logger.info("✓ Garsonlar kaydedildi")
            return True
        except Exception as e:
            logger.error(f"Garson kaydetme hatası: {e}")
            return False

    def load_cashiers(self):
        """Kasiyerleri dosyadan yükle"""
        if os.path.exists(CASHIERS_FILE):
            try:
                with open(CASHIERS_FILE, "r", encoding="utf-8") as f:
                    self.cashiers = json.load(f)
                logger.info(f"✓ {len(self.cashiers)} kasiyer yüklendi")
            except Exception as e:
                logger.error(f"Kasiyer yükleme hatası: {e}")
                self.cashiers = []
        else:
            self.cashiers = []

    def save_cashiers(self):
        """Kasiyerleri dosyaya kaydet"""
        try:
            with open(CASHIERS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cashiers, f, ensure_ascii=False, indent=2)
            logger.info("✓ Kasiyerler kaydedildi")
            return True
        except Exception as e:
            logger.error(f"Kasiyer kaydetme hatası: {e}")
            return False
            
    def send_to_kitchen_legacy(self, masa_adi, urun_adi, adet=1):
        """Mevcut mutfak.py (port 5556) sistemine sipariş gönderir"""
        def task():
            try:
                kitchen_ip = getattr(self, 'kitchen_ip', '127.0.0.1')
                kitchen_port = getattr(self, 'kitchen_port', 5556)
                
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.settimeout(3)
                client.connect((kitchen_ip, kitchen_port))
                
                payload = {
                    "islem": "yeni_siparis",
                    "masa": masa_adi,
                    "siparisler": [{"urun": urun_adi, "adet": adet}],
                    "saat": datetime.datetime.now().strftime("%H:%M:%S"),
                    "terminal": self.terminal_id
                }
                
                client.send(json.dumps(payload).encode('utf-8'))
                client.close()
                logger.info(f"👨‍🍳 Legacy Mutfak onayladı: {urun_adi} -> {masa_adi}")
            except Exception as e:
                logger.error(f"⚠ Legacy Mutfak ekranına bağlanılamadı: {e}")
                
        threading.Thread(target=task, daemon=True).start()

    def load_salons(self):
        """Salon listesini yükle"""
        if os.path.exists(SALONS_FILE):
            try:
                with open(SALONS_FILE, "r", encoding="utf-8") as f:
                    self.salons = json.load(f)
                logger.info(f"✓ {len(self.salons)} salon yüklendi")
            except Exception as e:
                logger.error(f"Salon yükleme hatası: {e}")
                self.salons = []
        else:
            self.salons = []

    def refresh_adisyonlar(self):
        """Masa/paket yapısını yeniden oluştur"""
        self.adisyonlar = {}
        
        # Salon masaları
        if self.salons:
            for salon in self.salons:
                for table in salon.get('tables', []):
                    self.adisyonlar[table] = []
        elif self.masa_sayisi > 0:
            for i in range(1, self.masa_sayisi + 1):
                self.adisyonlar[f"Masa {i}"] = []
                
        # Paketler
        if self.paket_sayisi > 0:
            for i in range(1, self.paket_sayisi + 1):
                self.adisyonlar[f"Paket {i}"] = []
        
        if not self.adisyonlar:
            self.adisyonlar["Genel"] = []
        
        logger.info(f"✓ {len(self.adisyonlar)} adisyon alanı oluşturuldu")

    def save_active_adisyonlar(self):
        """Aktif adisyonları dosyaya kaydet"""
        try:
            with open(ACTIVE_ADISYONLAR_FILE, "w", encoding="utf-8") as f:
                json.dump(self.adisyonlar, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Adisyon kaydetme hatası: {e}")
            return False

    def load_active_adisyonlar(self):
        """Aktif adisyonları dosyadan yükle"""
        if os.path.exists(ACTIVE_ADISYONLAR_FILE):
            try:
                with open(ACTIVE_ADISYONLAR_FILE, "r", encoding="utf-8") as f:
                    loaded_adisyonlar = json.load(f)
                    # Sadece mevcut masaları/paketleri güncelle (yapı değişmiş olabilir)
                    for masa, items in loaded_adisyonlar.items():
                        if masa in self.adisyonlar:
                            self.adisyonlar[masa] = items
                logger.info("✓ Aktif adisyonlar geri yüklendi")
            except Exception as e:
                logger.error(f"Adisyon yükleme hatası: {e}")
    
    def load_menu_data(self):
        """Menüyü yükle - DB'den veya dosyadan"""
        if USE_DATABASE:
            try:
                self.menu_data = db.get_menu_by_category()
                if self.menu_data:
                    logger.info(f"✓ Menü DB'den yüklendi: {len(self.menu_data)} kategori")
                    return
                else:
                    # DB boşsa dosyadan yükle
                    db.load_menu_from_file(MENU_FILE)
                    self.menu_data = db.get_menu_by_category()
                    logger.info("✓ Menü dosyadan DB'ye aktarıldı")
                    return
            except Exception as e:
                logger.error(f"DB menü hatası: {e}")
        
        # Dosyadan yükle
        self.menu_data = {}
        if not os.path.exists(MENU_FILE):
            self.menu_data = {"Genel": [["Örnek Ürün", 100.0]]}
            return
        
        try:
            with open(MENU_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split(";")
                    if len(parts) >= 3:
                        cat, item, price = parts[0].strip(), parts[1].strip(), parts[2].strip()
                        # Parse platform percentages if they exist
                        oran_ys = float(parts[3]) if len(parts) > 3 else 0
                        oran_ty = float(parts[4]) if len(parts) > 4 else 0
                        oran_gt = float(parts[5]) if len(parts) > 5 else 0
                        oran_mg = float(parts[6]) if len(parts) > 6 else 0
                        
                        if cat not in self.menu_data:
                            self.menu_data[cat] = []
                        self.menu_data[cat].append([item, float(price), oran_ys, oran_ty, oran_gt, oran_mg])
            logger.info(f"✓ Menü dosyadan yüklendi: {len(self.menu_data)} kategori")
        except Exception as e:
            logger.error(f"Menü yükleme hatası: {e}")
    
    def get_and_inc_counter(self):
        """Fiş numarası oluştur"""
        sira = 1
        if os.path.exists(COUNTER_FILE):
            try:
                with open(COUNTER_FILE, "r") as f:
                    sira = int(f.read().strip()) + 1
            except:
                sira = 1
        
        with open(COUNTER_FILE, "w") as f:
            f.write(str(sira))
        return sira
    
    def start_terminal_server(self):
        """Terminal sunucusunu başlat"""
        def run_server():
            try:
                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind(('0.0.0.0', SERVER_PORT))
                server.listen(10)
                logger.info(f"📡 Terminal sunucusu başladı: {get_local_ip()}:{SERVER_PORT}")
                
                while self.running:
                    try:
                        client_sock, addr = server.accept()
                        threading.Thread(target=self.handle_terminal_data, 
                                       args=(client_sock,), daemon=True).start()
                    except:
                        break
            except Exception as e:
                logger.error(f"Terminal sunucu hatası: {e}")
        
        self.running = True
        self.terminal_thread = threading.Thread(target=run_server, daemon=True)
        self.terminal_thread.start()
    
    def handle_terminal_data(self, client_sock):
        """Terminal verilerini işle"""
        try:
            raw_data = client_sock.recv(4096).decode('utf-8')
            if not raw_data:
                return
            
            data = json.loads(raw_data)
            masa_adi = data.get("masa")
            yeni_urunler = data.get("siparisler", [])
            terminal_adi = data.get("terminal", "Bilinmeyen")
            
            if masa_adi in self.adisyonlar:
                for item in yeni_urunler:
                    siparis_obj = {
                        "urun": item['urun'],
                        "adet": 1,
                        "fiyat": float(item['fiyat']),
                        "tip": "normal"
                    }
                    self.adisyonlar[masa_adi].append(siparis_obj)
                
                # Tüm bağlantılara bildir
                socketio.emit('masa_update', {
                    'masa': masa_adi,
                    'items': self.adisyonlar[masa_adi],
                    'source': 'terminal'
                })
                
                # Mutfak bildirimi
                for item in yeni_urunler:
                    socketio.emit('kitchen_new_order', {
                        'masa': masa_adi,
                        'urun': item['urun'],
                        'adet': 1,
                        'saat': datetime.datetime.now().strftime("%H:%M:%S"),
                        'terminal_id': f"TCP:{terminal_adi}"
                    })
                    self.send_to_kitchen_legacy(masa_adi, item['urun'], 1)
                
                logger.info(f"📲 Terminal siparişi: {terminal_adi} → {masa_adi}")
        except Exception as e:
            logger.error(f"Terminal veri hatası: {e}")
        finally:
            client_sock.close()

    def start_caller_id_listener(self):
        """Caller ID (Signal 7 veya Seri Port) dinleyicisini başlat"""
        if not self.cid_enabled:
            logger.info("🚫 Caller ID sistemi devre dışı.")
            return

        if self.cid_type == 'tcp':
            def run_cid_listener():
                try:
                    cid_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    cid_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    try:
                        cid_sock.bind(('0.0.0.0', self.cid_port))
                    except Exception as e:
                        logger.error(f"❌ Caller ID portu ({self.cid_port}) bağlanamadı: {e}")
                        return

                    cid_sock.listen(5)
                    logger.info(f"📡 TCP Caller ID Dinleyici başladı: Port {self.cid_port}")

                    while self.running:
                        try:
                            client, addr = cid_sock.accept()
                            logger.info(f"📞 Caller ID cihazı bağlandı: {addr}")
                            threading.Thread(target=self.handle_cid_data, args=(client,), daemon=True).start()
                        except:
                            if not self.running: break
                except Exception as e:
                    logger.error(f"❌ TCP Caller ID hatası: {e}")
            threading.Thread(target=run_cid_listener, daemon=True).start()
        
        elif self.cid_type == 'serial':
            def run_serial_cid():
                logger.info(f"🔌 Seri Port Caller ID Dinleyici başlatılıyor: {self.cid_serial_port}")
                while self.running:
                    try:
                        # PTTAVM 2'li modem ve benzeri cihazlar genelde 9600 baud kullanır
                        with serial.Serial(self.cid_serial_port, 9600, timeout=1) as ser:
                            logger.info(f"✅ Seri Port bağlandı: {self.cid_serial_port}")
                            while self.running:
                                line = ser.readline().decode('utf-8', errors='ignore').strip()
                                if line:
                                    logger.info(f"☎️ Seri Port Verisi: {line}")
                                    # PTTAVM 2'li modem formatı: "01 N 0532..."
                                    phone = ""
                                    if " N " in line:
                                        phone = line.split(" N ")[1].strip()
                                    elif line.isdigit():
                                        phone = line
                                    else:
                                        phone = ''.join(filter(str.isdigit, line))[-10:]
                                    
                                    if phone:
                                        self.process_incoming_call(phone)
                    except Exception as e:
                        if self.running:
                            logger.error(f"❌ Seri Port hatası ({self.cid_serial_port}): {e}. 10 saniye sonra tekrar denenecek...")
                            time.sleep(10)
                        else:
                            break
            threading.Thread(target=run_serial_cid, daemon=True).start()

    def handle_cid_data(self, client):
        """Gelen Caller ID verisini çöz ve yayınla"""
        try:
            # Signal 7 formatı genelde: 
            # "ID=1,NO=05321234567,DATE=21/02/2026,TIME=16:15" vb. 
            # veya sadece numara gönderir.
            data = client.recv(1024).decode('utf-8', errors='ignore').strip()
            if not data: return
            
            logger.info(f"☎️ Gelen Çağrı Verisi: {data}")
            
            # Telefon numarasını ayıkla (Basit bir regex veya split)
            phone = ""
            if "NO=" in data:
                phone = data.split("NO=")[1].split(",")[0].strip()
            elif data.isdigit():
                phone = data
            else:
                # Genel bir temizlik
                phone = ''.join(filter(str.isdigit, data))[-10:] # Son 10 hane (TR formatı)

            if phone:
                self.process_incoming_call(phone)
        except Exception as e:
            logger.error(f"❌ CID Veri işleme hatası: {e}")
        finally:
            client.close()

    def process_incoming_call(self, phone):
        """Gelen aramayı işle ve frontend'e gönder"""
        customer = None
        history = []
        
        if USE_DATABASE:
            customer = db.get_cari_by_phone(phone)
            if customer:
                history = db.get_customer_order_history(customer['cari_isim'])
                # Balance ekle
                customer['bakiye'] = db.get_cari_balance(customer['cari_isim'])
        
        # SocketIO ile tüm ekranlara (özellikle kasaya) bildir
        payload = {
            'phone': phone,
            'customer': customer,
            'history': [
                {
                    'urun': h['urun'], 
                    'adet': h['adet'], 
                    'fiyat': float(h['fiyat']), 
                    'tarih': str(h['tarih_saat']),
                    'odeme': h['odeme']
                } for h in history
            ],
            'timestamp': datetime.datetime.now().strftime("%H:%M:%S")
        }
        
        socketio.emit('incoming_call', payload)
        logger.info(f"🔔 Arama bildirildi: {phone} {'(' + customer['cari_isim'] + ')' if customer else '(Yeni Müşteri)'}")

# Global server instance
server = RestaurantServer()

# ==================== FLASK ROUTES ====================

@app.route('/')
def index():
    """Ana sayfa"""
    return app.send_static_file('index.html')

@app.route('/terminals')
def terminals():
    """Terminal yönetim sayfası"""
    return app.send_static_file('terminals.html')

@app.route('/settings')
def settings_page():
    """Ayarlar sayfası"""
    return app.send_static_file('settings.html')

@app.route('/menu_edit')
def menu_edit_page():
    """Menü düzenleme sayfası"""
    return app.send_static_file('menu_edit.html')

@app.route('/kasa')
def kasa_page_clean():
    """Kasa yönetimi sayfası (Temiz URL)"""
    return app.send_static_file('kasa_yonetimi.html')

@app.route('/kurye')
def kurye_page_clean():
    """Kurye yönetimi sayfası (Temiz URL)"""
    return app.send_static_file('kurye_yonetimi.html')

@app.route('/cari')
def cari_page():
    """Cari işlemler sayfası"""
    return app.send_static_file('cari.html')

@app.route('/gunsonu')
def gunsonu_page():
    """Gün sonu işlemleri sayfası"""
    return app.send_static_file('gunsonu.html')

@app.route('/mutfak')
def mutfak_page():
    """Mutfak sipariş takip sayfası"""
    return app.send_static_file('mutfak.html')

@app.route('/waiter')
def waiter_page():
    """Garson arayüzü"""
    return app.send_static_file('waiter.html')

@app.route('/waiters_manage')
def waiters_manage_page():
    """Garson yönetimi sayfası"""
    return app.send_static_file('waiters_manage.html')

@app.route('/api/system/info')
def system_info():
    """Sistem bilgileri"""
    return jsonify({
        'company_name': server.company_name,
        'terminal_id': server.terminal_id,
        'ip': get_local_ip(),
        'masa_sayisi': server.masa_sayisi,
        'paket_sayisi': server.paket_sayisi,
        'database': USE_DATABASE,
        'pdf': PDF_SUPPORT,
        'cid_enabled': server.cid_enabled,
        'cid_type': server.cid_type,
        'pos_enabled': server.pos_enabled,
        'pos_type': server.pos_type
    })

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Mevcut ayarları döndür"""
    return jsonify({
        'firma_ismi':   server.company_name,
        'terminal_id':  server.terminal_id,
        'masa_sayisi':  server.masa_sayisi,
        'paket_sayisi': server.paket_sayisi,
        'direct_print': server.direct_print,
        'cid_port': server.cid_port,
        'cid_type': server.cid_type,
        'cid_serial_port': server.cid_serial_port,
        'cid_enabled': server.cid_enabled,
        'pos_enabled': server.pos_enabled,
        'pos_ip': server.pos_ip,
        'pos_port': server.pos_port,
        'pos_type': server.pos_type,
        'salons': server.salons,
        'ip':           get_local_ip()
    })

@app.route('/api/settings', methods=['POST'])
def save_settings():
    """Ayarları kaydet"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Geçersiz veri'}), 400

    # Şifre doğrula
    mevcut_sifre = data.get('mevcut_sifre', '')
    if mevcut_sifre != server.admin_password:
        return jsonify({'success': False, 'error': 'Mevcut şifre hatalı!'}), 403

    # Yeni şifre varsa güncelle
    yeni_sifre = data.get('yeni_sifre', '')
    if yeni_sifre:
        server.admin_password = yeni_sifre

    # Diğer ayarları güncelle
    server.company_name  = data.get('firma_ismi',   server.company_name)
    server.terminal_id   = data.get('terminal_id',  server.terminal_id)
    server.direct_print  = data.get('direct_print', server.direct_print)

    yeni_masa   = int(data.get('masa_sayisi',  server.masa_sayisi))
    yeni_paket  = int(data.get('paket_sayisi', server.paket_sayisi))

    masa_degisti = (yeni_masa != server.masa_sayisi or yeni_paket != server.paket_sayisi)
    server.masa_sayisi   = yeni_masa
    server.paket_sayisi  = yeni_paket
    
    server.cid_port = int(data.get('cid_port', server.cid_port))
    server.cid_type = data.get('cid_type', server.cid_type)
    server.cid_serial_port = data.get('cid_serial_port', server.cid_serial_port)
    server.cid_enabled = data.get('cid_enabled', server.cid_enabled)
    
    server.pos_enabled = data.get('pos_enabled', server.pos_enabled)
    server.pos_ip = data.get('pos_ip', server.pos_ip)
    server.pos_port = int(data.get('pos_port', server.pos_port))
    server.pos_type = data.get('pos_type', server.pos_type)
    
    # POS Manager'ı güncelle
    server.pos_manager = POSManager(server.pos_enabled, server.pos_ip, server.pos_port, server.pos_type)

    # Kaydet
    ok = server.save_settings()
    if not ok:
        return jsonify({'success': False, 'error': 'Dosyaya yazılamadı'}), 500

    # Masa/paket yapısı değiştiyse yenile
    if masa_degisti:
        server.refresh_adisyonlar()
        socketio.emit('system_update', {
            'masa_sayisi':  server.masa_sayisi,
            'paket_sayisi': server.paket_sayisi,
            'company_name': server.company_name,
            'terminal_id':  server.terminal_id
        })

    logger.info(f"✅ Ayarlar güncellendi: {server.company_name} / Masa:{server.masa_sayisi} Paket:{server.paket_sayisi}")
    return jsonify({'success': True})

@app.route('/api/serial/ports')
def get_serial_ports():
    """Mevcut seri portları listele"""
    ports = serial.tools.list_ports.comports()
    result = []
    for p in ports:
        result.append({
            'device': p.device,
            'description': p.description
        })
    return jsonify(result)

# ==================== GÜN SONU API ====================

@app.route('/api/gunsonu/ozet')
def get_gunsonu_ozet():
    """Günlük özet rapor"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'}), 503
    tarih = request.args.get('tarih', datetime.datetime.now().strftime('%Y-%m-%d'))
    try:
        rows = db.get_daily_summary(tarih)
        result = []
        toplam = 0.0
        for r in rows:
            t = float(r['toplam'])
            toplam += t
            result.append({
                'odeme': r['odeme'],
                'tip': r['tip'],
                'toplam': t,
                'adet': r['adet']
            })
        return jsonify({'success': True, 'ozet': result, 'genel_toplam': toplam, 'tarih': tarih})
    except Exception as e:
        logger.error(f"Gün sonu özet hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gunsonu/detay')
def get_gunsonu_detay():
    """Günlük detay rapor"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'}), 503
    tarih = request.args.get('tarih', datetime.datetime.now().strftime('%Y-%m-%d'))
    try:
        rows = db.get_sales_by_date(tarih)
        result = []
        for r in rows:
            result.append({
                'urun': r['urun'],
                'adet': r['adet'],
                'fiyat': float(r['fiyat']),
                'odeme': r['odeme'],
                'tip': r.get('tip', 'normal'),
                'tarih_saat': str(r['tarih_saat']) if r['tarih_saat'] else ''
            })
        return jsonify({'success': True, 'detay': result, 'tarih': tarih})
    except Exception as e:
        logger.error(f"Gün sonu detay hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== CARİ İŞLEMLER API ====================

@app.route('/api/cari/hesaplar')
def get_cari_hesaplar():
    """Tüm cari hesapları döndür"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'}), 503
    try:
        hesaplar = db.get_all_cari_accounts()
        result = []
        for h in hesaplar:
            result.append({
                'id': h['id'],
                'cari_isim': h['cari_isim'],
                'bakiye': float(h['bakiye']),
                'olusturma_tarihi': str(h['olusturma_tarihi']) if h['olusturma_tarihi'] else ''
            })
        return jsonify({'success': True, 'hesaplar': result})
    except Exception as e:
        logger.error(f"Cari hesap listesi hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cari/hareketler/<cari_isim>')
def get_cari_hareketler(cari_isim):
    """Belirli cari hesabın hareketlerini döndür"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'}), 503
    try:
        hareketler = db.get_cari_transactions(cari_isim)
        bakiye = db.get_cari_balance(cari_isim)
        result = []
        for h in hareketler:
            result.append({
                'id': h['id'],
                'islem': h['islem'],
                'tutar': float(h['tutar']),
                'tarih': str(h['tarih']) if h['tarih'] else ''
            })
        return jsonify({'success': True, 'hareketler': result, 'bakiye': bakiye})
    except Exception as e:
        logger.error(f"Cari hareketler hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cari/islem', methods=['POST'])
def add_cari_islem():
    """Yeni cari işlem ekle (borç veya ödeme)"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'}), 503
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Geçersiz veri'}), 400
    
    cari_isim = data.get('cari_isim', '').strip()
    islem = data.get('islem', '')  # 'borc' veya 'odeme'
    tutar = data.get('tutar', 0)
    
    if not cari_isim:
        return jsonify({'success': False, 'error': 'Müşteri adı boş olamaz'}), 400
    if islem not in ('borc', 'odeme'):
        return jsonify({'success': False, 'error': 'Geçersiz işlem türü'}), 400
    try:
        tutar = float(tutar)
        if tutar <= 0:
            return jsonify({'success': False, 'error': 'Tutar sıfırdan büyük olmalı'}), 400
    except:
        return jsonify({'success': False, 'error': 'Geçersiz tutar'}), 400
    
    # Borç: pozitif, Ödeme: negatif
    gercek_tutar = tutar if islem == 'borc' else -tutar
    
    try:
        db.save_cari_transaction(cari_isim, islem, gercek_tutar)
        bakiye = db.get_cari_balance(cari_isim)
        logger.info(f"💰 Cari işlem: {cari_isim} | {islem} | {tutar:.2f} TL")
        return jsonify({'success': True, 'bakiye': bakiye})
    except Exception as e:
        logger.error(f"Cari işlem hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== KASA VE VARDIYA API ====================

@app.route('/api/kasa/liste')
def api_kasa_liste():
    if not USE_DATABASE: return jsonify([])
    return jsonify(db.get_kasalar())

@app.route('/api/kasa/ekle', methods=['POST'])
def api_kasa_ekle():
    if not USE_DATABASE: return jsonify({'success': False, 'error': 'DB yok'})
    data = request.json
    ad = data.get('ad')
    if not ad: return jsonify({'success': False, 'error': 'İsim gerekli'})
    try:
        kasa_id = db.add_kasa(ad)
        return jsonify({'success': True, 'id': kasa_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vardiya/durum')
def api_vardiya_durum():
    if not USE_DATABASE: return jsonify(None)
    kasa_id = request.args.get('kasa_id')
    if not kasa_id: return jsonify(None)
    shift = db.get_active_shift_by_kasa(kasa_id)
    return jsonify(shift)

@app.route('/api/vardiya/ac', methods=['POST'])
def api_vardiya_ac():
    if not USE_DATABASE: return jsonify({'success': False, 'error': 'DB yok'})
    data = request.json
    kasa_id = data.get('kasa_id')
    kasiyer = data.get('kasiyer')
    bakiye = float(data.get('acilis_bakiyesi', 0))
    if not kasa_id or not kasiyer: return jsonify({'success': False, 'error': 'Eksik bilgi'})
    try:
        shift_id = db.open_shift(kasa_id, kasiyer, bakiye)
        # Tüm bağlı istemcilere vardiya açıldığını bildir
        socketio.emit('vardiya_update', {
            'id': shift_id,
            'kasiyer': kasiyer,
            'kasa_id': int(kasa_id),
            'durum': 'acik',
            'acilis_zamani': datetime.datetime.now().isoformat()
        })
        return jsonify({'success': True, 'id': shift_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vardiya/kapat', methods=['POST'])
def api_vardiya_kapat():
    if not USE_DATABASE: return jsonify({'success': False, 'error': 'DB yok'})
    data = request.json
    shift_id = data.get('shift_id')
    nakit = float(data.get('nakit', 0))
    kart = float(data.get('kart', 0))
    if not shift_id: return jsonify({'success': False, 'error': 'Vardiya ID gerekli'})
    try:
        db.close_shift(shift_id, nakit, kart)
        # Tüm bağlı istemcilere vardiya kapandığını bildir
        socketio.emit('vardiya_update', None)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vardiya/ozet/<int:shift_id>')
def api_vardiya_ozet(shift_id):
    if not USE_DATABASE: return jsonify({'success': False})
    try:
        summary = db.get_shift_totals(shift_id)
        info = db.get_shift_by_id(shift_id)
        return jsonify({
            'success': True,
            'summary': summary,
            'info': info
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/vardiya/gecmis')
def api_vardiya_gecmis():
    if not USE_DATABASE: return jsonify([])
    return jsonify(db.get_all_shifts())

@app.route('/api/cari/hesap', methods=['POST'])
def add_cari_hesap():
    """Yeni cari hesap oluştur"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'}), 503
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Geçersiz veri'}), 400
    
    cari_isim = data.get('cari_isim', '').strip()
    if not cari_isim:
        return jsonify({'success': False, 'error': 'Müşteri adı boş olamaz'}), 400
    
    try:
        db.get_or_create_cari(cari_isim)
        logger.info(f"👤 Yeni cari hesap: {cari_isim}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Cari hesap oluşturma hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cari/hesap/<cari_isim>', methods=['DELETE'])
def delete_cari_hesap(cari_isim):
    """Cari hesabı sil"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'}), 503
    try:
        db.delete_cari_account(cari_isim)
        logger.info(f"🗑️ Cari hesap silindi: {cari_isim}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Cari hesap silme hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cari/lookup/<phone>')
def lookup_customer(phone):
    """Telefona göre müşteri bul"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'})
    try:
        customer = db.get_cari_by_phone(phone)
        if customer:
            history = db.get_customer_order_history(customer['cari_isim'])
            bakiye = db.get_cari_balance(customer['cari_isim'])
            return jsonify({
                'success': True, 
                'customer': {
                    'cari_isim': customer['cari_isim'],
                    'telefon': customer['telefon'],
                    'adres': customer['adres'],
                    'bakiye': bakiye
                },
                'history': [
                    {
                        'urun': h['urun'], 
                        'adet': h['adet'], 
                        'fiyat': float(h['fiyat']), 
                        'tarih': str(h['tarih_saat'])
                    } for h in history
                ]
            })
        return jsonify({'success': True, 'customer': None})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/cari/update_details', methods=['POST'])
def update_cari_details_api():
    """Müşteri detaylarını (tel/adres) güncelle"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'})
    data = request.get_json()
    cari_isim = data.get('cari_isim')
    telefon = data.get('telefon')
    adres = data.get('adres')
    
    if not cari_isim:
        return jsonify({'success': False, 'error': 'Müşteri adı gerekli'})
        
    try:
        db.update_cari_details(cari_isim, telefon, adres)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/couriers/<int:courier_id>', methods=['DELETE'])
def delete_courier_api(courier_id):
    if not USE_DATABASE: return jsonify({'success': False, 'error': 'DB yok'})
    try:
        db.delete_kurye(courier_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/courier-firms', methods=['GET'])
def get_courier_firms_api():
    if not USE_DATABASE: return jsonify([])
    return jsonify(db.get_kurye_firmalari())

@app.route('/api/courier-firms', methods=['POST'])
def add_courier_firm_api():
    if not USE_DATABASE: return jsonify({'success': False, 'error': 'DB yok'})
    data = request.json
    try:
        firm_id = db.add_kurye_firmasi(
            ad=data.get('ad'),
            api_key=data.get('api_key'),
            ayarlar=data.get('ayarlar')
        )
        return jsonify({'success': True, 'id': firm_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==================== ENTEGRASYONLAR API ====================

@app.route('/api/integration/settings', methods=['GET'])
def get_integration_settings():
    """Entegrasyon ayarlarını döndür"""
    return jsonify(server.integration_manager.settings)

@app.route('/api/integration/settings', methods=['POST'])
def save_integration_settings():
    """Entegrasyon ayarlarını kaydet"""
    data = request.get_json()
    if server.integration_manager.save_settings(data):
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Ayarlar kaydedilemedi'}), 500

@app.route('/api/integration/webhook/<platform>', methods=['POST'])
def integration_webhook(platform):
    """Platformlardan gelen siparişleri karşıla"""
    data = request.get_json()
    logger.info(f"📥 {platform.upper()} Webhook: {data}")
    
    order = server.integration_manager.process_webhook(platform, data, server.menu_data)
    if not order:
        return jsonify({'success': False, 'error': 'Sipariş işlenemedi'}), 400
        
    masa_adi = order.get('masa')
    items = order.get('items', [])
    
    # Adisyon alanını kontrol et veya oluştur
    if masa_adi not in server.adisyonlar:
        server.adisyonlar[masa_adi] = []
        
    # Siparişleri ekle
    for item in items:
        siparis_id = str(uuid.uuid4())[:8]
        siparis = {
            'uid': siparis_id,
            'urun': item['urun'],
            'adet': item['adet'],
            'fiyat': item['fiyat'],
            'tip': item['tip'],
            'garson': order.get('platform', 'Online'),
            'durum': 'mutfakta',
            'saat': datetime.datetime.now().strftime("%H:%M:%S")
        }
        server.adisyonlar[masa_adi].append(siparis)
        
        # Mutfak bildirimi
        socketio.emit('kitchen_new_order', {
            'uid': siparis_id,
            'masa': masa_adi,
            'urun': item['urun'],
            'adet': item['adet'],
            'saat': siparis['saat'],
            'garson': siparis['garson'],
            'terminal_id': f"API:{platform}"
        })
        
        # Legacy mutfak
        server.send_to_kitchen_legacy(masa_adi, item['urun'], item['adet'])
        
    # Tüm clientlara bildir
    socketio.emit('masa_update', {
        'masa': masa_adi,
        'items': server.adisyonlar[masa_adi],
        'total': sum(i['adet'] * i['fiyat'] for i in server.adisyonlar[masa_adi]),
        'source': platform
    })
    
    # Yeni sipariş uyarısı
    socketio.emit('new_online_order', {
        'platform': order.get('platform'),
        'masa': masa_adi,
        'customer': order.get('customer')
    })
    
    server.save_active_adisyonlar() # Persistence
    return jsonify({'success': True})

# ==================== SALON YÖNETİMİ ====================

# ==================== PERSONNEL MANAGEMENT APIs ====================

@app.route('/api/waiters', methods=['GET'])
def get_waiters_api():
    return jsonify(server.waiters)

@app.route('/api/waiters', methods=['POST'])
def add_waiter_api():
    try:
        data = request.json
        name = data.get('name', '').strip()
        pin = data.get('pin', '').strip()
        if not name or not pin:
            return jsonify({'success': False, 'error': 'İsim ve PIN gerekli'})
        
        server.waiters.append({'name': name, 'pin': pin})
        server.save_waiters()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/waiters/<int:idx>', methods=['DELETE'])
def delete_waiter_api(idx):
    try:
        if 0 <= idx < len(server.waiters):
            server.waiters.pop(idx)
            server.save_waiters()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Geçersiz indeks'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/cashiers', methods=['GET'])
def get_cashiers_api():
    return jsonify(server.cashiers)

@app.route('/api/cashiers', methods=['POST'])
def add_cashier_api():
    try:
        data = request.json
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'İsim gerekli'})
        server.cashiers.append({'name': data['name']})
        server.save_cashiers()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/cashiers/<int:idx>', methods=['DELETE'])
def delete_cashier_api(idx):
    try:
        if 0 <= idx < len(server.cashiers):
            server.cashiers.pop(idx)
            server.save_cashiers()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Geçersiz indeks'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/couriers', methods=['GET'])
def get_couriers_api_unified():
    if not USE_DATABASE:
        return jsonify([])
    try:
        with db.get_cursor() as cursor:
            cursor.execute("SELECT * FROM kuryeler ORDER BY id")
            return jsonify(cursor.fetchall())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/couriers', methods=['POST'])
def add_courier_api_unified():
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'DB bağlantısı yok'})
    try:
        data = request.json
        with db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO kuryeler (ad, telefon, plaka, aktif)
                VALUES (%s, %s, %s, %s)
            """, (data.get('ad'), data.get('telefon'), data.get('plaka'), data.get('aktif', True)))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/couriers/<int:id>', methods=['DELETE'])
def delete_courier_api_unified(id):
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'DB bağlantısı yok'})
    try:
        with db.get_cursor() as cursor:
            cursor.execute("DELETE FROM kuryeler WHERE id = %s", (id,))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/waiters/login', methods=['POST'])
def waiter_login_api_unified():
    data = request.json
    name = data.get('name', '')
    pin = data.get('pin', '')
    waiter = next((w for w in server.waiters if w['name'] == name and w['pin'] == pin), None)
    if waiter:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Hatalı PIN!'}), 401

@app.route('/api/salons', methods=['POST'])
def save_salons_api():
    """Salon düzenini kaydet"""
    try:
        data = request.json
        if not isinstance(data, list):
            return jsonify({'success': False, 'error': 'Geçersiz veri formatı'})
            
        with open(SALONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        # Sunucu cache'ini yenile
        global server
        server.salons = data
        
        # Tüm istemcilere güncel düzeni ve diğer ayarları gönder
        socketio.emit('initial_data', {
            'system': server.get_system_info(),
            'menu': server.menu_data,
            'adisyonlar': server.adisyonlar
        })
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Salon kaydetme hatası: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== MENÜ ====================

@app.route('/api/menu/save', methods=['POST'])
def save_menu_api():
    """Menüyü kaydet"""
    try:
        data = request.json
        if not data or 'menu' not in data:
            return jsonify({'success': False, 'error': 'Geçersiz veri'})
        
        new_menu = data['menu']
        
        # 1. menu.txt dosyasını güncelle
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            for cat, items in new_menu.items():
                for item in items:
                    # item structure: [name, price, ys, ty, gt, mg]
                    name = item[0]
                    price = item[1]
                    # Default percentages to 0 if not provided
                    ys = item[2] if len(item) > 2 else 0
                    ty = item[3] if len(item) > 3 else 0
                    gt = item[4] if len(item) > 4 else 0
                    mg = item[5] if len(item) > 5 else 0
                    f.write(f"{cat};{name};{price};{ys};{ty};{gt};{mg}\n")
        
        # 2. Veri tabanını güncelle (eğer kullanılıyorsa)
        if USE_DATABASE:
            try:
                db.load_menu_from_file(MENU_FILE)
            except Exception as e:
                logger.error(f"Menü DB güncelleme hatası: {e}")
        
        # 3. Sunucu cache'ini yenile
        global server
        server.menu_data = new_menu
        
        # 4. İstemcilere bildir
        socketio.emit('initial_data', {
            'system': server.get_system_info(),
            'menu': server.menu_data,
            'adisyonlar': server.adisyonlar
        })
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Menü kaydetme hatası: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/menu')
def get_menu():
    """Menüyü getir"""
    return jsonify(server.menu_data)

@app.route('/api/adisyonlar')
def get_adisyonlar():
    """Tüm adisyonları getir"""
    return jsonify(server.adisyonlar)

@app.route('/api/adisyon/<masa_adi>')
def get_adisyon(masa_adi):
    """Belirli bir adisyonu getir"""
    items = server.adisyonlar.get(masa_adi, [])
    total = sum(item['adet'] * item['fiyat'] for item in items)
    return jsonify({
        'masa': masa_adi,
        'items': items,
        'total': total
    })

# ==================== SOCKETIO EVENTS ====================

@socketio.on('connect')
def handle_connect():
    """Client bağlandı"""
    sid = request.sid
    client_ip = request.remote_addr
    server.active_connections[sid] = {
        'ip': client_ip,
        'connected_at': time.time()
    }
    logger.info(f"✅ Client bağlandı: {client_ip} ({sid})")
    
    # İlk verileri gönder
    emit('initial_data', {
        'menu': server.menu_data,
        'adisyonlar': server.adisyonlar,
        'system': {
            'company_name': server.company_name,
            'terminal_id': server.terminal_id,
            'ip': get_local_ip(),
            'masa_sayisi': server.masa_sayisi,
            'paket_sayisi': server.paket_sayisi,
            'salons': server.salons
        },
        'active_shift': server.get_sid_active_shift(sid)
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Client ayrıldı"""
    sid = request.sid
    if sid in server.active_connections:
        info = server.active_connections.pop(sid)
        # Garson session'larından temizle
        for waiter_name in list(server.waiter_sessions.keys()):
            if sid in server.waiter_sessions[waiter_name]:
                server.waiter_sessions[waiter_name].remove(sid)
                if not server.waiter_sessions[waiter_name]:
                    del server.waiter_sessions[waiter_name]
        logger.info(f"❌ Client ayrıldı: {info['ip']} ({sid})")

@socketio.on('waiter_init')
def handle_waiter_init(data):
    """Garson oturumunu kaydet"""
    sid = request.sid
    waiter_name = data.get('name')
    if waiter_name:
        server.waiter_sessions[waiter_name].add(sid)
        logger.info(f"🤵 Garson oturumu kaydedildi: {waiter_name} ({sid})")

@socketio.on('set_kasa')
def handle_set_kasa(data):
    """Kasa ID'sini bu session için ata"""
    sid = request.sid
    kasa_id = data.get('kasa_id')
    if kasa_id:
        server.sid_kasa_map[sid] = kasa_id
        logger.info(f"📟 Kasa atandı: {kasa_id} ({sid})")
        # Aktif vardiya bilgisini geri gönder
        emit('vardiya_update', server.get_sid_active_shift(sid))

@socketio.on('select_masa')
def handle_select_masa(data):
    """Masa seçimi"""
    sid = request.sid
    masa_adi = data.get('masa')
    server.current_selections[sid] = masa_adi
    
    items = server.adisyonlar.get(masa_adi, [])
    total = sum(item['adet'] * item['fiyat'] for item in items)
    
    emit('masa_selected', {
        'masa': masa_adi,
        'items': items,
        'total': total
    })

@socketio.on('add_item')
def handle_add_item(data):
    """Sipariş ekle"""
    sid = request.sid
    # Masayı önce gelen veriden al, yoksa session'dan bak
    masa_adi = data.get('masa') or server.current_selections.get(sid)
    
    if not masa_adi or masa_adi not in server.adisyonlar:
        emit('error', {'message': 'Lütfen önce masa seçiniz'})
        return
    
    urun = data.get('urun')
    fiyat = float(data.get('fiyat', 0))
    
    # Her siparişe benzersiz ID ve durum ekle
    siparis_id = str(uuid.uuid4())[:8]
    siparis = {
        'uid': siparis_id,
        'urun': urun,
        'adet': 1,
        'fiyat': fiyat,
        'tip': 'normal',
        'garson': data.get('garson', 'Bilinmiyor'),
        'durum': 'mutfakta',
        'saat': datetime.datetime.now().strftime("%H:%M:%S")
    }
    
    server.adisyonlar[masa_adi].append(siparis)
    server.save_active_adisyonlar() # Persistence
    
    # Tüm clientlara bildir
    items = server.adisyonlar[masa_adi]
    total = sum(item['adet'] * item['fiyat'] for item in items)
    
    socketio.emit('masa_update', {
        'masa': masa_adi,
        'items': items,
        'total': total
    })
    
    # Mutfak bildirimi gönder
    socketio.emit('kitchen_new_order', {
        'uid': siparis_id,
        'masa': masa_adi,
        'urun': urun,
        'adet': 1,
        'saat': datetime.datetime.now().strftime("%H:%M:%S"),
        'garson': data.get('garson', 'Bilinmiyor'),
        'terminal_id': f"sid:{sid}"
    })
    
    # Legacy mutfak sistemine gönder
    server.send_to_kitchen_legacy(masa_adi, urun, 1)

@socketio.on('kitchen_order_ready')
def handle_kitchen_order_ready(data):
    """Mutfaktan sipariş hazır bildirimi"""
    masa = data.get('masa')
    waiters = data.get('waiters', [])
    items_uids = data.get('items_uids', []) # Mutfaktan gelen hazır ürün ID'leri
    
    logger.info(f"📢 Sipariş hazır: {masa} (UIDs: {items_uids})")
    
    # Adisyondaki ürünlerin durumunu güncelle
    if masa in server.adisyonlar:
        for item in server.adisyonlar[masa]:
            if item.get('uid') in items_uids:
                item['durum'] = 'hazir'
        server.save_active_adisyonlar() # Persistence

    # Garsonlara bildir
    for waiter_name in waiters:
        if waiter_name in server.waiter_sessions:
            for sid in server.waiter_sessions[waiter_name]:
                socketio.emit('order_ready', {
                    'masa': masa,
                    'items_uids': items_uids,
                    'message': f"{masa} siparişi hazır!"
                }, room=sid)
    
    # Tüm masayı güncelle (durum değişikliği için)
    items = server.adisyonlar.get(masa, [])
    total = sum(item['adet'] * item['fiyat'] for item in items)
    socketio.emit('masa_update', {'masa': masa, 'items': items, 'total': total})

@socketio.on('cancel_item')
def handle_cancel_item(data):
    """Garson siparişi iptal eder"""
    sid = request.sid
    masa_adi = data.get('masa')
    item_uid = data.get('uid')
    
    if not masa_adi or not item_uid: return

    if masa_adi in server.adisyonlar:
        # Ürünü bul
        item_idx = -1
        for i, item in enumerate(server.adisyonlar[masa_adi]):
            if item.get('uid') == item_uid:
                if item.get('durum') == 'hazir':
                    emit('error', {'message': 'Hazır olan sipariş iptal edilemez!'})
                    return
                item_idx = i
                break
        
        if item_idx != -1:
            cancelled_item = server.adisyonlar[masa_adi].pop(item_idx)
            server.save_active_adisyonlar() # Persistence
            logger.info(f"🗑️ Sipariş iptal edildi: {masa_adi} - {cancelled_item['urun']}")
            
            # Mutfak ekranına bildir
            socketio.emit('kitchen_cancel_order', {
                'masa': masa_adi,
                'uid': item_uid
            })
            
            # Masa güncellemesini herkese duyur
            items = server.adisyonlar[masa_adi]
            total = sum(item['adet'] * item['fiyat'] for item in items)
            socketio.emit('masa_update', {
                'masa': masa_adi,
                'items': items,
                'total': total
            })

@socketio.on('transfer_table')
def handle_transfer_table(data):
    """Bir masadaki siparişleri başka bir masaya taşı"""
    source_masa = data.get('source_masa')
    target_masa = data.get('target_masa')
    
    if not source_masa or not target_masa:
        emit('error', {'message': 'Kaynak ve hedef masa bilgisi eksik'})
        return
        
    if source_masa == target_masa:
        emit('error', {'message': 'Kaynak ve hedef masa aynı olamaz'})
        return
        
    if source_masa not in server.adisyonlar or target_masa not in server.adisyonlar:
        emit('error', {'message': 'Geçersiz masa adı'})
        return
        
    items_to_move = server.adisyonlar[source_masa]
    if not items_to_move:
        emit('error', {'message': 'Kaynak masada sipariş bulunmuyor'})
        return
        
    # Taşıma işlemi
    server.adisyonlar[target_masa].extend(items_to_move)
    server.adisyonlar[source_masa] = []
    server.save_active_adisyonlar() # Persistence
    
    logger.info(f"🔄 Masa taşıma: {source_masa} ➔ {target_masa} ({len(items_to_move)} ürün)")
    
    # Her iki masa için de güncellemeleri tüm clientlara bildir
    for masa_adi in [source_masa, target_masa]:
        items = server.adisyonlar[masa_adi]
        total = sum(item['adet'] * item['fiyat'] for item in items)
        socketio.emit('masa_update', {
            'masa': masa_adi,
            'items': items,
            'total': total,
            'source': 'transfer'
        })
    
    emit('success', {'message': f'{source_masa} masası {target_masa} masasına başarıyla taşındı'})

@socketio.on('assign_courier')
def handle_assign_courier(data):
    """Siparişe kurye ata"""
    masa_adi = data.get('masa')
    kurye_id = data.get('kurye_id')
    kurye_ad = data.get('kurye_ad')
    
    if not masa_adi or not kurye_id:
        emit('error', {'message': 'Eksik bilgi'})
        return
        
    if masa_adi not in server.adisyonlar:
        emit('error', {'message': 'Masa bulunamadı'})
        return
        
    # Adisyona kurye bilgisini ekle
    # Not: server.adisyonlar bir liste değil, bi sözlük. Değerleri liste.
    # Kurye bilgisini adisyon seviyesinde tutmak için bi metadata alanı yok current yapıda.
    # Şimdilik adisyon listesine bi 'kurye' entry'si ekleyelim ya da masa bazlı tutalım.
    # En iyisi her sipariş kalemine kurye_id eklemek or masa bazlı bi meta store.
    
    # Masa bazlı kurye atamasını socketio ile duyur
    socketio.emit('courier_assigned', {
        'masa': masa_adi,
        'kurye_id': kurye_id,
        'kurye_ad': kurye_ad
    })
    
    logger.info(f"🛵 Kurye atandı: {masa_adi} -> {kurye_ad}")

@socketio.on('send_courier_info')
def handle_send_courier_info(data):
    """Kuryeye sipariş bilgilerini gönder (WhatsApp linki vb.)"""
    masa_adi = data.get('masa')
    kurye_tel = data.get('kurye_tel')
    
    if not masa_adi or not kurye_tel:
        emit('error', {'message': 'Eksik bilgi'})
        return
        
    adisyon = {
        'masa': masa_adi,
        'items': server.adisyonlar.get(masa_adi, []),
        'total': sum(i['adet'] * i['fiyat'] for i in server.adisyonlar.get(masa_adi, []))
    }
    
    # Müşteri bilgisini bul (Paket adından telefon çekmeye çalışalım)
    # Örn: "0532..." gibi bi isim varsa
    customer_info = {
        'cari_isim': masa_adi,
        'telefon': '',
        'adres': ''
    }
    
    if USE_DATABASE:
        # Eğer masa adı bi telefon ise cari'den bul
        import re
        phone_match = re.search(r'(\d{10,11})', masa_adi)
        if phone_match:
            customer = db.get_cari_by_phone(phone_match.group(1))
            if customer:
                customer_info = customer
        else:
            # Cari ismi olarak ara
            # Cari adı genellikle Paket X olur ama Caller ID ile müşteri adı atanmış olabilir
            pass

    message, maps_link = server.courier_manager.generate_courier_message(adisyon, customer_info)
    
    emit('courier_message_ready', {
        'message': message,
        'maps_link': maps_link,
        'whatsapp_url': f"https://wa.me/{kurye_tel}?text={urllib.parse.quote(message)}"
    })

@socketio.on('remove_item')
def handle_remove_item(data):
    """Sipariş kaldır"""
    sid = request.sid
    masa_adi = server.current_selections.get(sid)
    index = data.get('index', -1)
    
    if masa_adi and masa_adi in server.adisyonlar:
        if 0 <= index < len(server.adisyonlar[masa_adi]):
            server.adisyonlar[masa_adi].pop(index)
            server.save_active_adisyonlar() # Persistence
            
            items = server.adisyonlar[masa_adi]
            total = sum(item['adet'] * item['fiyat'] for item in items)
            
            socketio.emit('masa_update', {
                'masa': masa_adi,
                'items': items,
                'total': total
            })

@socketio.on('finalize_payment')
def handle_payment(data):
    """Ödeme al"""
    sid = request.sid
    masa_adi = server.current_selections.get(sid)
    
    if not masa_adi or masa_adi not in server.adisyonlar:
        emit('error', {'message': 'Geçersiz masa'})
        return
    
    items = server.adisyonlar[masa_adi]
    if not items:
        emit('error', {'message': 'Sipariş yok'})
        return

    # Ödeme listesini al (YENİ: Parçalı ödeme desteği)
    if data.get('role') == 'terminal':
        emit('error', {'message': 'Yetki hatası: Kasa işlemi yapılamaz'})
        return

    payments = data.get('payments', [])
    payment_type = data.get('type', 'Nakit') # Eski format desteği
    item_indices = data.get('item_indices', []) # YENİ: Seçili ürünlerin indexleri

    # Hangi kalemlerin ödendiğini belirle
    if item_indices:
        items_to_pay = []
        # Indexleri büyükten küçüğe sıralayarak pop işleminin diğer indexleri kaydırmasını önleyeceğiz
        # Ama önce kopyasını alıp işlem yapalım ki hata durumunda veri kaybolmasın
        for idx in item_indices:
            if 0 <= idx < len(server.adisyonlar[masa_adi]):
                items_to_pay.append(server.adisyonlar[masa_adi][idx])
        
        if not items_to_pay:
            emit('error', {'message': 'Seçilen ürünler bulunamadı'})
            return
        items = items_to_pay

    if not payments:
        total_amount = sum(item['adet'] * item['fiyat'] for item in items)
        payments = [{'type': payment_type, 'amount': total_amount}]
    
    # Aktif vardiya bilgisini al
    active_shift = server.get_sid_active_shift(sid)
    vardiya_id = active_shift['id'] if active_shift else None
    
    # Database'e kaydet
    try:
        timestamp = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        
        # Cari işlemleri kaydet
        for p in payments:
            if p['type'] == 'Açık Hesap' and USE_DATABASE:
                customer = p.get('customer', 'Genel Müşteri')
                amount = float(p.get('amount', 0))
                if amount > 0:
                    db.save_cari_transaction(customer, 'borc', amount)
                    logger.info(f"📝 Cari Borç: {customer} | {amount:.2f} TL")

        # POS İşlemi (Kart ödemesi varsa)
        if server.pos_enabled:
            card_amount = sum(p['amount'] for p in payments if p['type'] == 'Kredi Kartı')
            if card_amount > 0:
                logger.info(f"💳 POS Satış başlatılıyor: {card_amount:.2f} TL")
                success, msg = server.pos_manager.sale(card_amount, masa_adi)
                if not success:
                    raise Exception(msg)
                logger.info(f"✅ POS Satış başarılı: {msg}")

        # Satışları kaydet
        # Eğer birden fazla ödeme türü varsa 'Parçalı' olarak işaretle
        final_payment_label = payments[0]['type'] if len(payments) == 1 else "Parçalı"
        
        sales_data = []
        for item in items:
            sales_data.append({
                'urun': item['urun'],
                'adet': item['adet'],
                'fiyat': item['fiyat'],
                'odeme': final_payment_label,
                'tip': item.get('tip', 'normal'),
                'Tarih_Saat': timestamp,
                'masa': masa_adi,
                'terminal_id': server.terminal_id,
                'vardiya_id': vardiya_id
            })
        
        if USE_DATABASE:
            db.save_sales_batch(sales_data)
        
        # Adisyonu temizle (Sadece ödenen kalemleri)
        is_partial = False
        if item_indices:
            # Indexleri büyükten küçüğe sıralayıp sil
            for idx in sorted(item_indices, reverse=True):
                if 0 <= idx < len(server.adisyonlar[masa_adi]):
                    server.adisyonlar[masa_adi].pop(idx)
            
            # Eğer masada hala ürün varsa bu bir kısmi ödemedir
            if server.adisyonlar[masa_adi]:
                is_partial = True
        else:
            server.adisyonlar[masa_adi] = []
        
        server.save_active_adisyonlar() # Persistence
        
        # Tüm clientlara bildir
        socketio.emit('payment_completed', {
            'masa': masa_adi,
            'type': final_payment_label,
            'payments': payments,
            'is_partial': is_partial
        })

        # Eğer kısmi ödeme ise veya masada hala ürün varsa masa_update gönder
        if is_partial or server.adisyonlar[masa_adi]:
            remaining_total = sum(item['adet'] * item['fiyat'] for item in server.adisyonlar[masa_adi] if item.get('tip') != 'ikram')
            socketio.emit('masa_update', {
                'masa': masa_adi,
                'items': server.adisyonlar[masa_adi],
                'total': remaining_total
            })
        
        msg = f"{final_payment_label} ödemesi alındı"
        if final_payment_label == "Parçalı":
            details = ", ".join([f"{p['amount']} TL {p['type']}" for p in payments])
            msg = f"Parçalı ödeme alındı: {details}"
            
        emit('success', {'message': msg})
        
        # --- MUHASEBE ENTEGRASYONU ---
        try:
            order_data = {
                'masa': masa_adi,
                'customer': payments[0].get('customer', 'Genel Müşteri'),
                'items': [{
                    'urun': i['urun'],
                    'adet': i['adet'],
                    'fiyat': i['fiyat']
                } for i in items],
                'total': sum(i['adet'] * i['fiyat'] for i in items),
                'payment_type': final_payment_label,
                'timestamp': timestamp
            }
            # Arka planda gönder (Arayüzü bekletme)
            threading.Thread(
                target=server.integration_manager.send_to_accounting,
                args=(order_data,),
                daemon=True
            ).start()
        except Exception as ae:
            logger.error(f"Muhasebe gönderim hazırlık hatası: {ae}")
        
    except Exception as e:
        logger.error(f"Ödeme hatası: {e}")
        emit('error', {'message': str(e)})

@socketio.on('print_receipt')
def handle_print_receipt(data):
    """Fiş yazdır"""
    sid = request.sid
    masa_adi = server.current_selections.get(sid)
    
    if not masa_adi or masa_adi not in server.adisyonlar:
        emit('error', {'message': 'Geçersiz masa'})
        return
    
    items = [i for i in server.adisyonlar.get(masa_adi, []) if i.get('tip') != 'tip']
    if not items:
        emit('error', {'message': 'Yazdırılacak sipariş yok'})
        return
    
    try:
        sira = server.get_and_inc_counter()
        now = datetime.datetime.now().strftime("%d-%m-%Y      %H:%M")
        fn = os.path.join(FIS_KLASORU, f"Fis_{sira}.txt")
        total = sum(i['adet'] * i['fiyat'] for i in items)
        C_WIDTH = 19 
        
        with open(fn, "w", encoding="utf-8") as f:
            f.write(f"{server.company_name[:C_WIDTH]:^{C_WIDTH}}\n")
            f.write(f"{'SİPARİŞ FİŞİ':^{C_WIDTH}}\n")
            f.write(f"{'='*C_WIDTH}\n")
            f.write(f"{now}\n")
            f.write(f"Fiş No:{sira:<8} {masa_adi}\n")
            f.write(f"{'-'*C_WIDTH}\n")
            f.write(f"{'Ürün':<10} {'Ad.':<5} {'Tutar':}\n")
            f.write(f"{'-'*C_WIDTH}\n")
            for i in items:
                ik = " (IK)" if i.get("tip") == "ikram" else ""
                urun_adi = (i['urun'] + ik)[:14]
                f.write(f"{urun_adi:<12} {i['adet']:<1} {i['adet']*i['fiyat']:>6.2f}TL\n")
            f.write(f"{'='*C_WIDTH}\n")
            f.write(f"{'TOPLAM:':<10}{total:>11.2f}TL \n")
            f.write(f"{'='*C_WIDTH}\n")
            f.write(f"{'Afiyet Olsun':^{C_WIDTH}}\n")
            f.write("\n\n\n")

        full_path = os.path.abspath(fn)
        
        # Yazdırma komutu
        if server.direct_print:
            system = platform.system()
            try:
                if system == "Windows":
                    os.startfile(full_path, "print")
                elif system == "Darwin": # MacOS
                    subprocess.run(["lp", full_path], check=True)
                else: # Linux
                    subprocess.run(["lpr", full_path], check=True)
            except Exception as e:
                logger.error(f"Yazdırma hatası: {e}")
                # Fallback: Dosyayı aç
                if system == "Darwin":
                    subprocess.run(["open", full_path])
                elif system == "Windows":
                    os.startfile(full_path)
        else:
            # Direct print kapalıysa sadece dosyayı aç (izleme amaçlı)
            system = platform.system()
            if system == "Darwin":
                subprocess.run(["open", full_path])
            elif system == "Windows":
                os.startfile(full_path)
            else:
                subprocess.run(["xdg-open", full_path])

        emit('success', {'message': 'Fiş oluşturuldu ve yazdırılmaya gönderildi'})
        
    except Exception as e:
        logger.error(f"Fiş oluşturma hatası: {e}")
        emit('error', {'message': f'Fiş oluşturulamadı: {str(e)}'})

if __name__ == '__main__':
    # Terminal sunucusunu başlat
    server.start_terminal_server()
    
    # Caller ID sunucusunu başlat
    server.start_caller_id_listener()
    
    # Web sunucuyu başlat
    logger.info(f"🌐 Web sunucu başlatılıyor: http://{get_local_ip()}:8000")
    socketio.run(app, host='0.0.0.0', port=8000, debug=False, allow_unsafe_werkzeug=True)
