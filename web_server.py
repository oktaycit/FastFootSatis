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
import io
import logging
import socket
import subprocess
import platform
import uuid
import re
import hmac
import hashlib
import base64
import secrets
import serial
import serial.tools.list_ports
import urllib.parse
import unicodedata
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
MENU_META_FILE = os.path.join(SCRIPT_DIR, "menu_meta.json")
FIS_KLASORU = os.path.join(SCRIPT_DIR, "Fisler")
MENU_UPLOAD_DIR = os.path.join(SCRIPT_DIR, "web", "uploads", "menu")
MENU_UPLOAD_URL_PREFIX = "/uploads/menu"
MAX_MENU_IMAGE_BYTES = 8 * 1024 * 1024
ALLOWED_MENU_IMAGE_FORMATS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
    "GIF": "gif",
}
COUNTER_FILE = os.path.join(SCRIPT_DIR, "sira_no.txt")
WAITERS_FILE = os.path.join(SCRIPT_DIR, "waiters.json")
INTEGRATION_CONFIG = os.path.join(SCRIPT_DIR, "integrations.json")
SALONS_FILE = os.path.join(SCRIPT_DIR, "salons.json")
CASHIERS_FILE = os.path.join(SCRIPT_DIR, "cashiers.json")
KITCHEN_FILE = os.path.join(SCRIPT_DIR, "kitchen.json")
ACTIVE_ADISYONLAR_FILE = os.path.join(SCRIPT_DIR, "active_adisyonlar.json")
PORTION_STOCK_FILE = os.path.join(SCRIPT_DIR, "portion_stock.json")
PORTION_STOCK_RESET_FILE = os.path.join(SCRIPT_DIR, "portion_stock_reset.json")
DAILY_MEALS_FILE = os.path.join(SCRIPT_DIR, "gunluk_yemekler.txt")
DAILY_MEALS_HISTORY_DIR = os.path.join(SCRIPT_DIR, "gunluk_yemekler")
DEFAULT_PORTION_STOCK = 40
SERVER_PORT = 5555

PREP_PANELS = {
    "izgara": {
        "id": "izgara",
        "name": "Izgara",
        "title": "IZGARA SİPARİŞ TAKİP",
        "ticket_title": "IZGARA FİŞİ",
        "emoji": "🔥",
        "aggregate": False
    },
    "mutfak": {
        "id": "mutfak",
        "name": "Mutfak",
        "title": "MUTFAK SİPARİŞ TAKİP",
        "ticket_title": "MUTFAK FİŞİ",
        "emoji": "👨‍🍳",
        "aggregate": False
    },
    "icecek": {
        "id": "icecek",
        "name": "İçecek",
        "title": "İÇECEK SİPARİŞ TAKİP",
        "ticket_title": "İÇECEK FİŞİ",
        "emoji": "🥤",
        "aggregate": True
    },
    "tatli": {
        "id": "tatli",
        "name": "Tatlı",
        "title": "TATLI SİPARİŞ TAKİP",
        "ticket_title": "TATLI FİŞİ",
        "emoji": "🍰",
        "aggregate": False
    }
}

PREP_PANEL_CATEGORY_KEYWORDS = {
    "izgara": ("izgara", "kebap", "kofte", "sis"),
    "icecek": ("icecek", "mesrubat", "cay", "kahve", "soda"),
    "tatli": ("tatli", "baklava", "dondurma", "sut tatlilari", "sutlu tatli")
}

PREP_PANEL_PRODUCT_KEYWORDS = {
    "izgara": (
        "izgara", "kofte", "kebap", "adana", "beyti", "sis", "kanat",
        "incik", "biftek", "karisik", "tepsi"
    ),
    "icecek": ("ayran", "salgam", "soda", "gazoz", "meyve suyu", "mesrubat", "kahve", "cay"),
    "tatli": ("baklava", "sutlac", "kazandibi", "supangle", "dondurma")
}

PREP_PANEL_PRODUCT_EXCLUSIONS = {
    "izgara": ("kiremitte",)
}

PAYMENT_METHODS = ("Nakit", "Kredi Kartı", "Açık Hesap")

DAILY_MEAL_GROUPS = (
    {
        "name": "Dana Etli Yemekler",
        "keywords": ("dana etli yemek",)
    },
    {
        "name": "Kuzu Etli Yemekler",
        "keywords": ("kuzu etli yemek",)
    },
    {
        "name": "Kıymalı Yemekler",
        "keywords": ("kiymali yemek",)
    },
    {
        "name": "Tavuk Etli Yemekler",
        "keywords": ("tavuk etli yemek", "tavuklu yemek")
    },
    {
        "name": "Etsiz Yemekler",
        "keywords": ("etsiz yemek",)
    }
)

# Klasörleri oluştur
if not os.path.exists(FIS_KLASORU):
    os.makedirs(FIS_KLASORU)
os.makedirs(MENU_UPLOAD_DIR, exist_ok=True)
os.makedirs(DAILY_MEALS_HISTORY_DIR, exist_ok=True)

# Flask app setup
app = Flask(__name__, static_folder='web', static_url_path='')
app.config['SECRET_KEY'] = 'fastfoot_secret_key_2026'
app.json.sort_keys = False
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='threading',
                   max_http_buffer_size=1000000,
                   ping_timeout=60000,
                   ping_interval=25000)

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_env_int(name, default):
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except Exception:
        return default

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

def slugify_filename(value, fallback="menu-gorsel"):
    """Dosya adını yerel depoda güvenli kullanılacak hale getir."""
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    chars = []
    for ch in normalized.lower():
        if ch.isalnum():
            chars.append(ch)
        elif ch in (" ", "-", "_", "."):
            chars.append("-")
    slug = "-".join("".join(chars).split("-"))
    return slug.strip("-") or fallback

def save_menu_image(file_storage, product_name=""):
    """Yüklenen/yapıştırılan menü görselini web/uploads/menu altında sakla."""
    if not file_storage:
        return None, "Görsel dosyası bulunamadı"

    raw = file_storage.read(MAX_MENU_IMAGE_BYTES + 1)
    if not raw:
        return None, "Boş görsel dosyası"
    if len(raw) > MAX_MENU_IMAGE_BYTES:
        return None, "Görsel en fazla 8 MB olabilir"

    try:
        from PIL import Image
        image = Image.open(io.BytesIO(raw))
        image.verify()
        image_format = (image.format or "").upper()
    except Exception:
        return None, "Geçerli bir görsel dosyası yükleyin"

    extension = ALLOWED_MENU_IMAGE_FORMATS.get(image_format)
    if not extension:
        return None, "Sadece JPG, PNG, WEBP veya GIF görseller desteklenir"

    original_name = os.path.splitext(file_storage.filename or "")[0]
    base_name = slugify_filename(product_name or original_name)
    filename = f"{base_name}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}.{extension}"
    path = os.path.join(MENU_UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(raw)

    return {
        "filename": filename,
        "url": f"{MENU_UPLOAD_URL_PREFIX}/{filename}",
        "size": len(raw),
    }, None

class RestaurantServer:
    """Ana restoran yönetim sınıfı"""
    
    def __init__(self):
        # Sistem ayarları
        self.company_name = "LİVA RESTORAN"
        self.terminal_id = "1"
        self.admin_password = "1234"
        self.paket_sayisi = 5
        self.direct_print = False
        self.default_payment_method = "Nakit"
        self.prep_panel_settings = self.get_default_prep_panel_settings()
        self.prep_category_overrides = {}
        self.prep_printers = self.get_default_prep_printer_settings()
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
        self.daily_meal_categories = []
        self.daily_meals = []
        self.daily_meals_date = None
        self.daily_meals_mtime = None
        self.portion_stock = {}
        self.portion_lock = threading.RLock()
        self.portion_stock_reset_date = None
        self.portion_reset_thread = None
        
        # Garsonlar ve Kasiyerler
        self.waiters = [] # [{"name": "Ahmet", "pin": "1234"}]
        self.cashiers = [] # [{"name": "Kasa 1"}]
        self.kitchen = [] # [{"name": "Aşçı 1"}]
        
        # Aktif bağlantılar
        self.active_connections = {}
        self.waiter_sessions = defaultdict(set) # waiter_name -> set(sids)
        
        # Terminal sunucusu
        self.terminal_thread = None
        self.running = False

        # Public QR sipariş güvenlik durumu (DB'siz fallback, runtime memory)
        self.qr_secret = os.getenv("FASTFOOT_QR_SECRET", app.config['SECRET_KEY'])
        self.public_sessions = {}      # session_id -> session_info
        self.public_nonce_store = {}   # nonce -> nonce_info
        self.public_rate_limit = defaultdict(list)  # session_id -> [timestamps]
        # verify_mode ve online_orders_enabled load_settings() içinde set edilecek
        self.verify_mode = "hybrid"  # load_settings() ile override edilecek
        self.online_orders_enabled = True  # load_settings() ile override edilecek
        self.public_policy = {
            'dynamic_qr_ttl_sec': max(120, min(get_env_int("FASTFOOT_DYNAMIC_QR_TTL_SEC", 900), 1800)),
            'session_ttl_sec': max(300, min(get_env_int("FASTFOOT_PUBLIC_SESSION_TTL_SEC", 3600), 7200)),
            'session_slide_sec': max(120, min(get_env_int("FASTFOOT_PUBLIC_SESSION_SLIDE_SEC", 900), 1800)),
            'max_items_per_order': max(1, min(get_env_int("FASTFOOT_MAX_ITEMS_PER_ORDER", 25), 100)),
            'max_item_qty': max(1, min(get_env_int("FASTFOOT_MAX_ITEM_QTY", 20), 50)),
            'max_orders_per_minute': max(1, min(get_env_int("FASTFOOT_MAX_ORDERS_PER_MIN", 3), 30))
        }

        if USE_DATABASE:
            try:
                db.init_database()
            except Exception as e:
                logger.error(f"DB init hatası (public session şeması): {e}")
        
        # Ayarları yükle
        self.load_settings()
        self.load_salons()
        self.load_waiters()
        self.load_cashiers()
        self.load_kitchen()
        self.refresh_adisyonlar()
        self.load_active_adisyonlar() # Aktif adisyonları geri yükle
        self.load_menu_data()
        self.load_menu_metadata()
        self.normalize_active_order_panels()
        self.load_daily_meals()
        self.load_portion_stock()
        
        # Sid -> Kasa ID haritalaması (Vardiya işlemleri için)
        self.sid_kasa_map = {} # {sid: kasa_id}
        
        logger.info("🚀 RestaurantServer initialized")
        logger.info(f"📊 Masa: {self.masa_sayisi}, Paket: {self.paket_sayisi}")
        logger.info(f"📡 IP: {get_local_ip()}")
        logger.info(f"🔐 Public verify mode: {self.verify_mode}")

    @staticmethod
    def is_ikram_item(item):
        """Adisyon kaleminin ikram olup olmadığını döndür."""
        return (item or {}).get('tip') == 'ikram'

    @staticmethod
    def item_line_total(item):
        """Adisyon kalemi için liste fiyatı üzerinden satır toplamı."""
        try:
            adet = int((item or {}).get('adet', 1))
            fiyat = float((item or {}).get('fiyat', 0))
            return max(0, adet) * max(0.0, fiyat)
        except Exception:
            return 0.0

    def calculate_adisyon_totals(self, items):
        """Ciroya girecek tutarı ve ikram değerini ayrı hesapla."""
        payable_total = 0.0
        ikram_total = 0.0
        gross_total = 0.0
        for item in items or []:
            line_total = self.item_line_total(item)
            gross_total += line_total
            if self.is_ikram_item(item):
                ikram_total += line_total
            else:
                payable_total += line_total
        return {
            'total': payable_total,
            'payable_total': payable_total,
            'ikram_total': ikram_total,
            'gross_total': gross_total
        }

    # ==================== PUBLIC QR SESSION HELPERS ====================
    def _b64url_encode(self, raw):
        return base64.urlsafe_b64encode(raw).decode('ascii').rstrip("=")

    def _b64url_decode(self, raw):
        raw = raw + "=" * (-len(raw) % 4)
        return base64.urlsafe_b64decode(raw.encode('ascii'))

    def _cleanup_public_security_state(self):
        now_ts = time.time()
        if USE_DATABASE:
            try:
                db.cleanup_public_security_state()
            except Exception as e:
                logger.error(f"Public state DB cleanup hatası: {e}")

        expired_nonces = [
            nonce for nonce, data in self.public_nonce_store.items()
            if data.get('expires_at', 0) <= now_ts or data.get('used_at')
        ]
        for nonce in expired_nonces:
            self.public_nonce_store.pop(nonce, None)

        expired_sessions = [
            sid for sid, data in self.public_sessions.items()
            if data.get('status') != 'active' or data.get('expires_at', 0) <= now_ts
        ]
        for sid in expired_sessions:
            self.public_sessions.pop(sid, None)
            self.public_rate_limit.pop(sid, None)

    def _create_signed_qr_token(self, table_name, shift_id=None, ttl_seconds=900):
        self._cleanup_public_security_state()
        nonce = secrets.token_urlsafe(10)
        exp_ts = int(time.time()) + int(ttl_seconds)
        payload = {
            'table_name': table_name,
            'shift_id': shift_id,
            'nonce': nonce,
            'exp': exp_ts
        }
        payload_bytes = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        payload_b64 = self._b64url_encode(payload_bytes)
        signature = hmac.new(self.qr_secret.encode('utf-8'), payload_b64.encode('ascii'), hashlib.sha256).digest()
        token = f"{payload_b64}.{self._b64url_encode(signature)}"

        self.public_nonce_store[nonce] = {
            'table_name': table_name,
            'shift_id': shift_id,
            'expires_at': exp_ts,
            'used_at': None
        }
        if USE_DATABASE:
            try:
                db.create_public_nonce(
                    nonce=nonce,
                    table_name=table_name,
                    shift_id=shift_id,
                    expires_at=datetime.datetime.fromtimestamp(exp_ts)
                )
            except Exception as e:
                logger.error(f"Public nonce DB kayıt hatası: {e}")
        return token, exp_ts

    def _verify_signed_qr_token(self, token):
        self._cleanup_public_security_state()
        try:
            payload_b64, sig_b64 = token.split('.', 1)
            expected_sig = hmac.new(
                self.qr_secret.encode('utf-8'),
                payload_b64.encode('ascii'),
                hashlib.sha256
            ).digest()
            actual_sig = self._b64url_decode(sig_b64)
            if not hmac.compare_digest(expected_sig, actual_sig):
                return None, "Geçersiz imza"

            payload_raw = self._b64url_decode(payload_b64)
            payload = json.loads(payload_raw.decode('utf-8'))
        except Exception:
            return None, "Geçersiz token formatı"

        now_ts = int(time.time())
        if payload.get('exp', 0) < now_ts:
            return None, "Token süresi dolmuş"

        nonce = payload.get('nonce')
        nonce_data = self.public_nonce_store.get(nonce)
        if USE_DATABASE:
            try:
                db_nonce = db.get_public_nonce(nonce)
                if db_nonce:
                    nonce_data = {
                        'table_name': db_nonce.get('table_name'),
                        'shift_id': db_nonce.get('shift_id'),
                        'expires_at': int(db_nonce.get('expires_at').timestamp()) if db_nonce.get('expires_at') else 0,
                        'used_at': db_nonce.get('used_at')
                    }
            except Exception as e:
                logger.error(f"Public nonce DB okuma hatası: {e}")
        if not nonce_data:
            return None, "Token geçersiz veya kullanılmış"
        if nonce_data.get('used_at'):
            return None, "Token daha önce kullanılmış"
        if nonce_data.get('expires_at', 0) < now_ts:
            return None, "Token süresi dolmuş"

        return payload, None

    def create_public_session_from_qr(self, token, device_fingerprint="", ip=""):
        payload, err = self._verify_signed_qr_token(token)
        if err:
            return None, err

        nonce = payload['nonce']
        self.public_nonce_store[nonce]['used_at'] = int(time.time())
        if USE_DATABASE:
            try:
                db.mark_public_nonce_used(nonce)
            except Exception as e:
                logger.error(f"Public nonce DB used update hatası: {e}")

        session_id = secrets.token_urlsafe(24)
        expires_at = int(time.time()) + int(self.public_policy.get('session_ttl_sec', 3600))
        session_data = {
            'id': session_id,
            'table_name': payload['table_name'],
            'shift_id': payload.get('shift_id'),
            'verify_method': 'dynamic_qr',
            'device_fingerprint': device_fingerprint[:200],
            'ip': ip,
            'status': 'active',
            'created_at': int(time.time()),
            'expires_at': expires_at
        }
        self.public_sessions[session_id] = session_data
        if USE_DATABASE:
            try:
                db.create_public_session(
                    session_id=session_id,
                    table_name=session_data['table_name'],
                    shift_id=session_data.get('shift_id'),
                    verify_method='dynamic_qr',
                    device_fingerprint=session_data.get('device_fingerprint', ''),
                    ip=ip,
                    expires_at=datetime.datetime.fromtimestamp(expires_at)
                )
            except Exception as e:
                logger.error(f"Public session DB kayıt hatası: {e}")
        return session_data, None

    def create_public_session_from_nfc(self, table_name, nfc_uid, device_fingerprint="", ip=""):
        if table_name not in self.adisyonlar:
            return None, "Geçersiz masa"
        if not nfc_uid:
            return None, "NFC verisi gerekli"

        nfc_hash = hashlib.sha256(nfc_uid.encode('utf-8')).hexdigest()
        expected_hash = None
        if USE_DATABASE:
            try:
                expected_hash = db.get_nfc_tag_hash(table_name)
            except Exception as e:
                logger.error(f"NFC hash DB okuma hatası: {e}")

        if not expected_hash:
            return None, "Bu masa için NFC doğrulama henüz tanımlı değil"
        if expected_hash != nfc_hash:
            return None, "NFC etiketi masa ile eşleşmiyor"

        session_id = secrets.token_urlsafe(24)
        expires_at = int(time.time()) + int(self.public_policy.get('session_ttl_sec', 3600))
        session_data = {
            'id': session_id,
            'table_name': table_name,
            'shift_id': None,
            'verify_method': 'nfc',
            'device_fingerprint': device_fingerprint[:200],
            'ip': ip,
            'status': 'active',
            'created_at': int(time.time()),
            'expires_at': expires_at
        }
        self.public_sessions[session_id] = session_data
        if USE_DATABASE:
            try:
                db.create_public_session(
                    session_id=session_id,
                    table_name=table_name,
                    shift_id=None,
                    verify_method='nfc',
                    device_fingerprint=session_data.get('device_fingerprint', ''),
                    ip=ip,
                    expires_at=datetime.datetime.fromtimestamp(expires_at)
                )
            except Exception as e:
                logger.error(f"NFC session DB kayıt hatası: {e}")
        return session_data, None

    def validate_public_session(self, session_id, table_name=None):
        self._cleanup_public_security_state()
        s = self.public_sessions.get(session_id)
        if USE_DATABASE:
            try:
                db_session = db.get_public_session(session_id)
                if db_session:
                    s = {
                        'id': db_session.get('id'),
                        'table_name': db_session.get('table_name'),
                        'shift_id': db_session.get('shift_id'),
                        'verify_method': db_session.get('verify_method'),
                        'device_fingerprint': db_session.get('device_fingerprint'),
                        'ip': db_session.get('ip'),
                        'status': db_session.get('status'),
                        'created_at': int(db_session.get('created_at').timestamp()) if db_session.get('created_at') else 0,
                        'expires_at': int(db_session.get('expires_at').timestamp()) if db_session.get('expires_at') else 0
                    }
            except Exception as e:
                logger.error(f"Public session DB okuma hatası: {e}")
        if not s:
            return None, "Oturum bulunamadı"
        if s.get('status') != 'active':
            return None, "Oturum aktif değil"
        if s.get('expires_at', 0) < int(time.time()):
            return None, "Oturum süresi dolmuş"
        if table_name and s.get('table_name') != table_name:
            return None, "Masa uyuşmazlığı"
        return s, None

    def can_place_public_order(self, session_id, max_per_minute=3):
        now_ts = time.time()
        recent = [t for t in self.public_rate_limit.get(session_id, []) if now_ts - t <= 60]
        if len(recent) >= max_per_minute:
            self.public_rate_limit[session_id] = recent
            return False
        recent.append(now_ts)
        self.public_rate_limit[session_id] = recent
        return True

    def revoke_public_sessions_for_table(self, table_name):
        if USE_DATABASE:
            try:
                db.revoke_public_sessions_for_table(table_name)
            except Exception as e:
                logger.error(f"Public session table revoke DB hatası: {e}")
        for session in self.public_sessions.values():
            if session.get('table_name') == table_name and session.get('status') == 'active':
                session['status'] = 'revoked'

    def revoke_public_sessions_for_shift(self, shift_id):
        if USE_DATABASE:
            try:
                db.revoke_public_sessions_for_shift(shift_id)
            except Exception as e:
                logger.error(f"Public session shift revoke DB hatası: {e}")
        for session in self.public_sessions.values():
            if session.get('shift_id') == shift_id and session.get('status') == 'active':
                session['status'] = 'revoked'

    def bool_from_setting(self, value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().upper() in ("EVET", "TRUE", "1", "YES", "ON")

    def bounded_int(self, value, default, minimum, maximum):
        try:
            parsed = int(value)
        except Exception:
            parsed = default
        return max(minimum, min(parsed, maximum))

    def sanitize_payment_method(self, value):
        normalized = str(value or "").strip().lower()
        aliases = {
            "nakit": "Nakit",
            "cash": "Nakit",
            "kart": "Kredi Kartı",
            "kredi kartı": "Kredi Kartı",
            "kredi karti": "Kredi Kartı",
            "card": "Kredi Kartı",
            "açık hesap": "Açık Hesap",
            "acik hesap": "Açık Hesap",
            "cari": "Açık Hesap"
        }
        if value in PAYMENT_METHODS:
            return value
        return aliases.get(normalized, "Nakit")

    def normalize_keyword_list(self, value, fallback=None):
        if fallback is None:
            fallback = []
        if isinstance(value, str):
            raw_items = value.replace("\n", ",").split(",")
        elif isinstance(value, (list, tuple)):
            raw_items = value
        else:
            raw_items = fallback

        keywords = []
        for item in raw_items:
            keyword = self._normalize_text_for_match(item).strip()
            if keyword and keyword not in keywords:
                keywords.append(keyword[:40])
        return keywords

    def get_default_prep_panel_settings(self):
        settings = {}
        for panel_id, panel in PREP_PANELS.items():
            settings[panel_id] = {
                **panel,
                "category_keywords": list(PREP_PANEL_CATEGORY_KEYWORDS.get(panel_id, ())),
                "product_keywords": list(PREP_PANEL_PRODUCT_KEYWORDS.get(panel_id, ()))
            }
        return settings

    def get_default_prep_printer_settings(self):
        return {
            panel_id: {
                "enabled": False,
                "ip": "",
                "port": 9100,
                "copies": 1
            }
            for panel_id in PREP_PANELS.keys()
        }

    def coerce_json_setting(self, value, fallback):
        if value is None:
            return fallback
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except Exception:
            return fallback

    def sanitize_prep_panel_settings(self, panels_data=None):
        defaults = self.get_default_prep_panel_settings()
        panels_data = self.coerce_json_setting(panels_data, {})
        if isinstance(panels_data, dict) and isinstance(panels_data.get("panels"), list):
            panels_data = panels_data["panels"]

        by_id = {}
        if isinstance(panels_data, dict):
            by_id = panels_data
        elif isinstance(panels_data, list):
            by_id = {
                str(item.get("id", "")).strip(): item
                for item in panels_data
                if isinstance(item, dict)
            }

        sanitized = {}
        for panel_id, default in defaults.items():
            raw = by_id.get(panel_id, {})
            if not isinstance(raw, dict):
                raw = {}

            name = str(raw.get("name") or default["name"]).strip()[:40] or default["name"]
            title = str(raw.get("title") or default["title"]).strip()[:80] or default["title"]
            ticket_title = str(raw.get("ticket_title") or default["ticket_title"]).strip()[:40] or default["ticket_title"]
            emoji = str(raw.get("emoji") or default.get("emoji", "")).strip()[:8]
            sanitized[panel_id] = {
                "id": panel_id,
                "name": name,
                "title": title,
                "ticket_title": ticket_title,
                "emoji": emoji,
                "aggregate": self.bool_from_setting(raw.get("aggregate"), default.get("aggregate", False)),
                "category_keywords": self.normalize_keyword_list(
                    raw.get("category_keywords"),
                    default.get("category_keywords", [])
                ),
                "product_keywords": self.normalize_keyword_list(
                    raw.get("product_keywords"),
                    default.get("product_keywords", [])
                )
            }
        return sanitized

    def sanitize_prep_category_overrides(self, overrides=None):
        overrides = self.coerce_json_setting(overrides, {})
        if not isinstance(overrides, dict):
            return {}

        valid_panels = set(self.prep_panel_settings.keys())
        clean = {}
        for category, panel_id in overrides.items():
            category_name = str(category or "").strip()[:80]
            target_panel = str(panel_id or "").strip()
            if category_name and target_panel in valid_panels:
                clean[category_name] = target_panel
        return clean

    def sanitize_prep_printer_settings(self, printers_data=None):
        defaults = self.get_default_prep_printer_settings()
        printers_data = self.coerce_json_setting(printers_data, {})
        if not isinstance(printers_data, dict):
            printers_data = {}

        sanitized = {}
        for panel_id, default in defaults.items():
            raw = printers_data.get(panel_id, {})
            if not isinstance(raw, dict):
                raw = {}
            sanitized[panel_id] = {
                "enabled": self.bool_from_setting(raw.get("enabled"), default["enabled"]),
                "ip": str(raw.get("ip") or default["ip"]).strip()[:80],
                "port": self.bounded_int(raw.get("port"), default["port"], 1, 65535),
                "copies": self.bounded_int(raw.get("copies"), default["copies"], 1, 5)
            }
        return sanitized

    def get_prep_panel_info(self, panel_id):
        return (
            self.prep_panel_settings.get(panel_id)
            or self.prep_panel_settings.get("mutfak")
            or PREP_PANELS["mutfak"]
        )

    def normalize_active_order_panels(self):
        changed = False
        for masa_items in self.adisyonlar.values():
            for item in masa_items:
                if not isinstance(item, dict):
                    continue
                urun = item.get("urun")
                if not urun:
                    continue
                kategori = item.get("kategori") or self.get_menu_category_for_product(urun)
                panel = self.get_preparation_panel_for_product(urun, kategori)
                if item.get("kategori") != kategori:
                    item["kategori"] = kategori
                    changed = True
                if item.get("panel") != panel:
                    item["panel"] = panel
                    changed = True
        if changed:
            self.save_active_adisyonlar()

    def add_order_item(self, masa_adi, urun, fiyat, garson='Bilinmiyor', adet=1,
                       not_bilgisi='', tip='normal', terminal_id=None, return_error=False):
        if masa_adi not in self.adisyonlar:
            return (None, 'Masa bulunamadı') if return_error else None

        not_bilgisi = str(not_bilgisi or '').strip()[:160]
        try:
            adet = max(1, int(adet))
        except Exception:
            adet = 1
        try:
            fiyat = float(fiyat)
        except Exception:
            return (None, 'Ürün fiyatı geçersiz') if return_error else None

        stock_ok, stock_error = self.consume_portion_stock(urun, adet, not_bilgisi)
        if not stock_ok:
            return (None, stock_error) if return_error else None

        siparis_id = str(uuid.uuid4())[:8]
        kategori = self.get_menu_category_for_product(urun)
        panel = self.get_preparation_panel_for_product(urun, kategori)
        panel_info = self.get_prep_panel_info(panel)
        siparis = {
            'uid': siparis_id,
            'urun': urun,
            'kategori': kategori,
            'panel': panel,
            'adet': adet,
            'fiyat': fiyat,
            'tip': tip,
            'garson': garson,
            'not': not_bilgisi,
            'durum': 'mutfakta',
            'saat': datetime.datetime.now().strftime("%H:%M:%S")
        }
        self.adisyonlar[masa_adi].append(siparis)
        self.save_active_adisyonlar()

        items = self.adisyonlar[masa_adi]
        totals = self.calculate_adisyon_totals(items)
        socketio.emit('masa_update', {
            'masa': masa_adi,
            'items': items,
            **totals
        })
        ticket_payload = {
            'uid': siparis_id,
            'masa': masa_adi,
            'urun': urun,
            'kategori': kategori,
            'panel': panel,
            'panel_adi': panel_info['name'],
            'adet': adet,
            'not': not_bilgisi,
            'saat': siparis['saat'],
            'garson': garson,
            'terminal_id': terminal_id or f"public:{masa_adi}"
        }
        socketio.emit('kitchen_new_order', ticket_payload)
        self.send_prep_ticket_to_printer(panel, ticket_payload)
        if panel == "mutfak":
            self.send_to_kitchen_legacy(masa_adi, f"{urun} ({not_bilgisi})" if not_bilgisi else urun, adet)
        return (siparis, None) if return_error else siparis
    
    def load_settings(self):
        """Ayarları dosyadan yükle"""
        defaults = {
            "password": "1234",
            "direct_print": "HAYIR",
            "masa_sayisi": "30",
            "paket_sayisi": "5",
            "firma_ismi": "LİVA RESTORAN",
            "terminal_id": "1",
            "default_payment_method": "Nakit",
            "cid_port": "101",
            "cid_type": "tcp",
            "cid_serial_port": "COM3",
            "cid_enabled": "EVET",
            "pos_enabled": "HAYIR",
            "pos_ip": "127.0.0.1",
            "pos_port": "5000",
            "pos_type": "demo",
            "verify_mode": "hybrid",
            "online_orders_enabled": "EVET",
            "va_max_duration": "3",
            "va_rate_limit": "5",
            "va_sms_verify": "HAYIR",
            "va_kitchen_approval": "EVET",
            "prep_panels_json": "",
            "prep_category_overrides_json": "{}",
            "prep_printers_json": "{}"
        }
        for panel_id in PREP_PANELS.keys():
            defaults[f"prep_printer_{panel_id}_enabled"] = "HAYIR"
            defaults[f"prep_printer_{panel_id}_ip"] = ""
            defaults[f"prep_printer_{panel_id}_port"] = "9100"
            defaults[f"prep_printer_{panel_id}_copies"] = "1"
        
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
        self.default_payment_method = self.sanitize_payment_method(defaults.get("default_payment_method"))
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

        # Hazırlık reyonları ve IP termal yazıcı ayarları
        self.prep_panel_settings = self.sanitize_prep_panel_settings(defaults.get("prep_panels_json"))
        self.prep_category_overrides = self.sanitize_prep_category_overrides(
            defaults.get("prep_category_overrides_json")
        )
        printer_json = self.coerce_json_setting(defaults.get("prep_printers_json"), {})
        if not printer_json:
            printer_json = {}
            for panel_id in PREP_PANELS.keys():
                printer_json[panel_id] = {
                    "enabled": defaults.get(f"prep_printer_{panel_id}_enabled"),
                    "ip": defaults.get(f"prep_printer_{panel_id}_ip"),
                    "port": defaults.get(f"prep_printer_{panel_id}_port"),
                    "copies": defaults.get(f"prep_printer_{panel_id}_copies")
                }
        self.prep_printers = self.sanitize_prep_printer_settings(printer_json)
        
        # QR Menü ve Online Sipariş Ayarları
        # Env değişkeni varsa önceliklidir, yoksa config.txt'ten okunur
        env_verify = os.getenv("FASTFOOT_VERIFY_MODE", "").strip().lower()
        cfg_verify = defaults.get("verify_mode", "hybrid").strip().lower()
        self.verify_mode = env_verify if env_verify in ("none", "dynamic_qr", "nfc", "hybrid") else (
            cfg_verify if cfg_verify in ("none", "dynamic_qr", "nfc", "hybrid") else "hybrid"
        )
        self.online_orders_enabled = (defaults.get("online_orders_enabled", "EVET") == "EVET")
    
        # Sesli Asistan Güvenlik Ayarları
        self.va_max_duration = int(defaults.get("va_max_duration", 3))
        self.va_rate_limit = int(defaults.get("va_rate_limit", 5))
        self.va_sms_verify = (defaults.get("va_sms_verify", "HAYIR") == "EVET")
        self.va_kitchen_approval = (defaults.get("va_kitchen_approval", "EVET") == "EVET")
    
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
                f.write(f"default_payment_method:{self.default_payment_method}\n")
                f.write(f"cid_port:{self.cid_port}\n")
                f.write(f"cid_type:{self.cid_type}\n")
                f.write(f"cid_serial_port:{self.cid_serial_port}\n")
                f.write(f"cid_enabled:{'EVET' if self.cid_enabled else 'HAYIR'}\n")
                f.write(f"pos_enabled:{'EVET' if self.pos_enabled else 'HAYIR'}\n")
                f.write(f"pos_ip:{self.pos_ip}\n")
                f.write(f"pos_port:{self.pos_port}\n")
                f.write(f"pos_type:{self.pos_type}\n")
                f.write(
                    "prep_panels_json:"
                    f"{json.dumps(list(self.prep_panel_settings.values()), ensure_ascii=False)}\n"
                )
                f.write(
                    "prep_category_overrides_json:"
                    f"{json.dumps(self.prep_category_overrides, ensure_ascii=False)}\n"
                )
                f.write(
                    "prep_printers_json:"
                    f"{json.dumps(self.prep_printers, ensure_ascii=False)}\n"
                )
                for panel_id, printer in self.prep_printers.items():
                    f.write(f"prep_printer_{panel_id}_enabled:{'EVET' if printer.get('enabled') else 'HAYIR'}\n")
                    f.write(f"prep_printer_{panel_id}_ip:{printer.get('ip', '')}\n")
                    f.write(f"prep_printer_{panel_id}_port:{printer.get('port', 9100)}\n")
                    f.write(f"prep_printer_{panel_id}_copies:{printer.get('copies', 1)}\n")
                f.write(f"verify_mode:{self.verify_mode}\n")
                f.write(f"online_orders_enabled:{'EVET' if self.online_orders_enabled else 'HAYIR'}\n")
                f.write(f"va_max_duration:{self.va_max_duration}\n")
                f.write(f"va_rate_limit:{self.va_rate_limit}\n")
                f.write(f"va_sms_verify:{'EVET' if self.va_sms_verify else 'HAYIR'}\n")
                f.write(f"va_kitchen_approval:{'EVET' if self.va_kitchen_approval else 'HAYIR'}\n")
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
            'pos_enabled': self.pos_enabled,
            'pos_type': self.pos_type,
            'default_payment_method': self.default_payment_method
        }

    def get_initial_payload(self, sid=None):
        """İstemcilere gönderilen tam ekran durumunu hazırla."""
        payload = {
            'menu': self.get_order_menu_data(),
            'adisyonlar': self.adisyonlar,
            'system': self.get_system_info(),
            'prep_panels': self.get_preparation_panels(),
            'prep_category_overrides': self.prep_category_overrides,
            'portion_stock': self.get_portion_stock_snapshot(),
            'daily_meals': self.get_daily_meals_payload()
        }
        if sid is not None:
            payload['active_shift'] = self.get_sid_active_shift(sid)
        return payload

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
            for key, value in list(shift_dict.items()):
                if isinstance(value, Decimal):
                    shift_dict[key] = float(value)
                elif isinstance(value, (datetime.datetime, datetime.date)):
                    shift_dict[key] = value.isoformat()
                    
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

    def load_kitchen(self):
        """Mutfak personelini dosyadan yükle"""
        if os.path.exists(KITCHEN_FILE):
            try:
                with open(KITCHEN_FILE, "r", encoding="utf-8") as f:
                    self.kitchen = json.load(f)
                logger.info(f"✓ {len(self.kitchen)} mutfak personeli yüklendi")
            except Exception as e:
                logger.error(f"Mutfak personeli yükleme hatası: {e}")
                self.kitchen = []
        else:
            self.kitchen = []

    def save_kitchen(self):
        """Mutfak personelini dosyaya kaydet"""
        try:
            with open(KITCHEN_FILE, "w", encoding="utf-8") as f:
                json.dump(self.kitchen, f, ensure_ascii=False, indent=2)
            logger.info("✓ Mutfak personeli kaydedildi")
            return True
        except Exception as e:
            logger.error(f"Mutfak personeli kaydetme hatası: {e}")
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

    def wrap_ticket_text(self, value, width=32):
        text = str(value or "").strip()
        if not text:
            return []
        lines = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if len(candidate) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            while len(word) > width:
                lines.append(word[:width])
                word = word[width:]
            current = word
        if current:
            lines.append(current)
        return lines

    def build_prep_ticket_text(self, panel_id, order_data):
        panel = self.get_prep_panel_info(panel_id)
        width = 32
        now = datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        lines = [
            self.company_name[:width].center(width),
            str(panel.get("ticket_title") or "SIPARIS FISI")[:width].center(width),
            "=" * width,
            now,
            f"Reyon: {panel.get('name', panel_id)}",
            f"Masa : {order_data.get('masa', '-')}",
            f"Saat : {order_data.get('saat', '-')}",
            f"Garson: {order_data.get('garson') or '-'}",
            "-" * width,
        ]
        item_text = f"{order_data.get('adet', 1)} x {order_data.get('urun', '')}"
        lines.extend(self.wrap_ticket_text(item_text, width))
        note = str(order_data.get("not") or "").strip()
        if note:
            lines.append("-" * width)
            lines.append("Not:")
            lines.extend(self.wrap_ticket_text(note, width))
        lines.extend(["=" * width, "", "", ""])
        return "\n".join(lines)

    def encode_thermal_ticket(self, text):
        # ESC/POS: init, Turkish code page on many devices, body, paper cut.
        return b"\x1b@\x1bt\r" + text.encode("cp857", errors="replace") + b"\n\n\n\x1dV\x00"

    def send_prep_ticket_to_printer(self, panel_id, order_data):
        printer = self.prep_printers.get(panel_id, {})
        if not printer.get("enabled"):
            return

        ip = str(printer.get("ip") or "").strip()
        if not ip:
            logger.warning(f"Reyon yazıcısı IP eksik: {panel_id}")
            return

        port = self.bounded_int(printer.get("port"), 9100, 1, 65535)
        copies = self.bounded_int(printer.get("copies"), 1, 1, 5)
        payload = self.encode_thermal_ticket(self.build_prep_ticket_text(panel_id, order_data))

        def task():
            for copy_index in range(copies):
                try:
                    with socket.create_connection((ip, port), timeout=5) as client:
                        client.sendall(payload)
                    logger.info(f"🖨️ {panel_id} fişi yazıcıya gönderildi: {ip}:{port} ({copy_index + 1}/{copies})")
                except Exception as e:
                    logger.error(f"Reyon yazıcı hatası ({panel_id} {ip}:{port}): {e}")

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

    def refresh_adisyonlar(self, preserve_existing=False):
        """Masa/paket yapısını yeniden oluştur."""
        previous_adisyonlar = self.adisyonlar if preserve_existing else {}
        next_adisyonlar = {}

        def add_adisyon_name(name):
            clean_name = str(name or "").strip()
            if not clean_name or clean_name in next_adisyonlar:
                return
            next_adisyonlar[clean_name] = previous_adisyonlar.get(clean_name, [])

        # Salon masaları
        if self.salons:
            for salon in self.salons:
                for table in salon.get('tables', []):
                    add_adisyon_name(table)
        elif self.masa_sayisi > 0:
            for i in range(1, self.masa_sayisi + 1):
                add_adisyon_name(f"Masa {i}")
                
        # Paketler
        if self.paket_sayisi > 0:
            for i in range(1, self.paket_sayisi + 1):
                add_adisyon_name(f"Paket {i}")
        
        if not next_adisyonlar:
            add_adisyon_name("Genel")

        if preserve_existing:
            for masa, items in previous_adisyonlar.items():
                if masa not in next_adisyonlar and items:
                    next_adisyonlar[masa] = items

        self.adisyonlar = next_adisyonlar
        
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
                if os.path.exists(MENU_FILE) and os.path.getsize(MENU_FILE) > 0:
                    db.load_menu_from_file(MENU_FILE)
                    self.menu_data = db.get_menu_by_category()
                    if self.menu_data:
                        logger.info(f"✓ Menü menu.txt'den DB'ye senkronlandı: {len(self.menu_data)} kategori")
                        return

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
                        image_url = parts[7].strip() if len(parts) > 7 else ""
                        visible_raw = parts[8].strip().lower() if len(parts) > 8 else "1"
                        menu_visible = visible_raw not in ("0", "false", "hayir", "hayır", "no", "off")
                        
                        if cat not in self.menu_data:
                            self.menu_data[cat] = []
                        self.menu_data[cat].append([item, float(price), oran_ys, oran_ty, oran_gt, oran_mg, image_url, menu_visible])
            logger.info(f"✓ Menü dosyadan yüklendi: {len(self.menu_data)} kategori")
        except Exception as e:
            logger.error(f"Menü yükleme hatası: {e}")

    def _legacy_daily_meal_categories(self):
        return [group["name"] for group in DAILY_MEAL_GROUPS]

    def _canonical_menu_category(self, category):
        target = self._normalize_text_for_match(category)
        if not target:
            return ''
        for existing in self.menu_data.keys():
            if self._normalize_text_for_match(existing) == target:
                return existing
        return str(category or '').strip()

    def sanitize_daily_meal_categories(self, categories):
        if isinstance(categories, str):
            categories = [categories]
        if not isinstance(categories, list):
            return []

        clean = []
        seen = set()
        for raw_category in categories:
            category = str(raw_category or '').strip()[:80]
            if not category:
                continue
            canonical = self._canonical_menu_category(category)
            key = self._normalize_text_for_match(canonical)
            if not key or key in seen:
                continue
            clean.append(canonical)
            seen.add(key)
        return clean

    def get_default_daily_meal_categories(self):
        defaults = []
        menu_categories = {
            self._normalize_text_for_match(category): category
            for category in self.menu_data.keys()
        }
        for category in self._legacy_daily_meal_categories():
            canonical = menu_categories.get(self._normalize_text_for_match(category))
            if canonical:
                defaults.append(canonical)
        return defaults

    def load_menu_metadata(self):
        """Menüye ait kategori metadatasını yükle."""
        self.daily_meal_categories = self.get_default_daily_meal_categories()
        if not os.path.exists(MENU_META_FILE):
            return

        try:
            with open(MENU_META_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            categories = raw.get("daily_meal_categories", []) if isinstance(raw, dict) else raw
            self.daily_meal_categories = self.sanitize_daily_meal_categories(categories)
        except Exception as e:
            logger.error(f"Menü metadatası yüklenemedi: {e}")

    def save_menu_metadata(self, daily_meal_categories=None):
        """Menü kategori metadatasını kaydet."""
        if daily_meal_categories is not None:
            self.daily_meal_categories = self.sanitize_daily_meal_categories(daily_meal_categories)
        try:
            with open(MENU_META_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "daily_meal_categories": self.daily_meal_categories
                }, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Menü metadatası kaydedilemedi: {e}")
            return False

    def get_menu_metadata_payload(self):
        return {
            "daily_meal_categories": self._daily_meal_categories()
        }

    def is_menu_item_visible(self, item):
        """Public/web menüde gösterilecek ürünleri belirle"""
        if not isinstance(item, (list, tuple)) or len(item) <= 7:
            return True
        value = item[7]
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in ("0", "false", "hayir", "hayır", "no", "off")

    def get_public_menu_data(self):
        """Menüde göster işaretli ürünlerden public menü oluştur"""
        order_menu = self.get_order_menu_data()
        visible_menu = {}
        for category, items in order_menu.items():
            visible_items = [item for item in items if self.is_menu_item_visible(item)]
            if visible_items:
                visible_menu[category] = visible_items
        return visible_menu

    def _normalize_text_for_match(self, value):
        text = unicodedata.normalize('NFKD', str(value or '').casefold())
        text = ''.join(ch for ch in text if not unicodedata.combining(ch))
        return text.replace('ı', 'i')

    def _normalize_product_key(self, urun):
        return str(urun or '').strip().casefold()

    def _coerce_portion_amount(self, value, default=0):
        try:
            return max(0.0, round(float(value), 2))
        except Exception:
            return float(default)

    def _portion_amount_for_json(self, value):
        amount = self._coerce_portion_amount(value)
        if abs(amount - round(amount)) < 0.001:
            return int(round(amount))
        return amount

    def _format_portion_amount(self, value):
        amount = self._portion_amount_for_json(value)
        return str(amount).replace('.', ',')

    def _strip_portion_variant_prefix(self, urun):
        name = str(urun or '').strip()
        match = re.match(r'^(tam|yarım|yarim)\s+porsiyon\s+(.+)$', name, flags=re.IGNORECASE)
        return match.group(2).strip() if match else name

    def _find_menu_product_entry(self, urun):
        target = self._normalize_product_key(urun)
        for category, items in self.menu_data.items():
            for item in items:
                name = str(item[0] or '').strip()
                if self._normalize_product_key(name) == target:
                    return category, name, item
        return '', '', None

    def _find_menu_product_name(self, urun):
        _, name, _ = self._find_menu_product_entry(urun)
        if name:
            return name
        return str(urun or '').strip()

    def _get_daily_meal_group_for_text(self, text):
        normalized = self._normalize_text_for_match(text)
        for category in self._daily_meal_categories():
            category_key = self._normalize_text_for_match(category)
            if category_key and category_key in normalized:
                return category

        for group in DAILY_MEAL_GROUPS:
            canonical = self.get_canonical_daily_meal_category(group["name"])
            if canonical and any(keyword in normalized for keyword in group["keywords"]):
                return canonical
        return ''

    def get_canonical_daily_meal_category(self, category):
        target = self._normalize_text_for_match(category)
        if not target:
            return ''
        for daily_category in self._daily_meal_categories():
            if self._normalize_text_for_match(daily_category) == target:
                return daily_category
        return ''

    def is_daily_meal_category(self, category):
        return bool(self.get_canonical_daily_meal_category(category))

    def get_daily_meal_group_for_product(self, urun, kategori=None):
        product_name = str(urun or '').strip()
        if kategori:
            daily_category = self.get_canonical_daily_meal_category(kategori)
            if daily_category:
                return daily_category

        if kategori is None:
            matched_category, matched_name, _ = self._find_menu_product_entry(urun)
            if matched_category:
                kategori = matched_category
                daily_category = self.get_canonical_daily_meal_category(kategori)
                if daily_category:
                    return daily_category
            if matched_name:
                product_name = matched_name
        return self._get_daily_meal_group_for_text(f"{kategori or ''} {product_name}")

    def _menu_item_copy_with_name(self, item, name):
        defaults = ["", 0.0, 0, 0, 0, 0, "", True]
        next_item = defaults[:]
        if isinstance(item, (list, tuple)):
            for idx, value in enumerate(list(item)[:8]):
                next_item[idx] = value
        next_item[0] = name
        return next_item

    def _build_daily_meal_portion_item(self, group_name, portion_prefix, source_items):
        group_key = self._normalize_text_for_match(group_name)
        candidates = []
        for item in source_items:
            if not item:
                continue
            item_name = str(item[0] or '').strip()
            normalized = self._normalize_text_for_match(item_name)
            if normalized.startswith(portion_prefix):
                candidates.append(item)
        if not candidates:
            return None

        exact = None
        for item in candidates:
            base_name = self._strip_portion_variant_prefix(item[0])
            if self._normalize_text_for_match(base_name) == group_key:
                exact = item
                break

        source_item = exact or candidates[0]
        display_prefix = "Tam Porsiyon" if portion_prefix == "tam porsiyon" else "Yarım Porsiyon"
        return self._menu_item_copy_with_name(source_item, f"{display_prefix} {group_name}")

    def _append_daily_meal_group_to_menu(self, target, group_name, source_items):
        if not source_items:
            return False

        collapsed_items = []
        full_item = self._build_daily_meal_portion_item(group_name, "tam porsiyon", source_items)
        half_item = self._build_daily_meal_portion_item(group_name, "yarim porsiyon", source_items)
        if full_item:
            collapsed_items.append(full_item)
        if half_item:
            collapsed_items.append(half_item)
        if not collapsed_items:
            return False

        target.setdefault(group_name, []).extend(collapsed_items)
        return True

    def _append_daily_meal_groups_to_menu(self, target, grouped_items, categories=None):
        inserted = set()
        group_names = self._daily_meal_categories() if categories is None else categories
        for group_name in group_names:
            source_items = grouped_items.get(group_name) or []
            if self._append_daily_meal_group_to_menu(target, group_name, source_items):
                inserted.add(group_name)
        return inserted

    def get_order_menu_data(self):
        """Sipariş ekranları için günlük yemek çeşitlerini ana sınıf + porsiyona indirger."""
        grouped_items = defaultdict(list)
        category_entries = []

        for category, items in self.menu_data.items():
            remaining_items = []
            for item in items:
                if not item:
                    continue
                group_name = self.get_daily_meal_group_for_product(item[0], category)
                if group_name:
                    grouped_items[group_name].append(item)
                else:
                    remaining_items.append(item)
            category_entries.append((category, remaining_items))

        order_menu = {}
        inserted_groups = set()
        for category, remaining_items in category_entries:
            if remaining_items:
                order_menu[category] = remaining_items
            daily_category = self.get_canonical_daily_meal_category(category)
            if daily_category:
                inserted_groups.update(
                    self._append_daily_meal_groups_to_menu(order_menu, grouped_items, [daily_category])
                )

        remaining_groups = [
            category for category in self._daily_meal_categories()
            if category not in inserted_groups
        ]
        self._append_daily_meal_groups_to_menu(order_menu, grouped_items, remaining_groups)

        return order_menu

    def _daily_meals_history_file(self, date_key):
        safe_date = re.sub(r'[^0-9-]', '', str(date_key or ''))
        return os.path.join(DAILY_MEALS_HISTORY_DIR, f"{safe_date}.txt")

    def _extract_daily_meals_date(self, text):
        for line in str(text or '').splitlines()[:6]:
            match = re.match(r'^\s*#\s*Tarih\s*:\s*(\d{4}-\d{2}-\d{2})\s*$', line)
            if match:
                return match.group(1)
        return None

    def _daily_meal_categories(self):
        return list(self.daily_meal_categories or [])

    def _empty_daily_meals_text(self, date_key=None):
        date_key = date_key or self.get_portion_stock_today_key()
        return (
            f"# Tarih: {date_key}\n"
            "# Format: Kategori;Yemek;Porsiyon\n"
            "# Örnek: Dana Etli Yemekler;Macar;12\n"
        )

    def parse_daily_meals_text(self, text):
        """Günlük üretim metnini kategori/yemek/porsiyon satırlarına çevir."""
        valid_categories = set(self._daily_meal_categories())
        items = []
        errors = []
        for line_no, raw_line in enumerate(str(text or '').splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [part.strip() for part in line.split(';')]
            if len(parts) != 3:
                errors.append(f"{line_no}. satır formatı Kategori;Yemek;Porsiyon olmalı")
                continue
            category, meal_name, amount_raw = parts
            if category not in valid_categories:
                errors.append(f"{line_no}. satır kategori geçersiz: {category}")
                continue
            if not meal_name:
                errors.append(f"{line_no}. satır yemek adı boş olamaz")
                continue
            try:
                amount = self._coerce_portion_amount(str(amount_raw).replace(',', '.'))
            except Exception:
                errors.append(f"{line_no}. satır porsiyon sayısı geçersiz: {amount_raw}")
                continue
            items.append({
                'kategori': category,
                'yemek': meal_name,
                'porsiyon': amount
            })
        return items, errors

    def format_daily_meals_text(self, items, date_key=None):
        date_key = date_key or self.get_portion_stock_today_key()
        grouped = defaultdict(list)
        for item in items or []:
            category = str(item.get('kategori') or '').strip()
            meal_name = str(item.get('yemek') or '').strip()
            if not category or not meal_name:
                continue
            amount = self._portion_amount_for_json(item.get('porsiyon', item.get('kalan', 0)))
            grouped[category].append((meal_name, amount))

        lines = [
            f"# Tarih: {date_key}",
            "# Format: Kategori;Yemek;Porsiyon"
        ]
        for category in self._daily_meal_categories():
            for meal_name, amount in grouped.get(category, []):
                lines.append(f"{category};{meal_name};{str(amount).replace('.', ',')}")
        return "\n".join(lines) + "\n"

    def _read_daily_meals_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _write_daily_meals_file(self, path, text):
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _latest_daily_meals_history_text(self):
        try:
            paths = sorted(
                path for path in os.listdir(DAILY_MEALS_HISTORY_DIR)
                if re.match(r'^\d{4}-\d{2}-\d{2}\.txt$', path)
            )
            for filename in reversed(paths):
                path = os.path.join(DAILY_MEALS_HISTORY_DIR, filename)
                text = self._read_daily_meals_file(path)
                if text.strip():
                    return text
        except Exception as e:
            logger.error(f"Günlük yemek geçmişi okunamadı: {e}")
        return None

    def ensure_daily_meals_file_for_today(self):
        today_key = self.get_portion_stock_today_key()
        text = ''
        if os.path.exists(DAILY_MEALS_FILE):
            text = self._read_daily_meals_file(DAILY_MEALS_FILE)
            file_date = self._extract_daily_meals_date(text)
            if file_date == today_key:
                return text
            if file_date:
                history_path = self._daily_meals_history_file(file_date)
                if not os.path.exists(history_path):
                    self._write_daily_meals_file(history_path, text)

        source_text = text.strip() and text or self._latest_daily_meals_history_text()
        items, _ = self.parse_daily_meals_text(source_text or '')
        next_text = self.format_daily_meals_text(items, today_key) if items else self._empty_daily_meals_text(today_key)
        self._write_daily_meals_file(DAILY_MEALS_FILE, next_text)
        self._write_daily_meals_file(self._daily_meals_history_file(today_key), next_text)
        return next_text

    def load_daily_meals(self):
        try:
            text = self.ensure_daily_meals_file_for_today()
            items, errors = self.parse_daily_meals_text(text)
            if errors:
                logger.warning(f"Günlük yemek dosyası uyarıları: {errors}")
            self.daily_meals = items
            self.daily_meals_date = self._extract_daily_meals_date(text) or self.get_portion_stock_today_key()
            self.daily_meals_mtime = os.path.getmtime(DAILY_MEALS_FILE) if os.path.exists(DAILY_MEALS_FILE) else None
            logger.info(f"✓ {len(self.daily_meals)} günlük yemek çeşidi yüklendi")
        except Exception as e:
            logger.error(f"Günlük yemek listesi yüklenemedi: {e}")
            self.daily_meals = []
            self.daily_meals_date = self.get_portion_stock_today_key()

    def save_daily_meals_text(self, text):
        date_key = self.get_portion_stock_today_key()
        items, errors = self.parse_daily_meals_text(text)
        if errors:
            return False, errors
        formatted = self.format_daily_meals_text(items, date_key)
        self._write_daily_meals_file(DAILY_MEALS_FILE, formatted)
        self._write_daily_meals_file(self._daily_meals_history_file(date_key), formatted)
        self.daily_meals = items
        self.daily_meals_date = date_key
        self.daily_meals_mtime = os.path.getmtime(DAILY_MEALS_FILE) if os.path.exists(DAILY_MEALS_FILE) else None
        self.apply_daily_meal_stock(reset_values=True)
        return True, []

    def get_daily_meals_payload(self):
        text = self.ensure_daily_meals_file_for_today()
        current_mtime = os.path.getmtime(DAILY_MEALS_FILE) if os.path.exists(DAILY_MEALS_FILE) else None
        if current_mtime and current_mtime != self.daily_meals_mtime:
            items, errors = self.parse_daily_meals_text(text)
            if not errors:
                self.daily_meals = items
                self.daily_meals_date = self._extract_daily_meals_date(text) or self.get_portion_stock_today_key()
                self.daily_meals_mtime = current_mtime
                self.apply_daily_meal_stock(reset_values=True)
        return {
            'date': self.daily_meals_date or self.get_portion_stock_today_key(),
            'text': text,
            'items': [
                {
                    'kategori': item['kategori'],
                    'yemek': item['yemek'],
                    'porsiyon': self._portion_amount_for_json(item.get('porsiyon', 0)),
                    'kalan': self._portion_amount_for_json(
                        self.portion_stock.get(self._normalize_product_key(item['yemek']), {}).get('kalan', item.get('porsiyon', 0))
                    )
                }
                for item in self.daily_meals
            ],
            'categories': self._daily_meal_categories(),
            'file': os.path.basename(DAILY_MEALS_FILE)
        }

    def get_daily_meals_for_category(self, category):
        return [
            item for item in self.daily_meals
            if self._normalize_text_for_match(item.get('kategori')) == self._normalize_text_for_match(category)
        ]

    def get_daily_meal_group_total(self, category):
        return round(sum(
            self._coerce_portion_amount(item.get('porsiyon', 0))
            for item in self.get_daily_meals_for_category(category)
        ), 2)

    def sync_daily_meal_group_stock_locked(self, now_iso=None):
        """Günlük çeşitlerin kalan toplamını ana grup stoğuna yansıt."""
        now_iso = now_iso or datetime.datetime.now().isoformat()
        changed = []
        for category in self._daily_meal_categories():
            total = 0.0
            has_items = False
            for item in self.get_daily_meals_for_category(category):
                meal_name = item.get('yemek')
                if not meal_name:
                    continue
                has_items = True
                meal_key = self._normalize_product_key(meal_name)
                entry = self.portion_stock.get(meal_key)
                if entry:
                    total += self._coerce_portion_amount(entry.get('kalan', 0))
                else:
                    total += self._coerce_portion_amount(item.get('porsiyon', 0))

            if not has_items:
                continue

            group_key = self._normalize_product_key(category)
            current = self.portion_stock.get(group_key)
            current_amount = self._coerce_portion_amount(current.get('kalan', 0)) if current else None
            total = round(total, 2)
            if current is None or abs(current_amount - total) > 0.001:
                self.portion_stock[group_key] = {
                    'urun': category,
                    'kategori': category,
                    'kalan': total,
                    'updated_at': now_iso,
                    'is_default': False
                }
                changed.append({
                    'urun': category,
                    'kategori': category,
                    'kalan': self._portion_amount_for_json(total),
                    'tracked': True
                })
        return changed

    def apply_daily_meal_stock(self, reset_values=False):
        """Günlük üretim listesindeki çeşitleri porsiyon stoğuna yansıt."""
        now_iso = datetime.datetime.now().isoformat()
        changed = []
        with self.portion_lock:
            if reset_values:
                daily_categories = set(self._daily_meal_categories())
                for stock_key, entry in list(self.portion_stock.items()):
                    if entry.get('kategori') in daily_categories or entry.get('urun') in daily_categories:
                        del self.portion_stock[stock_key]

            for category in self._daily_meal_categories():
                total = self.get_daily_meal_group_total(category)
                group_key = self._normalize_product_key(category)
                if total > 0 and (reset_values or group_key not in self.portion_stock):
                    self.portion_stock[group_key] = {
                        'urun': category,
                        'kalan': total,
                        'updated_at': now_iso,
                        'is_default': False
                    }
                    changed.append({
                        'urun': category,
                        'kalan': self._portion_amount_for_json(total),
                        'tracked': True
                    })

            for item in self.daily_meals:
                meal_name = item.get('yemek')
                if not meal_name:
                    continue
                amount = self._coerce_portion_amount(item.get('porsiyon', 0))
                meal_key = self._normalize_product_key(meal_name)
                if reset_values or meal_key not in self.portion_stock:
                    self.portion_stock[meal_key] = {
                        'urun': meal_name,
                        'kategori': item.get('kategori'),
                        'kalan': amount,
                        'updated_at': now_iso,
                        'is_default': False
                    }
                    changed.append({
                        'urun': meal_name,
                        'kategori': item.get('kategori'),
                        'kalan': self._portion_amount_for_json(amount),
                        'tracked': True
                    })

            if changed:
                self.save_portion_stock()
        if changed:
            self.emit_portion_stock_update(changed)
        return changed

    def get_daily_meal_name_from_note(self, urun, not_bilgisi=''):
        category = self.get_daily_meal_group_for_product(urun)
        if not category:
            return ''
        note = str(not_bilgisi or '').strip()
        note = re.sub(r'^(yemek|çeşit|cesit)\s*:\s*', '', note, flags=re.IGNORECASE).strip()
        if not note:
            meals = self.get_daily_meals_for_category(category)
            return meals[0]['yemek'] if len(meals) == 1 else ''
        note_key = self._normalize_product_key(note)
        for item in self.get_daily_meals_for_category(category):
            if self._normalize_product_key(item.get('yemek')) == note_key:
                return item['yemek']
        return ''

    def get_order_portion_stock_name(self, urun, not_bilgisi=''):
        meal_name = self.get_daily_meal_name_from_note(urun, not_bilgisi)
        if meal_name:
            return meal_name
        return self.get_portion_stock_name(urun)

    def get_portion_stock_name(self, urun):
        """Tam/Yarım porsiyon varyantlarını aynı stok satırında toplar."""
        category, product_name, _ = self._find_menu_product_entry(urun)
        if not product_name:
            product_name = str(urun or '').strip()
        daily_group = self.get_daily_meal_group_for_product(product_name, category)
        if daily_group:
            return daily_group
        return self._strip_portion_variant_prefix(product_name)

    def get_portion_stock_key(self, urun, not_bilgisi=''):
        return self._normalize_product_key(self.get_order_portion_stock_name(urun, not_bilgisi))

    def get_portion_units_for_order(self, urun, adet=1):
        try:
            adet = max(1, int(adet))
        except Exception:
            adet = 1

        product_name = self._find_menu_product_name(urun)
        normalized = self._normalize_text_for_match(product_name)
        multiplier = 0.5 if normalized.startswith('yarim porsiyon ') else 1.0
        return round(adet * multiplier, 2)

    def get_menu_category_for_product(self, urun):
        target = self._normalize_product_key(urun)
        for category, items in self.menu_data.items():
            for item in items:
                name = str(item[0] or '').strip()
                if self._normalize_product_key(name) == target:
                    return category
        daily_group = self.get_daily_meal_group_for_product(urun)
        if daily_group:
            return daily_group
        return ''

    def get_preparation_panel_for_category(self, category):
        category_name = str(category or '').strip()
        if category_name in self.prep_category_overrides:
            return self.prep_category_overrides[category_name]

        normalized = self._normalize_text_for_match(category)
        for panel_id, panel in self.prep_panel_settings.items():
            keywords = panel.get('category_keywords', [])
            if any(keyword in normalized for keyword in keywords):
                return panel_id
        return "mutfak"

    def get_preparation_panel_for_product(self, urun, kategori=None):
        category = kategori if kategori is not None else self.get_menu_category_for_product(urun)
        product_text = self._normalize_text_for_match(urun)

        product_panel_id = None
        for fallback_panel_id, panel in self.prep_panel_settings.items():
            excluded = PREP_PANEL_PRODUCT_EXCLUSIONS.get(fallback_panel_id, ())
            if excluded and any(keyword in product_text for keyword in excluded):
                continue
            keywords = panel.get('product_keywords', [])
            if any(keyword in product_text for keyword in keywords):
                product_panel_id = fallback_panel_id
                break

        if product_panel_id == "izgara":
            return product_panel_id

        panel_id = self.get_preparation_panel_for_category(category)
        if category and panel_id != "mutfak":
            return panel_id

        if product_panel_id:
            return product_panel_id
        if " su " in f" {product_text} ":
            return "icecek"
        return panel_id

    def get_preparation_panels(self):
        category_map = defaultdict(list)
        for category in self.menu_data.keys():
            panel_id = self.get_preparation_panel_for_category(category)
            category_map[panel_id].append(category)

        panels = []
        for panel_id, panel in self.prep_panel_settings.items():
            panel_data = dict(panel)
            panel_data['categories'] = category_map.get(panel_id, [])
            panels.append(panel_data)
        return panels

    def get_portion_stock_today_key(self):
        return datetime.date.today().isoformat()

    def load_portion_stock_reset_date(self):
        if not os.path.exists(PORTION_STOCK_RESET_FILE):
            return None
        try:
            with open(PORTION_STOCK_RESET_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return (data.get('date') or '').strip() or None
            if isinstance(data, str):
                return data.strip() or None
        except Exception as e:
            logger.error(f"Porsiyon stok reset tarihi okunamadı: {e}")
        return None

    def save_portion_stock_reset_date(self, date_key):
        try:
            with open(PORTION_STOCK_RESET_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    'date': date_key,
                    'default_portion_stock': DEFAULT_PORTION_STOCK,
                    'updated_at': datetime.datetime.now().isoformat()
                }, f, ensure_ascii=False, indent=2)
            self.portion_stock_reset_date = date_key
            return True
        except Exception as e:
            logger.error(f"Porsiyon stok reset tarihi kaydedilemedi: {e}")
            return False

    def reset_portion_stock_to_default(self, date_key=None, persist=True):
        date_key = date_key or self.get_portion_stock_today_key()
        now_iso = datetime.datetime.now().isoformat()
        with self.portion_lock:
            self.portion_stock = {}
            for items in self.menu_data.values():
                for item in items:
                    if not item:
                        continue
                    stock_name = self.get_portion_stock_name(item[0])
                    stock_key = self._normalize_product_key(stock_name)
                    if not stock_key or stock_key in self.portion_stock:
                        continue
                    default_amount = self.get_daily_meal_group_total(stock_name) or DEFAULT_PORTION_STOCK
                    self.portion_stock[stock_key] = {
                        'urun': stock_name,
                        'kalan': float(default_amount),
                        'updated_at': now_iso,
                        'is_default': True,
                        'reset_date': date_key
                    }
            for item in self.daily_meals:
                meal_name = item.get('yemek')
                if not meal_name:
                    continue
                meal_key = self._normalize_product_key(meal_name)
                if not meal_key:
                    continue
                self.portion_stock[meal_key] = {
                    'urun': meal_name,
                    'kategori': item.get('kategori'),
                    'kalan': self._coerce_portion_amount(item.get('porsiyon', 0)),
                    'updated_at': now_iso,
                    'is_default': False,
                    'reset_date': date_key
                }
            self.portion_stock_reset_date = date_key
            if persist:
                self.save_portion_stock()
                self.save_portion_stock_reset_date(date_key)
        logger.info(f"✓ Porsiyon stokları {date_key} için {DEFAULT_PORTION_STOCK} varsayılana yenilendi")

    def reset_daily_portion_stock_if_needed(self):
        today_key = self.get_portion_stock_today_key()
        if self.portion_stock_reset_date is None:
            self.portion_stock_reset_date = self.load_portion_stock_reset_date()
        if self.portion_stock_reset_date == today_key:
            return False
        self.reset_portion_stock_to_default(today_key)
        return True

    def start_portion_stock_reset_scheduler(self):
        if self.portion_reset_thread and self.portion_reset_thread.is_alive():
            return

        def task():
            while True:
                try:
                    if self.reset_daily_portion_stock_if_needed():
                        self.emit_portion_stock_update()
                except Exception as e:
                    logger.error(f"Günlük porsiyon stok yenileme hatası: {e}")
                time.sleep(300)

        self.portion_reset_thread = threading.Thread(target=task, daemon=True)
        self.portion_reset_thread.start()

    def ensure_default_portion_stock(self):
        """Menüdeki her ortak porsiyon satırına varsayılan stok aç."""
        now_iso = datetime.datetime.now().isoformat()
        with self.portion_lock:
            for items in self.menu_data.values():
                for item in items:
                    if not item:
                        continue
                    stock_name = self.get_portion_stock_name(item[0])
                    stock_key = self._normalize_product_key(stock_name)
                    if stock_key and stock_key not in self.portion_stock:
                        default_amount = self.get_daily_meal_group_total(stock_name) or DEFAULT_PORTION_STOCK
                        self.portion_stock[stock_key] = {
                            'urun': stock_name,
                            'kalan': float(default_amount),
                            'updated_at': now_iso,
                            'is_default': True
                        }
            for item in self.daily_meals:
                meal_name = item.get('yemek')
                meal_key = self._normalize_product_key(meal_name)
                if meal_key and meal_key not in self.portion_stock:
                    self.portion_stock[meal_key] = {
                        'urun': meal_name,
                        'kategori': item.get('kategori'),
                        'kalan': self._coerce_portion_amount(item.get('porsiyon', 0)),
                        'updated_at': now_iso,
                        'is_default': False
                    }

    def load_portion_stock(self):
        """Mutfak tarafından girilen tahmini kalan porsiyonları yükle."""
        with self.portion_lock:
            self.portion_stock = {}
            self.portion_stock_reset_date = self.load_portion_stock_reset_date()
            today_key = self.get_portion_stock_today_key()
            if self.portion_stock_reset_date != today_key:
                self.reset_portion_stock_to_default(today_key)
                return

            if not os.path.exists(PORTION_STOCK_FILE):
                self.reset_portion_stock_to_default(today_key)
                return
            try:
                with open(PORTION_STOCK_FILE, "r", encoding="utf-8") as f:
                    raw_stock = json.load(f)
                if not isinstance(raw_stock, dict):
                    self.reset_portion_stock_to_default(today_key)
                    return

                for key, value in raw_stock.items():
                    if isinstance(value, dict):
                        urun = value.get('urun') or value.get('name') or key
                        kategori = value.get('kategori')
                        kalan = value.get('kalan')
                        updated_at = value.get('updated_at')
                    else:
                        urun = key
                        kategori = None
                        kalan = value
                        updated_at = None

                    try:
                        kalan = self._coerce_portion_amount(kalan)
                    except Exception:
                        continue

                    canonical_name = self.get_portion_stock_name(urun)
                    stock_key = self._normalize_product_key(canonical_name)
                    if stock_key:
                        self.portion_stock[stock_key] = {
                            'urun': canonical_name,
                            'kategori': kategori,
                            'kalan': kalan,
                            'updated_at': updated_at or datetime.datetime.now().isoformat()
                        }
                self.ensure_default_portion_stock()
                self.save_portion_stock_reset_date(today_key)
                logger.info(f"✓ {len(self.portion_stock)} ürün için porsiyon stoku yüklendi")
            except Exception as e:
                logger.error(f"Porsiyon stok yükleme hatası: {e}")
                self.reset_portion_stock_to_default(today_key)

    def save_portion_stock(self):
        """Porsiyon stoklarını dosyaya kaydet."""
        with self.portion_lock:
            try:
                payload = {}
                for entry in sorted(self.portion_stock.values(), key=lambda x: x.get('urun', '')):
                    urun = entry.get('urun')
                    if not urun:
                        continue
                    payload[urun] = {
                        'urun': urun,
                        'kategori': entry.get('kategori'),
                        'kalan': self._portion_amount_for_json(entry.get('kalan', 0)),
                        'updated_at': entry.get('updated_at') or datetime.datetime.now().isoformat()
                    }
                with open(PORTION_STOCK_FILE, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                return True
            except Exception as e:
                logger.error(f"Porsiyon stok kaydetme hatası: {e}")
                return False

    def get_portion_stock_snapshot(self):
        self.reset_daily_portion_stock_if_needed()
        self.ensure_default_portion_stock()
        with self.portion_lock:
            snapshot = {}
            for entry in self.portion_stock.values():
                urun = entry.get('urun')
                if not urun:
                    continue
                kalan = self._coerce_portion_amount(entry.get('kalan', 0))
                snapshot[urun] = {
                    'urun': urun,
                    'kategori': entry.get('kategori'),
                    'kalan': self._portion_amount_for_json(kalan),
                    'tracked': True,
                    'status': 'tukendi' if kalan <= 0 else ('az' if kalan <= 5 else 'var'),
                    'updated_at': entry.get('updated_at')
                }
            return snapshot

    def get_portion_stock_by_category(self):
        snapshot = self.get_portion_stock_snapshot()
        categorized = {}
        for cat, items in self.menu_data.items():
            categorized[cat] = []
            for item in items:
                urun = str(item[0] or '').strip()
                stock_name = self.get_portion_stock_name(urun)
                stock = snapshot.get(stock_name)
                categorized[cat].append({
                    'urun': urun,
                    'stok_urun': stock_name,
                    'kalan': stock.get('kalan') if stock else None,
                    'tracked': bool(stock)
                })
        return categorized

    def set_portion_stock_items(self, updates):
        self.reset_daily_portion_stock_if_needed()
        errors = []
        changed = []
        pending_changes = []
        for update in updates:
            urun = str(update.get('urun') or update.get('name') or '').strip()
            if not urun:
                errors.append('Ürün adı gerekli')
                continue

            raw_kalan = update.get('kalan')
            canonical_name = self.get_portion_stock_name(urun)
            kategori = str(update.get('kategori') or update.get('category') or '').strip()
            stock_key = self._normalize_product_key(canonical_name)
            if raw_kalan is None or raw_kalan == '':
                raw_kalan = DEFAULT_PORTION_STOCK

            try:
                kalan = max(0.0, round(float(raw_kalan), 2))
            except Exception:
                errors.append(f"{canonical_name} için porsiyon sayısı geçersiz")
                continue
            if kalan < 0:
                errors.append(f"{canonical_name} için porsiyon sayısı negatif olamaz")
                continue

            pending_changes.append({
                'action': 'set',
                'stock_key': stock_key,
                'urun': canonical_name,
                'kategori': kategori,
                'kalan': kalan
            })

        if errors:
            return False, errors, []

        with self.portion_lock:
            now_iso = datetime.datetime.now().isoformat()
            for change in pending_changes:
                existing = self.portion_stock.get(change['stock_key'], {})
                kategori = change.get('kategori') or existing.get('kategori')
                self.portion_stock[change['stock_key']] = {
                    'urun': change['urun'],
                    'kategori': kategori,
                    'kalan': change['kalan'],
                    'is_default': False,
                    'updated_at': now_iso
                }
                changed.append({
                    'urun': change['urun'],
                    'kategori': kategori,
                    'kalan': self._portion_amount_for_json(change['kalan']),
                    'tracked': True
                })

            changed.extend(self.sync_daily_meal_group_stock_locked(now_iso))
            self.save_portion_stock()

        self.emit_portion_stock_update(changed)
        return True, [], changed

    def validate_portion_stock_for_order(self, items):
        self.reset_daily_portion_stock_if_needed()
        self.ensure_default_portion_stock()
        required = defaultdict(float)
        names = {}
        for item in items:
            urun = str(item.get('urun') or item.get('name') or '').strip()
            if not urun:
                continue
            not_bilgisi = item.get('not') or item.get('not_bilgisi') or ''
            units = self.get_portion_units_for_order(urun, item.get('adet', 1))
            key = self.get_portion_stock_key(urun, not_bilgisi)
            required[key] += units
            names[key] = self.get_order_portion_stock_name(urun, not_bilgisi)
            group_name = self.get_daily_meal_group_for_product(urun)
            if group_name and self._normalize_product_key(group_name) != key:
                group_key = self._normalize_product_key(group_name)
                required[group_key] += units
                names[group_key] = group_name

        with self.portion_lock:
            for key, required_units in required.items():
                entry = self.portion_stock.get(key)
                if not entry:
                    continue
                kalan = self._coerce_portion_amount(entry.get('kalan', 0))
                urun = entry.get('urun') or names.get(key, 'Ürün')
                if kalan <= 0:
                    return False, f"{urun} tükendi"
                if kalan + 0.001 < required_units:
                    return False, f"{urun} için sadece {self._format_portion_amount(kalan)} porsiyon kaldı"
        return True, None

    def consume_portion_stock(self, urun, adet=1, not_bilgisi=''):
        self.reset_daily_portion_stock_if_needed()
        self.ensure_default_portion_stock()
        units = self.get_portion_units_for_order(urun, adet)
        stock_name = self.get_order_portion_stock_name(urun, not_bilgisi)
        key = self._normalize_product_key(stock_name)
        group_name = self.get_daily_meal_group_for_product(urun)
        group_key = self._normalize_product_key(group_name) if group_name else ''
        changed = []

        with self.portion_lock:
            keys_to_consume = [key]
            if group_key and group_key != key:
                keys_to_consume.append(group_key)

            entries = [(consume_key, self.portion_stock.get(consume_key)) for consume_key in keys_to_consume]
            if not entries or not entries[0][1]:
                return True, None

            for _, entry in entries:
                if not entry:
                    continue
                kalan = self._coerce_portion_amount(entry.get('kalan', 0))
                display_name = entry.get('urun') or urun
                if kalan <= 0:
                    return False, f"{display_name} tükendi"
                if kalan + 0.001 < units:
                    return False, f"{display_name} için sadece {self._format_portion_amount(kalan)} porsiyon kaldı"

            now_iso = datetime.datetime.now().isoformat()
            for _, entry in entries:
                if not entry:
                    continue
                kalan = self._coerce_portion_amount(entry.get('kalan', 0))
                entry['kalan'] = round(kalan - units, 2)
                entry['is_default'] = False
                entry['updated_at'] = now_iso
                changed.append({
                    'urun': entry.get('urun') or urun,
                    'kategori': entry.get('kategori'),
                    'kalan': self._portion_amount_for_json(entry['kalan']),
                    'tracked': True
                })
            self.save_portion_stock()

        self.emit_portion_stock_update(changed)
        return True, None

    def restore_portion_stock(self, urun, adet=1, not_bilgisi=''):
        self.reset_daily_portion_stock_if_needed()
        self.ensure_default_portion_stock()
        units = self.get_portion_units_for_order(urun, adet)
        stock_name = self.get_order_portion_stock_name(urun, not_bilgisi)
        key = self._normalize_product_key(stock_name)
        group_name = self.get_daily_meal_group_for_product(urun)
        group_key = self._normalize_product_key(group_name) if group_name else ''
        changed = []

        with self.portion_lock:
            keys_to_restore = [key]
            if group_key and group_key != key:
                keys_to_restore.append(group_key)
            entries = [(restore_key, self.portion_stock.get(restore_key)) for restore_key in keys_to_restore]
            if not entries or not entries[0][1]:
                return False
            now_iso = datetime.datetime.now().isoformat()
            for _, entry in entries:
                if not entry:
                    continue
                entry['kalan'] = round(self._coerce_portion_amount(entry.get('kalan', 0)) + units, 2)
                entry['is_default'] = False
                entry['updated_at'] = now_iso
                changed.append({
                    'urun': entry.get('urun') or urun,
                    'kategori': entry.get('kategori'),
                    'kalan': self._portion_amount_for_json(entry['kalan']),
                    'tracked': True
                })
            self.save_portion_stock()

        self.emit_portion_stock_update(changed)
        return True

    def emit_portion_stock_update(self, changed=None):
        socketio.emit('portion_stock_update', {
            'portion_stock': self.get_portion_stock_snapshot(),
            'changed': changed or []
        })
    
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
                stock_ok, stock_error = self.validate_portion_stock_for_order(yeni_urunler)
                if not stock_ok:
                    logger.warning(f"Terminal siparişi stok nedeniyle reddedildi: {stock_error}")
                    return

                for item in yeni_urunler:
                    siparis, err = self.add_order_item(
                        masa_adi=masa_adi,
                        urun=item.get('urun'),
                        fiyat=item.get('fiyat', 0),
                        garson=f"Terminal {terminal_adi}",
                        adet=item.get('adet', 1),
                        not_bilgisi=item.get('not') or item.get('not_bilgisi') or '',
                        terminal_id=f"TCP:{terminal_adi}",
                        return_error=True
                    )
                    if not siparis:
                        logger.warning(f"Terminal siparişi eklenemedi: {err}")
                
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

@app.route('/izgara')
def izgara_page():
    """Izgara sipariş takip sayfası"""
    return app.send_static_file('mutfak.html')

@app.route('/icecek')
def icecek_page():
    """İçecek sipariş takip sayfası"""
    return app.send_static_file('mutfak.html')

@app.route('/tatli')
def tatli_page():
    """Tatlı sipariş takip sayfası"""
    return app.send_static_file('mutfak.html')

@app.route('/reyon/<panel_id>')
def reyon_page(panel_id):
    """Hazırlık reyonu takip sayfası"""
    if panel_id not in server.prep_panel_settings:
        return app.send_static_file('mutfak.html')
    return app.send_static_file('mutfak.html')

@app.route('/porsiyon')
def porsiyon_page():
    """Günlük yemek porsiyon takip sayfası"""
    return app.send_static_file('porsiyon_takip.html')

@app.route('/waiter')
def waiter_page():
    """Garson arayüzü"""
    return app.send_static_file('waiter.html')

@app.route('/waiters_manage')
def waiters_manage_page():
    """Garson yönetimi sayfası"""
    return app.send_static_file('waiters_manage.html')

@app.route('/puantaj')
def puantaj_page():
    """Çalışan puantaj takip sayfası"""
    return app.send_static_file('puantaj.html')

@app.route('/personel')
def personel_page():
    """Personel yönetimi sayfası"""
    return app.send_static_file('personel.html')

@app.route('/menu/public')
def public_menu_page():
    """Müşteri QR menü sayfası"""
    return app.send_static_file('customer_menu.html')

@app.route('/menu/liva')
@app.route('/liva')
def liva_menu_page():
    """Liva müşteri menü sayfası"""
    return app.send_static_file('customer_menu.html')

@app.route('/menu/tokatliva')
@app.route('/tokatliva')
def tokatliva_menu_page():
    """Tokatliva.com menü kopyası"""
    return app.send_static_file('tokatliva_menu.html')

@app.route('/menu/qr-card')
def liva_qr_card_page():
    """Liva masa karekod kartı"""
    return app.send_static_file('liva_qr_card.html')

@app.route('/waiter/table-session')
def waiter_table_session_page():
    """Garson için dinamik masa oturumu üretici"""
    return app.send_static_file('table_session.html')

@app.route('/api/system/info')
def system_info():
    """Sistem bilgileri"""
    return jsonify(server.get_system_info())

@app.route('/api/public/menu-qr.svg')
def api_public_menu_qr_svg():
    """Statik QR menü kartları için SVG QR üretir"""
    try:
        import qrcode
        import qrcode.image.svg
    except Exception as e:
        return jsonify({'success': False, 'error': f'QR modülü yok: {e}'}), 503

    table_name = (request.args.get('table') or request.args.get('table_hint') or 'C').strip().upper()[:24] or 'C'
    target = (request.args.get('target') or '').strip()
    if not target:
        query = urllib.parse.urlencode({'table_hint': table_name, 'mode': 'view'})
        target = urllib.parse.urljoin(request.host_url, f"menu/public?{query}")
    if len(target) > 700 or not target.startswith(('http://', 'https://')):
        return jsonify({'success': False, 'error': 'Geçersiz QR hedefi'}), 400

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=1,
        image_factory=qrcode.image.svg.SvgPathImage,
    )
    qr.add_data(target)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#161616", back_color="#ffffff")
    out = io.BytesIO()
    image.save(out)
    response = app.response_class(out.getvalue(), mimetype='image/svg+xml')
    response.headers['Cache-Control'] = 'no-cache'
    return response

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Mevcut ayarları döndür"""
    return jsonify({
        'firma_ismi':   server.company_name,
        'terminal_id':  server.terminal_id,
        'masa_sayisi':  server.masa_sayisi,
        'paket_sayisi': server.paket_sayisi,
        'direct_print': server.direct_print,
        'default_payment_method': server.default_payment_method,
        'cid_port': server.cid_port,
        'cid_type': server.cid_type,
        'cid_serial_port': server.cid_serial_port,
        'cid_enabled': server.cid_enabled,
        'pos_enabled': server.pos_enabled,
        'pos_ip': server.pos_ip,
        'pos_port': server.pos_port,
        'pos_type': server.pos_type,
        'salons': server.salons,
        'prep_panels': server.get_preparation_panels(),
        'prep_category_overrides': server.prep_category_overrides,
        'prep_printers': server.prep_printers,
        'menu_categories': list(server.menu_data.keys()),
        'daily_meal_categories': server._daily_meal_categories(),
        'va_max_duration': server.va_max_duration,
        'va_rate_limit': server.va_rate_limit,
        'va_sms_verify': server.va_sms_verify,
        'va_kitchen_approval': server.va_kitchen_approval,
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
    server.default_payment_method = server.sanitize_payment_method(
        data.get('default_payment_method', server.default_payment_method)
    )

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

    server.prep_panel_settings = server.sanitize_prep_panel_settings(
        data.get('prep_panels', server.prep_panel_settings)
    )
    server.prep_category_overrides = server.sanitize_prep_category_overrides(
        data.get('prep_category_overrides', server.prep_category_overrides)
    )
    server.prep_printers = server.sanitize_prep_printer_settings(
        data.get('prep_printers', server.prep_printers)
    )
    server.normalize_active_order_panels()

    server.va_max_duration = int(data.get('va_max_duration', server.va_max_duration))
    server.va_rate_limit = int(data.get('va_rate_limit', server.va_rate_limit))
    server.va_sms_verify = data.get('va_sms_verify', server.va_sms_verify)
    server.va_kitchen_approval = data.get('va_kitchen_approval', server.va_kitchen_approval)
    
    # POS Manager'ı güncelle
    server.pos_manager = POSManager(server.pos_enabled, server.pos_ip, server.pos_port, server.pos_type)

    # Kaydet
    ok = server.save_settings()
    if not ok:
        return jsonify({'success': False, 'error': 'Dosyaya yazılamadı'}), 500

    # Masa/paket yapısı değiştiyse yenile
    if masa_degisti:
        server.refresh_adisyonlar(preserve_existing=True)
        server.save_active_adisyonlar()
        socketio.emit('system_update', {
            'masa_sayisi':  server.masa_sayisi,
            'paket_sayisi': server.paket_sayisi,
            'company_name': server.company_name,
            'terminal_id':  server.terminal_id
        })
        socketio.emit('initial_data', server.get_initial_payload())
    else:
        socketio.emit('initial_data', server.get_initial_payload())
    socketio.emit('system_info', server.get_system_info())

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
        ikram_toplam = 0.0
        for r in rows:
            t = float(r['toplam'])
            ik = float(r.get('ikram_toplam') or 0)
            toplam += t
            ikram_toplam += ik
            result.append({
                'odeme': r['odeme'],
                'tip': r['tip'],
                'toplam': t,
                'ikram_toplam': ik,
                'adet': r['adet']
            })
        return jsonify({
            'success': True,
            'ozet': result,
            'genel_toplam': toplam,
            'genel_ikram_toplam': ikram_toplam,
            'tarih': tarih
        })
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
    
    # Kasiyerin kayıtlı olup olmadığını kontrol et (Eğer sistemde kayıtlı kasiyer varsa zorunlu tut)
    if server.cashiers:
        registered_cashier_names = [c['name'] for c in server.cashiers]
        if kasiyer not in registered_cashier_names:
            logger.warning(f"⚠️ Kayıtlı olmayan bir isimle vardiya açma girişimi: {kasiyer}")
            return jsonify({'success': False, 'error': f'"{kasiyer}" isimli kullanıcı kasiyer olarak kayıtlı değil.'}), 403

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
    
    # Boş string gelirse 0 kabul et (ValueError önlemek için)
    val_nakit = data.get('nakit')
    val_kart = data.get('kart')
    nakit = float(val_nakit) if val_nakit and str(val_nakit).strip() != "" else 0.0
    kart = float(val_kart) if val_kart and str(val_kart).strip() != "" else 0.0
    
    if not shift_id: return jsonify({'success': False, 'error': 'Vardiya ID gerekli'})
    try:
        db.close_shift(shift_id, nakit, kart)
        server.revoke_public_sessions_for_shift(int(shift_id))
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
    stock_ok, stock_error = server.validate_portion_stock_for_order(items)
    if not stock_ok:
        return jsonify({'success': False, 'error': stock_error}), 409
    
    # Adisyon alanını kontrol et veya oluştur
    if masa_adi not in server.adisyonlar:
        server.adisyonlar[masa_adi] = []
        
    # Siparişleri ekle
    for item in items:
        siparis, err = server.add_order_item(
            masa_adi=masa_adi,
            urun=item.get('urun'),
            fiyat=item.get('fiyat', 0),
            garson=order.get('platform', 'Online'),
            adet=item.get('adet', 1),
            not_bilgisi=item.get('not') or item.get('not_bilgisi') or '',
            tip=item.get('tip', 'normal'),
            terminal_id=f"API:{platform}",
            return_error=True
        )
        if not siparis:
            return jsonify({'success': False, 'error': err or 'Sipariş eklenemedi'}), 409
        
    # Tüm clientlara bildir
    totals = server.calculate_adisyon_totals(server.adisyonlar[masa_adi])
    socketio.emit('masa_update', {
        'masa': masa_adi,
        'items': server.adisyonlar[masa_adi],
        **totals,
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

@app.route('/api/kitchen', methods=['GET'])
def get_kitchen_api():
    """Mutfak personeli listesini getir"""
    return jsonify(server.kitchen)

@app.route('/api/kitchen', methods=['POST'])
def add_kitchen_api():
    """Yeni mutfak personeli ekle"""
    try:
        data = request.json
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'İsim gerekli'}), 400
            
        server.kitchen.append({'name': name})
        server.save_kitchen()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/kitchen/<int:idx>', methods=['DELETE'])
def delete_kitchen_api(idx):
    """Mutfak personelini sil"""
    try:
        if 0 <= idx < len(server.kitchen):
            server.kitchen.pop(idx)
            server.save_kitchen()
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

@app.route('/api/portion-stock', methods=['GET'])
def get_portion_stock_api():
    """Mutfak porsiyon stoklarını getir."""
    return jsonify({
        'success': True,
        'portion_stock': server.get_portion_stock_snapshot(),
        'by_category': server.get_portion_stock_by_category()
    })

@app.route('/api/portion-stock', methods=['POST'])
def save_portion_stock_api():
    """Mutfaktan girilen kalan porsiyonları kaydet."""
    data = request.get_json(silent=True) or {}
    updates = data.get('items')
    if updates is None:
        updates = [{'urun': data.get('urun'), 'kalan': data.get('kalan')}]
    if not isinstance(updates, list):
        return jsonify({'success': False, 'error': 'Geçersiz veri formatı'}), 400

    ok, errors, changed = server.set_portion_stock_items(updates)
    if not ok:
        return jsonify({'success': False, 'errors': errors, 'error': ', '.join(errors)}), 400

    return jsonify({
        'success': True,
        'changed': changed,
        'portion_stock': server.get_portion_stock_snapshot()
    })

@app.route('/api/daily-meals', methods=['GET'])
def get_daily_meals_api():
    """Günlük üretim metnini ve kalan porsiyonları getir."""
    return jsonify({
        'success': True,
        'daily_meals': server.get_daily_meals_payload(),
        'portion_stock': server.get_portion_stock_snapshot()
    })

@app.route('/api/daily-meals', methods=['POST'])
def save_daily_meals_api():
    """Günlük üretim metnini kaydet."""
    data = request.get_json(silent=True) or {}
    text = data.get('text')
    if text is None:
        return jsonify({'success': False, 'error': 'Günlük yemek metni gerekli'}), 400
    ok, errors = server.save_daily_meals_text(text)
    if not ok:
        return jsonify({'success': False, 'errors': errors, 'error': ', '.join(errors)}), 400

    payload = server.get_daily_meals_payload()
    socketio.emit('daily_meals_update', {
        'daily_meals': payload,
        'portion_stock': server.get_portion_stock_snapshot()
    })
    socketio.emit('initial_data', server.get_initial_payload())
    return jsonify({
        'success': True,
        'daily_meals': payload,
        'portion_stock': server.get_portion_stock_snapshot()
    })

# ==================== PUANTAJ API ====================

@app.route('/api/puantaj', methods=['GET'])
def get_puantaj_api():
    """Puantaj kayıtlarını listele (tarih filtrelenebilir)"""
    if not USE_DATABASE:
        return jsonify([])
    try:
        tarih = request.args.get('tarih')        # YYYY-MM-DD
        ay    = request.args.get('ay')           # YYYY-MM
        personel = request.args.get('personel')  # isim filtresi

        if tarih:
            records = db.get_puantaj_records(tarih_baslangic=tarih, tarih_bitis=tarih, personel_adi=personel)
        elif ay:
            yil, mon = ay.split('-')
            import calendar
            son_gun = calendar.monthrange(int(yil), int(mon))[1]
            bas = f"{yil}-{mon}-01"
            bit = f"{yil}-{mon}-{son_gun:02d}"
            records = db.get_puantaj_records(tarih_baslangic=bas, tarih_bitis=bit, personel_adi=personel)
        else:
            from datetime import date
            bugun = date.today().isoformat()
            records = db.get_puantaj_records(tarih_baslangic=bugun, tarih_bitis=bugun, personel_adi=personel)

        result = []
        for r in records:
            result.append({
                'id': r['id'],
                'personel_adi': r['personel_adi'],
                'rol': r['rol'],
                'tarih': str(r['tarih']),
                'giris_saati': r['giris_saati'].strftime('%Y-%m-%dT%H:%M:%S') if r['giris_saati'] else None,
                'cikis_saati': r['cikis_saati'].strftime('%Y-%m-%dT%H:%M:%S') if r['cikis_saati'] else None,
                'toplam_dakika': r['toplam_dakika'],
                'notlar': r['notlar'] or ''
            })
        return jsonify(result)
    except Exception as e:
        logger.error(f"Puantaj listele hatası: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/puantaj', methods=['POST'])
def add_puantaj_api():
    """Yeni puantaj kaydı ekle"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'DB bağlantısı yok'})
    try:
        data = request.json
        personel_adi = (data.get('personel_adi') or '').strip()
        rol = data.get('rol', 'garson')
        giris_str = data.get('giris_saati')
        notlar = data.get('notlar', '')
        cikis_str = data.get('cikis_saati')

        if not personel_adi:
            return jsonify({'success': False, 'error': 'Personel adı gerekli'}), 400

        import datetime as dt
        giris = dt.datetime.fromisoformat(giris_str) if giris_str else dt.datetime.now()

        record_id = db.add_puantaj_record(personel_adi, rol, giris, notlar)

        # Çıkış saati de verildiyse hemen güncelle
        if cikis_str:
            cikis = dt.datetime.fromisoformat(cikis_str)
            db.update_puantaj_checkout(record_id, cikis, notlar)

        logger.info(f"📋 Puantaj kaydı eklendi: {personel_adi} ({rol})")
        return jsonify({'success': True, 'id': record_id})
    except Exception as e:
        logger.error(f"Puantaj kayıt hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/puantaj/<int:record_id>', methods=['PUT'])
def update_puantaj_api(record_id):
    """Puantaj kaydını güncelle (çıkış saati veya notlar)"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'DB bağlantısı yok'})
    try:
        data = request.json
        cikis_str = data.get('cikis_saati')
        notlar = data.get('notlar')

        import datetime as dt
        cikis = dt.datetime.fromisoformat(cikis_str) if cikis_str else None
        db.update_puantaj_checkout(record_id, cikis, notlar)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Puantaj güncelleme hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/puantaj/<int:record_id>', methods=['DELETE'])
def delete_puantaj_api(record_id):
    """Puantaj kaydını sil"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'DB bağlantısı yok'})
    try:
        db.delete_puantaj_record(record_id)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Puantaj silme hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/puantaj/ozet', methods=['GET'])
def puantaj_ozet_api():
    """Aylık personel bazlı puantaj özeti"""
    if not USE_DATABASE:
        return jsonify([])
    try:
        ay = request.args.get('ay', '')  # YYYY-MM
        if not ay:
            from datetime import date
            ay = date.today().strftime('%Y-%m')
        yil, mon = ay.split('-')
        rows = db.get_puantaj_monthly_summary(int(yil), int(mon))
        result = []
        for r in rows:
            result.append({
                'personel_adi': r['personel_adi'],
                'rol': r['rol'],
                'toplam_gun': r['toplam_gun'],
                'toplam_dakika': int(r['toplam_dakika'] or 0),
                'toplam_saat': round(int(r['toplam_dakika'] or 0) / 60, 1)
            })
        return jsonify(result)
    except Exception as e:
        logger.error(f"Puantaj özet hatası: {e}")
        return jsonify({'error': str(e)}), 500

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
        server.refresh_adisyonlar(preserve_existing=True)
        server.save_active_adisyonlar()
        
        # Tüm istemcilere güncel düzeni ve diğer ayarları gönder
        socketio.emit('initial_data', server.get_initial_payload())
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Salon kaydetme hatası: {e}")
        return jsonify({'success': False, 'error': str(e)})

# ==================== PUBLIC QR ORDERING ====================

@app.route('/api/public/menu')
def api_public_menu():
    table_hint = (request.args.get('table_hint') or "").strip()
    table_exists = table_hint in server.adisyonlar if table_hint else False
    return jsonify({
        'success': True,
        'table_hint': table_hint,
        'table_exists': table_exists,
        'menu': server.get_public_menu_data(),
        'portion_stock': server.get_portion_stock_snapshot(),
        'daily_meals': server.get_daily_meals_payload()
    })

@app.route('/api/public/policy')
def api_public_policy():
    verify_mode = server.verify_mode
    return jsonify({
        'success': True,
        'verify_mode': verify_mode,
        'verify_required': verify_mode != 'none',
        'allow_dynamic_qr': verify_mode in ('dynamic_qr', 'hybrid'),
        'allow_nfc': verify_mode in ('nfc', 'hybrid'),
        'max_items_per_order': server.public_policy.get('max_items_per_order', 25),
        'max_item_qty': server.public_policy.get('max_item_qty', 20),
        'max_orders_per_minute': server.public_policy.get('max_orders_per_minute', 3),
        'online_orders_enabled': server.online_orders_enabled
    })

@app.route('/api/public/policy/update', methods=['POST'])
def api_public_policy_update():
    """QR Menu ve online siparis politikasini guncelle (admin gerektirir)"""
    data = request.get_json(silent=True) or {}
    admin_password = (data.get('admin_password') or '').strip()
    if admin_password != server.admin_password:
        return jsonify({'success': False, 'error': 'Admin sifresi hatali'}), 403

    new_verify_mode = (data.get('verify_mode') or '').strip().lower()
    if new_verify_mode in ('none', 'dynamic_qr', 'nfc', 'hybrid'):
        server.verify_mode = new_verify_mode
        logger.info(f"🔐 verify_mode guncellendi: {server.verify_mode}")

    if 'online_orders_enabled' in data:
        server.online_orders_enabled = bool(data['online_orders_enabled'])
        logger.info(f"🛒 Online siparis: {'ACIK' if server.online_orders_enabled else 'KAPALI'}")

    server.save_settings()
    return jsonify({
        'success': True,
        'verify_mode': server.verify_mode,
        'online_orders_enabled': server.online_orders_enabled
    })

# Online siparis rate limiting (telefon numarasina gore)
_online_order_rate = defaultdict(list)

@app.route('/api/online/order', methods=['POST'])
def api_online_order():
    """Uzaktan (online) siparis al — dogrulama gerektirmez, musteri bilgileri zorunlu"""
    if not server.online_orders_enabled:
        return jsonify({'success': False, 'error': 'Online siparis su an kapali'}), 503

    data = request.get_json(silent=True) or {}
    musteri_adi = (data.get('musteri_adi') or '').strip()
    telefon = (data.get('telefon') or '').strip()
    adres = (data.get('adres') or '').strip()
    not_bilgisi = (data.get('not') or '').strip()
    odeme_tipi = (data.get('odeme_tipi') or 'nakit').strip().lower()
    if odeme_tipi not in ('nakit', 'kart'):
        odeme_tipi = 'nakit'
    raw_items = data.get('items') or []

    # Validasyon
    if not musteri_adi:
        return jsonify({'success': False, 'error': 'Ad Soyad zorunludur'}), 400
    if not telefon or len(''.join(filter(str.isdigit, telefon))) < 10:
        return jsonify({'success': False, 'error': 'Gecerli bir telefon numarasi girin (min 10 hane)'}), 400
    if not adres:
        return jsonify({'success': False, 'error': 'Teslimat adresi zorunludur'}), 400
    if not isinstance(raw_items, list) or not raw_items:
        return jsonify({'success': False, 'error': 'Siparis kalemleri bos olamaz'}), 400

    # Rate limiting: ayni telefondan 60 saniyede max 3 siparis
    clean_tel = ''.join(filter(str.isdigit, telefon))
    now_ts = time.time()
    _online_order_rate[clean_tel] = [t for t in _online_order_rate[clean_tel] if now_ts - t < 60]
    if len(_online_order_rate[clean_tel]) >= 3:
        return jsonify({'success': False, 'error': 'Cok sik siparis gonderdiniz, lutfen bekleyin'}), 429
    _online_order_rate[clean_tel].append(now_ts)

    max_items = int(server.public_policy.get('max_items_per_order', 25))
    max_qty = int(server.public_policy.get('max_item_qty', 20))
    order_candidates = []
    for it in raw_items[:max_items]:
        try:
            urun = (it.get('urun') or '').strip()
            adet = min(max(1, int(it.get('adet', 1))), max_qty)
            fiyat = float(it.get('fiyat', 0))
        except Exception:
            continue
        if not urun or adet <= 0 or fiyat < 0:
            continue
        order_candidates.append({'urun': urun, 'adet': adet, 'fiyat': fiyat, 'not': not_bilgisi})

    if not order_candidates:
        return jsonify({'success': False, 'error': 'Gecerli siparis kalemi bulunamadi'}), 400

    stock_ok, stock_error = server.validate_portion_stock_for_order(order_candidates)
    if not stock_ok:
        return jsonify({'success': False, 'error': stock_error}), 409

    # Adisyon adi: "Online - Ad Soyad" (cakisma olursa numara ekle)
    base_adisyon = f"Online - {musteri_adi[:30]}"
    adisyon_adi = base_adisyon
    suffix = 2
    while adisyon_adi in server.adisyonlar and server.adisyonlar[adisyon_adi]:
        adisyon_adi = f"{base_adisyon} ({suffix})"
        suffix += 1

    server.adisyonlar[adisyon_adi] = []

    # Urunleri ekle
    added = []
    for item in order_candidates:
        siparis, err = server.add_order_item(
            masa_adi=adisyon_adi,
            urun=item['urun'],
            fiyat=item['fiyat'],
            garson='Online Siparis',
            adet=item['adet'],
            not_bilgisi=not_bilgisi,
            return_error=True
        )
        if not siparis:
            del server.adisyonlar[adisyon_adi]
            return jsonify({'success': False, 'error': err or 'Siparis eklenemedi'}), 409
        added.append(siparis)

    if not added:
        del server.adisyonlar[adisyon_adi]
        return jsonify({'success': False, 'error': 'Gecerli siparis kalemi bulunamadi'}), 400

    # Kasaya ve mutfaga bildir
    totals = server.calculate_adisyon_totals(server.adisyonlar[adisyon_adi])
    socketio.emit('masa_update', {
        'masa': adisyon_adi,
        'items': server.adisyonlar[adisyon_adi],
        **totals,
        'source': 'online_order'
    })
    socketio.emit('system_update', {
        'new_online_order': True,
        'masa': adisyon_adi,
        'musteri_adi': musteri_adi,
        'telefon': telefon,
        'adres': adres,
        'odeme_tipi': odeme_tipi
    })

    # DB'ye kaydet (varsa)
    if USE_DATABASE:
        try:
            db.save_online_order(
                musteri_adi=musteri_adi,
                telefon=clean_tel,
                adres=adres,
                not_bilgisi=not_bilgisi,
                items=added,
                adisyon_adi=adisyon_adi,
                odeme_tipi=odeme_tipi
            )
        except Exception as e:
            logger.warning(f"Online siparis DB kaydedilemedi: {e}")

    server.save_active_adisyonlar()
    added_count = sum(int(item.get('adet', 1)) for item in added)
    logger.info(f"🛒 Online siparis: {musteri_adi} | {clean_tel} | {added_count} kalem | {adisyon_adi}")

    return jsonify({
        'success': True,
        'adisyon_adi': adisyon_adi,
        'added_count': added_count,
        'portion_stock': server.get_portion_stock_snapshot(),
        'message': 'Sipariminiz alindi! En kisa surede sizi arayacagiz.'
    })

@app.route('/api/online/orders', methods=['GET'])
def api_online_orders():
    """Online siparisleri listele (kasiyer paneli)"""
    # Adisyonlar icinden "Online - " ile baslayanlar
    online = []
    for masa_adi, items in server.adisyonlar.items():
        if masa_adi.startswith('Online - ') and items:
            totals = server.calculate_adisyon_totals(items)
            online.append({
                'masa': masa_adi,
                'kalem_sayisi': len(items),
                'toplam': totals['payable_total'],
                'ikram_toplam': totals['ikram_total'],
                'items': items
            })
    return jsonify({'success': True, 'orders': online})

@app.route('/api/waiter/table-session/create', methods=['POST'])
def api_waiter_create_table_session():
    data = request.get_json(silent=True) or {}
    table_name = (data.get('table_name') or "").strip()
    kasa_id = data.get('kasa_id')
    ttl_seconds = int(data.get('ttl_seconds', server.public_policy.get('dynamic_qr_ttl_sec', 900)))
    waiter_name = (data.get('waiter_name') or "").strip()
    waiter_pin = (data.get('waiter_pin') or "").strip()
    admin_password = (data.get('admin_password') or "").strip()

    authorized = False
    if admin_password and admin_password == server.admin_password:
        authorized = True
    elif waiter_name and waiter_pin:
        waiter = next((w for w in server.waiters if w.get('name') == waiter_name and w.get('pin') == waiter_pin), None)
        authorized = waiter is not None
    if not authorized:
        return jsonify({'success': False, 'error': 'Yetkisiz istek'}), 401

    if not table_name:
        return jsonify({'success': False, 'error': 'Masa adı gerekli'}), 400
    if table_name not in server.adisyonlar:
        return jsonify({'success': False, 'error': 'Geçersiz masa adı'}), 400

    shift_id = None
    if USE_DATABASE and kasa_id:
        shift = db.get_active_shift_by_kasa(kasa_id)
        if shift:
            shift_id = shift.get('id')

    token, expires_at = server._create_signed_qr_token(
        table_name=table_name,
        shift_id=shift_id,
        ttl_seconds=max(120, min(ttl_seconds, 1800))
    )
    verify_url = f"/menu/public?table_hint={urllib.parse.quote(table_name)}&qr_token={urllib.parse.quote(token)}"

    return jsonify({
        'success': True,
        'table_name': table_name,
        'shift_id': shift_id,
        'qr_token': token,
        'expires_at_unix': expires_at,
        'verify_url': verify_url
    })

@app.route('/api/waiter/nfc-tag/register', methods=['POST'])
def api_waiter_register_nfc_tag():
    data = request.get_json(silent=True) or {}
    table_name = (data.get('table_name') or "").strip()
    nfc_uid = (data.get('nfc_uid') or "").strip()
    waiter_name = (data.get('waiter_name') or "").strip()
    waiter_pin = (data.get('waiter_pin') or "").strip()
    admin_password = (data.get('admin_password') or "").strip()

    authorized = False
    if admin_password and admin_password == server.admin_password:
        authorized = True
    elif waiter_name and waiter_pin:
        waiter = next((w for w in server.waiters if w.get('name') == waiter_name and w.get('pin') == waiter_pin), None)
        authorized = waiter is not None
    if not authorized:
        return jsonify({'success': False, 'error': 'Yetkisiz istek'}), 401

    if not table_name or table_name not in server.adisyonlar:
        return jsonify({'success': False, 'error': 'Gecerli masa gerekli'}), 400
    if not nfc_uid:
        return jsonify({'success': False, 'error': 'NFC UID gerekli'}), 400
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'NFC dogrulama icin DB gerekli'}), 400

    try:
        nfc_hash = hashlib.sha256(nfc_uid.encode('utf-8')).hexdigest()
        db.save_nfc_tag_hash(table_name, nfc_hash)
        return jsonify({'success': True, 'table_name': table_name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/public/session/verify-dynamic-qr', methods=['POST'])
def api_public_verify_dynamic_qr():
    if server.verify_mode not in ('dynamic_qr', 'hybrid'):
        return jsonify({'success': False, 'error': 'Dinamik QR doğrulama kapalı'}), 403

    data = request.get_json(silent=True) or {}
    qr_token = (data.get('qr_token') or "").strip()
    table_hint = (data.get('table_hint') or "").strip()
    device_fingerprint = (data.get('device_fingerprint') or "").strip()

    if not qr_token:
        return jsonify({'success': False, 'error': 'QR token gerekli'}), 400

    session, err = server.create_public_session_from_qr(
        token=qr_token,
        device_fingerprint=device_fingerprint,
        ip=request.remote_addr or ""
    )
    if err:
        return jsonify({'success': False, 'error': err}), 401
    if session['table_name'] not in server.adisyonlar:
        return jsonify({'success': False, 'error': 'Masa aktif degil'}), 400

    if table_hint and session['table_name'] != table_hint:
        return jsonify({'success': False, 'error': 'Masa uyuşmuyor'}), 403

    return jsonify({
        'success': True,
        'session_token': session['id'],
        'table_name': session['table_name'],
        'expires_at_unix': session['expires_at']
    })

@app.route('/api/public/session/verify-nfc', methods=['POST'])
def api_public_verify_nfc():
    if server.verify_mode not in ('nfc', 'hybrid'):
        return jsonify({'success': False, 'error': 'NFC doğrulama kapalı'}), 403

    data = request.get_json(silent=True) or {}
    table_hint = (data.get('table_hint') or "").strip()
    nfc_uid = (data.get('nfc_uid') or "").strip()
    device_fingerprint = (data.get('device_fingerprint') or "").strip()

    if not table_hint or not nfc_uid:
        return jsonify({'success': False, 'error': 'Masa ve NFC bilgisi gerekli'}), 400

    session, err = server.create_public_session_from_nfc(
        table_name=table_hint,
        nfc_uid=nfc_uid,
        device_fingerprint=device_fingerprint,
        ip=request.remote_addr or ""
    )
    if err:
        return jsonify({'success': False, 'error': err}), 401

    return jsonify({
        'success': True,
        'session_token': session['id'],
        'table_name': session['table_name'],
        'expires_at_unix': session['expires_at']
    })

@app.route('/api/public/order', methods=['POST'])
def api_public_order():
    data = request.get_json(silent=True) or {}
    session_token = (data.get('session_token') or "").strip()
    table_name = (data.get('table_name') or "").strip()
    raw_items = data.get('items') or []

    if not table_name:
        return jsonify({'success': False, 'error': 'Masa bilgisi gerekli'}), 400
    if not isinstance(raw_items, list) or not raw_items:
        return jsonify({'success': False, 'error': 'Sipariş kalemleri gerekli'}), 400
    if table_name not in server.adisyonlar:
        return jsonify({'success': False, 'error': 'Masa bulunamadı'}), 400

    verify_mode = server.verify_mode
    session = None
    rate_key = session_token or f"none:{request.remote_addr}:{table_name}"
    if verify_mode != 'none':
        if not session_token:
            return jsonify({'success': False, 'error': 'Doğrulama gerekli'}), 401
        session, err = server.validate_public_session(session_token, table_name=table_name)
        if err:
            return jsonify({'success': False, 'error': err}), 401
        rate_key = session_token

    if not server.can_place_public_order(rate_key, max_per_minute=int(server.public_policy.get('max_orders_per_minute', 3))):
        return jsonify({'success': False, 'error': 'Çok sık sipariş gönderildi, lütfen bekleyin'}), 429

    max_items = int(server.public_policy.get('max_items_per_order', 25))
    max_qty = int(server.public_policy.get('max_item_qty', 20))
    order_candidates = []
    for it in raw_items[:max_items]:
        try:
            urun = (it.get('urun') or "").strip()
            adet = min(max(1, int(it.get('adet', 1))), max_qty)
            fiyat = float(it.get('fiyat', 0))
            item_note = str(it.get('not') or it.get('not_bilgisi') or '').strip()[:160]
        except Exception:
            continue
        if not urun or adet <= 0 or fiyat < 0:
            continue
        order_candidates.append({'urun': urun, 'adet': adet, 'fiyat': fiyat, 'not': item_note})

    if not order_candidates:
        return jsonify({'success': False, 'error': 'Geçerli sipariş kalemi bulunamadı'}), 400

    stock_ok, stock_error = server.validate_portion_stock_for_order(order_candidates)
    if not stock_ok:
        return jsonify({'success': False, 'error': stock_error}), 409

    added = []
    for item in order_candidates[:max_items]:
        order_item, err = server.add_order_item(
            masa_adi=table_name,
            urun=item['urun'],
            fiyat=item['fiyat'],
            garson='Müşteri QR',
            adet=item['adet'],
            not_bilgisi=item.get('not', ''),
            return_error=True
        )
        if not order_item:
            return jsonify({'success': False, 'error': err or 'Sipariş eklenemedi'}), 409
        added.append(order_item)

    if not added:
        return jsonify({'success': False, 'error': 'Geçerli sipariş kalemi bulunamadı'}), 400

    session_exp = None
    if session:
        session['expires_at'] = min(
            int(time.time()) + int(server.public_policy.get('session_slide_sec', 900)),
            session['created_at'] + int(server.public_policy.get('session_ttl_sec', 3600))
        )
        session_exp = session['expires_at']
        if USE_DATABASE:
            try:
                db.update_public_session_expiry(
                    session_token,
                    datetime.datetime.fromtimestamp(session['expires_at'])
                )
            except Exception as e:
                logger.error(f"Public session expiry update DB hatası: {e}")

    return jsonify({
        'success': True,
        'table_name': table_name,
        'added_count': sum(int(item.get('adet', 1)) for item in added),
        'session_expires_at_unix': session_exp,
        'verify_mode': verify_mode,
        'portion_stock': server.get_portion_stock_snapshot()
    })

# ==================== MENÜ ====================

@app.route('/api/menu/save', methods=['POST'])
def save_menu_api():
    """Menüyü kaydet"""
    global server
    try:
        data = request.json
        if not data or 'menu' not in data:
            return jsonify({'success': False, 'error': 'Geçersiz veri'})
        
        new_menu = data['menu']
        daily_meal_categories = data.get('daily_meal_categories')
        
        # 1. menu.txt dosyasını güncelle
        with open(MENU_FILE, "w", encoding="utf-8") as f:
            for cat, items in new_menu.items():
                for item in items:
                    # item structure: [name, price, ys, ty, gt, mg, image_url, menu_visible]
                    name = item[0]
                    price = item[1]
                    # Default percentages to 0 if not provided
                    ys = item[2] if len(item) > 2 else 0
                    ty = item[3] if len(item) > 3 else 0
                    gt = item[4] if len(item) > 4 else 0
                    mg = item[5] if len(item) > 5 else 0
                    image_url = str(item[6]).strip() if len(item) > 6 and item[6] is not None else ""
                    image_url = image_url.replace(";", "")
                    menu_visible = "1" if server.is_menu_item_visible(item) else "0"
                    f.write(f"{cat};{name};{price};{ys};{ty};{gt};{mg};{image_url};{menu_visible}\n")

        # Kategori metadatası menu_data'ya göre normalize edildiği için cache'i önce yenile.
        server.menu_data = new_menu
        if daily_meal_categories is not None and not server.save_menu_metadata(daily_meal_categories):
            return jsonify({'success': False, 'error': 'Menü metadatası kaydedilemedi'}), 500
        
        # 2. Veri tabanını güncelle (eğer kullanılıyorsa)
        if USE_DATABASE:
            try:
                db.load_menu_from_file(MENU_FILE)
            except Exception as e:
                logger.error(f"Menü DB güncelleme hatası: {e}")
        
        # 3. Sunucu cache'ini yenile
        server.menu_data = new_menu
        server.load_daily_meals()
        server.apply_daily_meal_stock(reset_values=False)
        
        # 4. İstemcilere bildir
        socketio.emit('initial_data', server.get_initial_payload())
        socketio.emit('daily_meals_update', {
            'daily_meals': server.get_daily_meals_payload(),
            'portion_stock': server.get_portion_stock_snapshot()
        })
        
        return jsonify({'success': True, 'menu_meta': server.get_menu_metadata_payload()})
    except Exception as e:
        logger.error(f"Menü kaydetme hatası: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/menu/images')
def list_menu_images_api():
    """Yerel menü görsel deposunu listele"""
    try:
        os.makedirs(MENU_UPLOAD_DIR, exist_ok=True)
        allowed_extensions = {f".{ext}" for ext in ALLOWED_MENU_IMAGE_FORMATS.values()}
        images = []
        for filename in os.listdir(MENU_UPLOAD_DIR):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in allowed_extensions:
                continue
            path = os.path.join(MENU_UPLOAD_DIR, filename)
            if not os.path.isfile(path):
                continue
            stat = os.stat(path)
            images.append({
                "filename": filename,
                "url": f"{MENU_UPLOAD_URL_PREFIX}/{filename}",
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            })
        images.sort(key=lambda item: item["mtime"], reverse=True)
        return jsonify({"success": True, "images": images})
    except Exception as e:
        logger.error(f"Menü görsel listesi hatası: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/menu/images/upload', methods=['POST'])
def upload_menu_image_api():
    """Menü editöründen gelen görseli yerel depoya kaydet"""
    try:
        if request.content_length and request.content_length > MAX_MENU_IMAGE_BYTES + 1024 * 1024:
            return jsonify({"success": False, "error": "Görsel en fazla 8 MB olabilir"}), 413

        image_file = request.files.get('image') or request.files.get('file')
        product_name = (request.form.get('product_name') or request.form.get('urun') or '').strip()
        saved, error = save_menu_image(image_file, product_name)
        if error:
            return jsonify({"success": False, "error": error}), 400
        return jsonify({"success": True, **saved})
    except Exception as e:
        logger.error(f"Menü görsel upload hatası: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/menu/meta')
def get_menu_meta_api():
    """Menü kategori metadatasını getir."""
    return jsonify({
        'success': True,
        **server.get_menu_metadata_payload()
    })

@app.route('/api/menu')
def get_menu():
    """Menüyü getir"""
    return jsonify(server.menu_data)

@app.route('/api/prep-panels')
def get_prep_panels():
    """Ürün gruplarının hazırlık paneli yönlendirmelerini getir"""
    return jsonify({
        'success': True,
        'panels': server.get_preparation_panels(),
        'category_overrides': server.prep_category_overrides
    })

@app.route('/api/adisyonlar')
def get_adisyonlar():
    """Tüm adisyonları getir"""
    return jsonify(server.adisyonlar)

@app.route('/api/adisyon/<masa_adi>')
def get_adisyon(masa_adi):
    """Belirli bir adisyonu getir"""
    items = server.adisyonlar.get(masa_adi, [])
    totals = server.calculate_adisyon_totals(items)
    return jsonify({
        'masa': masa_adi,
        'items': items,
        **totals
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
    emit('initial_data', server.get_initial_payload(sid))

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
    totals = server.calculate_adisyon_totals(items)
    
    emit('masa_selected', {
        'masa': masa_adi,
        'items': items,
        **totals
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
    
    urun = (data.get('urun') or "").strip()
    fiyat = float(data.get('fiyat', 0))
    not_bilgisi = str(data.get('not') or data.get('not_bilgisi') or '').strip()[:160]
    if not urun:
        emit('error', {'message': 'Ürün adı gerekli'})
        return

    order_item, err = server.add_order_item(
        masa_adi=masa_adi,
        urun=urun,
        fiyat=fiyat,
        garson=data.get('garson', 'Bilinmiyor'),
        adet=1,
        not_bilgisi=not_bilgisi,
        tip=data.get('tip', 'normal'),
        return_error=True
    )
    if not order_item:
        emit('error', {'message': err or 'Sipariş eklenemedi'})

@socketio.on('kitchen_order_ready')
def handle_kitchen_order_ready(data):
    """Mutfaktan sipariş hazır bildirimi"""
    masa = data.get('masa')
    waiters = data.get('waiters', [])
    items_uids = data.get('items_uids', []) # Mutfaktan gelen hazır ürün ID'leri
    items_uid_set = set(items_uids)
    
    logger.info(f"📢 Sipariş hazır: {masa} (UIDs: {items_uids})")

    changed_masas = set()
    notified_waiters = set(waiters or [])

    # Adisyondaki ürünlerin durumunu güncelle. İçecek paneli gibi toplu
    # paneller masa göndermeden farklı masalardaki UID'leri tek seferde kapatabilir.
    for masa_adi, masa_items in server.adisyonlar.items():
        if masa and masa_adi != masa:
            continue
        for item in masa_items:
            if item.get('uid') in items_uid_set:
                item['durum'] = 'hazir'
                changed_masas.add(masa_adi)
                if item.get('garson'):
                    notified_waiters.add(item.get('garson'))

    if changed_masas:
        server.save_active_adisyonlar() # Persistence

    # Garsonlara bildir
    for waiter_name in notified_waiters:
        if waiter_name in server.waiter_sessions:
            for sid in server.waiter_sessions[waiter_name]:
                socketio.emit('order_ready', {
                    'masa': masa or 'Hazırlık',
                    'items_uids': items_uids,
                    'message': f"{masa or 'Hazırlık'} siparişi hazır!"
                }, room=sid)
    
    # Değişen tüm masaları güncelle (toplu içecek onayı birden fazla masayı etkileyebilir)
    for changed_masa in changed_masas:
        items = server.adisyonlar.get(changed_masa, [])
        totals = server.calculate_adisyon_totals(items)
        socketio.emit('masa_update', {'masa': changed_masa, 'items': items, **totals})

@socketio.on('mark_order_served')
def handle_mark_order_served(data):
    """Garson hazır siparişi masaya servis etti olarak işaretler."""
    masa_adi = data.get('masa')
    items_uids = data.get('items_uids') or []
    garson = data.get('garson') or 'Bilinmiyor'

    if not masa_adi or masa_adi not in server.adisyonlar:
        emit('error', {'message': 'Geçersiz masa'})
        return

    uid_set = set(items_uids)
    changed = 0
    servis_saati = datetime.datetime.now().strftime("%H:%M:%S")

    for item in server.adisyonlar[masa_adi]:
        if item.get('durum') != 'hazir':
            continue
        if uid_set and item.get('uid') not in uid_set:
            continue
        item['durum'] = 'servis_edildi'
        item['servis_garson'] = garson
        item['servis_saati'] = servis_saati
        changed += 1

    if not changed:
        emit('error', {'message': 'Servis edilecek hazır ürün bulunamadı'})
        return

    server.save_active_adisyonlar()
    items = server.adisyonlar[masa_adi]
    totals = server.calculate_adisyon_totals(items)
    socketio.emit('masa_update', {'masa': masa_adi, 'items': items, **totals})
    emit('success', {'message': f'{changed} ürün servis edildi'})
    logger.info(f"🍽️ Sipariş servis edildi: {masa_adi} ({changed} ürün) - {garson}")

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
                if item.get('durum') in ('hazir', 'servis_edildi'):
                    emit('error', {'message': 'Hazır veya servis edilmiş sipariş iptal edilemez!'})
                    return
                item_idx = i
                break
        
        if item_idx != -1:
            cancelled_item = server.adisyonlar[masa_adi].pop(item_idx)
            server.restore_portion_stock(
                cancelled_item.get('urun'),
                cancelled_item.get('adet', 1),
                cancelled_item.get('not', '')
            )
            server.save_active_adisyonlar() # Persistence
            logger.info(f"🗑️ Sipariş iptal edildi: {masa_adi} - {cancelled_item['urun']}")
            
            # Mutfak ekranına bildir
            socketio.emit('kitchen_cancel_order', {
                'masa': masa_adi,
                'uid': item_uid,
                'panel': cancelled_item.get('panel') or server.get_preparation_panel_for_product(
                    cancelled_item.get('urun'),
                    cancelled_item.get('kategori', '')
                )
            })
            
            # Masa güncellemesini herkese duyur
            items = server.adisyonlar[masa_adi]
            totals = server.calculate_adisyon_totals(items)
            socketio.emit('masa_update', {
                'masa': masa_adi,
                'items': items,
                **totals
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
        totals = server.calculate_adisyon_totals(items)
        socketio.emit('masa_update', {
            'masa': masa_adi,
            'items': items,
            **totals,
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
        'total': server.calculate_adisyon_totals(server.adisyonlar.get(masa_adi, []))['payable_total']
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
            if server.adisyonlar[masa_adi][index].get('durum') in ('hazir', 'servis_edildi'):
                emit('error', {'message': 'Hazır veya servis edilmiş sipariş kaldırılamaz'})
                return
            removed_item = server.adisyonlar[masa_adi].pop(index)
            server.restore_portion_stock(
                removed_item.get('urun'),
                removed_item.get('adet', 1),
                removed_item.get('not', '')
            )
            server.save_active_adisyonlar() # Persistence

            if removed_item.get('uid') and removed_item.get('durum') == 'mutfakta':
                socketio.emit('kitchen_cancel_order', {
                    'masa': masa_adi,
                    'uid': removed_item.get('uid'),
                    'panel': removed_item.get('panel') or server.get_preparation_panel_for_product(
                        removed_item.get('urun'),
                        removed_item.get('kategori', '')
                    )
                })
            
            items = server.adisyonlar[masa_adi]
            totals = server.calculate_adisyon_totals(items)
            
            socketio.emit('masa_update', {
                'masa': masa_adi,
                'items': items,
                **totals
            })

@socketio.on('set_item_comp')
def handle_set_item_comp(data):
    """Seçili adisyon kalemlerini ikram/normal olarak işaretle."""
    sid = request.sid
    if data.get('role') == 'terminal':
        emit('error', {'message': 'Yetki hatası: Kasa işlemi yapılamaz'})
        return

    masa_adi = data.get('masa') or server.current_selections.get(sid)
    if not masa_adi or masa_adi not in server.adisyonlar:
        emit('error', {'message': 'Geçersiz masa'})
        return

    item_indices = data.get('item_indices', [])
    if not item_indices:
        emit('error', {'message': 'İşaretlenecek ürün seçilmedi'})
        return

    ikram = bool(data.get('ikram', True))
    items = server.adisyonlar[masa_adi]
    changed = 0
    for idx in item_indices:
        try:
            idx = int(idx)
        except Exception:
            continue
        if 0 <= idx < len(items):
            items[idx]['tip'] = 'ikram' if ikram else 'normal'
            changed += 1

    if not changed:
        emit('error', {'message': 'Seçilen ürünler bulunamadı'})
        return

    server.save_active_adisyonlar()
    totals = server.calculate_adisyon_totals(items)
    socketio.emit('masa_update', {
        'masa': masa_adi,
        'items': items,
        **totals
    })

    durum = 'ikram olarak işaretlendi' if ikram else 'normal hesaba alındı'
    emit('success', {'message': f'{changed} ürün {durum}'})

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
    normalized_item_indices = []
    if item_indices:
        items_to_pay = []
        # Indexleri büyükten küçüğe sıralayarak pop işleminin diğer indexleri kaydırmasını önleyeceğiz
        # Ama önce kopyasını alıp işlem yapalım ki hata durumunda veri kaybolmasın
        for idx in item_indices:
            try:
                idx = int(idx)
            except Exception:
                continue
            if 0 <= idx < len(server.adisyonlar[masa_adi]):
                normalized_item_indices.append(idx)
                items_to_pay.append(server.adisyonlar[masa_adi][idx])
        
        if not items_to_pay:
            emit('error', {'message': 'Seçilen ürünler bulunamadı'})
            return
        items = items_to_pay

    payment_totals = server.calculate_adisyon_totals(items)
    payable_total = payment_totals['payable_total']
    ikram_total = payment_totals['ikram_total']
    payable_items = [item for item in items if not server.is_ikram_item(item)]

    if payable_total <= 0.01:
        emit('error', {'message': 'Ödenecek tutar yok. Hesabı İkram Kapat ile kapatın.'})
        return

    if not payments:
        payments = [{'type': payment_type, 'amount': payable_total}]

    normalized_payments = []
    for payment in payments:
        try:
            normalized = dict(payment)
            normalized['amount'] = float(payment.get('amount', 0))
            normalized['type'] = payment.get('type') or payment_type
            if normalized['amount'] > 0:
                normalized_payments.append(normalized)
        except Exception:
            logger.warning(f"Geçersiz ödeme satırı atlandı: {payment}")
    payments = normalized_payments
    if not payments:
        emit('error', {'message': 'Geçerli ödeme tutarı bulunamadı'})
        return
    
    # Aktif vardiya bilgisini al
    active_shift = server.get_sid_active_shift(sid)
    vardiya_id = active_shift['id'] if active_shift else None
    
    # Database'e kaydet
    try:
        timestamp = datetime.datetime.now()
        
        # POS/ÖKC işlemi
        if server.pos_enabled:
            card_amount = sum(p['amount'] for p in payments if p.get('type') == 'Kredi Kartı')
            token_bridge_enabled = server.pos_type in POSManager.TOKEN_BRIDGE_TYPES
            pos_amount = sum(p['amount'] for p in payments) if token_bridge_enabled else card_amount
            if pos_amount > 0:
                logger.info(f"💳 POS/ÖKC satış başlatılıyor: {pos_amount:.2f} TL | {server.pos_type}")
                success, msg = server.pos_manager.sale(
                    pos_amount,
                    masa_adi,
                    items=payable_items,
                    payments=payments,
                    order_id=str(uuid.uuid4())
                )
                if not success:
                    raise Exception(msg)
                logger.info(f"✅ POS/ÖKC satış başarılı: {msg}")

        # Cari işlemleri POS/ÖKC başarılı olduktan sonra kaydet
        for p in payments:
            if p.get('type') == 'Açık Hesap' and USE_DATABASE:
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
            item_tip = item.get('tip', 'normal')
            sales_data.append({
                'urun': item['urun'],
                'adet': item['adet'],
                'fiyat': item['fiyat'],
                'odeme': 'İkram' if item_tip == 'ikram' else final_payment_label,
                'tip': item_tip,
                'Tarih_Saat': timestamp,
                'masa': masa_adi,
                'terminal_id': server.terminal_id,
                'vardiya_id': vardiya_id
            })
        
        if USE_DATABASE:
            db.save_sales_batch(sales_data)
        
        # Adisyonu temizle (Sadece ödenen kalemleri)
        is_partial = False
        if normalized_item_indices:
            # Indexleri büyükten küçüğe sıralayıp sil
            for idx in sorted(normalized_item_indices, reverse=True):
                if 0 <= idx < len(server.adisyonlar[masa_adi]):
                    server.adisyonlar[masa_adi].pop(idx)
            
            # Eğer masada hala ürün varsa bu bir kısmi ödemedir
            if server.adisyonlar[masa_adi]:
                is_partial = True
        else:
            server.adisyonlar[masa_adi] = []

        if not server.adisyonlar[masa_adi]:
            server.revoke_public_sessions_for_table(masa_adi)
        
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
            remaining_totals = server.calculate_adisyon_totals(server.adisyonlar[masa_adi])
            socketio.emit('masa_update', {
                'masa': masa_adi,
                'items': server.adisyonlar[masa_adi],
                **remaining_totals
            })
        
        msg = f"{final_payment_label} ödemesi alındı"
        if final_payment_label == "Parçalı":
            details = ", ".join([f"{p['amount']} TL {p['type']}" for p in payments])
            msg = f"Parçalı ödeme alındı: {details}"
        if ikram_total > 0:
            msg += f" | İkram: {ikram_total:.2f} TL"
            
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
                } for i in payable_items],
                'total': payable_total,
                'ikram_total': ikram_total,
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

@socketio.on('close_complimentary_bill')
def handle_close_complimentary_bill(data):
    """Tamamı ikram olan hesabı tahsilat oluşturmadan kapat."""
    sid = request.sid
    if data.get('role') == 'terminal':
        emit('error', {'message': 'Yetki hatası: Kasa işlemi yapılamaz'})
        return

    masa_adi = data.get('masa') or server.current_selections.get(sid)
    if not masa_adi or masa_adi not in server.adisyonlar:
        emit('error', {'message': 'Geçersiz masa'})
        return

    items = server.adisyonlar[masa_adi]
    if not items:
        emit('error', {'message': 'Sipariş yok'})
        return

    totals = server.calculate_adisyon_totals(items)
    if totals['payable_total'] > 0.01:
        emit('error', {'message': 'Önce ücretli ürünleri tahsil edin veya ikram olarak işaretleyin.'})
        return

    try:
        timestamp = datetime.datetime.now()
        active_shift = server.get_sid_active_shift(sid)
        vardiya_id = active_shift['id'] if active_shift else None

        for item in items:
            item['tip'] = 'ikram'

        ikram_total = server.calculate_adisyon_totals(items)['ikram_total']
        sales_data = [{
            'urun': item['urun'],
            'adet': item['adet'],
            'fiyat': item['fiyat'],
            'odeme': 'İkram',
            'tip': 'ikram',
            'Tarih_Saat': timestamp,
            'masa': masa_adi,
            'terminal_id': server.terminal_id,
            'vardiya_id': vardiya_id
        } for item in items]

        if USE_DATABASE:
            db.save_sales_batch(sales_data)

        server.adisyonlar[masa_adi] = []
        server.revoke_public_sessions_for_table(masa_adi)
        server.save_active_adisyonlar()

        socketio.emit('payment_completed', {
            'masa': masa_adi,
            'type': 'İkram',
            'payments': [],
            'is_partial': False,
            'ikram_total': ikram_total
        })
        emit('success', {'message': f'Hesap ikram olarak kapatıldı: {ikram_total:.2f} TL'})
    except Exception as e:
        logger.error(f"İkram kapatma hatası: {e}")
        emit('error', {'message': str(e)})

@socketio.on('print_receipt')
def handle_print_receipt(data):
    """Fiş yazdır"""
    sid = request.sid
    masa_adi = server.current_selections.get(sid)
    
    if not masa_adi or masa_adi not in server.adisyonlar:
        emit('error', {'message': 'Geçersiz masa'})
        return
    
    items = server.adisyonlar.get(masa_adi, [])
    if not items:
        emit('error', {'message': 'Yazdırılacak sipariş yok'})
        return
    
    try:
        sira = server.get_and_inc_counter()
        now = datetime.datetime.now().strftime("%d-%m-%Y      %H:%M")
        fn = os.path.join(FIS_KLASORU, f"Fis_{sira}.txt")
        totals = server.calculate_adisyon_totals(items)
        total = totals['payable_total']
        ikram_total = totals['ikram_total']
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
                line_total = 0 if i.get("tip") == "ikram" else server.item_line_total(i)
                f.write(f"{urun_adi:<12} {i['adet']:<1} {line_total:>6.2f}TL\n")
            f.write(f"{'='*C_WIDTH}\n")
            if ikram_total > 0:
                f.write(f"{'IKRAM:':<10}{ikram_total:>11.2f}TL \n")
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

# ==================== SESLİ ASİSTAN GÜVENLİK ENDPOINTLERİ ====================

def admin_required(f):
    """Admin decorator - basit implementasyon"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Basit admin check - header'dan veya session'dan kontrol edilebilir
        # Şimdilik her zaman izin veriyoruz (güvenlik production'da artırılmalı)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/va/blacklist', methods=['GET'])
@admin_required
def api_get_va_blacklist():
    try:
        if not db:
            return jsonify({'success': False, 'error': 'Veritabanı bağlantısı yok'}), 500
        
        raw_list = db.get_blacklist()
        blacklist = []
        for item in raw_list:
            blacklist.append({
                'id': item[0],
                'telefon': item[1],
                'sebep': item[2],
                'tarih': item[3].isoformat() if item[3] else None
            })
        return jsonify({'success': True, 'blacklist': blacklist})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/va/blacklist', methods=['POST'])
@admin_required
def api_add_va_blacklist():
    try:
        data = request.json
        telefon = data.get('telefon')
        sebep = data.get('sebep', 'Belirtilmedi')
        
        if not telefon:
            return jsonify({'success': False, 'error': 'Telefon numarası eksik'}), 400
            
        db.add_to_blacklist(telefon, sebep)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/va/blacklist/<telefon>', methods=['DELETE'])
@admin_required
def api_remove_va_blacklist(telefon):
    try:
        db.remove_from_blacklist(telefon)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Terminal sunucusunu başlat
    server.start_terminal_server()
    
    # Caller ID sunucusunu başlat
    server.start_caller_id_listener()

    # Porsiyon stoklarını gün değişiminde otomatik varsayılana döndür
    server.start_portion_stock_reset_scheduler()
    
    # Web sunucuyu başlat
    logger.info(f"🌐 Web sunucu başlatılıyor: http://{get_local_ip()}:8000")
    
    socketio.run(app, host='0.0.0.0', port=8000, debug=False, allow_unsafe_werkzeug=True)
