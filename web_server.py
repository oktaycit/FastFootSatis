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
from collections import defaultdict

# Database modülünü yükle
try:
    from database import db
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
        self.masa_sayisi = 30
        self.paket_sayisi = 5
        self.direct_print = False
        
        # Adisyon durumları
        self.adisyonlar = {}
        self.current_selections = {}  # {sid: masa_adi}
        
        # Menu
        self.menu_data = {}
        
        # Aktif bağlantılar
        self.active_connections = {}
        
        # Terminal sunucusu
        self.terminal_thread = None
        self.running = False
        
        # Ayarları yükle
        self.load_settings()
        self.refresh_adisyonlar()
        self.load_menu_data()
        
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
            "terminal_id": "1"
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
            return True
        except Exception as e:
            logger.error(f"Ayar kaydetme hatası: {e}")
            return False
    
    def refresh_adisyonlar(self):
        """Masa/paket yapısını yeniden oluştur"""
        self.adisyonlar = {}
        if self.masa_sayisi > 0:
            for i in range(1, self.masa_sayisi + 1):
                self.adisyonlar[f"Masa {i}"] = []
        if self.paket_sayisi > 0:
            for i in range(1, self.paket_sayisi + 1):
                self.adisyonlar[f"Paket {i}"] = []
        if not self.adisyonlar:
            self.adisyonlar["Genel"] = []
        
        logger.info(f"✓ {len(self.adisyonlar)} adisyon alanı oluşturuldu")
    
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
                    if len(parts) == 3:
                        cat, item, price = parts[0].strip(), parts[1].strip(), parts[2].strip()
                        if cat not in self.menu_data:
                            self.menu_data[cat] = []
                        self.menu_data[cat].append([item, float(price)])
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
                
                logger.info(f"📲 Terminal siparişi: {terminal_adi} → {masa_adi}")
        except Exception as e:
            logger.error(f"Terminal veri hatası: {e}")
        finally:
            client_sock.close()

# Global server instance
server = RestaurantServer()

# ==================== FLASK ROUTES ====================

@app.route('/')
def index():
    """Ana sayfa"""
    return app.send_static_file('index.html')

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
        'pdf': PDF_SUPPORT
    })

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
            'paket_sayisi': server.paket_sayisi
        }
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Client ayrıldı"""
    sid = request.sid
    if sid in server.active_connections:
        info = server.active_connections.pop(sid)
        logger.info(f"❌ Client ayrıldı: {info['ip']} ({sid})")

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
    masa_adi = server.current_selections.get(sid)
    
    if not masa_adi or masa_adi not in server.adisyonlar:
        emit('error', {'message': 'Lütfen önce masa seçiniz'})
        return
    
    urun = data.get('urun')
    fiyat = float(data.get('fiyat', 0))
    
    siparis = {
        'urun': urun,
        'adet': 1,
        'fiyat': fiyat,
        'tip': 'normal'
    }
    
    server.adisyonlar[masa_adi].append(siparis)
    
    # Tüm clientlara bildir
    items = server.adisyonlar[masa_adi]
    total = sum(item['adet'] * item['fiyat'] for item in items)
    
    socketio.emit('masa_update', {
        'masa': masa_adi,
        'items': items,
        'total': total
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
    payment_type = data.get('type', 'Nakit')
    
    if not masa_adi or masa_adi not in server.adisyonlar:
        emit('error', {'message': 'Geçersiz masa'})
        return
    
    items = server.adisyonlar[masa_adi]
    if not items:
        emit('error', {'message': 'Sipariş yok'})
        return
    
    # Database'e kaydet
    try:
        timestamp = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        sales_data = []
        
        for item in items:
            sales_data.append({
                'urun': item['urun'],
                'adet': item['adet'],
                'fiyat': item['fiyat'],
                'odeme': payment_type,
                'tip': item.get('tip', 'normal'),
                'Tarih_Saat': timestamp
            })
        
        if USE_DATABASE:
            db.save_sales_batch(sales_data)
        
        # Adisyonu temizle
        server.adisyonlar[masa_adi] = []
        
        # Tüm clientlara bildir
        socketio.emit('payment_completed', {
            'masa': masa_adi,
            'type': payment_type
        })
        
        emit('success', {'message': f'{payment_type} ödemesi alındı'})
        
    except Exception as e:
        logger.error(f"Ödeme hatası: {e}")
        emit('error', {'message': str(e)})

if __name__ == '__main__':
    # Terminal sunucusunu başlat
    server.start_terminal_server()
    
    # Web sunucuyu başlat
    logger.info(f"🌐 Web sunucu başlatılıyor: http://{get_local_ip()}:8000")
    socketio.run(app, host='0.0.0.0', port=8000, debug=True, allow_unsafe_werkzeug=True)
