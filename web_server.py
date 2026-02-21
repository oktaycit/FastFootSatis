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
            
    def send_to_kitchen_legacy(self, masa_adi, urun_adi, adet=1):
        """Mevcut mutfak.py (port 5556) sistemine sipariş gönderir"""
        def task():
            try:
                # Ayarları yükle (Kitchen IP/Port her seferinde kontrol edilebilir veya tek seferlik yüklenebilir)
                # Buradaki self.kitchen_ip ve self.kitchen_port varsayılan olarak sipariscari.py'den gelebilir
                # web_server.py'de henüz bu ayarlar yok, ekleyelim.
                kitchen_ip = getattr(self, 'kitchen_ip', '127.0.0.1')
                kitchen_port = getattr(self, 'kitchen_port', 5556)
                
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.settimeout(3)
                client.connect((kitchen_ip, kitchen_port))
                
                payload = {
                    "islem": "yeni_siparis",
                    "masa": masa_adi,
                    "siparisler": [{"urun": urun_adi, "adet": adet}], # mutfak.py bu formatı bekliyor olabilir
                    "saat": datetime.datetime.now().strftime("%H:%M:%S"),
                    "terminal": self.terminal_id
                }
                
                client.send(json.dumps(payload).encode('utf-8'))
                client.close()
                logger.info(f"👨‍🍳 Legacy Mutfak onayladı: {urun_adi} -> {masa_adi}")
            except Exception as e:
                logger.error(f"⚠ Legacy Mutfak ekranına bağlanılamadı: {e}")
                
        threading.Thread(target=task, daemon=True).start()
    
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

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Mevcut ayarları döndür"""
    return jsonify({
        'firma_ismi':   server.company_name,
        'terminal_id':  server.terminal_id,
        'masa_sayisi':  server.masa_sayisi,
        'paket_sayisi': server.paket_sayisi,
        'direct_print': server.direct_print,
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
                    f.write(f"{cat};{item[0]};{item[1]}\n")
        
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
        'tip': 'normal',
        'saat': datetime.datetime.now().strftime("%H:%M:%S")
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
    
    # Mutfak bildirimi gönder
    socketio.emit('kitchen_new_order', {
        'masa': masa_adi,
        'urun': urun,
        'adet': 1,
        'saat': datetime.datetime.now().strftime("%H:%M:%S"),
        'terminal_id': f"sid:{sid}"
    })
    
    # Legacy mutfak sistemine gönder
    server.send_to_kitchen_legacy(masa_adi, urun, 1)

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

@socketio.on('kitchen_order_ready')
def handle_kitchen_ready(data):
    """Mutfak siparişi tamamladı"""
    masa_adi = data.get('masa')
    terminal_ids = data.get('terminal_ids', [])
    
    logger.info(f"👨‍🍳 Mutfak bildirdi: {masa_adi} hazır!")
    
    # İlgili terminallere bildir (sid: ile başlayanlara)
    for t_id in terminal_ids:
        if t_id.startswith('sid:'):
            target_sid = t_id.split('sid:')[1]
            socketio.emit('order_ready', {
                'masa': masa_adi,
                'message': f"{masa_adi} Siparişi Hazır!"
            }, to=target_sid)
        
    # Genel sistem bildirimi (opsiyonel - istenirse tüm garsonlara gidebilir)
    # socketio.emit('global_notification', {'title': 'Mutfak', 'message': f'{masa_adi} hazır!'})


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
                'terminal_id': server.terminal_id
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
    
    # Web sunucuyu başlat
    logger.info(f"🌐 Web sunucu başlatılıyor: http://{get_local_ip()}:8000")
    socketio.run(app, host='0.0.0.0', port=8000, debug=False, allow_unsafe_werkzeug=True)
