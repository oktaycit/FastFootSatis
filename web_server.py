#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Restoran - Web Server
Flask tabanlı restoran yönetim sistemi
"""

from flask import Flask, render_template, request, jsonify, send_file, redirect, make_response, g
from flask_socketio import SocketIO, emit
import threading
import time
import datetime
import json
import os
import sys
import io
import csv
import copy
import logging
import socket
import subprocess
import platform
import tarfile
import tempfile
import shutil
import uuid
import re
import hmac
import hashlib
import base64
import secrets
import serial
import serial.tools.list_ports
import urllib.parse
import urllib.request
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
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
PAKET_LABELS_FILE = os.path.join(SCRIPT_DIR, "paket_labels.json")
CASHIERS_FILE = os.path.join(SCRIPT_DIR, "cashiers.json")
KITCHEN_FILE = os.path.join(SCRIPT_DIR, "kitchen.json")
USERS_FILE = os.path.join(SCRIPT_DIR, "users.json")
AUTH_SESSIONS_FILE = os.path.join(SCRIPT_DIR, "auth_sessions.json")
ACTIVE_ADISYONLAR_FILE = os.path.join(SCRIPT_DIR, "active_adisyonlar.json")
TABLE_NOTES_FILE = os.path.join(SCRIPT_DIR, "table_notes.json")
RESERVATIONS_FILE = os.path.join(SCRIPT_DIR, "reservations.json")
PORTION_STOCK_FILE = os.path.join(SCRIPT_DIR, "portion_stock.json")
PORTION_STOCK_RESET_FILE = os.path.join(SCRIPT_DIR, "portion_stock_reset.json")
DAILY_MEALS_FILE = os.path.join(SCRIPT_DIR, "gunluk_yemekler.txt")
DAILY_MEALS_HISTORY_DIR = os.path.join(SCRIPT_DIR, "gunluk_yemekler")
BACKUP_DIR = os.path.join(SCRIPT_DIR, "backups")
DEFAULT_PORTION_STOCK = 40
SERVER_PORT = 5555
AUTH_COOKIE_NAME = "ff_auth_token"
AUTH_SESSION_DAYS = 30
DASHBOARD_STATUS_TIMEOUT_SECONDS = 0.45
DASHBOARD_STATUS_CACHE_SECONDS = 10
DASHBOARD_STATUS_FAILURE_CACHE_SECONDS = 60
DASHBOARD_STATUS_ERROR_LOG_SECONDS = 300
DEFAULT_PRINTER_ALERT_MODE = "escpos_buzzer"
PRINTER_ALERT_MODES = {"escpos_buzzer", "cash_drawer", "both"}

AUTH_PAGE_DEFINITIONS = {
    "dashboard": {
        "label": "Ana kasa ekranı",
        "paths": ["/", "/index.html", "/kasa-terminal", "/reservations", "/reservations.html"],
    },
    "settings": {
        "label": "Sistem ayarları",
        "paths": ["/settings", "/settings.html"],
    },
    "personel": {
        "label": "Personel ve yetkiler",
        "paths": ["/personel", "/personel.html", "/waiters_manage", "/waiters_manage.html"],
    },
    "menu": {
        "label": "Menü düzenleme",
        "paths": ["/menu_edit", "/menu_edit.html"],
    },
    "kasa": {
        "label": "Kasa ve vardiya",
        "paths": ["/kasa", "/kasa_yonetimi.html"],
    },
    "gunsonu": {
        "label": "Gün sonu",
        "paths": ["/gunsonu", "/gunsonu.html"],
    },
    "raporlar": {
        "label": "Raporlar",
        "paths": ["/raporlar", "/raporlar.html"],
    },
    "cari": {
        "label": "Cari hesaplar",
        "paths": ["/cari", "/cari.html"],
    },
    "kurye": {
        "label": "Kurye yönetimi",
        "paths": ["/kurye", "/kurye_yonetimi.html"],
    },
    "terminals": {
        "label": "Terminal yönetimi",
        "paths": ["/terminals", "/terminals.html"],
    },
    "waiter": {
        "label": "Garson ekranı",
        "paths": ["/waiter", "/waiter.html", "/garson-terminal", "/waiter/shared"],
    },
    "table_session": {
        "label": "Masa QR/NFC oturumu",
        "paths": ["/waiter/table-session", "/table_session.html"],
    },
    "kitchen": {
        "label": "Hazırlık ekranları",
        "paths": ["/mutfak", "/mutfak.html", "/izgara", "/icecek", "/tatli"],
        "prefixes": ["/reyon/"],
    },
    "porsiyon": {
        "label": "Porsiyon takibi",
        "paths": ["/porsiyon", "/porsiyon_takip.html"],
    },
    "puantaj": {
        "label": "Puantaj",
        "paths": ["/puantaj", "/puantaj.html"],
    },
}

AUTH_ROLE_DEFINITIONS = {
    "admin": {
        "label": "Yönetici",
        "level": 100,
        "permissions": ["*"],
    },
    "manager": {
        "label": "Müdür",
        "level": 80,
        "permissions": [
            "dashboard", "settings", "personel", "menu", "kasa", "cari",
            "kurye", "terminals", "waiter", "table_session", "kitchen", "porsiyon", "puantaj",
            "raporlar"
        ],
    },
    "cashier": {
        "label": "Kasiyer",
        "level": 60,
        "permissions": ["dashboard", "kasa", "cari", "kurye", "waiter", "kitchen", "porsiyon"],
    },
    "waiter": {
        "label": "Garson",
        "level": 30,
        "permissions": ["waiter", "table_session"],
    },
    "kitchen": {
        "label": "Mutfak",
        "level": 25,
        "permissions": ["kitchen", "porsiyon"],
    },
    "courier": {
        "label": "Kurye",
        "level": 20,
        "permissions": ["kurye"],
    },
}

ADMIN_ONLY_PAGE_KEYS = {"gunsonu"}

AUTH_PATH_TO_PAGE = {}
AUTH_PREFIX_TO_PAGE = []
for page_key, page_info in AUTH_PAGE_DEFINITIONS.items():
    for page_path in page_info.get("paths", []):
        AUTH_PATH_TO_PAGE[page_path] = page_key
    for page_prefix in page_info.get("prefixes", []):
        AUTH_PREFIX_TO_PAGE.append((page_prefix, page_key))

AUTH_API_PREFIX_PERMISSIONS = [
    ("/api/dashboard", "dashboard"),
    ("/api/settings", "settings"),
    ("/api/serial/ports", "settings"),
    ("/api/salons", "settings"),
    ("/api/integration/settings", "settings"),
    ("/api/public/policy/update", "settings"),
    ("/api/va/blacklist", "settings"),
    ("/api/menu/save", "menu"),
    ("/api/menu/images", "menu"),
    ("/api/menu/meta", "menu"),
    ("/api/waiters", "personel"),
    ("/api/cashiers", "personel"),
    ("/api/kitchen", "personel"),
    ("/api/couriers", "personel"),
    ("/api/puantaj", "puantaj"),
    ("/api/kasa", "kasa"),
    ("/api/vardiya", "kasa"),
    ("/api/gunsonu", "gunsonu"),
    ("/api/raporlar", "raporlar"),
    ("/api/cari", "cari"),
    ("/api/courier-firms", "kurye"),
    ("/api/online/orders", "dashboard"),
    ("/api/reservations", "dashboard"),
    ("/api/waiter/table-session", "table_session"),
    ("/api/waiter/nfc-tag", "table_session"),
    ("/api/portion-stock", "porsiyon"),
    ("/api/daily-meals", "porsiyon"),
]

AUTH_PUBLIC_PATH_PREFIXES = (
    "/login",
    "/login.html",
    "/api/auth/login",
    "/api/auth/options",
    "/api/auth/me",
    "/api/waiters/login",
    "/api/public/",
    "/api/online/order",
    "/api/integration/webhook/",
    "/api/system/info",
    "/menu/public",
    "/menu/liva",
    "/liva",
    "/menu/tokatliva",
    "/tokatliva",
    "/menu/qr-card",
    "/customer_menu.html",
    "/tokatliva_menu.html",
    "/liva_qr_card.html",
    "/uploads/",
    "/socket.io/",
)

AUTH_PUBLIC_STATIC_EXTENSIONS = {
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".ico", ".woff", ".woff2", ".ttf", ".map", ".txt"
}

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

PREP_PANEL_QUICK_NOTES = {
    "izgara": ("Az Pişmiş", "Orta Pişmiş", "Çok Pişmiş", "Soğansız"),
    "mutfak": ("Bulgur pilavlı", "Pirinç pilavlı", "Pilavsız"),
    "icecek": ("Buzsuz", "Az buzlu", "Şekersiz"),
    "tatli": ("Dondurmalı", "Kaymaksız")
}

DEFAULT_PREP_TICKET_SKIP_PRODUCTS = ("su",)

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
app.config['SECRET_KEY'] = 'restoran_secret_key_2026'
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
        self.paket_labels = []
        self.paket_labels_configured = False
        self.direct_print = False
        self.default_payment_method = "Nakit"
        self.shift_auto_close_enabled = True
        self.shift_auto_close_time = "00:00"
        self.auto_backup_enabled = True
        self.auto_backup_time = "00:05"
        self.auto_backup_dir = BACKUP_DIR
        self.auto_backup_retention_days = 30
        self.auto_backup_last_date = ""
        self.last_backup_info = {}
        self.prep_panel_settings = self.get_default_prep_panel_settings()
        self.prep_category_overrides = {}
        self.prep_printers = self.get_default_prep_printer_settings()
        self.prep_ticket_skip_products = list(DEFAULT_PREP_TICKET_SKIP_PRODUCTS)
        self.receipt_printer = self.get_default_receipt_printer_settings()
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
        self.okc_busy = False
        self.okc_busy_context = {}
        self.okc_busy_lock = threading.RLock()

        self.cid_port = 101 # Caller ID Port (Signal 7 standardı)
        self.cid_type = 'tcp' # 'tcp' veya 'serial'
        self.cid_serial_port = 'COM3'
        self.cid_enabled = True
        
        # Adisyon durumları
        self.adisyonlar = {}
        self.table_notes = {}
        self.reservations = []
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
        self.shift_auto_close_thread = None
        self.auto_backup_thread = None
        
        # Garsonlar ve Kasiyerler
        self.waiters = [] # [{"name": "Ahmet", "pin": "1234"}]
        self.cashiers = [] # [{"name": "Kasa 1"}]
        self.kitchen = [] # [{"name": "Aşçı 1"}]
        self.users = []
        self.auth_sessions = {}
        
        # Aktif bağlantılar
        self.active_connections = {}
        self.waiter_sessions = defaultdict(set) # waiter_name -> set(sids)
        
        # Terminal sunucusu
        self.terminal_thread = None
        self.running = False
        self.dashboard_status_cache = {}
        self.dashboard_probe_cache = {}
        self.dashboard_status_lock = threading.RLock()
        self.dashboard_error_log_times = {}

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
        self.load_paket_labels()
        self.load_waiters()
        self.load_cashiers()
        self.load_kitchen()
        self.load_users()
        self.load_auth_sessions()
        self.refresh_adisyonlar()
        self.load_active_adisyonlar() # Aktif adisyonları geri yükle
        self.load_table_notes()
        self.load_reservations()
        self.load_menu_data()
        self.load_menu_metadata()
        self.normalize_active_order_panels()
        self.load_daily_meals()
        self.load_portion_stock()

        self.prep_printer_batch_delay = 1.0
        self.prep_printer_batch_lock = threading.Lock()
        self.prep_printer_batches = {}
        
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
            adet = RestaurantServer.coerce_order_quantity((item or {}).get('adet', 1))
            fiyat = float((item or {}).get('fiyat', 0))
            return max(0, adet) * max(0.0, fiyat)
        except Exception:
            return 0.0

    @staticmethod
    def coerce_order_quantity(value, default=1):
        """Adet/kg miktarını pozitif sayı olarak normalize eder."""
        try:
            quantity = float(str(value).replace(',', '.'))
        except Exception:
            quantity = float(default)
        if quantity <= 0:
            quantity = float(default)
        quantity = round(quantity, 3)
        return int(quantity) if quantity.is_integer() else quantity

    @staticmethod
    def format_order_quantity(value):
        quantity = RestaurantServer.coerce_order_quantity(value)
        if isinstance(quantity, int):
            return str(quantity)
        return f"{quantity:.3f}".rstrip('0').rstrip('.')

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

    def normalize_selected_item_quantities(self, items, item_quantities=None, item_indices=None):
        """Ödeme için seçilen satır/miktarları doğrula ve normalize et."""
        if not items:
            return [], None

        selections = defaultdict(float)
        if item_quantities:
            for entry in item_quantities:
                if not isinstance(entry, dict):
                    continue
                try:
                    idx = int(entry.get('index'))
                except Exception:
                    continue
                quantity = float(self.coerce_order_quantity(
                    entry.get('quantity', entry.get('adet', 0)),
                    default=0
                ))
                if 0 <= idx < len(items) and quantity > 0:
                    selections[idx] += quantity
        elif item_indices:
            for idx in item_indices:
                try:
                    idx = int(idx)
                except Exception:
                    continue
                if 0 <= idx < len(items):
                    selections[idx] += float(self.coerce_order_quantity(items[idx].get('adet', 1)))

        normalized = []
        for idx, quantity in sorted(selections.items()):
            available = float(self.coerce_order_quantity(items[idx].get('adet', 1)))
            if quantity > available + 0.001:
                return [], 'Seçilen ürün miktarı adisyondaki miktardan fazla'
            quantity = min(quantity, available)
            normalized.append({
                'index': idx,
                'quantity': self.coerce_order_quantity(quantity)
            })

        return normalized, None

    def selected_items_for_payment(self, items, selections):
        """Seçilen miktarlara göre satış/POS için bağımsız kalem kopyaları üret."""
        selected_items = []
        for selection in selections:
            idx = selection['index']
            if 0 <= idx < len(items):
                item_copy = dict(items[idx])
                item_copy['adet'] = selection['quantity']
                selected_items.append(item_copy)
        return selected_items

    def remove_selected_item_quantities(self, items, selections):
        """Tahsil edilen miktarı aktif adisyondan düş."""
        for selection in sorted(selections, key=lambda item: item['index'], reverse=True):
            idx = selection['index']
            if not (0 <= idx < len(items)):
                continue
            current_quantity = float(self.coerce_order_quantity(items[idx].get('adet', 1)))
            paid_quantity = float(self.coerce_order_quantity(selection['quantity'], default=0))
            remaining = round(current_quantity - paid_quantity, 3)
            if remaining <= 0.001:
                items.pop(idx)
            else:
                items[idx]['adet'] = self.coerce_order_quantity(remaining)

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

    def sanitize_time_setting(self, value, default="00:00"):
        raw = str(value or default).strip()
        match = re.fullmatch(r"(\d{1,2}):(\d{2})", raw)
        if not match:
            return default
        hour = int(match.group(1))
        minute = int(match.group(2))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return default
        return f"{hour:02d}:{minute:02d}"

    def sanitize_backup_dir(self, value):
        raw = str(value or "").strip()
        if not raw:
            return BACKUP_DIR
        expanded = os.path.expanduser(raw)
        if not os.path.isabs(expanded):
            expanded = os.path.join(SCRIPT_DIR, expanded)
        return os.path.abspath(expanded)

    def sanitize_tax_rate(self, value, default=10.0):
        try:
            rate = float(value)
        except (TypeError, ValueError):
            rate = default
        return max(0.0, min(rate, 100.0))

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

    def normalize_note_option_list(self, value, fallback=None):
        if fallback is None:
            fallback = []
        if isinstance(value, str):
            raw_items = value.replace("\n", ",").split(",")
        elif isinstance(value, (list, tuple)):
            raw_items = value
        else:
            raw_items = fallback

        notes = []
        seen = set()
        for item in raw_items:
            note = re.sub(r"\s+", " ", str(item or "")).strip()
            note_key = self._normalize_text_for_match(note)
            if note and note_key and note_key not in seen:
                notes.append(note[:60])
                seen.add(note_key)
            if len(notes) >= 24:
                break
        return notes

    def get_default_prep_panel_settings(self):
        settings = {}
        for panel_id, panel in PREP_PANELS.items():
            settings[panel_id] = {
                **panel,
                "category_keywords": list(PREP_PANEL_CATEGORY_KEYWORDS.get(panel_id, ())),
                "product_keywords": list(PREP_PANEL_PRODUCT_KEYWORDS.get(panel_id, ())),
                "quick_notes": list(PREP_PANEL_QUICK_NOTES.get(panel_id, ()))
            }
        return settings

    def get_default_prep_printer_settings(self):
        return {
            panel_id: {
                "enabled": False,
                "ip": "",
                "port": 9100,
                "copies": 1,
                "alert_enabled": False,
                "alert_mode": DEFAULT_PRINTER_ALERT_MODE
            }
            for panel_id in PREP_PANELS.keys()
        }

    def get_default_receipt_printer_settings(self):
        return {
            "enabled": False,
            "ip": "",
            "port": 9100,
            "copies": 1,
            "alert_enabled": False,
            "alert_mode": DEFAULT_PRINTER_ALERT_MODE
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
                ),
                "quick_notes": self.normalize_note_option_list(
                    raw.get("quick_notes"),
                    default.get("quick_notes", [])
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

    def sanitize_prep_ticket_skip_products(self, products=None):
        parsed = self.coerce_json_setting(products, None)
        if isinstance(parsed, list):
            raw_items = parsed
        elif isinstance(products, str):
            raw_items = re.split(r"[\n,]+", products)
        elif products is None:
            raw_items = DEFAULT_PREP_TICKET_SKIP_PRODUCTS
        else:
            raw_items = []

        clean = []
        seen = set()
        for item in raw_items:
            name = re.sub(r"\s+", " ", str(item or "")).strip()
            key = self._prep_ticket_match_text(name)
            if not name or not key or key in seen:
                continue
            clean.append(name[:80])
            seen.add(key)
            if len(clean) >= 200:
                break
        return clean

    def _prep_ticket_match_text(self, value):
        normalized = self._normalize_text_for_match(value)
        return re.sub(r"[^0-9a-z]+", " ", normalized).strip()

    def _prep_ticket_term_matches(self, text, term):
        haystack = self._prep_ticket_match_text(text)
        needle = self._prep_ticket_match_text(term)
        if not haystack or not needle:
            return False
        if haystack == needle:
            return True
        return re.search(rf"(^|\s){re.escape(needle)}($|\s)", haystack) is not None

    def should_skip_prep_ticket_for_product(self, urun):
        product_names = [str(urun or "").strip()]
        menu_name = self._find_menu_product_name(urun)
        if menu_name and menu_name not in product_names:
            product_names.append(menu_name)

        for term in self.prep_ticket_skip_products:
            if any(self._prep_ticket_term_matches(product_name, term) for product_name in product_names):
                return True
        return False

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
                "copies": self.bounded_int(raw.get("copies"), default["copies"], 1, 5),
                "alert_enabled": self.bool_from_setting(
                    raw.get("alert_enabled"),
                    default["alert_enabled"]
                ),
                "alert_mode": self.sanitize_printer_alert_mode(
                    raw.get("alert_mode"),
                    default["alert_mode"]
                )
            }
        return sanitized

    def sanitize_printer_alert_mode(self, value, default=DEFAULT_PRINTER_ALERT_MODE):
        mode = str(value or default).strip().lower()
        if mode in PRINTER_ALERT_MODES:
            return mode
        return default

    def sanitize_receipt_printer_settings(self, printer_data=None):
        default = self.get_default_receipt_printer_settings()
        printer_data = self.coerce_json_setting(printer_data, {})
        if not isinstance(printer_data, dict):
            printer_data = {}

        return {
            "enabled": self.bool_from_setting(printer_data.get("enabled"), default["enabled"]),
            "ip": str(printer_data.get("ip") or default["ip"]).strip()[:80],
            "port": self.bounded_int(printer_data.get("port"), default["port"], 1, 65535),
            "copies": self.bounded_int(printer_data.get("copies"), default["copies"], 1, 5),
            "alert_enabled": self.bool_from_setting(
                printer_data.get("alert_enabled"),
                default["alert_enabled"]
            ),
            "alert_mode": self.sanitize_printer_alert_mode(
                printer_data.get("alert_mode"),
                default["alert_mode"]
            )
        }

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
                       not_bilgisi='', tip='normal', terminal_id=None, kategori=None,
                       return_error=False, emit_updates=True, emit_ticket=True,
                       extra_fields=None, prep_ticket_skipped=None, persist=True,
                       consume_stock=True):
        if masa_adi not in self.adisyonlar:
            return (None, 'Masa bulunamadı') if return_error else None

        not_bilgisi = str(not_bilgisi or '').strip()[:160]
        try:
            adet = self.coerce_order_quantity(adet)
        except Exception:
            adet = 1
        try:
            fiyat = float(fiyat)
        except Exception:
            return (None, 'Ürün fiyatı geçersiz') if return_error else None

        if consume_stock:
            stock_ok, stock_error = self.consume_portion_stock(urun, adet, not_bilgisi)
            if not stock_ok:
                return (None, stock_error) if return_error else None

        siparis_id = str(uuid.uuid4())[:8]
        created_at = datetime.datetime.now().astimezone()
        kategori = self.resolve_order_category(urun, kategori)
        panel = self.get_preparation_panel_for_product(urun, kategori)
        panel_info = self.get_prep_panel_info(panel)
        skip_prep_ticket = (
            bool(prep_ticket_skipped)
            if prep_ticket_skipped is not None
            else self.should_skip_prep_ticket_for_product(urun)
        )
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
            'prep_ticket_skipped': skip_prep_ticket,
            'saat': created_at.strftime("%H:%M:%S"),
            'created_at': created_at.isoformat(timespec='seconds')
        }
        if isinstance(extra_fields, dict):
            allowed_extra_fields = {'plate_group'}
            for key in allowed_extra_fields:
                if key in extra_fields:
                    siparis[key] = extra_fields[key]
        self.adisyonlar[masa_adi].append(siparis)
        if persist:
            self.save_active_adisyonlar()

        if not emit_updates:
            return (siparis, None) if return_error else siparis

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
            'created_at': siparis['created_at'],
            'garson': garson,
            'prep_ticket_skipped': skip_prep_ticket,
            'terminal_id': terminal_id or f"public:{masa_adi}"
        }
        if siparis.get('plate_group'):
            ticket_payload['plate_group'] = siparis.get('plate_group')
        socketio.emit('kitchen_new_order', ticket_payload)
        if skip_prep_ticket:
            logger.info(f"🧾 Reyon fişi atlandı: {urun} -> {masa_adi} ({panel})")
        elif emit_ticket:
            self.send_prep_ticket_to_printer(panel, ticket_payload)
        if panel == "mutfak":
            self.send_to_kitchen_legacy(masa_adi, f"{urun} ({not_bilgisi})" if not_bilgisi else urun, adet)
        return (siparis, None) if return_error else siparis

    def plate_group_label(self, plate_group):
        if not isinstance(plate_group, dict):
            return ""
        label = str(plate_group.get("label") or "").strip()
        group_id = str(plate_group.get("id") or "").strip()
        if label and group_id:
            return f"{label} #{group_id}"
        return label or (f"Tabak #{group_id}" if group_id else "")

    def order_item_ticket_payload(self, masa_adi, item, terminal_id=None):
        panel = item.get('panel') or self.get_preparation_panel_for_product(
            item.get('urun'),
            item.get('kategori', '')
        )
        panel_info = self.get_prep_panel_info(panel)
        payload = {
            'uid': item.get('uid'),
            'masa': masa_adi,
            'urun': item.get('urun'),
            'kategori': item.get('kategori'),
            'panel': panel,
            'panel_adi': panel_info['name'],
            'adet': item.get('adet', 1),
            'not': item.get('not') or '',
            'saat': item.get('saat') or '',
            'created_at': item.get('created_at') or '',
            'garson': item.get('garson') or '',
            'prep_ticket_skipped': bool(item.get('prep_ticket_skipped')),
            'terminal_id': terminal_id or f"public:{masa_adi}"
        }
        if item.get('plate_group'):
            payload['plate_group'] = item.get('plate_group')
        return payload

    def plate_group_key(self, plate_group):
        if not isinstance(plate_group, dict):
            return ""
        return str(plate_group.get("id") or plate_group.get("label") or "").strip()

    def daily_meal_portion_price(self, category, portion_amount):
        canonical = self.get_canonical_daily_meal_category(category) or str(category or "").strip()
        if not canonical:
            return 0.0

        target_amount = round(float(portion_amount or 0), 3)
        full_price = 0.0
        half_price = 0.0
        category_key = self._normalize_product_key(canonical)
        for item in self.menu_data.get(canonical, []):
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                continue
            name = str(item[0] or "").strip()
            if self._normalize_product_key(self._strip_portion_variant_prefix(name)) != category_key:
                continue
            try:
                price = float(item[1])
            except Exception:
                continue
            normalized = self._normalize_text_for_match(name)
            if normalized.startswith("tam porsiyon "):
                full_price = price
            elif normalized.startswith("yarim porsiyon "):
                half_price = price

        if abs(target_amount - 1) < 0.001 and full_price > 0:
            return round(full_price, 2)
        if abs(target_amount - 0.5) < 0.001 and half_price > 0:
            return round(half_price, 2)
        if full_price > 0:
            return round(full_price * target_amount, 2)
        return 0.0

    def daily_meal_full_portion_price(self, category):
        return self.daily_meal_portion_price(category, 1)

    def daily_meal_plate_combo_price(self, categories, portion_amount):
        full_prices = [
            self.daily_meal_full_portion_price(category)
            for category in categories
        ]
        full_prices = [price for price in full_prices if price > 0]
        if not full_prices:
            return 0.0
        try:
            target_amount = round(float(portion_amount or 0), 3)
        except Exception:
            target_amount = 0
        if target_amount <= 0:
            return 0.0
        return round(max(full_prices) * target_amount, 2)

    def normalize_plate_combo_pricing(self, order_items):
        normalized_items = [dict(item) if isinstance(item, dict) else item for item in (order_items or [])]
        grouped = defaultdict(list)

        for item in normalized_items:
            if not isinstance(item, dict) or item.get('prep_ticket_skipped'):
                continue
            plate_key = self.plate_group_key(item.get('plate_group'))
            if not plate_key:
                continue
            urun = str(item.get('urun') or item.get('name') or '').strip()
            category = self.get_canonical_daily_meal_category(item.get('kategori') or item.get('category')) \
                or self.get_daily_meal_group_for_product(urun, item.get('kategori') or item.get('category'))
            if not category:
                continue
            portions = self.get_portion_units_for_order(urun, item.get('adet', item.get('quantity', 1)))
            if portions <= 0:
                continue
            grouped[plate_key].append({
                'item': item,
                'category': category,
                'portions': portions
            })

        for entries in grouped.values():
            if len(entries) < 2:
                continue
            total_portions = round(sum(entry['portions'] for entry in entries), 3)
            if total_portions <= 0.5:
                continue
            target_total = self.daily_meal_plate_combo_price(
                [entry['category'] for entry in entries],
                total_portions
            )
            if target_total <= 0:
                continue

            target_cents = int(round(target_total * 100))
            allocated_cents = 0
            for index, entry in enumerate(entries):
                item = entry['item']
                try:
                    adet = self.coerce_order_quantity(item.get('adet', item.get('quantity', 1)))
                except Exception:
                    adet = 1
                if index == len(entries) - 1:
                    line_cents = target_cents - allocated_cents
                else:
                    line_cents = int(round(target_cents * (entry['portions'] / total_portions)))
                    allocated_cents += line_cents
                line_total = line_cents / 100
                item['fiyat'] = round(line_total / max(float(adet), 0.001), 2)

        return normalized_items

    def emit_order_batch_updates(self, masa_adi, added_items, terminal_id=None):
        items = self.adisyonlar.get(masa_adi, [])
        totals = self.calculate_adisyon_totals(items)
        socketio.emit('masa_update', {
            'masa': masa_adi,
            'items': items,
            **totals
        })

        grouped = defaultdict(list)
        for item in added_items:
            if item.get('prep_ticket_skipped'):
                continue
            payload = self.order_item_ticket_payload(masa_adi, item, terminal_id)
            group_id = ''
            if isinstance(payload.get('plate_group'), dict):
                group_id = str(payload['plate_group'].get('id') or '')
            grouped[(payload.get('panel') or '', group_id)].append(payload)

        for (panel, group_id), payload_items in grouped.items():
            if not panel or not payload_items:
                continue
            first = payload_items[0]
            batch_payload = {
                **first,
                'uid': first.get('uid'),
                'items': payload_items
            }
            socketio.emit('kitchen_new_order', batch_payload)
            self.send_prep_ticket_to_printer(panel, batch_payload)

            if panel == "mutfak":
                legacy_items = ", ".join(
                    self.prep_ticket_item_title({
                        "urun": entry.get("urun"),
                        "adet": entry.get("adet", 1),
                        "not": entry.get("not") or ""
                    })
                    for entry in payload_items
                )
                self.send_to_kitchen_legacy(masa_adi, legacy_items, 1)

    def add_order_items(self, masa_adi, order_items, garson='Bilinmiyor', terminal_id=None,
                        return_error=False):
        if masa_adi not in self.adisyonlar:
            return ([], 'Masa bulunamadı') if return_error else []

        if not isinstance(order_items, list) or not order_items:
            return ([], 'Sipariş kalemi bulunamadı') if return_error else []

        order_items = self.normalize_plate_combo_pricing(order_items)

        prepared_items = []
        for raw in order_items:
            if not isinstance(raw, dict):
                continue
            urun = str(raw.get('urun') or raw.get('name') or '').strip()
            if not urun:
                continue
            try:
                fiyat = float(raw.get('fiyat', raw.get('price', 0)))
            except Exception:
                return ([], 'Ürün fiyatı geçersiz') if return_error else []
            plate_group = raw.get('plate_group')
            if not isinstance(plate_group, dict):
                plate_group = None
            item = {
                'urun': urun,
                'fiyat': fiyat,
                'garson': raw.get('garson') or garson,
                'adet': raw.get('adet', raw.get('quantity', 1)),
                'not': raw.get('not') or raw.get('not_bilgisi') or '',
                'tip': raw.get('tip', 'normal'),
                'kategori': raw.get('kategori') or raw.get('category'),
                'prep_ticket_skipped': None,
                'plate_group': plate_group
            }
            if 'prep_ticket_skipped' in raw or 'skip_prep_ticket' in raw:
                item['prep_ticket_skipped'] = bool(raw.get('prep_ticket_skipped') or raw.get('skip_prep_ticket'))
            prepared_items.append(item)

        if not prepared_items:
            return ([], 'Geçerli sipariş kalemi bulunamadı') if return_error else []

        stock_ok, stock_error = self.consume_portion_stock_for_order(prepared_items)
        if not stock_ok:
            return ([], stock_error) if return_error else []

        added = []
        try:
            for raw in prepared_items:
                siparis, err = self.add_order_item(
                    masa_adi=masa_adi,
                    urun=raw['urun'],
                    fiyat=raw['fiyat'],
                    garson=raw['garson'],
                    adet=raw['adet'],
                    not_bilgisi=raw['not'],
                    tip=raw.get('tip', 'normal'),
                    terminal_id=terminal_id,
                    kategori=raw.get('kategori'),
                    return_error=True,
                    emit_updates=False,
                    emit_ticket=False,
                    prep_ticket_skipped=raw.get('prep_ticket_skipped'),
                    persist=False,
                    consume_stock=False,
                    extra_fields={'plate_group': raw['plate_group']} if raw.get('plate_group') else None
                )
                if not siparis:
                    raise ValueError(err or 'Sipariş eklenemedi')
                added.append(siparis)
        except Exception as e:
            for item in prepared_items:
                try:
                    self.restore_portion_stock(item.get('urun'), item.get('adet', 1), item.get('not', ''))
                except Exception:
                    pass
            for item in added:
                try:
                    if item in self.adisyonlar.get(masa_adi, []):
                        self.adisyonlar[masa_adi].remove(item)
                except Exception:
                    pass
            self.save_active_adisyonlar()
            return ([], str(e) or 'Sipariş eklenemedi') if return_error else []

        if not added:
            return ([], 'Geçerli sipariş kalemi bulunamadı') if return_error else []

        self.save_active_adisyonlar()
        self.emit_order_batch_updates(masa_adi, added, terminal_id)
        return (added, None) if return_error else added
    
    def load_settings(self):
        """Ayarları dosyadan yükle"""
        defaults = {
            "password": "1234",
            "direct_print": "HAYIR",
            "shift_auto_close_enabled": "EVET",
            "shift_auto_close_time": "00:00",
            "auto_backup_enabled": "EVET",
            "auto_backup_time": "00:05",
            "auto_backup_dir": BACKUP_DIR,
            "auto_backup_retention_days": "30",
            "auto_backup_last_date": "",
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
            "default_kdv_rate": "10",
            "verify_mode": "hybrid",
            "online_orders_enabled": "EVET",
            "va_max_duration": "3",
            "va_rate_limit": "5",
            "va_sms_verify": "HAYIR",
            "va_kitchen_approval": "EVET",
            "prep_panels_json": "",
            "prep_category_overrides_json": "{}",
            "prep_ticket_skip_products_json": json.dumps(list(DEFAULT_PREP_TICKET_SKIP_PRODUCTS), ensure_ascii=False),
            "prep_printers_json": "{}",
            "receipt_printer_json": "{}",
            "receipt_printer_enabled": "HAYIR",
            "receipt_printer_ip": "",
            "receipt_printer_port": "9100",
            "receipt_printer_copies": "1",
            "receipt_printer_alert_enabled": "HAYIR",
            "receipt_printer_alert_mode": DEFAULT_PRINTER_ALERT_MODE
        }
        for panel_id in PREP_PANELS.keys():
            defaults[f"prep_printer_{panel_id}_enabled"] = "HAYIR"
            defaults[f"prep_printer_{panel_id}_ip"] = ""
            defaults[f"prep_printer_{panel_id}_port"] = "9100"
            defaults[f"prep_printer_{panel_id}_copies"] = "1"
            defaults[f"prep_printer_{panel_id}_alert_enabled"] = "HAYIR"
            defaults[f"prep_printer_{panel_id}_alert_mode"] = DEFAULT_PRINTER_ALERT_MODE
        
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
        self.shift_auto_close_enabled = (defaults.get("shift_auto_close_enabled", "EVET") == "EVET")
        self.shift_auto_close_time = self.sanitize_time_setting(defaults.get("shift_auto_close_time"), "00:00")
        self.auto_backup_enabled = self.bool_from_setting(defaults.get("auto_backup_enabled"), True)
        self.auto_backup_time = self.sanitize_time_setting(defaults.get("auto_backup_time"), "00:05")
        self.auto_backup_dir = self.sanitize_backup_dir(defaults.get("auto_backup_dir"))
        self.auto_backup_retention_days = self.bounded_int(
            defaults.get("auto_backup_retention_days"),
            30,
            1,
            3650
        )
        self.auto_backup_last_date = str(defaults.get("auto_backup_last_date") or "").strip()
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
        self.default_kdv_rate = self.sanitize_tax_rate(defaults.get("default_kdv_rate"), 10.0)
        self.pos_manager = POSManager(
            self.pos_enabled,
            self.pos_ip,
            self.pos_port,
            self.pos_type,
            self.default_kdv_rate
        )

        # Hazırlık reyonları ve IP termal yazıcı ayarları
        self.prep_panel_settings = self.sanitize_prep_panel_settings(defaults.get("prep_panels_json"))
        self.prep_category_overrides = self.sanitize_prep_category_overrides(
            defaults.get("prep_category_overrides_json")
        )
        self.prep_ticket_skip_products = self.sanitize_prep_ticket_skip_products(
            defaults.get("prep_ticket_skip_products_json")
        )
        printer_json = self.coerce_json_setting(defaults.get("prep_printers_json"), {})
        if not printer_json:
            printer_json = {}
            for panel_id in PREP_PANELS.keys():
                printer_json[panel_id] = {
                    "enabled": defaults.get(f"prep_printer_{panel_id}_enabled"),
                    "ip": defaults.get(f"prep_printer_{panel_id}_ip"),
                    "port": defaults.get(f"prep_printer_{panel_id}_port"),
                    "copies": defaults.get(f"prep_printer_{panel_id}_copies"),
                    "alert_enabled": defaults.get(f"prep_printer_{panel_id}_alert_enabled"),
                    "alert_mode": defaults.get(f"prep_printer_{panel_id}_alert_mode")
                }
        self.prep_printers = self.sanitize_prep_printer_settings(printer_json)

        receipt_json = self.coerce_json_setting(defaults.get("receipt_printer_json"), {})
        if not receipt_json:
            receipt_json = {
                "enabled": defaults.get("receipt_printer_enabled"),
                "ip": defaults.get("receipt_printer_ip"),
                "port": defaults.get("receipt_printer_port"),
                "copies": defaults.get("receipt_printer_copies"),
                "alert_enabled": defaults.get("receipt_printer_alert_enabled"),
                "alert_mode": defaults.get("receipt_printer_alert_mode")
            }
        self.receipt_printer = self.sanitize_receipt_printer_settings(receipt_json)
        
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
                f.write(f"shift_auto_close_enabled:{'EVET' if self.shift_auto_close_enabled else 'HAYIR'}\n")
                f.write(f"shift_auto_close_time:{self.shift_auto_close_time}\n")
                f.write(f"auto_backup_enabled:{'EVET' if self.auto_backup_enabled else 'HAYIR'}\n")
                f.write(f"auto_backup_time:{self.auto_backup_time}\n")
                f.write(f"auto_backup_dir:{self.auto_backup_dir}\n")
                f.write(f"auto_backup_retention_days:{self.auto_backup_retention_days}\n")
                f.write(f"auto_backup_last_date:{self.auto_backup_last_date}\n")
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
                f.write(f"default_kdv_rate:{self.default_kdv_rate:g}\n")
                f.write(
                    "prep_panels_json:"
                    f"{json.dumps(list(self.prep_panel_settings.values()), ensure_ascii=False)}\n"
                )
                f.write(
                    "prep_category_overrides_json:"
                    f"{json.dumps(self.prep_category_overrides, ensure_ascii=False)}\n"
                )
                f.write(
                    "prep_ticket_skip_products_json:"
                    f"{json.dumps(self.prep_ticket_skip_products, ensure_ascii=False)}\n"
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
                    f.write(f"prep_printer_{panel_id}_alert_enabled:{'EVET' if printer.get('alert_enabled') else 'HAYIR'}\n")
                    f.write(f"prep_printer_{panel_id}_alert_mode:{printer.get('alert_mode', DEFAULT_PRINTER_ALERT_MODE)}\n")
                f.write(
                    "receipt_printer_json:"
                    f"{json.dumps(self.receipt_printer, ensure_ascii=False)}\n"
                )
                f.write(f"receipt_printer_enabled:{'EVET' if self.receipt_printer.get('enabled') else 'HAYIR'}\n")
                f.write(f"receipt_printer_ip:{self.receipt_printer.get('ip', '')}\n")
                f.write(f"receipt_printer_port:{self.receipt_printer.get('port', 9100)}\n")
                f.write(f"receipt_printer_copies:{self.receipt_printer.get('copies', 1)}\n")
                f.write(f"receipt_printer_alert_enabled:{'EVET' if self.receipt_printer.get('alert_enabled') else 'HAYIR'}\n")
                f.write(f"receipt_printer_alert_mode:{self.receipt_printer.get('alert_mode', DEFAULT_PRINTER_ALERT_MODE)}\n")
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

    def get_staffing_status(self):
        """Aktif garson oturumlarını yönetici ekranı için özetle."""
        ignored_names = {
            "",
            "kasa",
            "bilinmiyor",
            "ortak terminal",
            "musteri qr",
            "müşteri qr",
            "online siparis",
            "online sipariş",
        }
        active_waiters = []
        for waiter_name, sids in self.waiter_sessions.items():
            clean_name = str(waiter_name or "").strip()
            normalized = clean_name.casefold()
            if not clean_name or not sids:
                continue
            if normalized in ignored_names or normalized.startswith("terminal "):
                continue
            active_waiters.append(clean_name)

        active_waiters = sorted(set(active_waiters), key=lambda name: name.casefold())
        return {
            'active_waiters': active_waiters,
            'active_waiter_count': len(active_waiters)
        }

    def get_system_info(self):
        """Sistem bilgilerini döndür"""
        info = {
            'company_name': self.company_name,
            'terminal_id': self.terminal_id,
            'ip': get_local_ip(),
            'masa_sayisi': self.masa_sayisi,
            'paket_sayisi': self.paket_sayisi,
            'paket_labels': self.get_paket_labels(),
            'salons': self.salons,
            'database': USE_DATABASE,
            'pdf': PDF_SUPPORT,
            'cid_enabled': self.cid_enabled,
            'pos_enabled': self.pos_enabled,
            'pos_type': self.pos_type,
            'default_payment_method': self.default_payment_method,
            'receipt_printer_enabled': self.receipt_printer.get("enabled", False)
        }
        info.update(self.get_staffing_status())
        return info

    def get_initial_payload(self, sid=None):
        """İstemcilere gönderilen tam ekran durumunu hazırla."""
        payload = {
            'menu': self.get_order_menu_data(),
            'adisyonlar': self.adisyonlar,
            'table_notes': self.get_table_notes_payload(),
            'reservations': self.get_reservations_payload(),
            'system': self.get_system_info(),
            'prep_panels': self.get_preparation_panels(),
            'prep_category_overrides': self.prep_category_overrides,
            'prep_ticket_skip_products': self.prep_ticket_skip_products,
            'portion_stock': self.get_portion_stock_snapshot(),
            'daily_meals': self.get_daily_meals_payload(),
            'okc_busy': self.get_okc_busy_payload()
        }
        if sid is not None:
            payload['active_shift'] = self.get_sid_active_shift(sid)
        return payload

    def get_okc_busy_payload(self):
        with self.okc_busy_lock:
            payload = dict(self.okc_busy_context or {})
            payload['busy'] = bool(self.okc_busy)
            return payload

    def try_start_okc_operation(self, context=None):
        with self.okc_busy_lock:
            if self.okc_busy:
                return False, self.get_okc_busy_payload()

            self.okc_busy = True
            self.okc_busy_context = dict(context or {})
            self.okc_busy_context['started_at'] = datetime.datetime.now().isoformat(timespec='seconds')
            payload = self.get_okc_busy_payload()

        socketio.emit('okc_busy_update', payload)
        return True, payload

    def finish_okc_operation(self):
        with self.okc_busy_lock:
            if not self.okc_busy:
                return

            self.okc_busy = False
            self.okc_busy_context = {}
            payload = self.get_okc_busy_payload()

        socketio.emit('okc_busy_update', payload)

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

    def get_dashboard_operational_status(self, kasa_id=None):
        """Ana ekran için teknik detay içermeyen kasa/ÖKC/yazıcı özeti."""
        cache_key = ("operational", str(kasa_id or ""), self.dashboard_status_signature())
        cached = self.get_dashboard_cache(cache_key)
        if cached is not None:
            return cached

        cash_register = self.get_dashboard_cash_register_status(kasa_id)
        okc = self.get_dashboard_okc_status()
        printers = self.get_dashboard_printer_statuses()

        active_items = [cash_register, okc] + [p for p in printers if p.get("state") != "off"]
        if any(item.get("state") == "error" for item in active_items):
            overall_state = "error"
        elif any(item.get("state") == "warn" for item in active_items):
            overall_state = "warn"
        else:
            overall_state = "ok"

        payload = {
            "success": True,
            "updated_at": datetime.datetime.now().isoformat(),
            "overall_state": overall_state,
            "cash_register": cash_register,
            "okc": okc,
            "printers": printers
        }
        self.set_dashboard_cache(cache_key, payload, DASHBOARD_STATUS_CACHE_SECONDS)
        return payload

    def dashboard_status_signature(self):
        printer_targets = []
        for panel_id in sorted(PREP_PANELS.keys()):
            printer = self.prep_printers.get(panel_id, {}) or {}
            printer_targets.append((
                panel_id,
                bool(printer.get("enabled")),
                str(printer.get("ip") or ""),
                int(printer.get("port") or 9100)
            ))
        receipt = self.receipt_printer or {}
        return (
            bool(self.pos_enabled),
            str(self.pos_type or ""),
            str(self.pos_ip or ""),
            int(self.pos_port or 0),
            bool(self.direct_print),
            bool(receipt.get("enabled")),
            str(receipt.get("ip") or ""),
            int(receipt.get("port") or 9100),
            tuple(printer_targets)
        )

    def get_dashboard_cache(self, key):
        now = time.monotonic()
        with self.dashboard_status_lock:
            entry = self.dashboard_status_cache.get(key)
            if not entry:
                return None
            expires_at, payload = entry
            if expires_at <= now:
                self.dashboard_status_cache.pop(key, None)
                return None
            return copy.deepcopy(payload)

    def set_dashboard_cache(self, key, payload, ttl_seconds):
        with self.dashboard_status_lock:
            self.dashboard_status_cache[key] = (
                time.monotonic() + max(1, float(ttl_seconds or 1)),
                copy.deepcopy(payload)
            )

    def clear_dashboard_status_cache(self):
        with self.dashboard_status_lock:
            self.dashboard_status_cache.clear()
            self.dashboard_probe_cache.clear()
            self.dashboard_error_log_times.clear()

    def status_item(self, key, label, state, status_text, message=""):
        return {
            "key": key,
            "label": label,
            "state": state,
            "status_text": status_text,
            "message": message
        }

    def get_dashboard_cash_register_status(self, kasa_id=None):
        if not USE_DATABASE:
            return self.status_item("cash_register", "Kasa", "ok", "Açık", "Demo vardiya")

        try:
            kasa_id = int(kasa_id or 0)
        except (TypeError, ValueError):
            kasa_id = 0

        if kasa_id <= 0:
            return self.status_item("cash_register", "Kasa", "warn", "Seçilmedi", "Kasa seçimi bekleniyor")

        try:
            shift = db.get_active_shift_by_kasa(kasa_id)
        except Exception as e:
            logger.error(f"Dashboard kasa durumu alınamadı: {e}")
            return self.status_item("cash_register", "Kasa", "error", "Kontrol yok", "Vardiya durumu alınamadı")

        if not shift:
            return self.status_item("cash_register", "Kasa", "error", "Kapalı", "Vardiya kapalı")

        kasiyer = ""
        try:
            kasiyer = str(dict(shift).get("kasiyer") or "").strip()
        except Exception:
            kasiyer = ""
        message = f"{kasiyer} açık" if kasiyer else "Vardiya açık"
        return self.status_item("cash_register", "Kasa", "ok", "Açık", message)

    def get_dashboard_okc_status(self):
        if not self.pos_enabled:
            return self.status_item("okc", "ÖKC", "off", "Kapalı", "POS/ÖKC entegrasyonu kapalı")

        if self.pos_type == "demo":
            return self.status_item("okc", "ÖKC", "ok", "Demo", "Demo mod aktif")

        if not str(self.pos_ip or "").strip() or not self.pos_port:
            return self.status_item("okc", "ÖKC", "warn", "Ayar eksik", "Bağlantı ayarı tamamlanmalı")

        if self.pos_type in POSManager.TOKEN_BRIDGE_TYPES:
            return self.get_dashboard_token_bridge_status()

        if self.probe_tcp_service(self.pos_ip, self.pos_port):
            return self.status_item("okc", "POS", "ok", "Hazır", "Bağlantı hazır")
        return self.status_item("okc", "POS", "error", "Bağlantı yok", "POS cihazına ulaşılamıyor")

    def get_dashboard_token_bridge_status(self):
        cache_key = ("http_health", str(self.pos_ip or ""), int(self.pos_port or 0), str(self.pos_type or ""))
        cached = self.get_dashboard_probe_cache(cache_key)
        if cached is not None:
            return cached

        try:
            url = f"http://{self.pos_ip}:{self.pos_port}/health"
            with urllib.request.urlopen(url, timeout=DASHBOARD_STATUS_TIMEOUT_SECONDS) as response:
                payload = response.read(4096).decode("utf-8", errors="replace")
            data = json.loads(payload or "{}")
        except Exception as e:
            self.log_dashboard_probe_error(cache_key, f"Dashboard ÖKC bridge durumu alınamadı: {e}")
            result = self.status_item("okc", "ÖKC", "error", "Bağlantı yok", "Bridge yanıt vermiyor")
            self.set_dashboard_probe_cache(cache_key, result, DASHBOARD_STATUS_FAILURE_CACHE_SECONDS)
            return result

        device_state_known = data.get("deviceStateKnown")
        device_connected = data.get("deviceConnected")
        recovery_active = data.get("callbackRecoveryActive")
        try:
            uptime_seconds = int(data.get("uptimeSeconds") or 0)
        except (TypeError, ValueError):
            uptime_seconds = 0

        if device_state_known is True and device_connected is True:
            result = self.status_item("okc", "ÖKC", "ok", "Hazır", "Cihaz hazır")
            self.set_dashboard_probe_cache(cache_key, result, DASHBOARD_STATUS_CACHE_SECONDS)
            return result
        if device_state_known is True and device_connected is False:
            result = self.status_item("okc", "ÖKC", "error", "Cihaz yok", "ÖKC bağlantısı yok")
            self.set_dashboard_probe_cache(cache_key, result, DASHBOARD_STATUS_FAILURE_CACHE_SECONDS)
            return result
        if recovery_active or uptime_seconds < POSManager.TOKEN_BRIDGE_STARTUP_GRACE_SECONDS:
            result = self.status_item("okc", "ÖKC", "warn", "Başlatılıyor", "Cihaz bağlantısı bekleniyor")
            self.set_dashboard_probe_cache(cache_key, result, DASHBOARD_STATUS_CACHE_SECONDS)
            return result
        result = self.status_item("okc", "ÖKC", "warn", "Bekleniyor", "Cihaz durumu kesinleşmedi")
        self.set_dashboard_probe_cache(cache_key, result, DASHBOARD_STATUS_CACHE_SECONDS)
        return result

    def get_dashboard_printer_statuses(self):
        targets = [
            ("receipt", "Hesap", self.receipt_printer, self.direct_print)
        ]

        for panel_id in PREP_PANELS.keys():
            panel_info = self.get_prep_panel_info(panel_id)
            printer = self.prep_printers.get(panel_id, {})
            targets.append(
                (
                    f"prep_{panel_id}",
                    panel_info.get("name") or panel_id.title(),
                    printer,
                    False
                )
            )

        with ThreadPoolExecutor(max_workers=min(len(targets), 6)) as executor:
            return list(executor.map(
                lambda args: self.get_dashboard_printer_status(*args),
                targets
            ))

    def get_dashboard_printer_status(self, key, label, printer, local_print_enabled=False):
        printer = printer or {}
        if not printer.get("enabled"):
            if local_print_enabled:
                return self.status_item(key, label, "ok", "Yerel", "Yerel yazdırma açık")
            return self.status_item(key, label, "off", "Kapalı", "Yazıcı kapalı")

        host = str(printer.get("ip") or "").strip()
        port = printer.get("port") or 9100
        if not host:
            return self.status_item(key, label, "warn", "Ayar eksik", "Yazıcı adresi eksik")

        if self.probe_tcp_service(host, port):
            return self.status_item(key, label, "ok", "Online", "Yazıcı hazır")
        return self.status_item(key, label, "error", "Bağlantı yok", "Yazıcıya ulaşılamıyor")

    def probe_tcp_service(self, host, port, timeout=DASHBOARD_STATUS_TIMEOUT_SECONDS):
        cache_key = ("tcp", str(host or ""), int(port or 0))
        cached = self.get_dashboard_probe_cache(cache_key)
        if cached is not None:
            return bool(cached)

        try:
            with socket.create_connection((str(host), int(port)), timeout=timeout):
                self.set_dashboard_probe_cache(cache_key, True, DASHBOARD_STATUS_CACHE_SECONDS)
                return True
        except Exception as e:
            self.log_dashboard_probe_error(cache_key, f"Dashboard TCP kontrolü başarısız: {host}:{port} - {e}")
            self.set_dashboard_probe_cache(cache_key, False, DASHBOARD_STATUS_FAILURE_CACHE_SECONDS)
            return False

    def get_dashboard_probe_cache(self, key):
        now = time.monotonic()
        with self.dashboard_status_lock:
            entry = self.dashboard_probe_cache.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at <= now:
                self.dashboard_probe_cache.pop(key, None)
                return None
            return copy.deepcopy(value)

    def set_dashboard_probe_cache(self, key, value, ttl_seconds):
        with self.dashboard_status_lock:
            self.dashboard_probe_cache[key] = (
                time.monotonic() + max(1, float(ttl_seconds or 1)),
                copy.deepcopy(value)
            )

    def log_dashboard_probe_error(self, key, message):
        now = time.monotonic()
        with self.dashboard_status_lock:
            last_logged = self.dashboard_error_log_times.get(key, 0)
            if now - last_logged < DASHBOARD_STATUS_ERROR_LOG_SECONDS:
                return
            self.dashboard_error_log_times[key] = now
        logger.warning(message)

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

    # ==================== AUTH / USER MANAGEMENT ====================

    def get_auth_page_definitions(self):
        return {
            key: {
                "key": key,
                "label": info.get("label", key),
                "paths": info.get("paths", []),
                "prefixes": info.get("prefixes", []),
            }
            for key, info in AUTH_PAGE_DEFINITIONS.items()
        }

    def get_auth_role_definitions(self):
        return {
            key: {
                "key": key,
                "label": info.get("label", key),
                "level": int(info.get("level", 0)),
                "permissions": list(info.get("permissions", [])),
            }
            for key, info in AUTH_ROLE_DEFINITIONS.items()
        }

    def get_role_permissions(self, role):
        role_info = AUTH_ROLE_DEFINITIONS.get(role) or AUTH_ROLE_DEFINITIONS["waiter"]
        permissions = role_info.get("permissions", [])
        if "*" in permissions:
            return ["*"]
        valid_pages = set(AUTH_PAGE_DEFINITIONS.keys())
        return [p for p in permissions if p in valid_pages]

    def get_role_level(self, role):
        return int((AUTH_ROLE_DEFINITIONS.get(role) or {}).get("level", 0))

    def normalize_permissions(self, permissions, role):
        if permissions == "*" or permissions == ["*"]:
            return ["*"]
        valid_pages = set(AUTH_PAGE_DEFINITIONS.keys())
        if not isinstance(permissions, list):
            permissions = self.get_role_permissions(role)
        cleaned = []
        for page in permissions:
            page = str(page or "").strip()
            if page in valid_pages and page not in cleaned:
                cleaned.append(page)
        return cleaned or self.get_role_permissions(role)

    @staticmethod
    def auth_user_name_key(name):
        return str(name or "").strip().lower()

    def build_staff_auth_user(self, staff, role, source, default_pin=""):
        staff = staff if isinstance(staff, dict) else {"name": staff}
        name = str(staff.get("name") or staff.get("ad") or "").strip()
        if not name:
            return None
        pin = staff.get("pin")
        if pin is None:
            pin = default_pin
        stable_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"fastfoot:{source}:{name.lower()}")
        return {
            "id": f"{source}-{stable_id.hex}",
            "name": name,
            "pin": str(pin or ""),
            "role": role,
            "active": True,
            "permissions": self.get_role_permissions(role),
            "schedule": {"enabled": False},
        }

    def add_missing_staff_auth_users(self, users, seen_names):
        added = 0
        staff_sources = (
            (self.waiters, "waiter", "waiter", ""),
            (self.cashiers, "cashier", "cashier", "0000"),
            (self.kitchen, "kitchen", "kitchen", "0000"),
        )
        for staff_list, role, source, default_pin in staff_sources:
            for staff in staff_list:
                raw_user = self.build_staff_auth_user(staff, role, source, default_pin)
                if not raw_user:
                    continue
                key = self.auth_user_name_key(raw_user.get("name"))
                if key in seen_names:
                    continue
                user = self.normalize_user(raw_user)
                if not user:
                    continue
                users.append(user)
                seen_names.add(key)
                added += 1
        return added

    def sync_staff_auth_user(self, name, pin, role, source):
        name = str(name or "").strip()
        if not name:
            return None, "Kullanıcı adı gerekli"

        existing = self.find_user(name=name)
        payload = {
            "name": name,
            "pin": str(pin or ""),
            "role": role,
            "active": True,
            "permissions": self.get_role_permissions(role),
            "schedule": {"enabled": False},
        }

        if existing:
            if existing.get("role") == "admin" or existing.get("role") != role:
                return existing, None

            payload.update({
                "id": existing.get("id"),
                "permissions": existing.get("permissions") or self.get_role_permissions(role),
                "schedule": existing.get("schedule") or {"enabled": False},
            })

        return self.upsert_user(payload)

    def staff_list_for_source(self, source):
        if source == "waiter":
            return self.waiters
        if source == "cashier":
            return self.cashiers
        if source == "kitchen":
            return self.kitchen
        return []

    def save_staff_list_for_source(self, source):
        if source == "waiter":
            return self.save_waiters()
        if source == "cashier":
            return self.save_cashiers()
        if source == "kitchen":
            return self.save_kitchen()
        return False

    def staff_source_for_role(self, role):
        role_sources = {
            "waiter": "waiter",
            "cashier": "cashier",
            "kitchen": "kitchen",
        }
        return role_sources.get(role)

    def staff_record_exists(self, name, source):
        name_key = self.auth_user_name_key(name)
        if not name_key:
            return False
        for staff in self.staff_list_for_source(source):
            staff = staff if isinstance(staff, dict) else {"name": staff}
            staff_name = staff.get("name") or staff.get("ad")
            if self.auth_user_name_key(staff_name) == name_key:
                return True
        return False

    def upsert_staff_record_for_user(self, user, pin=None):
        source = self.staff_source_for_role(user.get("role"))
        if not source or not user.get("active", True):
            return False

        name = str(user.get("name") or "").strip()
        if not name:
            return False

        staff_list = self.staff_list_for_source(source)
        name_key = self.auth_user_name_key(name)
        for staff in staff_list:
            if not isinstance(staff, dict):
                continue
            staff_name = staff.get("name") or staff.get("ad")
            if self.auth_user_name_key(staff_name) == name_key:
                staff["name"] = name
                if pin:
                    staff["pin"] = str(pin)
                self.save_staff_list_for_source(source)
                return True

        staff = {"name": name}
        if pin:
            staff["pin"] = str(pin)
        staff_list.append(staff)
        self.save_staff_list_for_source(source)
        return True

    def remove_staff_record_by_name(self, name, source):
        name_key = self.auth_user_name_key(name)
        if not name_key:
            return False

        staff_list = self.staff_list_for_source(source)
        kept = []
        removed = False
        for staff in staff_list:
            staff_obj = staff if isinstance(staff, dict) else {"name": staff}
            staff_name = staff_obj.get("name") or staff_obj.get("ad")
            if self.auth_user_name_key(staff_name) == name_key:
                removed = True
                continue
            kept.append(staff)

        if not removed:
            return False

        if source == "waiter":
            self.waiters = kept
        elif source == "cashier":
            self.cashiers = kept
        elif source == "kitchen":
            self.kitchen = kept
        self.save_staff_list_for_source(source)
        return True

    def sync_staff_record_after_user_save(self, user, previous_user=None, pin=None):
        if previous_user:
            previous_source = self.staff_source_for_role(previous_user.get("role"))
            current_source = self.staff_source_for_role(user.get("role"))
            name_changed = self.auth_user_name_key(previous_user.get("name")) != self.auth_user_name_key(user.get("name"))
            if previous_source and (previous_source != current_source or name_changed or not user.get("active", True)):
                self.remove_staff_record_by_name(previous_user.get("name"), previous_source)

        self.upsert_staff_record_for_user(user, pin=pin)

    def sync_staff_lists_from_auth_users(self):
        for user in self.users:
            self.sync_staff_record_after_user_save(user)

    def is_orphaned_staff_auth_user(self, user):
        if not user:
            return False
        staff_roles = {
            "waiter": "waiter",
            "cashier": "cashier",
            "kitchen": "kitchen",
        }
        for source, role in staff_roles.items():
            if user.get("role") == role:
                return not self.staff_record_exists(user.get("name"), source)
        return False

    def delete_staff_auth_user(self, name, role):
        name_key = self.auth_user_name_key(name)
        if not name_key:
            return 0

        removed_ids = []
        kept_users = []
        for user in self.users:
            same_name = self.auth_user_name_key(user.get("name")) == name_key
            same_staff_role = user.get("role") == role
            should_remove = same_name and same_staff_role and user.get("role") != "admin"
            if should_remove:
                removed_ids.append(user.get("id"))
            else:
                kept_users.append(user)

        if not removed_ids:
            return 0

        self.users = kept_users
        for token_hash, session in list(self.auth_sessions.items()):
            if session.get("user_id") in removed_ids:
                self.auth_sessions.pop(token_hash, None)
        self.save_users()
        self.save_auth_sessions()
        return len(removed_ids)

    def normalize_schedule(self, schedule=None):
        schedule = schedule if isinstance(schedule, dict) else {}
        days = schedule.get("days")
        if not isinstance(days, list):
            days = list(range(7))
        clean_days = []
        for day in days:
            try:
                day_int = int(day)
            except Exception:
                continue
            if 0 <= day_int <= 6 and day_int not in clean_days:
                clean_days.append(day_int)
        return {
            "enabled": bool(schedule.get("enabled", False)),
            "days": clean_days or list(range(7)),
            "start": self.normalize_time_string(schedule.get("start"), "00:00"),
            "end": self.normalize_time_string(schedule.get("end"), "23:59"),
        }

    @staticmethod
    def normalize_time_string(value, fallback="00:00"):
        value = str(value or "").strip()
        match = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", value)
        if not match:
            return fallback
        return f"{int(match.group(1)):02d}:{match.group(2)}"

    def hash_pin(self, pin, salt=None):
        salt = salt or secrets.token_hex(12)
        raw = f"{salt}:{pin}:{app.config['SECRET_KEY']}".encode("utf-8")
        return salt, hashlib.sha256(raw).hexdigest()

    def normalize_user(self, raw, fallback_role="waiter"):
        raw = raw if isinstance(raw, dict) else {}
        name = str(raw.get("name") or raw.get("username") or "").strip()
        if not name:
            return None
        role = str(raw.get("role") or fallback_role or "waiter").strip()
        if role not in AUTH_ROLE_DEFINITIONS:
            role = "waiter"

        user = {
            "id": str(raw.get("id") or uuid.uuid4()),
            "name": name,
            "role": role,
            "active": bool(raw.get("active", True)),
            "permissions": self.normalize_permissions(raw.get("permissions"), role),
            "schedule": self.normalize_schedule(raw.get("schedule")),
            "created_at": raw.get("created_at") or datetime.datetime.now().isoformat(timespec="seconds"),
            "updated_at": raw.get("updated_at") or datetime.datetime.now().isoformat(timespec="seconds"),
        }

        if raw.get("pin_hash") and raw.get("pin_salt"):
            user["pin_hash"] = raw.get("pin_hash")
            user["pin_salt"] = raw.get("pin_salt")
        elif raw.get("pin") is not None:
            salt, pin_hash = self.hash_pin(str(raw.get("pin")))
            user["pin_hash"] = pin_hash
            user["pin_salt"] = salt
        else:
            user["pin_hash"] = raw.get("pin_hash", "")
            user["pin_salt"] = raw.get("pin_salt", "")

        return user

    def build_default_users(self):
        users = [
            {
                "id": "bootstrap-admin",
                "name": "Yönetici",
                "pin": self.admin_password,
                "role": "admin",
                "active": True,
                "permissions": ["*"],
                "schedule": {"enabled": False},
            }
        ]

        existing_names = {"yönetici"}
        for waiter in self.waiters:
            user = self.build_staff_auth_user(waiter, "waiter", "waiter")
            if not user:
                continue
            key = self.auth_user_name_key(user.get("name"))
            if key in existing_names:
                continue
            existing_names.add(key)
            users.append(user)

        for cashier in self.cashiers:
            user = self.build_staff_auth_user(cashier, "cashier", "cashier", "0000")
            if not user:
                continue
            key = self.auth_user_name_key(user.get("name"))
            if key in existing_names:
                continue
            existing_names.add(key)
            users.append(user)

        for cook in self.kitchen:
            user = self.build_staff_auth_user(cook, "kitchen", "kitchen", "0000")
            if not user:
                continue
            key = self.auth_user_name_key(user.get("name"))
            if key in existing_names:
                continue
            existing_names.add(key)
            users.append(user)

        return users

    def load_users(self):
        raw_users = []
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    raw_users = json.load(f)
            except Exception as e:
                logger.error(f"Kullanıcı yükleme hatası: {e}")
                raw_users = []
        else:
            raw_users = self.build_default_users()

        normalized = []
        seen_names = set()
        for raw in raw_users if isinstance(raw_users, list) else []:
            user = self.normalize_user(raw)
            if not user:
                continue
            key = self.auth_user_name_key(user["name"])
            if key in seen_names:
                continue
            seen_names.add(key)
            normalized.append(user)

        if not any(u.get("role") == "admin" for u in normalized):
            admin = self.normalize_user({
                "id": "bootstrap-admin",
                "name": "Yönetici",
                "pin": self.admin_password,
                "role": "admin",
                "permissions": ["*"],
                "active": True,
            })
            if admin:
                normalized.insert(0, admin)
                seen_names.add(self.auth_user_name_key(admin.get("name")))

        added_staff_users = self.add_missing_staff_auth_users(normalized, seen_names)

        self.users = sorted(
            normalized,
            key=lambda u: (-self.get_role_level(u.get("role")), u.get("name", "").lower())
        )
        self.sync_staff_lists_from_auth_users()
        if added_staff_users and os.path.exists(USERS_FILE):
            self.save_users()
            logger.info(f"✓ {added_staff_users} personel yetki kullanıcısı eklendi")
        logger.info(f"✓ {len(self.users)} kullanıcı/yetki yüklendi")

    def save_users(self):
        try:
            now = datetime.datetime.now().isoformat(timespec="seconds")
            for user in self.users:
                user["updated_at"] = now
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            logger.info("✓ Kullanıcı/yetki ayarları kaydedildi")
            return True
        except Exception as e:
            logger.error(f"Kullanıcı kaydetme hatası: {e}")
            return False

    def sync_admin_password_to_auth_user(self, pin):
        """Legacy ayar şifresi değişince varsayılan Yönetici PIN'ini de güncelle."""
        pin = str(pin or "")
        updated = False
        for user in self.users:
            if user.get("role") != "admin":
                continue
            is_default_admin = (
                user.get("id") == "bootstrap-admin"
                or self.auth_user_name_key(user.get("name")) == "yönetici"
            )
            if not is_default_admin:
                continue
            salt, pin_hash = self.hash_pin(pin)
            user["pin_salt"] = salt
            user["pin_hash"] = pin_hash
            updated = True

        if not updated:
            return True
        return self.save_users()

    def public_user(self, user, include_permissions=True):
        if not user:
            return None
        data = {
            "id": user.get("id"),
            "name": user.get("name"),
            "role": user.get("role"),
            "role_label": AUTH_ROLE_DEFINITIONS.get(user.get("role"), {}).get("label", user.get("role")),
            "level": self.get_role_level(user.get("role")),
            "active": bool(user.get("active", True)),
            "schedule": user.get("schedule") or self.normalize_schedule(),
        }
        if include_permissions:
            data["permissions"] = list(user.get("permissions") or [])
        return data

    def list_login_users(self):
        return [
            self.public_user(user, include_permissions=False)
            for user in self.users
            if user.get("active", True)
        ]

    def find_user(self, user_id=None, name=None):
        if user_id:
            for user in self.users:
                if str(user.get("id")) == str(user_id):
                    return user
        if name:
            wanted = str(name).strip().lower()
            for user in self.users:
                if str(user.get("name", "")).strip().lower() == wanted:
                    return user
        return None

    def verify_user_pin(self, user, pin):
        if not user:
            return False
        pin = str(pin or "")
        if user.get("pin_hash") and user.get("pin_salt"):
            _, pin_hash = self.hash_pin(pin, user.get("pin_salt"))
            return hmac.compare_digest(pin_hash, user.get("pin_hash"))
        return hmac.compare_digest(str(user.get("pin", "")), pin)

    def user_schedule_allowed(self, user, now=None):
        if not user or not user.get("active", True):
            return False, "Kullanıcı pasif"
        schedule = self.normalize_schedule(user.get("schedule"))
        if not schedule.get("enabled"):
            return True, None

        now = now or datetime.datetime.now()
        start = datetime.datetime.strptime(schedule["start"], "%H:%M").time()
        end = datetime.datetime.strptime(schedule["end"], "%H:%M").time()
        current = now.time()
        today = now.weekday()
        yesterday = (today - 1) % 7
        days = set(schedule.get("days") or [])

        if start <= end:
            allowed = today in days and start <= current <= end
        else:
            allowed = (today in days and current >= start) or (yesterday in days and current <= end)
        if allowed:
            return True, None
        return False, "Bu kullanıcı için giriş saati dışında"

    def user_has_permission(self, user, page_key):
        if not page_key:
            return True
        if not user or not user.get("active", True):
            return False
        if page_key in ADMIN_ONLY_PAGE_KEYS:
            return user.get("role") == "admin"
        permissions = user.get("permissions") or self.get_role_permissions(user.get("role"))
        return "*" in permissions or page_key in permissions

    def required_page_for_path(self, path):
        path = (path or "/").split("?", 1)[0]
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")
        if path in AUTH_PATH_TO_PAGE:
            return AUTH_PATH_TO_PAGE[path]
        for prefix, page_key in AUTH_PREFIX_TO_PAGE:
            if path.startswith(prefix):
                return page_key
        if path.startswith("/api/"):
            if request.method == "GET" and path in ("/api/waiters", "/api/cashiers", "/api/kitchen", "/api/couriers"):
                return None
            for prefix, page_key in AUTH_API_PREFIX_PERMISSIONS:
                if path == prefix or path.startswith(prefix + "/"):
                    return page_key
            return None
        return None

    def is_public_request_path(self, path):
        path = path or "/"
        if path == "/api/public/policy/update":
            return False
        for prefix in AUTH_PUBLIC_PATH_PREFIXES:
            if prefix.endswith("/"):
                if path.startswith(prefix):
                    return True
            elif path == prefix:
                return True
        ext = os.path.splitext(path)[1].lower()
        return ext in AUTH_PUBLIC_STATIC_EXTENSIONS

    @staticmethod
    def normalize_local_path(value, fallback="/"):
        value = str(value or "").strip() or fallback
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme or parsed.netloc:
            return fallback
        path = parsed.path or fallback
        if not path.startswith("/"):
            path = "/" + path
        if parsed.query:
            path = f"{path}?{parsed.query}"
        return path

    def authenticate_login(self, name, pin, requested_path="/"):
        requested_path = self.normalize_local_path(requested_path)
        user = self.find_user(name=name)
        if not user or not self.verify_user_pin(user, pin):
            return None, "Kullanıcı adı veya PIN hatalı"
        allowed, reason = self.user_schedule_allowed(user)
        if not allowed:
            return None, reason
        return user, None

    def get_user_landing_page(self, user):
        """Kullanıcının yetkili olduğu ilk sayfanın yolunu döndür."""
        permissions = user.get("permissions") or self.get_role_permissions(user.get("role"))
        if "*" in permissions:
            return "/"
        # Rol tanımındaki izin sırasına göre ilk yetkili sayfayı bul
        for perm in permissions:
            page_info = AUTH_PAGE_DEFINITIONS.get(perm)
            if page_info:
                paths = page_info.get("paths", [])
                if paths:
                    return paths[0]
        return "/"

    def hash_auth_token(self, token):
        return hmac.new(
            app.config["SECRET_KEY"].encode("utf-8"),
            str(token or "").encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def load_auth_sessions(self):
        self.auth_sessions = {}
        if not os.path.exists(AUTH_SESSIONS_FILE):
            return
        try:
            with open(AUTH_SESSIONS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            now_ts = time.time()
            for token_hash, session in (raw if isinstance(raw, dict) else {}).items():
                if float(session.get("expires_at", 0)) > now_ts:
                    self.auth_sessions[token_hash] = session
        except Exception as e:
            logger.error(f"Oturum yükleme hatası: {e}")
            self.auth_sessions = {}

    def save_auth_sessions(self):
        try:
            now_ts = time.time()
            active = {
                token_hash: session
                for token_hash, session in self.auth_sessions.items()
                if float(session.get("expires_at", 0)) > now_ts
            }
            self.auth_sessions = active
            with open(AUTH_SESSIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(active, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Oturum kaydetme hatası: {e}")
            return False

    def create_auth_session(self, user, remember=True, device_name="", ip="", user_agent=""):
        token = secrets.token_urlsafe(32)
        token_hash = self.hash_auth_token(token)
        now_ts = time.time()
        max_age = AUTH_SESSION_DAYS * 24 * 60 * 60 if remember else 12 * 60 * 60
        self.auth_sessions[token_hash] = {
            "user_id": user.get("id"),
            "created_at": now_ts,
            "last_seen_at": now_ts,
            "expires_at": now_ts + max_age,
            "remember": bool(remember),
            "device_name": str(device_name or "")[:80],
            "ip": str(ip or "")[:80],
            "user_agent": str(user_agent or "")[:240],
        }
        self.save_auth_sessions()
        return token, max_age

    def revoke_auth_session(self, token):
        token_hash = self.hash_auth_token(token)
        removed = self.auth_sessions.pop(token_hash, None) is not None
        if removed:
            self.save_auth_sessions()
        return removed

    def validate_auth_token(self, token, required_page=None):
        if not token:
            return None, "Oturum bulunamadı", 401
        token_hash = self.hash_auth_token(token)
        session = self.auth_sessions.get(token_hash)
        if not session:
            return None, "Oturum geçersiz veya süresi dolmuş", 401
        if float(session.get("expires_at", 0)) <= time.time():
            self.auth_sessions.pop(token_hash, None)
            self.save_auth_sessions()
            return None, "Oturum süresi dolmuş", 401

        user = self.find_user(user_id=session.get("user_id"))
        if not user:
            return None, "Kullanıcı bulunamadı", 401

        allowed, reason = self.user_schedule_allowed(user)
        if not allowed:
            return None, reason, 403

        if required_page and not self.user_has_permission(user, required_page):
            page_label = AUTH_PAGE_DEFINITIONS.get(required_page, {}).get("label", required_page)
            return None, f"Bu kullanıcının {page_label} yetkisi yok", 403

        now_ts = time.time()
        if now_ts - float(session.get("last_seen_at", 0)) > 120:
            session["last_seen_at"] = now_ts
        return user, None, 200

    def get_request_token(self):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            return auth_header.split(" ", 1)[1].strip()
        return request.cookies.get(AUTH_COOKIE_NAME, "")

    def validate_current_request(self, required_page=None):
        return self.validate_auth_token(self.get_request_token(), required_page=required_page)

    def get_socket_user(self, sid, required_pages=None):
        info = self.active_connections.get(sid) or {}
        user = self.find_user(user_id=info.get("user_id"))
        if not user:
            return None, "Oturum bulunamadı"
        allowed, reason = self.user_schedule_allowed(user)
        if not allowed:
            return None, reason
        if required_pages:
            if isinstance(required_pages, str):
                required_pages = [required_pages]
            if not any(self.user_has_permission(user, page) for page in required_pages):
                return None, "Bu işlem için yetkiniz yok"
        return user, None

    def can_manage_user(self, actor, target_role):
        if not actor:
            return False
        actor_role = actor.get("role")
        if actor_role == "admin":
            return True
        return self.get_role_level(actor_role) > self.get_role_level(target_role)

    def upsert_user(self, data, actor=None):
        data = data if isinstance(data, dict) else {}
        user_id = str(data.get("id") or "").strip()
        existing = self.find_user(user_id=user_id) if user_id else None
        role = str(data.get("role") or (existing or {}).get("role") or "waiter")
        if role not in AUTH_ROLE_DEFINITIONS:
            role = "waiter"
        if actor and not self.can_manage_user(actor, role):
            return None, "Bu yetki seviyesindeki kullanıcıyı düzenleyemezsiniz"

        name = str(data.get("name") or (existing or {}).get("name") or "").strip()
        if not name:
            return None, "Kullanıcı adı gerekli"
        duplicate = self.find_user(name=name)
        if duplicate and (not existing or duplicate.get("id") != existing.get("id")):
            if not existing and self.is_orphaned_staff_auth_user(duplicate):
                existing = duplicate
                user_id = str(duplicate.get("id") or "")
            else:
                return None, "Bu isimde bir kullanıcı zaten var"

        previous_user = dict(existing) if existing else None
        raw = dict(existing or {})
        raw.update({
            "id": user_id or raw.get("id") or str(uuid.uuid4()),
            "name": name,
            "role": role,
            "active": bool(data.get("active", raw.get("active", True))),
            "permissions": self.normalize_permissions(data.get("permissions"), role),
            "schedule": self.normalize_schedule(data.get("schedule")),
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        })
        if data.get("pin"):
            salt, pin_hash = self.hash_pin(str(data.get("pin")))
            raw["pin_salt"] = salt
            raw["pin_hash"] = pin_hash
        elif not existing:
            return None, "Yeni kullanıcı için PIN gerekli"

        user = self.normalize_user(raw)
        if not user:
            return None, "Kullanıcı oluşturulamadı"

        if existing:
            idx = self.users.index(existing)
            self.users[idx] = user
        else:
            self.users.append(user)
        self.users = sorted(
            self.users,
            key=lambda u: (-self.get_role_level(u.get("role")), u.get("name", "").lower())
        )
        self.save_users()
        self.sync_staff_record_after_user_save(user, previous_user=previous_user, pin=data.get("pin"))
        return user, None

    def delete_user(self, user_id, actor=None):
        user = self.find_user(user_id=user_id)
        if not user:
            return False, "Kullanıcı bulunamadı"
        if actor and actor.get("id") == user.get("id"):
            return False, "Kendi kullanıcınızı silemezsiniz"
        if actor and not self.can_manage_user(actor, user.get("role")):
            return False, "Bu yetki seviyesindeki kullanıcıyı silemezsiniz"
        if user.get("role") == "admin" and sum(1 for u in self.users if u.get("role") == "admin") <= 1:
            return False, "Son yönetici kullanıcısı silinemez"
        source = self.staff_source_for_role(user.get("role"))
        if source:
            self.remove_staff_record_by_name(user.get("name"), source)
        self.users = [u for u in self.users if u.get("id") != user.get("id")]
        for token_hash, session in list(self.auth_sessions.items()):
            if session.get("user_id") == user.get("id"):
                self.auth_sessions.pop(token_hash, None)
        self.save_users()
        self.save_auth_sessions()
        return True, None
            
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

    def ticket_upper(self, value):
        """Türkçe karakterleri koruyarak termal fiş için büyük harfe çevir."""
        text = str(value or "")
        translation = str.maketrans({
            "i": "İ",
            "ı": "I",
            "ğ": "Ğ",
            "ü": "Ü",
            "ş": "Ş",
            "ö": "Ö",
            "ç": "Ç",
        })
        return text.translate(translation).upper()

    def get_section_name_for_adisyon(self, masa_adi):
        table_name = str(masa_adi or "").strip()
        table_key = self.normalize_ticket_table_name(table_name)
        for salon in self.salons:
            if table_name in salon.get("tables", []):
                return salon.get("name") or "Bölüm"
            if any(self.normalize_ticket_table_name(table) == table_key for table in salon.get("tables", [])):
                return salon.get("name") or "Bölüm"
        normalized = table_name.lower()
        if normalized.startswith("paket"):
            return "Paket"
        if normalized.startswith("online"):
            return "Online"
        prefix_match = re.match(r"^([A-ZÇĞİÖŞÜ]+)\d+$", table_key)
        fallback_sections = {
            "D": "Bahçe",
            "E": "Bahçe",
            "F": "Bahçe",
            "A": "Ana Salon",
            "B": "Ana Salon",
            "C": "Ana Salon",
            "P": "Ana Salon",
            "T": "Teras",
            "V": "Vip",
        }
        if prefix_match:
            section = fallback_sections.get(prefix_match.group(1))
            if section:
                return section
        return "Genel"

    def normalize_ticket_table_name(self, masa_adi):
        text = str(masa_adi or "").strip().upper().replace(" ", "")
        match = re.match(r"^([A-ZÇĞİÖŞÜ]+)0*(\d+)$", text)
        if match:
            return f"{match.group(1)}{int(match.group(2))}"
        return text

    def display_table_name_for_ticket(self, masa_adi):
        text = str(masa_adi or "").strip()
        match = re.match(r"^([A-Za-zÇĞİÖŞÜçğıöşü]+)0+(\d+)$", text)
        if match:
            return f"{match.group(1)}{int(match.group(2))}"
        return text

    def clean_prep_ticket_note(self, note):
        text = str(note or "").strip()
        return re.sub(r'^(not|yemek|çeşit|cesit)\s*:\s*', '', text, flags=re.IGNORECASE).strip()

    def split_order_note_details(self, note):
        """Günlük yemek çeşidini kalem notlarından ayır."""
        text = str(note or "").strip()
        if not text:
            return "", ""

        meal_name = ""
        note_parts = []
        for line in re.split(r'[\r\n]+', text):
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(yemek|çeşit|cesit)\s*:\s*(.+)$', line, flags=re.IGNORECASE)
            if match and not meal_name:
                value = match.group(2).strip()
                split_value = re.split(r'\s*[|•]\s*', value, maxsplit=1)
                meal_name = split_value[0].strip()
                if len(split_value) > 1 and split_value[1].strip():
                    note_parts.append(split_value[1].strip())
                continue

            cleaned = self.clean_prep_ticket_note(line)
            if cleaned:
                note_parts.append(cleaned)

        return meal_name, " / ".join(note_parts)

    def prep_ticket_portion_label(self, value):
        amount = self.coerce_order_quantity(value, default=0)
        if abs(amount - 0.5) < 0.001:
            return "Yarım Porsiyon"
        if abs(amount - 1) < 0.001:
            return "Tam Porsiyon"
        if abs(amount - 1.5) < 0.001:
            return "Bir Buçuk Porsiyon"
        return ""

    def prep_ticket_explicit_portion_info(self, urun):
        name = str(urun or "").strip()
        match = re.match(r'^(tam|yarım|yarim)\s+porsiyon\s+(.+)$', name, flags=re.IGNORECASE)
        if match:
            label = "Yarım Porsiyon" if self._normalize_text_for_match(match.group(1)) == "yarim" else "Tam Porsiyon"
            return label, match.group(2).strip()

        match = re.match(r'^(tam|yarım|yarim)\s+(.+)$', name, flags=re.IGNORECASE)
        if match:
            label = "Yarım Porsiyon" if self._normalize_text_for_match(match.group(1)) == "yarim" else "Tam Porsiyon"
            return label, match.group(2).strip()

        match = re.search(r'\(\s*(\d+(?:[,.]\d+)?)\s*porsiyon\s*\)\s*$', name, flags=re.IGNORECASE)
        if match:
            label = self.prep_ticket_portion_label(match.group(1).replace(',', '.'))
            if label:
                base_name = re.sub(r'\(\s*\d+(?:[,.]\d+)?\s*porsiyon\s*\)\s*$', '', name, flags=re.IGNORECASE).strip()
                return label, base_name
        return "", name

    def prep_ticket_portion_display_name(self, portion_label, base_name):
        name = str(base_name or "").strip()
        label_key = self._normalize_text_for_match(portion_label)
        if label_key.startswith("tam"):
            return name
        if label_key.startswith("yarim"):
            if self._normalize_text_for_match(name).startswith("yarim "):
                return name
            return f"Yarım {name}".strip()
        if label_key.startswith("bir bucuk"):
            if self._normalize_text_for_match(name).startswith("bir bucuk "):
                return name
            return f"Bir Buçuk {name}".strip()
        label = re.sub(r'\s+porsiyon\s*$', '', str(portion_label or "").strip(), flags=re.IGNORECASE)
        return f"{label} {name}".strip() if label else name

    def prep_ticket_meal_display_name(self, urun, meal_name):
        meal_label, meal_base_name = self.prep_ticket_explicit_portion_info(meal_name)
        if meal_label and meal_base_name:
            return self.prep_ticket_portion_display_name(meal_label, meal_base_name)

        label, _ = self.prep_ticket_explicit_portion_info(urun)
        if label:
            return self.prep_ticket_portion_display_name(label, meal_name)

        return str(meal_name or "").strip()

    def is_dynamic_prep_portion_order(self, raw, urun, adet):
        if not self.prep_ticket_portion_label(adet):
            return False
        panel = str(raw.get("panel") or "").strip()
        kategori = raw.get("kategori")
        if not panel:
            panel = self.get_preparation_panel_for_product(urun, kategori)
        return panel == "izgara"

    def prep_ticket_display_item(self, raw, urun, adet):
        label, base_name = self.prep_ticket_explicit_portion_info(urun)
        if label and base_name:
            return self.prep_ticket_portion_display_name(label, base_name), adet

        if self.is_dynamic_prep_portion_order(raw, urun, adet):
            label = self.prep_ticket_portion_label(adet)
            return self.prep_ticket_portion_display_name(label, urun), 1

        return urun, adet

    def prep_ticket_group_value(self, value):
        return re.sub(r"\s+", " ", self._normalize_text_for_match(value)).strip()

    def prep_ticket_item_group_key(self, raw, display_urun, note):
        category = str(raw.get("kategori") or "").strip()
        if not category:
            category = self.get_menu_category_for_product(raw.get("urun"))
        panel = str(raw.get("panel") or "").strip()
        return (
            self.prep_ticket_group_value(panel),
            self.prep_ticket_group_value(category),
            self.prep_ticket_group_value(display_urun),
            self.prep_ticket_group_value(note),
        )

    def prep_ticket_item_title(self, item):
        if item.get("separator"):
            return "-" * 32
        heading = str(item.get("heading") or "").strip()
        if heading:
            return heading
        adet = self.format_order_quantity(item.get("adet", 1))
        urun = str(item.get("urun") or "").strip()
        note = str(item.get("not") or "").strip()
        detail = f"{urun} {note}".strip() if note else urun
        return f"{adet} x {detail}".strip()

    def prep_ticket_same_plate_heading(self, detail):
        text = str(detail or "").strip()
        match = re.match(r"^(?:tek\s+tabak|tabak)\s+(#\S+)$", text, flags=re.IGNORECASE)
        if match:
            return f"AYNI TABAK {match.group(1)}"
        return f"AYNI TABAK: {text}" if text else ""

    def extract_meal_name_from_note(self, note):
        """Not alanında 'Yemek: xxx' formatı varsa yemek adını döndür."""
        meal_name, _ = self.split_order_note_details(note)
        return meal_name or None

    def prep_ticket_items(self, order_data):
        raw_items = order_data.get("items")
        has_child_items = isinstance(raw_items, list) and bool(raw_items)
        if not has_child_items:
            raw_items = [order_data]

        def raw_plate_group(raw):
            if isinstance(raw.get("plate_group"), dict):
                return raw.get("plate_group")
            if not has_child_items and isinstance(order_data.get("plate_group"), dict):
                return order_data.get("plate_group")
            return None

        def raw_plate_heading(raw):
            plate = raw_plate_group(raw)
            plate_label = self.plate_group_label(plate)
            if not plate_label:
                return ""
            plate_note = str(plate.get("note") or "").strip() if isinstance(plate, dict) else ""
            return " / ".join(part for part in [plate_label, plate_note] if part)

        has_plate_items = any(
            isinstance(raw, dict) and str(raw.get("urun") or "").strip() and raw_plate_heading(raw)
            for raw in raw_items
        )

        sections = []
        section_map = {}

        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            urun = str(raw.get("urun") or "").strip()
            if not urun:
                continue
            plate_heading = raw_plate_heading(raw)
            section_key = f"plate:{self.prep_ticket_group_value(plate_heading)}" if plate_heading else "normal"
            if section_key not in section_map:
                heading = self.prep_ticket_same_plate_heading(plate_heading) if plate_heading else ("AYRI SERVİS" if has_plate_items else "")
                section_map[section_key] = {
                    "heading": heading,
                    "is_plate": bool(plate_heading),
                    "items": [],
                    "grouped_index": {}
                }
                sections.append(section_map[section_key])

            raw_note = str(raw.get("not") or "").strip()
            meal_name, extra_note = self.split_order_note_details(raw_note)
            adet = self.coerce_order_quantity(raw.get("adet", 1))
            raw_with_context = dict(raw)
            if not raw_with_context.get("kategori"):
                raw_with_context["kategori"] = order_data.get("kategori") or self.get_menu_category_for_product(urun)
            if not raw_with_context.get("panel"):
                raw_with_context["panel"] = (
                    order_data.get("panel")
                    or self.get_preparation_panel_for_product(urun, raw_with_context.get("kategori"))
                )

            if meal_name:
                # Tam porsiyon yazısını fişte sadeleştir, yarım gibi hazırlık bilgisini koru.
                display_urun = self.prep_ticket_meal_display_name(urun, meal_name)
                display_adet = adet
                note = extra_note
            else:
                display_urun, display_adet = self.prep_ticket_display_item(raw_with_context, urun, adet)
                note = self.clean_prep_ticket_note(raw_note)

            if (
                plate_heading
                and self.prep_ticket_group_value(display_urun) == self.prep_ticket_group_value(plate_heading)
                and not note
            ):
                continue

            section = section_map[section_key]
            key = self.prep_ticket_item_group_key(raw_with_context, display_urun, note)
            if key in section["grouped_index"]:
                existing = section["items"][section["grouped_index"][key]]
                existing["adet"] = self.coerce_order_quantity(
                    self.coerce_order_quantity(existing.get("adet", 1)) + display_adet
                )
            else:
                section["grouped_index"][key] = len(section["items"])
                section["items"].append({
                    "urun": display_urun,
                    "adet": display_adet,
                    "not": note,
                    "kategori": raw_with_context.get("kategori"),
                    "panel": raw_with_context.get("panel"),
                })

        grouped = []
        for section in sections:
            if section["heading"]:
                grouped.append({"heading": section["heading"]})
            grouped.extend(section["items"])
            if section.get("is_plate") and section["items"]:
                grouped.append({"separator": True})
        return grouped

    def thermal_text_bytes(self, value):
        return str(value or "").encode("cp1254", errors="replace")

    def escpos_line(self, value="", align="left", bold=False, size=0, font_b=False):
        align_map = {"left": 0, "center": 1, "right": 2}
        body = [
            b"\x1ba" + bytes([align_map.get(align, 0)]),
            b"\x1bE" + (b"\x01" if bold else b"\x00"),
            b"\x1bM" + (b"\x01" if font_b else b"\x00"),
            b"\x1d!" + bytes([size]),
            self.thermal_text_bytes(value),
            b"\n",
        ]
        return b"".join(body)

    def prep_ticket_font(self, size, bold=False):
        try:
            from PIL import ImageFont
            font_candidates = [
                "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf" if bold else
                "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                "/Library/Fonts/Arial Unicode.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf",
            ]
            for font_path in font_candidates:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size=size)
            return ImageFont.load_default()
        except Exception:
            return None

    def text_pixel_width(self, draw, text, font):
        bbox = draw.textbbox((0, 0), str(text or ""), font=font)
        return bbox[2] - bbox[0]

    def wrap_ticket_text_pixels(self, draw, text, font, max_width):
        words = str(text or "").strip().split()
        if not words:
            return []
        lines = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if self.text_pixel_width(draw, candidate, font) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word
            while self.text_pixel_width(draw, current, font) > max_width and len(current) > 1:
                split_at = max(1, len(current) - 1)
                while split_at > 1 and self.text_pixel_width(draw, current[:split_at], font) > max_width:
                    split_at -= 1
                lines.append(current[:split_at])
                current = current[split_at:]
        if current:
            lines.append(current)
        return lines

    def escpos_raster_image(self, image):
        bw = image.convert("L").point(lambda pixel: 0 if pixel < 180 else 255, "1")
        width, height = bw.size
        width_bytes = (width + 7) // 8
        padded_width = width_bytes * 8
        if padded_width != width:
            from PIL import Image
            padded = Image.new("1", (padded_width, height), 1)
            padded.paste(bw, (0, 0))
            bw = padded
            width = padded_width

        pixels = bw.load()
        data = bytearray()
        for y in range(height):
            for x_byte in range(width_bytes):
                value = 0
                for bit in range(8):
                    x = x_byte * 8 + bit
                    if pixels[x, y] == 0:
                        value |= 0x80 >> bit
                data.append(value)

        x_l = width_bytes & 0xFF
        x_h = (width_bytes >> 8) & 0xFF
        y_l = height & 0xFF
        y_h = (height >> 8) & 0xFF
        return b"\x1dv0\x00" + bytes([x_l, x_h, y_l, y_h]) + bytes(data)

    def build_prep_ticket_raster(self, order_data):
        try:
            from PIL import Image, ImageDraw
        except Exception as e:
            logger.warning(f"Raster fiş desteği yok, metin fişe dönülüyor: {e}")
            return None

        canvas_width = 576
        margin_x = 26
        y = 8
        image = Image.new("L", (canvas_width, 1200), 255)
        draw = ImageDraw.Draw(image)
        label_font = self.prep_ticket_font(23, bold=True)
        small_font = self.prep_ticket_font(26, bold=True)
        section_font = self.prep_ticket_font(43, bold=True)
        date_font = self.prep_ticket_font(30, bold=True)
        item_font = self.prep_ticket_font(39, bold=True)

        if not all([label_font, small_font, section_font, date_font, item_font]):
            return None

        masa_adi = str(order_data.get("masa") or "-").strip()
        section = self.ticket_upper(self.get_section_name_for_adisyon(masa_adi))
        masa = self.ticket_upper(self.display_table_name_for_ticket(masa_adi))
        now = datetime.datetime.now().strftime("%d.%m.%Y / %H:%M")
        garson = self.ticket_upper(order_data.get("garson") or "")
        ticket_items = self.prep_ticket_items(order_data)

        def draw_text(x, text, font, fill=0):
            nonlocal y
            draw.text((x, y), text, font=font, fill=fill)
            bbox = draw.textbbox((x, y), text, font=font)
            return bbox[3] - bbox[1]

        def rule(offset=0):
            nonlocal y
            y += offset
            draw.line((margin_x, y, canvas_width - margin_x, y), fill=0, width=2)
            y += 8

        draw.text((170, y), "Bölüm", font=label_font, fill=0)
        draw.text((385, y), "Masa", font=label_font, fill=0)
        y += 30
        rule()

        draw.text((margin_x, y), section[:14], font=section_font, fill=0)
        masa_width = self.text_pixel_width(draw, masa, section_font)
        draw.text((canvas_width - margin_x - masa_width, y), masa, font=section_font, fill=0)
        y += 44
        date_width = self.text_pixel_width(draw, now, date_font)
        draw.text((canvas_width - margin_x - date_width, y), now, font=date_font, fill=0)
        y += 36
        rule(2)

        if garson:
            draw.text((margin_x, y), garson, font=small_font, fill=0)
            y += 31
            rule(2)

        max_item_width = canvas_width - (margin_x * 2)
        for item_index, item in enumerate(ticket_items):
            if item_index > 0:
                y += 4
            if item.get("separator"):
                separator_text = "-" * 32
                for line in self.wrap_ticket_text_pixels(draw, separator_text, small_font, max_item_width):
                    draw.text((margin_x, y), line, font=small_font, fill=0)
                    y += 31
                continue
            item_text = self.ticket_upper(self.prep_ticket_item_title(item))
            for line in self.wrap_ticket_text_pixels(draw, item_text, item_font, max_item_width):
                draw.text((margin_x, y), line, font=item_font, fill=0)
                y += 42

        if not ticket_items:
            draw.text((margin_x, y), "SİPARİŞ", font=item_font, fill=0)
            y += 42

        y += 28
        cropped = image.crop((0, 0, canvas_width, min(y, image.height)))
        return self.escpos_raster_image(cropped)

    def build_prep_ticket_text(self, panel_id, order_data):
        raster_ticket = self.build_prep_ticket_raster(order_data)
        if raster_ticket:
            return raster_ticket

        width = 32
        wide_width = 16
        masa_adi = str(order_data.get("masa") or "-").strip()
        section = self.ticket_upper(self.get_section_name_for_adisyon(masa_adi))
        masa = self.ticket_upper(self.display_table_name_for_ticket(masa_adi))
        now = datetime.datetime.now().strftime("%d.%m.%Y / %H:%M")
        garson = self.ticket_upper(order_data.get("garson") or "")
        ticket_items = self.prep_ticket_items(order_data)

        output = []
        output.append(self.escpos_line(f"{'Bölüm':^16}{'Masa':^16}", align="left", font_b=True))
        output.append(self.escpos_line("-" * width))
        output.append(self.escpos_line(f"{section[:12]:<12}{masa[:4]:>4}", bold=True, size=0x10))
        output.append(self.escpos_line(now, align="right", bold=True))
        output.append(self.escpos_line("-" * width))
        if garson:
            output.append(self.escpos_line(garson, bold=True, font_b=True))
            output.append(self.escpos_line("-" * width))

        for item in ticket_items:
            if item.get("separator"):
                output.append(self.escpos_line("-" * width, bold=True))
                continue
            item_text = self.ticket_upper(self.prep_ticket_item_title(item))
            for index, line in enumerate(self.wrap_ticket_text(item_text, wide_width)):
                prefix = "" if index == 0 else "  "
                output.append(self.escpos_line(f"{prefix}{line}", bold=True, size=0x10))

        return b"".join(output)

    def build_receipt_ticket_text(self, masa_adi, items, sira):
        width = 32
        now = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
        totals = self.calculate_adisyon_totals(items)
        total = totals['payable_total']
        ikram_total = totals['ikram_total']
        lines = [
            self.company_name[:width].center(width),
            "HESAP BILGISI".center(width),
            "=" * width,
            now,
            f"Fis No: {sira}",
            f"Masa  : {masa_adi}",
        ]

        table_note = self.get_table_note(masa_adi)
        if table_note:
            lines.append("-" * width)
            lines.append("Masa Notu:")
            lines.extend(self.wrap_ticket_text(table_note, width))

        lines.append("-" * width)

        for item in items:
            ikram = " (IKRAM)" if item.get("tip") == "ikram" else ""
            item_title = f"{self.format_order_quantity(item.get('adet', 1))} x {item.get('urun', '')}{ikram}"
            lines.extend(self.wrap_ticket_text(item_title, width))
            line_total = 0 if item.get("tip") == "ikram" else self.item_line_total(item)
            lines.append(f"{line_total:>26.2f} TL")
            note = str(item.get("not") or "").strip()
            if note:
                lines.extend(self.wrap_ticket_text(f"Not: {note}", width))
            lines.append("-" * width)

        if lines[-1] == "-" * width:
            lines.pop()
        lines.append("=" * width)
        if ikram_total > 0:
            lines.append(f"{'IKRAM:':<18}{ikram_total:>10.2f} TL")
        lines.append(f"{'TOPLAM:':<18}{total:>10.2f} TL")
        lines.extend(["=" * width, "Afiyet Olsun".center(width), "", "", ""])
        return "\n".join(lines)

    def build_thermal_printer_alert_payload(self, printer):
        if not printer.get("alert_enabled", True):
            return b""

        mode = self.sanitize_printer_alert_mode(printer.get("alert_mode"))
        internal_buzzer = b"\x07\x1bB\x03\x03"
        drawer_buzzer = b"\x1bp\x00\x32\xfa"

        if mode == "cash_drawer":
            return drawer_buzzer
        if mode == "both":
            return internal_buzzer + drawer_buzzer
        return internal_buzzer

    def encode_thermal_ticket(self, text):
        # ESC/POS: init, Turkish code page on many devices, body, paper cut.
        if isinstance(text, bytes):
            payload = text
            feed = b"\n\n\n"
        else:
            payload = text.encode("cp1254", errors="replace")
            feed = b"\n\n\n"
        return b"\x1b@\x1bR\x0c\x1bt\x30" + payload + feed + b"\x1dV\x00"

    def send_thermal_alert_to_ip_printer(self, ip, port, alert_payload, label):
        if not alert_payload:
            return False

        try:
            time.sleep(0.25)
            with socket.create_connection((ip, port), timeout=2) as client:
                client.sendall(alert_payload)
            logger.info(f"🔔 {label} uyarı komutu gönderildi: {ip}:{port}")
            return True
        except Exception as e:
            logger.warning(f"Termal yazıcı uyarı komutu gönderilemedi ({label} {ip}:{port}): {e}")
            return False

    def send_thermal_text_to_ip_printer(self, printer, text, label):
        if not printer.get("enabled"):
            return False

        ip = str(printer.get("ip") or "").strip()
        if not ip:
            logger.warning(f"Termal yazıcı IP eksik: {label}")
            return False

        port = self.bounded_int(printer.get("port"), 9100, 1, 65535)
        copies = self.bounded_int(printer.get("copies"), 1, 1, 5)
        payload = self.encode_thermal_ticket(text)
        alert_payload = self.build_thermal_printer_alert_payload(printer)

        def task():
            for copy_index in range(copies):
                try:
                    with socket.create_connection((ip, port), timeout=5) as client:
                        client.sendall(payload)
                    logger.info(f"🖨️ {label} yazıcıya gönderildi: {ip}:{port} ({copy_index + 1}/{copies})")
                    self.send_thermal_alert_to_ip_printer(ip, port, alert_payload, label)
                except Exception as e:
                    logger.error(f"Termal yazıcı hatası ({label} {ip}:{port}): {e}")

        threading.Thread(target=task, daemon=True).start()
        return True

    def should_batch_prep_ticket(self, panel_id):
        panel = self.get_prep_panel_info(panel_id)
        return bool(panel.get("aggregate")) or panel_id == "icecek"

    def queue_prep_ticket_batch(self, panel_id, order_data):
        key = (
            str(panel_id or "").strip(),
            str(order_data.get("masa") or "").strip(),
        )
        if not key[0] or not key[1]:
            return False

        raw_items = order_data.get("items")
        if isinstance(raw_items, list) and raw_items:
            queued_items = []
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                queued_item = {
                    "uid": raw.get("uid"),
                    "urun": raw.get("urun"),
                    "kategori": raw.get("kategori") or order_data.get("kategori"),
                    "panel": raw.get("panel") or order_data.get("panel") or panel_id,
                    "adet": raw.get("adet", 1),
                    "not": raw.get("not") or "",
                    "saat": raw.get("saat") or order_data.get("saat") or "",
                    "garson": raw.get("garson") or order_data.get("garson") or "",
                }
                if raw.get("plate_group") or order_data.get("plate_group"):
                    queued_item["plate_group"] = raw.get("plate_group") or order_data.get("plate_group")
                queued_items.append(queued_item)
        else:
            queued_items = [{
                "uid": order_data.get("uid"),
                "urun": order_data.get("urun"),
                "kategori": order_data.get("kategori"),
                "panel": order_data.get("panel") or panel_id,
                "adet": order_data.get("adet", 1),
                "not": order_data.get("not") or "",
                "saat": order_data.get("saat") or "",
                "garson": order_data.get("garson") or "",
                "plate_group": order_data.get("plate_group")
            }]
        queued_items = [item for item in queued_items if item.get("urun")]
        if not queued_items:
            return False

        with self.prep_printer_batch_lock:
            batch = self.prep_printer_batches.get(key)
            if not batch:
                batch = {
                    "panel_id": key[0],
                    "payload": {
                        **order_data,
                        "items": [],
                    },
                    "timer": None,
                }
                self.prep_printer_batches[key] = batch

            batch["payload"]["items"].extend(queued_items)
            batch["payload"]["saat"] = order_data.get("saat") or batch["payload"].get("saat", "")
            if order_data.get("garson"):
                current_garson = batch["payload"].get("garson")
                if not current_garson:
                    batch["payload"]["garson"] = order_data.get("garson")
                elif current_garson != order_data.get("garson") and order_data.get("garson") not in current_garson:
                    batch["payload"]["garson"] = f"{current_garson} / {order_data.get('garson')}"

            timer = batch.get("timer")
            if timer:
                timer.cancel()
            batch["timer"] = threading.Timer(
                self.prep_printer_batch_delay,
                self.flush_prep_ticket_batch,
                args=(key,)
            )
            batch["timer"].daemon = True
            batch["timer"].start()
        return True

    def flush_prep_ticket_batch(self, key):
        with self.prep_printer_batch_lock:
            batch = self.prep_printer_batches.pop(key, None)
        if not batch:
            return

        panel_id = batch["panel_id"]
        payload = batch["payload"]
        item_count = len(payload.get("items") or [])
        printer = self.prep_printers.get(panel_id, {})
        text = self.build_prep_ticket_text(panel_id, payload)
        sent = self.send_thermal_text_to_ip_printer(printer, text, f"{panel_id} toplu fisi")
        if sent:
            logger.info(
                f"🖨️ {panel_id} toplu fişi hazırlandı: "
                f"{payload.get('masa')} ({item_count} kalem)"
            )

    def send_prep_ticket_to_printer(self, panel_id, order_data):
        if self.should_batch_prep_ticket(panel_id):
            self.queue_prep_ticket_batch(panel_id, order_data)
            return

        printer = self.prep_printers.get(panel_id, {})
        text = self.build_prep_ticket_text(panel_id, order_data)
        self.send_thermal_text_to_ip_printer(printer, text, f"{panel_id} fisi")

    def send_receipt_to_printer(self, receipt_text):
        return self.send_thermal_text_to_ip_printer(
            self.receipt_printer,
            receipt_text,
            "hesap fisi"
        )

    def get_system_default_printer_name(self):
        system = platform.system()
        if system == "Windows":
            command = [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Printer | Where-Object Default).Name"
            ]
        else:
            command = ["lpstat", "-d"]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=3,
                check=False
            )
        except Exception as e:
            logger.warning(f"Varsayılan yazıcı okunamadı: {e}")
            return ""

        output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())
        if not output:
            return ""

        first_line = output.splitlines()[0].strip()
        if "no system default" in first_line.lower():
            return ""
        if system != "Windows" and ":" in first_line:
            return first_line.rsplit(":", 1)[1].strip()
        return first_line

    def looks_like_barcode_printer(self, printer_name):
        normalized = self._normalize_text_for_match(printer_name)
        normalized = re.sub(r"[^0-9a-z]+", " ", normalized).strip()
        barcode_terms = (
            "barkod",
            "barcode",
            "etiket",
            "label",
            "zebra",
            "tsc",
            "godex",
            "argox",
            "dymo",
        )
        return any(term in normalized for term in barcode_terms)

    def send_raw_to_system_printer(self, printer_name, payload):
        if not printer_name or not payload:
            return False

        system = platform.system()
        try:
            if system == "Windows":
                return self.send_raw_to_windows_printer(printer_name, payload)

            commands = [
                ["lp", "-d", printer_name, "-o", "raw"],
                ["lpr", "-P", printer_name, "-o", "raw"],
            ]
            last_error = None
            for command in commands:
                try:
                    subprocess.run(
                        command,
                        input=payload,
                        timeout=3,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    return True
                except Exception as e:
                    last_error = e
                    continue
            if last_error:
                raise last_error
        except Exception as e:
            logger.warning(f"Ham yazıcı komutu gönderilemedi ({printer_name}): {e}")
        return False

    def send_raw_to_windows_printer(self, printer_name, payload):
        try:
            import ctypes
            from ctypes import wintypes

            class DocInfo(ctypes.Structure):
                _fields_ = [
                    ("pDocName", wintypes.LPWSTR),
                    ("pOutputFile", wintypes.LPWSTR),
                    ("pDatatype", wintypes.LPWSTR),
                ]

            winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
            open_printer = winspool.OpenPrinterW
            open_printer.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), wintypes.LPVOID]
            open_printer.restype = wintypes.BOOL

            close_printer = winspool.ClosePrinter
            close_printer.argtypes = [wintypes.HANDLE]
            close_printer.restype = wintypes.BOOL

            start_doc = winspool.StartDocPrinterW
            start_doc.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(DocInfo)]
            start_doc.restype = wintypes.DWORD

            end_doc = winspool.EndDocPrinter
            end_doc.argtypes = [wintypes.HANDLE]
            end_doc.restype = wintypes.BOOL

            start_page = winspool.StartPagePrinter
            start_page.argtypes = [wintypes.HANDLE]
            start_page.restype = wintypes.BOOL

            end_page = winspool.EndPagePrinter
            end_page.argtypes = [wintypes.HANDLE]
            end_page.restype = wintypes.BOOL

            write_printer = winspool.WritePrinter
            write_printer.argtypes = [
                wintypes.HANDLE,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
            ]
            write_printer.restype = wintypes.BOOL

            printer_handle = wintypes.HANDLE()
            if not open_printer(printer_name, ctypes.byref(printer_handle), None):
                raise ctypes.WinError(ctypes.get_last_error())

            started_doc = False
            started_page = False
            try:
                doc_info = DocInfo("FastFoot barkod bip", None, "RAW")
                if not start_doc(printer_handle, 1, ctypes.byref(doc_info)):
                    raise ctypes.WinError(ctypes.get_last_error())
                started_doc = True

                if not start_page(printer_handle):
                    raise ctypes.WinError(ctypes.get_last_error())
                started_page = True

                buffer = ctypes.create_string_buffer(payload)
                written = wintypes.DWORD()
                if not write_printer(printer_handle, buffer, len(payload), ctypes.byref(written)):
                    raise ctypes.WinError(ctypes.get_last_error())
                return written.value == len(payload)
            finally:
                if started_page:
                    end_page(printer_handle)
                if started_doc:
                    end_doc(printer_handle)
                close_printer(printer_handle)
        except Exception as e:
            logger.warning(f"Windows ham yazıcı komutu gönderilemedi ({printer_name}): {e}")
            return False

    def beep_if_system_printer_is_barcode(self):
        printer_name = self.get_system_default_printer_name()
        if not printer_name or not self.looks_like_barcode_printer(printer_name):
            return False

        payload = b"SOUND 5,200\r\n"
        sent = self.send_raw_to_system_printer(printer_name, payload)
        if sent:
            logger.info(f"🔔 Barkod yazıcı bip komutu gönderildi: {printer_name}")
        return sent

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

    def sanitize_paket_labels(self, labels):
        """Paket etiketi listesini temizle ve tekrarsız döndür."""
        if labels is None:
            return []
        if isinstance(labels, str):
            text = labels.strip()
            if not text:
                return []
            try:
                labels = json.loads(text)
            except Exception:
                labels = text.split(",")
        if not isinstance(labels, list):
            return []

        clean_labels = []
        seen = set()
        for label in labels:
            clean_label = str(label or "").strip()
            if not clean_label or clean_label in seen:
                continue
            seen.add(clean_label)
            clean_labels.append(clean_label)
            if len(clean_labels) >= 100:
                break
        return clean_labels

    def default_paket_labels(self, count=None):
        """Eski ayarlara uyumlu varsayılan paket etiketleri."""
        try:
            label_count = int(self.paket_sayisi if count is None else count)
        except Exception:
            label_count = 0
        label_count = max(0, min(label_count, 100))
        return [f"Paket {i}" for i in range(1, label_count + 1)]

    def get_paket_labels(self):
        """Aktif paket etiketlerini döndür."""
        labels = self.sanitize_paket_labels(self.paket_labels)
        if self.paket_labels_configured:
            return labels
        return labels or self.default_paket_labels()

    def load_paket_labels(self):
        """Paket etiket listesini yükle."""
        self.paket_labels = []
        self.paket_labels_configured = False
        if not os.path.exists(PAKET_LABELS_FILE):
            return
        try:
            with open(PAKET_LABELS_FILE, "r", encoding="utf-8") as f:
                self.paket_labels = self.sanitize_paket_labels(json.load(f))
            self.paket_labels_configured = True
            self.paket_sayisi = len(self.paket_labels)
            logger.info(f"✓ {len(self.paket_labels)} paket etiketi yüklendi")
        except Exception as e:
            logger.error(f"Paket etiketi yükleme hatası: {e}")
            self.paket_labels = []
            self.paket_labels_configured = False

    def save_paket_labels(self):
        """Paket etiket listesini dosyaya kaydet."""
        try:
            self.paket_labels = self.sanitize_paket_labels(self.paket_labels)
            self.paket_labels_configured = True
            self.paket_sayisi = len(self.paket_labels)
            with open(PAKET_LABELS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.paket_labels, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Paket etiketi kaydetme hatası: {e}")
            return False

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
        for label in self.get_paket_labels():
            add_adisyon_name(label)
        
        if not next_adisyonlar:
            add_adisyon_name("Genel")

        if preserve_existing:
            for masa, items in previous_adisyonlar.items():
                if masa not in next_adisyonlar and items:
                    next_adisyonlar[masa] = items

        self.adisyonlar = next_adisyonlar
        if getattr(self, "table_notes", None):
            self.table_notes = {
                masa: note
                for masa, note in self.table_notes.items()
                if masa in self.adisyonlar and note
            }
        
        logger.info(f"✓ {len(self.adisyonlar)} adisyon alanı oluşturuldu")

    def save_active_adisyonlar(self):
        """Aktif adisyonları dosyaya kaydet"""
        try:
            active_only = {
                masa: items
                for masa, items in self.adisyonlar.items()
                if items
            }
            tmp_file = f"{ACTIVE_ADISYONLAR_FILE}.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(active_only, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, ACTIVE_ADISYONLAR_FILE)
            return True
        except Exception as e:
            logger.error(f"Adisyon kaydetme hatası: {e}")
            return False

    def normalize_active_prep_order_names(self):
        """Eski aktif siparişlerde kalan porsiyon öneki tekrarlarını temizle."""
        changed = False
        for items in self.adisyonlar.values():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                urun = str(item.get("urun") or "").strip()
                if not urun:
                    continue
                if not re.match(r"^(tam|yarım|yarim)\s+(?:porsiyon\s+)?", urun, flags=re.IGNORECASE):
                    continue
                label, base_name = self.prep_ticket_explicit_portion_info(urun)
                normalized_name = self.prep_ticket_portion_display_name(label, base_name) if label else urun
                if normalized_name and normalized_name != urun:
                    item["urun"] = normalized_name
                    changed = True
        return changed

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
                if self.normalize_active_prep_order_names():
                    self.save_active_adisyonlar()
                logger.info("✓ Aktif adisyonlar geri yüklendi")
            except Exception as e:
                logger.error(f"Adisyon yükleme hatası: {e}")

    @staticmethod
    def sanitize_table_note(note):
        """Masa özel notunu kısa ve güvenli bir metne indirger."""
        text = str(note or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
        text = "\n".join(line for line in lines if line)
        return text[:500]

    def get_table_note(self, masa_adi):
        return str(self.table_notes.get(str(masa_adi or "").strip()) or "")

    def get_table_notes_payload(self):
        return {
            masa: note
            for masa, note in self.table_notes.items()
            if note and masa in self.adisyonlar
        }

    def save_table_notes(self):
        """Masa özel notlarını dosyaya kaydet."""
        try:
            payload = self.get_table_notes_payload()
            with open(TABLE_NOTES_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            self.table_notes = payload
            return True
        except Exception as e:
            logger.error(f"Masa notu kaydetme hatası: {e}")
            return False

    def load_table_notes(self):
        """Masa özel notlarını dosyadan yükle."""
        self.table_notes = {}
        if not os.path.exists(TABLE_NOTES_FILE):
            return
        try:
            with open(TABLE_NOTES_FILE, "r", encoding="utf-8") as f:
                raw_notes = json.load(f)
            if isinstance(raw_notes, dict):
                for masa, note in raw_notes.items():
                    masa_adi = str(masa or "").strip()
                    clean_note = self.sanitize_table_note(note)
                    if masa_adi in self.adisyonlar and clean_note:
                        self.table_notes[masa_adi] = clean_note
            logger.info(f"✓ {len(self.table_notes)} masa notu yüklendi")
        except Exception as e:
            logger.error(f"Masa notu yükleme hatası: {e}")

    def set_table_note(self, masa_adi, note, save=True):
        masa_adi = str(masa_adi or "").strip()
        if not masa_adi or masa_adi not in self.adisyonlar:
            return None, "Geçersiz masa"
        clean_note = self.sanitize_table_note(note)
        if clean_note:
            self.table_notes[masa_adi] = clean_note
        else:
            self.table_notes.pop(masa_adi, None)
        if save:
            self.save_table_notes()
        return clean_note, None

    def clear_table_note(self, masa_adi, save=True):
        masa_adi = str(masa_adi or "").strip()
        if not masa_adi:
            return False
        removed = self.table_notes.pop(masa_adi, None) is not None
        if removed and save:
            self.save_table_notes()
        return removed

    def merge_table_note(self, target_masa, note, save=True):
        note = self.sanitize_table_note(note)
        if not note:
            return self.get_table_note(target_masa), None
        current_note = self.get_table_note(target_masa)
        if current_note and note not in current_note:
            note = self.sanitize_table_note(f"{current_note}\n{note}")
        elif current_note:
            note = current_note
        return self.set_table_note(target_masa, note, save=save)

    @staticmethod
    def sanitize_reservation_text(value, max_len=160, multiline=False):
        """Rezervasyon metin alanlarını kısa ve güvenli hale getir."""
        text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if multiline:
            lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
            text = "\n".join(line for line in lines if line)
        else:
            text = re.sub(r"\s+", " ", text)
        return text[:max_len]

    @staticmethod
    def normalize_reservation_date(value):
        text = str(value or "").strip()[:10]
        try:
            date_value = datetime.date.fromisoformat(text)
        except Exception:
            return None, None, "Geçerli tarih girin"
        day_names = [
            "Pazartesi", "Salı", "Çarşamba", "Perşembe",
            "Cuma", "Cumartesi", "Pazar"
        ]
        return date_value.isoformat(), day_names[date_value.weekday()], None

    @staticmethod
    def normalize_reservation_time(value):
        text = str(value or "").strip()
        match = re.match(r"^(\d{1,2}):(\d{2})", text)
        if not match:
            return None, "Geçerli saat girin"
        hour = int(match.group(1))
        minute = int(match.group(2))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            return None, "Geçerli saat girin"
        return f"{hour:02d}:{minute:02d}", None

    @staticmethod
    def normalize_reservation_status(value):
        aliases = {
            "planlandi": "planlandi",
            "planlandı": "planlandi",
            "aktif": "planlandi",
            "geldi": "geldi",
            "tamamlandi": "geldi",
            "tamamlandı": "geldi",
            "iptal": "iptal",
            "iptal edildi": "iptal",
            "cancelled": "iptal",
            "canceled": "iptal",
        }
        normalized = str(value or "planlandi").strip().lower()
        return aliases.get(normalized, "planlandi")

    @staticmethod
    def reservation_status_label(status):
        return {
            "planlandi": "Planlandı",
            "geldi": "Geldi",
            "iptal": "İptal",
        }.get(status, "Planlandı")

    @staticmethod
    def normalize_reservation_source(value):
        aliases = {
            "telefon": "telefon",
            "phone": "telefon",
            "arama": "telefon",
            "sozlu": "sozlu",
            "sözlü": "sozlu",
            "yuz yuze": "sozlu",
            "yüz yüze": "sozlu",
        }
        normalized = str(value or "telefon").strip().lower()
        return aliases.get(normalized, "telefon")

    @staticmethod
    def reservation_source_label(source):
        return {
            "telefon": "Telefon",
            "sozlu": "Sözlü",
        }.get(source, "Telefon")

    @staticmethod
    def reservation_sort_key(reservation):
        status_order = {"planlandi": 0, "geldi": 1, "iptal": 2}
        return (
            reservation.get("date") or "9999-12-31",
            reservation.get("time") or "23:59",
            status_order.get(reservation.get("status"), 9),
            reservation.get("customer_name") or "",
        )

    def find_order_menu_item(self, urun, kategori=None):
        target = self._normalize_product_key(urun)
        category_target = self._normalize_text_for_match(kategori)
        for category, items in self.get_order_menu_data().items():
            if category_target and self._normalize_text_for_match(category) != category_target:
                continue
            for item in items:
                if not isinstance(item, (list, tuple)) or not item:
                    continue
                name = str(item[0] or "").strip()
                if self._normalize_product_key(name) == target:
                    return category, name, item
        return None, None, None

    def normalize_reservation_menu_items(self, items, validate_menu=True):
        """Rezervasyon için menüden seçilen ürünleri reyon bilgisiyle sakla."""
        if not isinstance(items, list):
            return [], None

        normalized = []
        for raw in items[:80]:
            if not isinstance(raw, dict):
                continue
            urun = self.sanitize_reservation_text(
                raw.get("urun") or raw.get("name"),
                max_len=140
            )
            if not urun:
                continue
            requested_category = self.sanitize_reservation_text(
                raw.get("kategori") or raw.get("category"),
                max_len=100
            )
            kategori, menu_name, menu_item = self.find_order_menu_item(urun, requested_category)
            if not menu_item:
                if validate_menu:
                    return None, f"Menüde bulunamayan ürün: {urun}"
                kategori = requested_category
                menu_name = urun

            try:
                adet = self.coerce_order_quantity(raw.get("adet", raw.get("quantity", 1)))
            except Exception:
                adet = 0
            if adet <= 0 or adet > 999:
                return None, f"{menu_name} için adet 1-999 arasında olmalı"

            note = self.sanitize_reservation_text(raw.get("not") or raw.get("note"), max_len=180)
            panel = self.get_preparation_panel_for_product(menu_name, kategori)
            panel_info = self.get_prep_panel_info(panel)
            normalized.append({
                "urun": menu_name,
                "kategori": kategori,
                "adet": adet,
                "not": note,
                "panel": panel,
                "panel_adi": panel_info.get("name") or panel,
            })

        return normalized, None

    def reservation_menu_summary(self, menu_items):
        parts = []
        for item in menu_items or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("urun") or "").strip()
            if not name:
                continue
            adet = self.format_order_quantity(item.get("adet", 1))
            note = str(item.get("not") or "").strip()
            label = f"{adet}x {name}"
            if note:
                label = f"{label} ({note})"
            parts.append(label)
        return "\n".join(parts)

    def normalize_reservation_record(self, data, existing=None, allow_unknown_masa=False):
        """API ve dosya kayıtlarını tek rezervasyon şemasına dönüştür."""
        existing = existing or {}
        data = data or {}
        now = datetime.datetime.now().isoformat(timespec="seconds")

        customer_name = self.sanitize_reservation_text(
            data.get("customer_name", existing.get("customer_name")),
            max_len=120
        )
        phone = self.sanitize_reservation_text(
            data.get("phone", existing.get("phone")),
            max_len=60
        )
        cari_isim = self.sanitize_reservation_text(
            data.get("cari_isim", existing.get("cari_isim")),
            max_len=120
        )
        date_key, day_name, date_error = self.normalize_reservation_date(
            data.get("date", existing.get("date"))
        )
        time_key, time_error = self.normalize_reservation_time(
            data.get("time", existing.get("time"))
        )
        masa = self.sanitize_reservation_text(
            data.get("masa", existing.get("masa")),
            max_len=80
        )

        if not customer_name:
            return None, "Rezervasyonu yaptıran kişi gerekli"
        if not phone:
            return None, "İletişim bilgisi gerekli"
        if date_error:
            return None, date_error
        if time_error:
            return None, time_error
        if masa and not allow_unknown_masa and masa not in self.adisyonlar:
            return None, "Geçerli masa seçin"

        try:
            guest_count = int(data.get("guest_count", existing.get("guest_count", 1)))
        except (TypeError, ValueError):
            guest_count = 0
        if guest_count <= 0 or guest_count > 999:
            return None, "Gelecek kişi sayısı 1-999 arasında olmalı"

        status = self.normalize_reservation_status(data.get("status", existing.get("status")))
        source = self.normalize_reservation_source(data.get("source", existing.get("source")))
        reservation_id = str(existing.get("id") or data.get("id") or uuid.uuid4().hex)
        if "menu_items" in data:
            menu_items, menu_error = self.normalize_reservation_menu_items(
                data.get("menu_items"),
                validate_menu=not allow_unknown_masa
            )
            if menu_error:
                return None, menu_error
        else:
            menu_items = existing.get("menu_items") if isinstance(existing.get("menu_items"), list) else []

        menu_preferences = self.sanitize_reservation_text(
            data.get("menu_preferences", existing.get("menu_preferences")),
            max_len=600,
            multiline=True
        )
        if menu_items and not menu_preferences:
            menu_preferences = self.sanitize_reservation_text(
                self.reservation_menu_summary(menu_items),
                max_len=600,
                multiline=True
            )

        record = {
            "id": reservation_id,
            "customer_name": customer_name,
            "phone": phone,
            "cari_isim": cari_isim,
            "source": source,
            "source_label": self.reservation_source_label(source),
            "date": date_key,
            "day": day_name,
            "time": time_key,
            "masa": masa,
            "guest_count": guest_count,
            "menu_items": menu_items,
            "menu_preferences": menu_preferences,
            "note": self.sanitize_reservation_text(
                data.get("note", existing.get("note")),
                max_len=500,
                multiline=True
            ),
            "status": status,
            "status_label": self.reservation_status_label(status),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
        }
        return record, None

    def load_reservations(self):
        """Masa rezervasyonlarını JSON dosyasından yükle."""
        self.reservations = []
        if not os.path.exists(RESERVATIONS_FILE):
            return
        try:
            with open(RESERVATIONS_FILE, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            raw_reservations = raw_data.get("reservations", raw_data) if isinstance(raw_data, dict) else raw_data
            if not isinstance(raw_reservations, list):
                raw_reservations = []
            for raw in raw_reservations:
                if not isinstance(raw, dict):
                    continue
                record, err = self.normalize_reservation_record(raw, allow_unknown_masa=True)
                if not err:
                    self.reservations.append(record)
            self.reservations.sort(key=self.reservation_sort_key)
            logger.info(f"✓ {len(self.reservations)} rezervasyon yüklendi")
        except Exception as e:
            logger.error(f"Rezervasyon yükleme hatası: {e}")
            self.reservations = []

    def save_reservations(self):
        """Masa rezervasyonlarını dosyaya kaydet."""
        try:
            self.reservations.sort(key=self.reservation_sort_key)
            with open(RESERVATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.reservations, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Rezervasyon kaydetme hatası: {e}")
            return False

    def get_reservations_payload(self):
        today_key = datetime.date.today().isoformat()
        active_by_table = defaultdict(list)
        active_count = 0
        today_count = 0

        for reservation in sorted(self.reservations, key=self.reservation_sort_key):
            if reservation.get("status") != "planlandi":
                continue
            if reservation.get("date") == today_key:
                today_count += 1
            if (reservation.get("date") or "") < today_key:
                continue
            active_count += 1
            masa = reservation.get("masa")
            if masa:
                active_by_table[masa].append(reservation)

        return {
            "success": True,
            "today": today_key,
            "reservations": sorted(self.reservations, key=self.reservation_sort_key),
            "active_by_table": dict(active_by_table),
            "active_count": active_count,
            "today_count": today_count,
        }

    def create_reservation(self, data):
        record, err = self.normalize_reservation_record(data)
        if err:
            return None, err
        self.reservations.append(record)
        if not self.save_reservations():
            return None, "Rezervasyon dosyaya kaydedilemedi"
        return record, None

    def build_reservation_menu_notice(self, reservation):
        menu_items = reservation.get("menu_items") if isinstance(reservation.get("menu_items"), list) else []
        if not menu_items:
            return None

        panels = []
        grouped = defaultdict(list)
        for item in menu_items:
            if not isinstance(item, dict):
                continue
            panel = item.get("panel") or self.get_preparation_panel_for_product(
                item.get("urun"),
                item.get("kategori")
            )
            item = dict(item)
            item["panel"] = panel
            item["panel_adi"] = self.get_prep_panel_info(panel).get("name") or panel
            grouped[panel].append(item)

        for panel, items in grouped.items():
            panel_info = self.get_prep_panel_info(panel)
            panels.append({
                "panel": panel,
                "panel_adi": panel_info.get("name") or panel,
                "items": items,
            })

        label = f"{reservation.get('date', '')} {reservation.get('time', '')}".strip()
        return {
            "id": reservation.get("id"),
            "customer_name": reservation.get("customer_name"),
            "phone": reservation.get("phone"),
            "date": reservation.get("date"),
            "day": reservation.get("day"),
            "time": reservation.get("time"),
            "masa": reservation.get("masa"),
            "guest_count": reservation.get("guest_count"),
            "note": reservation.get("note") or "",
            "menu_preferences": reservation.get("menu_preferences") or "",
            "menu_items": menu_items,
            "panels": panels,
            "message": (
                f"Rezervasyon menüsü: {label} {reservation.get('masa', '')} - "
                f"{reservation.get('customer_name', '')}"
            ).strip()
        }

    def notify_reservation_menu(self, reservation):
        notice = self.build_reservation_menu_notice(reservation)
        if not notice or reservation.get("status") != "planlandi":
            return False

        socketio.emit("reservation_menu_notice", notice)
        for panel_entry in notice.get("panels", []):
            panel = panel_entry.get("panel")
            items = panel_entry.get("items") or []
            if not panel or not items:
                continue
            ticket_payload = {
                "uid": f"reservation:{notice.get('id')}:{panel}",
                "masa": f"Rezervasyon {notice.get('masa') or ''}".strip(),
                "urun": "Rezervasyon Menüsü",
                "kategori": "Rezervasyon",
                "panel": panel,
                "panel_adi": panel_entry.get("panel_adi") or panel,
                "adet": 1,
                "not": "Bilgi fişi",
                "saat": notice.get("time") or "",
                "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "garson": "Rezervasyon",
                "items": [
                    {
                        "uid": f"reservation:{notice.get('id')}:{panel}:{idx}",
                        "urun": item.get("urun"),
                        "kategori": item.get("kategori"),
                        "panel": panel,
                        "adet": item.get("adet", 1),
                        "not": " / ".join(part for part in [
                            item.get("not") or "",
                            notice.get("customer_name") or "",
                            notice.get("phone") or "",
                            f"{notice.get('date') or ''} {notice.get('time') or ''}".strip(),
                            f"{notice.get('guest_count') or ''} kişi" if notice.get("guest_count") else "",
                            notice.get("note") or "",
                        ] if part),
                        "saat": notice.get("time") or "",
                        "garson": "Rezervasyon",
                    }
                    for idx, item in enumerate(items, start=1)
                ]
            }
            self.send_prep_ticket_to_printer(panel, ticket_payload)
        return True

    def update_reservation(self, reservation_id, data):
        reservation_id = str(reservation_id or "").strip()
        for index, existing in enumerate(self.reservations):
            if existing.get("id") != reservation_id:
                continue
            masa_is_unchanged = "masa" not in (data or {})
            allow_unknown_masa = masa_is_unchanged and existing.get("masa") not in self.adisyonlar
            record, err = self.normalize_reservation_record(
                data,
                existing=existing,
                allow_unknown_masa=allow_unknown_masa
            )
            if err:
                return None, err
            self.reservations[index] = record
            if not self.save_reservations():
                return None, "Rezervasyon dosyaya kaydedilemedi"
            return record, None
        return None, "Rezervasyon bulunamadı"

    def cancel_reservation(self, reservation_id):
        return self.update_reservation(reservation_id, {"status": "iptal"})
    
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

    def save_menu_data(self, new_menu, daily_meal_categories=None):
        """Menüyü dosyaya ve varsa veritabanına kaydet."""
        if not isinstance(new_menu, dict):
            return False, "Geçersiz menü verisi"

        with open(MENU_FILE, "w", encoding="utf-8") as f:
            for cat, items in new_menu.items():
                category = str(cat or "").strip()
                if not category or not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, list) or len(item) < 2:
                        continue
                    name = str(item[0] or "").strip()
                    if not name:
                        continue
                    price = item[1]
                    ys = item[2] if len(item) > 2 else 0
                    ty = item[3] if len(item) > 3 else 0
                    gt = item[4] if len(item) > 4 else 0
                    mg = item[5] if len(item) > 5 else 0
                    image_url = str(item[6]).strip() if len(item) > 6 and item[6] is not None else ""
                    image_url = image_url.replace(";", "")
                    menu_visible = "1" if self.is_menu_item_visible(item) else "0"
                    f.write(f"{category};{name};{price};{ys};{ty};{gt};{mg};{image_url};{menu_visible}\n")

        self.menu_data = new_menu
        if daily_meal_categories is not None and not self.save_menu_metadata(daily_meal_categories):
            return False, "Menü metadatası kaydedilemedi"

        if USE_DATABASE:
            try:
                db.load_menu_from_file(MENU_FILE)
            except Exception as e:
                logger.error(f"Menü DB güncelleme hatası: {e}")

        self.menu_data = new_menu
        self.load_daily_meals()
        self.apply_daily_meal_stock(reset_values=False)
        return True, None

    def rename_menu_categories(self, renames):
        """Ayarlar ekranından gelen menü kategori adı değişikliklerini uygula."""
        if not isinstance(renames, dict) or not renames:
            return True, None

        clean_renames = {}
        existing_by_key = {
            self._normalize_text_for_match(category): category
            for category in self.menu_data.keys()
        }
        target_keys = set()

        for old_category, new_category in renames.items():
            old_name = str(old_category or "").strip()
            new_name = str(new_category or "").strip()[:80]
            if not old_name or not new_name:
                continue

            old_key = self._normalize_text_for_match(old_name)
            new_key = self._normalize_text_for_match(new_name)
            canonical_old = existing_by_key.get(old_key)
            if not canonical_old or not new_key or old_key == new_key:
                continue
            if new_key in existing_by_key and existing_by_key[new_key] != canonical_old:
                return False, f'"{new_name}" kategorisi zaten var'
            if new_key in target_keys:
                return False, f'"{new_name}" kategori adı birden fazla kez kullanılamaz'

            clean_renames[canonical_old] = new_name
            target_keys.add(new_key)

        if not clean_renames:
            return True, None

        next_menu = {}
        for category, items in self.menu_data.items():
            next_menu[clean_renames.get(category, category)] = items

        def renamed_category_name(category):
            category_key = self._normalize_text_for_match(category)
            for old_name, new_name in clean_renames.items():
                if self._normalize_text_for_match(old_name) == category_key:
                    return new_name
            return category

        next_daily_categories = [renamed_category_name(category) for category in self.daily_meal_categories]
        next_overrides = {}
        for category, panel_id in self.prep_category_overrides.items():
            next_overrides[renamed_category_name(category)] = panel_id

        ok, error = self.save_menu_data(next_menu, next_daily_categories)
        if not ok:
            return ok, error

        self.prep_category_overrides = self.sanitize_prep_category_overrides(next_overrides)
        return True, None

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

    def get_menu_product_options(self):
        """Ayar ekranlarında ürün adı seçimi için sade menü listesi."""
        products = []
        for category, items in self.menu_data.items():
            for item in items:
                if not item:
                    continue
                name = str(item[0] or "").strip()
                if name:
                    products.append({
                        "category": category,
                        "name": name
                    })
        return products

    def _normalize_text_for_match(self, value):
        text = unicodedata.normalize('NFKD', str(value or '').casefold())
        text = ''.join(ch for ch in text if not unicodedata.combining(ch))
        return text.replace('ı', 'i')

    def _normalize_product_key(self, urun):
        return re.sub(r'\s+', ' ', self._normalize_text_for_match(urun)).strip()

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
        if match:
            name = match.group(2).strip()
        match = re.match(r'^(tam|yarım|yarim)\s+(.+)$', name, flags=re.IGNORECASE)
        if match and self._normalize_text_for_match(match.group(1)).startswith('tam'):
            name = match.group(2).strip()
        name = re.sub(r'\(\s*\d+(?:[,.]\d+)?\s*porsiyon\s*\)\s*$', '', name, flags=re.IGNORECASE).strip()
        return name

    def _portion_variant_match_rank(self, urun):
        normalized = self._normalize_text_for_match(urun)
        if normalized.startswith('tam porsiyon '):
            return 0
        if normalized.startswith('yarim porsiyon '):
            return 2
        return 1

    def _find_menu_product_entry(self, urun):
        target = self._normalize_product_key(urun)
        fallback_target = self._normalize_product_key(self._strip_portion_variant_prefix(urun))
        fallback_matches = []
        for category, items in self.menu_data.items():
            for item in items:
                name = str(item[0] or '').strip()
                if self._normalize_product_key(name) == target:
                    return category, name, item
                if fallback_target and self._normalize_product_key(self._strip_portion_variant_prefix(name)) == fallback_target:
                    fallback_matches.append((self._portion_variant_match_rank(name), category, name, item))
        if fallback_matches:
            _, category, name, item = sorted(fallback_matches, key=lambda entry: entry[0])[0]
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

    def _daily_meal_stock_keys(self):
        keys = set()
        for category in self._daily_meal_categories():
            if self.get_daily_meals_for_category(category):
                keys.add(self._normalize_product_key(category))
        for item in self.daily_meals:
            meal_name = str(item.get('yemek') or '').strip()
            if meal_name:
                keys.add(self._normalize_product_key(meal_name))
        return keys

    def _is_daily_meal_stock_name(self, urun):
        stock_name = str(urun or '').strip()
        if not stock_name:
            return False
        return self._normalize_product_key(stock_name) in self._daily_meal_stock_keys()

    def _is_daily_meal_stock_entry(self, key, entry=None):
        stock_key = self._normalize_product_key(key)
        if stock_key in self._daily_meal_stock_keys():
            return True
        if entry:
            return self._is_daily_meal_stock_name(entry.get('urun'))
        return False

    def _should_track_portion_order(self, urun, not_bilgisi=''):
        meal_name = self.get_daily_meal_name_from_note(urun, not_bilgisi)
        if meal_name:
            return True

        group_name = self.get_daily_meal_group_for_product(urun)
        if group_name and self.get_daily_meals_for_category(group_name):
            return True

        stock_name = self.get_portion_stock_name(urun)
        return self._is_daily_meal_stock_name(stock_name)

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
        meal_note, extra_note = self.split_order_note_details(not_bilgisi)
        note = meal_note or str(not_bilgisi or '').strip()
        if not meal_note:
            note = re.sub(r'^(yemek|çeşit|cesit)\s*:\s*', '', note, flags=re.IGNORECASE).strip()
        if not note or (extra_note and not meal_note):
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
            adet = self.coerce_order_quantity(adet)
        except Exception:
            adet = 1

        raw_name = str(urun or '').strip()
        normalized_raw = self._normalize_text_for_match(raw_name)
        trailing_match = re.search(r'\(\s*(\d+(?:[,.]\d+)?)\s*porsiyon\s*\)\s*$', raw_name, flags=re.IGNORECASE)
        if normalized_raw.startswith('yarim porsiyon '):
            multiplier = 0.5
        elif trailing_match:
            try:
                multiplier = max(0.0, float(trailing_match.group(1).replace(',', '.')))
            except Exception:
                multiplier = 1.0
        else:
            product_name = self._find_menu_product_name(urun)
            normalized = self._normalize_text_for_match(product_name)
            multiplier = 0.5 if normalized.startswith('yarim porsiyon ') else 1.0

        return round(adet * multiplier, 2)

    def get_menu_category_for_product(self, urun):
        category, _, _ = self._find_menu_product_entry(urun)
        if category:
            return category
        daily_group = self.get_daily_meal_group_for_product(urun)
        if daily_group:
            return daily_group
        return ''

    def resolve_order_category(self, urun, kategori=None):
        category_name = str(kategori or '').strip()
        if category_name:
            return self._canonical_menu_category(category_name)
        return self.get_menu_category_for_product(urun)

    def get_preparation_panel_for_category(self, category):
        category_name = str(category or '').strip()
        if category_name in self.prep_category_overrides:
            return self.prep_category_overrides[category_name]

        normalized = self._normalize_text_for_match(category_name)
        for override_category, panel_id in self.prep_category_overrides.items():
            if self._normalize_text_for_match(override_category) == normalized:
                return panel_id

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
            for category in self._daily_meal_categories():
                total = self.get_daily_meal_group_total(category)
                group_key = self._normalize_product_key(category)
                if total > 0 and group_key:
                    self.portion_stock[group_key] = {
                        'urun': category,
                        'kategori': category,
                        'kalan': self._coerce_portion_amount(total),
                        'updated_at': now_iso,
                        'is_default': False,
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
        logger.info(f"✓ Günlük yemek porsiyon stokları {date_key} için yenilendi")

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

    def get_backup_sources(self):
        files = [
            SETTINGS_FILE,
            MENU_FILE,
            MENU_META_FILE,
            COUNTER_FILE,
            WAITERS_FILE,
            INTEGRATION_CONFIG,
            SALONS_FILE,
            PAKET_LABELS_FILE,
            CASHIERS_FILE,
            KITCHEN_FILE,
            USERS_FILE,
            AUTH_SESSIONS_FILE,
            ACTIVE_ADISYONLAR_FILE,
            TABLE_NOTES_FILE,
            RESERVATIONS_FILE,
            PORTION_STOCK_FILE,
            PORTION_STOCK_RESET_FILE,
            DAILY_MEALS_FILE,
        ]
        directories = [
            FIS_KLASORU,
            DAILY_MEALS_HISTORY_DIR,
            MENU_UPLOAD_DIR,
        ]
        return files, directories

    def add_path_to_backup(self, archive, source_path, arcname=None):
        if not os.path.exists(source_path):
            return
        arcname = arcname or os.path.relpath(source_path, SCRIPT_DIR)
        archive.add(source_path, arcname=arcname, recursive=True)

    def create_database_backup(self, output_dir):
        if not USE_DATABASE:
            return None
        try:
            from db_config import DB_CONFIG
        except Exception as e:
            logger.error(f"Yedekleme DB ayarı okunamadı: {e}")
            return None

        database_name = DB_CONFIG.get("database") or DB_CONFIG.get("dbname")
        if not database_name:
            logger.error("Yedekleme için veritabanı adı bulunamadı")
            return None

        dump_path = os.path.join(output_dir, "postgresql.dump")
        cmd = [
            "pg_dump",
            "--format=custom",
            "--file", dump_path,
            "--host", str(DB_CONFIG.get("host", "localhost")),
            "--port", str(DB_CONFIG.get("port", 5432)),
            "--username", str(DB_CONFIG.get("user", "")),
            str(database_name),
        ]
        env = os.environ.copy()
        if DB_CONFIG.get("password"):
            env["PGPASSWORD"] = str(DB_CONFIG.get("password"))

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, env=env, timeout=120)
            return dump_path
        except FileNotFoundError:
            logger.error("PostgreSQL yedeği alınamadı: pg_dump bulunamadı")
        except subprocess.CalledProcessError as e:
            logger.error(f"PostgreSQL yedeği alınamadı: {e.stderr or e.stdout or e}")
        except subprocess.TimeoutExpired:
            logger.error("PostgreSQL yedeği zaman aşımına uğradı")
        return None

    def cleanup_old_backups(self):
        retention_days = self.bounded_int(self.auto_backup_retention_days, 30, 1, 3650)
        cutoff = time.time() - (retention_days * 86400)
        backup_dir = self.sanitize_backup_dir(self.auto_backup_dir)
        if not os.path.isdir(backup_dir):
            return
        for filename in os.listdir(backup_dir):
            if not (filename.startswith("fastfoot-backup-") and filename.endswith(".tar.gz")):
                continue
            path = os.path.join(backup_dir, filename)
            try:
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    logger.info(f"Eski yedek silindi: {path}")
            except Exception as e:
                logger.error(f"Eski yedek silinemedi ({path}): {e}")

    def create_system_backup(self, reason="auto"):
        backup_dir = self.sanitize_backup_dir(self.auto_backup_dir)
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_name = f"fastfoot-backup-{timestamp}.tar.gz"
        backup_path = os.path.join(backup_dir, backup_name)

        temp_dir = tempfile.mkdtemp(prefix="fastfoot-backup-")
        try:
            db_dump_path = self.create_database_backup(temp_dir)
            with tarfile.open(backup_path, "w:gz") as archive:
                manifest = {
                    "created_at": datetime.datetime.now().isoformat(),
                    "reason": reason,
                    "database_included": bool(db_dump_path),
                    "company_name": self.company_name,
                }
                manifest_path = os.path.join(temp_dir, "manifest.json")
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, ensure_ascii=False, indent=2)
                archive.add(manifest_path, arcname="manifest.json")
                if db_dump_path:
                    archive.add(db_dump_path, arcname="database/postgresql.dump")

                files, directories = self.get_backup_sources()
                for file_path in files:
                    self.add_path_to_backup(archive, file_path)
                for dir_path in directories:
                    self.add_path_to_backup(archive, dir_path)

            self.cleanup_old_backups()
            self.last_backup_info = {
                "path": backup_path,
                "created_at": datetime.datetime.now().isoformat(),
                "reason": reason,
            }
            logger.info(f"✅ Sistem yedeği oluşturuldu: {backup_path}")
            return backup_path
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def should_run_auto_backup(self, now=None):
        if not self.auto_backup_enabled:
            return False
        now = now or datetime.datetime.now()
        backup_time = datetime.datetime.strptime(self.auto_backup_time, "%H:%M").time()
        scheduled_at = datetime.datetime.combine(now.date(), backup_time)
        return now >= scheduled_at and self.auto_backup_last_date != now.date().isoformat()

    def run_auto_backup_if_needed(self):
        if not self.should_run_auto_backup():
            return None
        backup_path = self.create_system_backup(reason="auto")
        self.auto_backup_last_date = datetime.date.today().isoformat()
        self.save_settings()
        return backup_path

    def start_auto_backup_scheduler(self):
        if self.auto_backup_thread and self.auto_backup_thread.is_alive():
            return

        def task():
            while True:
                try:
                    self.run_auto_backup_if_needed()
                except Exception as e:
                    logger.error(f"Otomatik yedekleme zamanlayıcı hatası: {e}")
                time.sleep(60)

        self.auto_backup_thread = threading.Thread(target=task, daemon=True)
        self.auto_backup_thread.start()

    def close_shift_with_db_totals(self, shift_id, closing_data=None, source="manual"):
        """Vardiyayı satış toplamlarıyla kapat; boş manuel alanlarda DB toplamlarını kullan."""
        closing_data = closing_data or {}
        totals = db.get_shift_closing_totals(shift_id)

        def parse_closing_amount(field_name, default_value):
            raw_value = closing_data.get(field_name)
            if raw_value is None or str(raw_value).strip() == "":
                if source == "manual":
                    logger.warning(
                        f"Vardiya kapatma {field_name} boş geldi; DB satış toplamı kullanıldı "
                        f"(shift_id={shift_id}, tutar={default_value})"
                    )
                return float(default_value)
            try:
                amount = float(str(raw_value).replace(",", "."))
            except (TypeError, ValueError):
                raise ValueError(f"{field_name} tutarı geçersiz")
            if amount < 0:
                raise ValueError(f"{field_name} tutarı negatif olamaz")
            return amount

        nakit = parse_closing_amount('nakit', totals['nakit'])
        kart = parse_closing_amount('kart', totals['kart'])
        diger = parse_closing_amount('diger', totals['diger'])
        kapanis_bakiyesi = nakit + kart + diger
        db.close_shift(shift_id, nakit, kart, kapanis_bakiyesi)
        self.revoke_public_sessions_for_shift(int(shift_id))
        return {
            'success': True,
            'nakit': nakit,
            'kart': kart,
            'diger': diger,
            'kapanis_bakiyesi': kapanis_bakiyesi
        }

    def get_shift_auto_close_cutoff(self, now=None):
        now = now or datetime.datetime.now()
        close_time = datetime.datetime.strptime(self.shift_auto_close_time, "%H:%M").time()
        today_cutoff = datetime.datetime.combine(now.date(), close_time)
        if now >= today_cutoff:
            return today_cutoff
        return today_cutoff - datetime.timedelta(days=1)

    def get_seconds_until_next_shift_auto_close(self, now=None):
        now = now or datetime.datetime.now()
        close_time = datetime.datetime.strptime(self.shift_auto_close_time, "%H:%M").time()
        next_cutoff = datetime.datetime.combine(now.date(), close_time)
        if now >= next_cutoff:
            next_cutoff += datetime.timedelta(days=1)
        return max(10, (next_cutoff - now).total_seconds() + 2)

    def auto_close_overdue_shifts(self):
        """Seçilen kapanış saatini geçmiş açık vardiyaları otomatik kapat."""
        if not USE_DATABASE or not self.shift_auto_close_enabled:
            return []

        cutoff_at = self.get_shift_auto_close_cutoff()
        closed_shifts = []
        for shift in db.get_overdue_open_shifts(cutoff_at):
            shift_id = shift.get('id')
            try:
                result = self.close_shift_with_db_totals(shift_id, source="auto_close")
                closed_shifts.append({
                    'id': shift_id,
                    'kasa_id': shift.get('kasa_id'),
                    'kasa_adi': shift.get('kasa_adi'),
                    'kapanis_bakiyesi': result['kapanis_bakiyesi']
                })
                logger.info(
                    f"✓ Vardiya otomatik kapatıldı: shift_id={shift_id}, "
                    f"kasa={shift.get('kasa_adi')}, saat={self.shift_auto_close_time}, "
                    f"kesit={cutoff_at.isoformat()}, kapanis={result['kapanis_bakiyesi']:.2f}"
                )
            except Exception as e:
                logger.error(f"Vardiya otomatik kapatma hatası (shift_id={shift_id}): {e}")

        if closed_shifts:
            socketio.emit('vardiya_update', None)
        return closed_shifts

    def start_shift_auto_close_scheduler(self):
        if self.shift_auto_close_thread and self.shift_auto_close_thread.is_alive():
            return

        def task():
            while True:
                try:
                    self.auto_close_overdue_shifts()
                except Exception as e:
                    logger.error(f"Vardiya otomatik kapatma zamanlayıcı hatası: {e}")

                sleep_seconds = self.get_seconds_until_next_shift_auto_close()
                time.sleep(min(sleep_seconds, 60))

        self.shift_auto_close_thread = threading.Thread(target=task, daemon=True)
        self.shift_auto_close_thread.start()

    def ensure_default_portion_stock(self):
        """Sadece günlük yemekler için porsiyon stoku tut."""
        now_iso = datetime.datetime.now().isoformat()
        changed = False
        with self.portion_lock:
            for stock_key, entry in list(self.portion_stock.items()):
                if not self._is_daily_meal_stock_entry(stock_key, entry):
                    del self.portion_stock[stock_key]
                    changed = True

            for category in self._daily_meal_categories():
                total = self.get_daily_meal_group_total(category)
                group_key = self._normalize_product_key(category)
                if total > 0 and group_key:
                    if group_key not in self.portion_stock:
                        self.portion_stock[group_key] = {
                            'urun': category,
                            'kategori': category,
                            'kalan': self._coerce_portion_amount(total),
                            'updated_at': now_iso,
                            'is_default': False
                        }
                        changed = True
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
                    changed = True

            if changed:
                self.save_portion_stock()

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
                    if not self._is_daily_meal_stock_name(canonical_name):
                        continue
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
                    if not urun or not self._is_daily_meal_stock_name(urun):
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
            if not self._is_daily_meal_stock_name(canonical_name):
                errors.append(f"{canonical_name} günlük yemek listesinde değil")
                continue
            if raw_kalan is None or raw_kalan == '':
                stock_entry = self.portion_stock.get(stock_key, {})
                raw_kalan = stock_entry.get('kalan', 0)

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
            if not self._should_track_portion_order(urun, not_bilgisi):
                continue
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

    def consume_portion_stock_for_order(self, items):
        self.reset_daily_portion_stock_if_needed()
        self.ensure_default_portion_stock()
        required = defaultdict(float)
        names = {}
        for item in items:
            urun = str(item.get('urun') or item.get('name') or '').strip()
            if not urun:
                continue
            not_bilgisi = item.get('not') or item.get('not_bilgisi') or ''
            if not self._should_track_portion_order(urun, not_bilgisi):
                continue
            units = self.get_portion_units_for_order(urun, item.get('adet', 1))
            key = self.get_portion_stock_key(urun, not_bilgisi)
            required[key] += units
            names[key] = self.get_order_portion_stock_name(urun, not_bilgisi)
            group_name = self.get_daily_meal_group_for_product(urun)
            if group_name and self._normalize_product_key(group_name) != key:
                group_key = self._normalize_product_key(group_name)
                required[group_key] += units
                names[group_key] = group_name

        if not required:
            return True, None

        changed = []
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

            now_iso = datetime.datetime.now().isoformat()
            for key, required_units in required.items():
                entry = self.portion_stock.get(key)
                if not entry:
                    continue
                kalan = self._coerce_portion_amount(entry.get('kalan', 0))
                entry['kalan'] = round(kalan - required_units, 2)
                entry['is_default'] = False
                entry['updated_at'] = now_iso
                changed.append({
                    'urun': entry.get('urun') or names.get(key, 'Ürün'),
                    'kategori': entry.get('kategori'),
                    'kalan': self._portion_amount_for_json(entry['kalan']),
                    'tracked': True
                })
            self.save_portion_stock()

        self.emit_portion_stock_update(changed)
        return True, None

    def consume_portion_stock(self, urun, adet=1, not_bilgisi=''):
        self.reset_daily_portion_stock_if_needed()
        self.ensure_default_portion_stock()
        if not self._should_track_portion_order(urun, not_bilgisi):
            return True, None
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
        if not self._should_track_portion_order(urun, not_bilgisi):
            return False
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
                        kategori=item.get('kategori') or item.get('category'),
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
                    'adet': self.coerce_order_quantity(h['adet']),
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

def auth_error_response(message, status=401):
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"success": False, "error": message, "auth_required": status == 401}), status
    next_url = urllib.parse.quote(request.full_path if request.query_string else request.path)
    return redirect(f"/login?next={next_url}")


def require_auth_page(page_key=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user, err, status = server.validate_current_request(required_page=page_key)
            if not user:
                return auth_error_response(err, status)
            g.current_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator


@app.before_request
def enforce_auth_for_pages_and_apis():
    path = request.path or "/"
    if server.is_public_request_path(path):
        return None

    ext = os.path.splitext(path)[1].lower()
    required_page = server.required_page_for_path(path)

    if required_page or path.startswith("/api/") or ext == ".html":
        user, err, status = server.validate_current_request(required_page=required_page)
        if not user:
            return auth_error_response(err, status)
        g.current_user = user
    return None


@app.route('/login')
def login_page():
    """Kullanıcı giriş sayfası"""
    return app.send_static_file('login.html')


@app.route('/api/auth/options')
def auth_options_api():
    """Giriş ekranı için kullanıcı ve yetki seçenekleri."""
    return jsonify({
        'success': True,
        'users': server.list_login_users(),
        'roles': server.get_auth_role_definitions(),
        'pages': server.get_auth_page_definitions()
    })


@app.route('/api/auth/me')
def auth_me_api():
    """Aktif oturum bilgisi."""
    token = server.get_request_token()
    user, err, status = server.validate_auth_token(token) if token else (None, None, 200)
    if not user:
        return jsonify({'success': False, 'user': None, 'error': err, 'status': status})
    requested_path = request.args.get('path') or ''
    page_key = server.required_page_for_path(requested_path) if requested_path else None
    return jsonify({
        'success': True,
        'user': server.public_user(user),
        'can_access_path': server.user_has_permission(user, page_key) if page_key else True
    })


@app.route('/api/auth/login', methods=['POST'])
def auth_login_api():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or data.get('username') or '').strip()
    pin = str(data.get('pin') or '')
    requested_path = server.normalize_local_path(data.get('next') or data.get('path') or request.args.get('next') or '/')
    remember = bool(data.get('remember', True))
    user, err = server.authenticate_login(name, pin, requested_path=requested_path)
    if not user:
        return jsonify({'success': False, 'error': err or 'Giriş yapılamadı'}), 401

    # Hedef sayfaya yetkisi yoksa, yetkili olduğu sayfaya yönlendir
    redirect_path = requested_path or '/'
    page_key = server.required_page_for_path(redirect_path)
    if page_key and not server.user_has_permission(user, page_key):
        redirect_path = server.get_user_landing_page(user)

    token, max_age = server.create_auth_session(
        user,
        remember=remember,
        device_name=data.get('device_name') or '',
        ip=request.remote_addr or '',
        user_agent=request.headers.get('User-Agent', '')
    )
    response = make_response(jsonify({
        'success': True,
        'user': server.public_user(user),
        'next': redirect_path
    }))
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=max_age if remember else None,
        httponly=True,
        samesite='Lax'
    )
    return response


@app.route('/api/auth/logout', methods=['POST'])
@require_auth_page()
def auth_logout_api():
    token = server.get_request_token()
    if token:
        server.revoke_auth_session(token)
    response = make_response(jsonify({'success': True}))
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


@app.route('/logout')
def auth_logout_page():
    """Kullanıcı oturumunu kapatıp giriş ekranına döndür."""
    token = server.get_request_token()
    if token:
        server.revoke_auth_session(token)
    response = make_response(redirect('/login?next=/'))
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


@app.route('/api/auth/users', methods=['GET'])
@require_auth_page('personel')
def auth_users_api():
    return jsonify({
        'success': True,
        'users': [server.public_user(user) for user in server.users],
        'roles': server.get_auth_role_definitions(),
        'pages': server.get_auth_page_definitions()
    })


@app.route('/api/auth/users', methods=['POST'])
@require_auth_page('personel')
def auth_user_save_api():
    actor = getattr(g, 'current_user', None)
    user, err = server.upsert_user(request.get_json(silent=True) or {}, actor=actor)
    if not user:
        return jsonify({'success': False, 'error': err}), 400
    return jsonify({'success': True, 'user': server.public_user(user)})


@app.route('/api/auth/users/<user_id>', methods=['DELETE'])
@require_auth_page('personel')
def auth_user_delete_api(user_id):
    actor = getattr(g, 'current_user', None)
    ok, err = server.delete_user(user_id, actor=actor)
    if not ok:
        return jsonify({'success': False, 'error': err}), 400
    return jsonify({'success': True})

@app.route('/')
def index():
    """Ana sayfa"""
    return app.send_static_file('index.html')

@app.route('/kasa-terminal')
def kasa_terminal_page():
    """Sipariş girişi kapalı kasa/hesap terminali"""
    return app.send_static_file('index.html')

@app.route('/reservations')
def reservations_page():
    """Rezervasyon takip sayfası"""
    return app.send_static_file('reservations.html')

@app.route('/terminals')
def terminals():
    """Terminal yönetim sayfası"""
    return app.send_static_file('terminals.html')

@app.route('/settings')
def settings_page():
    """Ayarlar sayfası"""
    response = make_response(app.send_static_file('settings.html'))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response

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

@app.route('/raporlar')
def raporlar_page():
    """Operasyon raporları sayfası"""
    return app.send_static_file('raporlar.html')

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

@app.route('/garson-terminal')
@app.route('/waiter/shared')
def shared_waiter_terminal_page():
    """Ortak ve kilitli garson terminali"""
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

@app.route('/api/dashboard/status')
def dashboard_status():
    """Ana ekran için kasa/ÖKC/yazıcı durum özeti; teknik adres döndürmez."""
    kasa_id = request.args.get('kasa_id')
    return jsonify(server.get_dashboard_operational_status(kasa_id))

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
        'paket_labels': server.get_paket_labels(),
        'direct_print': server.direct_print,
        'default_payment_method': server.default_payment_method,
        'shift_auto_close_enabled': server.shift_auto_close_enabled,
        'shift_auto_close_time': server.shift_auto_close_time,
        'auto_backup_enabled': server.auto_backup_enabled,
        'auto_backup_time': server.auto_backup_time,
        'auto_backup_dir': server.auto_backup_dir,
        'auto_backup_retention_days': server.auto_backup_retention_days,
        'auto_backup_last_date': server.auto_backup_last_date,
        'last_backup_info': server.last_backup_info,
        'cid_port': server.cid_port,
        'cid_type': server.cid_type,
        'cid_serial_port': server.cid_serial_port,
        'cid_enabled': server.cid_enabled,
        'pos_enabled': server.pos_enabled,
        'pos_ip': server.pos_ip,
        'pos_port': server.pos_port,
        'pos_type': server.pos_type,
        'default_kdv_rate': server.default_kdv_rate,
        'salons': server.salons,
        'prep_panels': server.get_preparation_panels(),
        'prep_category_overrides': server.prep_category_overrides,
        'prep_ticket_skip_products': server.prep_ticket_skip_products,
        'prep_printers': server.prep_printers,
        'receipt_printer': server.receipt_printer,
        'menu_categories': list(server.menu_data.keys()),
        'menu_products': server.get_menu_product_options(),
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
        if not server.sync_admin_password_to_auth_user(yeni_sifre):
            return jsonify({'success': False, 'error': 'Yönetici şifresi güncellenemedi'}), 500

    # Diğer ayarları güncelle
    server.company_name  = data.get('firma_ismi',   server.company_name)
    server.terminal_id   = data.get('terminal_id',  server.terminal_id)
    server.direct_print  = data.get('direct_print', server.direct_print)
    server.default_payment_method = server.sanitize_payment_method(
        data.get('default_payment_method', server.default_payment_method)
    )
    server.shift_auto_close_enabled = server.bool_from_setting(
        data.get('shift_auto_close_enabled', server.shift_auto_close_enabled),
        server.shift_auto_close_enabled
    )
    server.shift_auto_close_time = server.sanitize_time_setting(
        data.get('shift_auto_close_time', server.shift_auto_close_time),
        server.shift_auto_close_time
    )
    server.auto_backup_enabled = server.bool_from_setting(
        data.get('auto_backup_enabled', server.auto_backup_enabled),
        server.auto_backup_enabled
    )
    server.auto_backup_time = server.sanitize_time_setting(
        data.get('auto_backup_time', server.auto_backup_time),
        server.auto_backup_time
    )
    server.auto_backup_dir = server.sanitize_backup_dir(
        data.get('auto_backup_dir', server.auto_backup_dir)
    )
    server.auto_backup_retention_days = server.bounded_int(
        data.get('auto_backup_retention_days', server.auto_backup_retention_days),
        server.auto_backup_retention_days,
        1,
        3650
    )

    yeni_masa = int(data.get('masa_sayisi', server.masa_sayisi))
    yeni_paket = int(data.get('paket_sayisi', server.paket_sayisi))
    yeni_paket_labels = server.paket_labels
    paket_labels_degisti = False
    if 'paket_labels' in data:
        yeni_paket_labels = server.sanitize_paket_labels(data.get('paket_labels'))
        yeni_paket = len(yeni_paket_labels)
        paket_labels_degisti = (yeni_paket_labels != server.get_paket_labels())

    masa_degisti = (
        yeni_masa != server.masa_sayisi
        or yeni_paket != server.paket_sayisi
        or paket_labels_degisti
    )
    server.masa_sayisi   = yeni_masa
    server.paket_sayisi  = yeni_paket
    if 'paket_labels' in data:
        server.paket_labels = yeni_paket_labels
        server.paket_labels_configured = True
    
    server.cid_port = int(data.get('cid_port', server.cid_port))
    server.cid_type = data.get('cid_type', server.cid_type)
    server.cid_serial_port = data.get('cid_serial_port', server.cid_serial_port)
    server.cid_enabled = data.get('cid_enabled', server.cid_enabled)
    
    server.pos_enabled = data.get('pos_enabled', server.pos_enabled)
    server.pos_ip = data.get('pos_ip', server.pos_ip)
    server.pos_port = int(data.get('pos_port', server.pos_port))
    server.pos_type = data.get('pos_type', server.pos_type)
    server.default_kdv_rate = server.sanitize_tax_rate(
        data.get('default_kdv_rate', server.default_kdv_rate),
        server.default_kdv_rate
    )

    server.prep_panel_settings = server.sanitize_prep_panel_settings(
        data.get('prep_panels', server.prep_panel_settings)
    )
    ok, rename_error = server.rename_menu_categories(data.get('menu_category_renames'))
    if not ok:
        return jsonify({'success': False, 'error': rename_error or 'Menü kategorileri güncellenemedi'}), 400

    server.prep_category_overrides = server.sanitize_prep_category_overrides(
        data.get('prep_category_overrides', server.prep_category_overrides)
    )
    server.prep_ticket_skip_products = server.sanitize_prep_ticket_skip_products(
        data.get('prep_ticket_skip_products', server.prep_ticket_skip_products)
    )
    server.prep_printers = server.sanitize_prep_printer_settings(
        data.get('prep_printers', server.prep_printers)
    )
    server.receipt_printer = server.sanitize_receipt_printer_settings(
        data.get('receipt_printer', server.receipt_printer)
    )
    server.normalize_active_order_panels()

    server.va_max_duration = int(data.get('va_max_duration', server.va_max_duration))
    server.va_rate_limit = int(data.get('va_rate_limit', server.va_rate_limit))
    server.va_sms_verify = data.get('va_sms_verify', server.va_sms_verify)
    server.va_kitchen_approval = data.get('va_kitchen_approval', server.va_kitchen_approval)
    
    # POS Manager'ı güncelle
    server.pos_manager = POSManager(
        server.pos_enabled,
        server.pos_ip,
        server.pos_port,
        server.pos_type,
        server.default_kdv_rate
    )
    server.clear_dashboard_status_cache()

    # Kaydet
    ok = server.save_settings()
    if ok and 'paket_labels' in data:
        ok = server.save_paket_labels()
    if not ok:
        return jsonify({'success': False, 'error': 'Dosyaya yazılamadı'}), 500

    if server.shift_auto_close_enabled:
        server.auto_close_overdue_shifts()

    # Masa/paket yapısı değiştiyse yenile
    if masa_degisti:
        server.refresh_adisyonlar(preserve_existing=True)
        server.save_active_adisyonlar()
        socketio.emit('system_update', {
            'masa_sayisi':  server.masa_sayisi,
            'paket_sayisi': server.paket_sayisi,
            'paket_labels': server.get_paket_labels(),
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

def _parse_report_date(value, default_value):
    raw = (value or default_value or '').strip()
    try:
        return datetime.datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError(f"Geçersiz tarih: {raw}")

def _date_range_from_request(default_days=0):
    today = datetime.date.today()
    default_start = today - datetime.timedelta(days=max(default_days, 0))
    baslangic = _parse_report_date(request.args.get('baslangic'), default_start.isoformat())
    bitis = _parse_report_date(request.args.get('bitis'), today.isoformat())
    if baslangic > bitis:
        raise ValueError("Başlangıç tarihi bitiş tarihinden sonra olamaz")
    if (bitis - baslangic).days > 366:
        raise ValueError("Rapor aralığı en fazla 366 gün olabilir")
    return baslangic.isoformat(), bitis.isoformat()

def _float_value(value):
    return float(value or 0)

def _int_value(value):
    return int(value or 0)

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
                'fatura_bekleyen_adet': int(r.get('fatura_bekleyen_adet') or 0),
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
    """Günlük ürün bazlı kalem toplamları"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'}), 503
    tarih = request.args.get('tarih', datetime.datetime.now().strftime('%Y-%m-%d'))
    try:
        rows = db.get_item_totals_by_date(tarih)
        result = []
        for r in rows:
            result.append({
                'urun': r['urun'],
                'adet': server.coerce_order_quantity(r['adet']),
                'satis_adet': server.coerce_order_quantity(r['satis_adet']),
                'ikram_adet': server.coerce_order_quantity(r['ikram_adet']),
                'toplam': _float_value(r['toplam']),
                'ikram_toplam': _float_value(r['ikram_toplam']),
                'ortalama_fiyat': _float_value(r['ortalama_fiyat'])
            })
        return jsonify({'success': True, 'detay': result, 'tarih': tarih})
    except Exception as e:
        logger.error(f"Gün sonu detay hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/gunsonu/fatura-istekleri')
def get_gunsonu_fatura_istekleri():
    """Günlük e-fatura/e-arşiv isteklerini adisyon bazında grupla."""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'}), 503
    tarih = request.args.get('tarih', datetime.datetime.now().strftime('%Y-%m-%d'))
    type_map = {
        9005: 'Matbu',
        9006: 'E-Fatura',
        9007: 'E-Arşiv',
    }
    try:
        rows = db.get_invoice_requests_by_date(tarih)
        result = []
        toplam = 0.0
        for r in rows:
            tutar = _float_value(r.get('toplam'))
            toplam += tutar
            document_type = _int_value(r.get('invoice_document_type') or 0)
            tarih_saat = r.get('tarih_saat')
            result.append({
                'id': r.get('ilk_satis_id'),
                'tarih_saat': tarih_saat.isoformat() if hasattr(tarih_saat, 'isoformat') else str(tarih_saat or ''),
                'masa': r.get('masa') or 'Kasa',
                'odeme': r.get('odeme') or 'Diğer',
                'terminal_id': r.get('terminal_id') or '',
                'vardiya_id': r.get('vardiya_id'),
                'invoice_document_type': document_type or None,
                'invoice_document_label': type_map.get(document_type, 'Fatura'),
                'invoice_tax_id': r.get('invoice_tax_id') or '',
                'invoice_serial_no': r.get('invoice_serial_no') or '',
                'invoice_note': r.get('invoice_note') or '',
                'satis_adet': _float_value(r.get('satis_adet')),
                'kalem_sayisi': _int_value(r.get('kalem_sayisi')),
                'toplam': tutar,
                'urunler': r.get('urunler') or '',
            })
        return jsonify({
            'success': True,
            'fatura_istekleri': result,
            'adet': len(result),
            'toplam': toplam,
            'tarih': tarih
        })
    except Exception as e:
        logger.error(f"Gün sonu fatura istekleri hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/raporlar/operasyon')
def get_operasyon_raporlari():
    """Talep, yoğunluk ve zaman raporları"""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'}), 503
    try:
        baslangic, bitis = _date_range_from_request(default_days=6)
        report = db.get_operational_reports(baslangic, bitis)
        totals = report.get('totals') or {}
        hourly_rows = {
            _int_value(row.get('saat')): row
            for row in report.get('hourly_load', [])
        }
        hourly_load = []
        for hour in range(24):
            row = hourly_rows.get(hour, {})
            hourly_load.append({
                'saat': hour,
                'adet': _float_value(row.get('adet')),
                'ciro': _float_value(row.get('ciro')),
                'satir_sayisi': _int_value(row.get('satir_sayisi')),
            })

        product_demand = [{
            'urun': row.get('urun') or 'Ürün',
            'adet': _float_value(row.get('adet')),
            'satis_adet': _float_value(row.get('satis_adet')),
            'ikram_adet': _float_value(row.get('ikram_adet')),
            'ciro': _float_value(row.get('ciro')),
            'ikram_toplam': _float_value(row.get('ikram_toplam')),
        } for row in report.get('product_demand', [])]

        channel_mix = [{
            'kanal': row.get('kanal') or 'Diğer',
            'adet': _float_value(row.get('adet')),
            'ciro': _float_value(row.get('ciro')),
            'satir_sayisi': _int_value(row.get('satir_sayisi')),
        } for row in report.get('channel_mix', [])]

        day_trend = [{
            'tarih': row['tarih'].isoformat() if hasattr(row.get('tarih'), 'isoformat') else str(row.get('tarih') or ''),
            'adet': _float_value(row.get('adet')),
            'ciro': _float_value(row.get('ciro')),
            'satir_sayisi': _int_value(row.get('satir_sayisi')),
        } for row in report.get('day_trend', [])]

        return jsonify({
            'success': True,
            'baslangic': baslangic,
            'bitis': bitis,
            'totals': {
                'ciro': _float_value(totals.get('ciro')),
                'adet': _float_value(totals.get('adet')),
                'ikram_adet': _float_value(totals.get('ikram_adet')),
                'ikram_toplam': _float_value(totals.get('ikram_toplam')),
                'satir_sayisi': _int_value(totals.get('satir_sayisi')),
                'gun_sayisi': _int_value(totals.get('gun_sayisi')),
                'aktif_saat_sayisi': _int_value(totals.get('aktif_saat_sayisi')),
            },
            'product_demand': product_demand,
            'hourly_load': hourly_load,
            'channel_mix': channel_mix,
            'day_trend': day_trend,
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Operasyon raporları hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== CARİ İŞLEMLER API ====================

def _normalize_csv_key(value):
    text = str(value or "").strip().lower()
    tr_map = str.maketrans({
        "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
        "Ç": "c", "Ğ": "g", "İ": "i", "I": "i", "Ö": "o", "Ş": "s", "Ü": "u",
    })
    text = text.translate(tr_map)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _csv_aliases(*names):
    return {_normalize_csv_key(name) for name in names}


CARI_CSV_FIELDS = {
    "cari_isim": _csv_aliases(
        "cari_isim", "cari isim", "cari adı", "cari adi", "cari ad",
        "müşteri", "musteri", "müşteri adı", "musteri adi", "musteri_adi",
        "müşteri ünvanı", "musteri unvani", "ad soyad", "ad_soyad",
        "adı soyadı", "adi soyadi", "isim", "unvan", "ünvan", "firma"
    ),
    "telefon": _csv_aliases(
        "telefon", "tel", "gsm", "cep", "cep telefonu", "telefon no",
        "telefon_no", "tel no", "tel_no", "cep tel", "cep_tel",
        "telefon numarası", "telefon numarasi", "phone"
    ),
    "vergi_no": _csv_aliases(
        "vkn", "tckn", "vkn/tckn", "vkn tckn", "vergi no",
        "vergi_no", "vergi numarası", "vergi numarasi", "tc kimlik no",
        "tc kimlik", "t.c. kimlik", "tax id", "tax_id"
    ),
    "adres": _csv_aliases(
        "adres", "address", "müşteri adresi", "musteri adresi",
        "teslimat adresi", "teslimat_adresi"
    ),
    "devreden_borc": _csv_aliases(
        "devreden borç", "devreden borc", "devreden_borc", "devir borcu",
        "devir_borcu", "önceki borç", "onceki borc", "eski borç",
        "eski borc", "borç", "borc", "borcu"
    ),
    "devreden_alacak": _csv_aliases(
        "devreden alacak", "devreden_alacak", "alacak", "alacağı",
        "alacagi", "credit"
    ),
    "bakiye": _csv_aliases(
        "bakiye", "balance", "devreden bakiye", "devreden_bakiye",
        "devir", "devreden"
    ),
}


def _decode_csv_upload(raw_bytes):
    for encoding in ("utf-8-sig", "utf-8", "cp1254", "iso-8859-9", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def _detect_csv_delimiter(text):
    sample = text[:4096]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {delimiter: sample.count(delimiter) for delimiter in [",", ";", "\t", "|"]}
        return max(counts, key=counts.get) if max(counts.values()) > 0 else ","


def _row_value(row, field_name):
    aliases = CARI_CSV_FIELDS[field_name]
    for key, value in row.items():
        if _csv_key_matches(key, aliases):
            return str(value or "").strip()
    return ""


def _csv_key_matches(key, aliases):
    normalized = _normalize_csv_key(key)
    return any(
        normalized == alias
        or normalized.startswith(f"{alias}_")
        or normalized.endswith(f"_{alias}")
        for alias in aliases
    )


def _parse_csv_money(value):
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0

    is_negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    cleaned = re.sub(r"[^0-9,.\-]", "", text).replace("-", "")
    if not cleaned:
        return 0.0

    last_comma = cleaned.rfind(",")
    last_dot = cleaned.rfind(".")
    if last_comma >= 0 and last_dot >= 0:
        if last_comma > last_dot:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif last_comma >= 0:
        decimal_len = len(cleaned) - last_comma - 1
        cleaned = cleaned.replace(".", "")
        cleaned = cleaned.replace(",", ".") if decimal_len in (1, 2) else cleaned.replace(",", "")
    else:
        parts = cleaned.split(".")
        if len(parts) > 2:
            if all(len(part) == 3 for part in parts[1:]):
                cleaned = "".join(parts)
            else:
                cleaned = "".join(parts[:-1]) + "." + parts[-1]
        elif len(parts) == 2 and len(parts[1]) == 3:
            cleaned = "".join(parts)

    try:
        amount = float(cleaned)
    except ValueError:
        return 0.0
    return -amount if is_negative else amount


def _normalize_tax_id(value):
    return re.sub(r"\D", "", str(value or ""))[:11]


def _has_csv_column(fieldnames, field_name):
    aliases = CARI_CSV_FIELDS[field_name]
    return any(_csv_key_matches(field, aliases) for field in (fieldnames or []))

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
                'telefon': h.get('telefon') or '',
                'adres': h.get('adres') or '',
                'vergi_no': h.get('vergi_no') or '',
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
                'tarih': str(h['tarih']) if h['tarih'] else '',
                'adisyon_detay': h.get('adisyon_detay')
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


@app.route('/api/cari/fatura', methods=['POST'])
def create_cari_invoice():
    """Cari hesabın açık borç bakiyesini e-fatura/e-arşiv taslağına gönder."""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'}), 503

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Geçersiz veri'}), 400

    cari_isim = data.get('cari_isim', '').strip()
    if not cari_isim:
        return jsonify({'success': False, 'error': 'Müşteri adı boş olamaz'}), 400

    customer = next(
        (h for h in db.get_all_cari_accounts() if h['cari_isim'] == cari_isim),
        None
    )
    data = dict(data)
    if not _normalize_tax_id(data.get('invoice_tax_id')) and customer:
        data['invoice_tax_id'] = customer.get('vergi_no') or ''
    invoice_info = normalize_invoice_info(data)
    invoice_error = validate_okc_invoice_info(invoice_info)
    if invoice_error:
        return jsonify({'success': False, 'error': invoice_error}), 400

    try:
        bakiye = db.get_cari_balance(cari_isim)
        if bakiye <= 0.01:
            return jsonify({'success': False, 'error': 'Faturaya dönüştürülecek açık borç yok'}), 400

        invoice_note = invoice_info['note'] or f"{cari_isim} cari hesap borç bakiyesi"
        timestamp = datetime.datetime.now()
        order_data = {
            'masa': f"Cari-{cari_isim}",
            'customer': cari_isim,
            'items': [{
                'urun': 'Cari hesap borç bakiyesi',
                'adet': 1,
                'fiyat': round(float(bakiye), 2),
            }],
            'total': round(float(bakiye), 2),
            'ikram_total': 0,
            'payment_type': 'Cari',
            'invoice_pending': True,
            'invoice_document_type': invoice_info['document_type'],
            'invoice_document_label': invoice_info['document_label'],
            'invoice_tax_id': invoice_info['tax_id'],
            'invoice_serial_no': invoice_info['serial_no'],
            'invoice_note': invoice_note,
            'timestamp': timestamp
        }
        if customer:
            contact_bits = [
                customer.get('telefon') or '',
                customer.get('adres') or ''
            ]
            order_data['invoice_note'] = invoice_note or ' | '.join(bit for bit in contact_bits if bit)

        success, message = server.integration_manager.send_to_accounting(order_data)
        if not success:
            return jsonify({'success': False, 'error': message}), 502

        logger.info(f"🧾 Cari fatura taslağı: {cari_isim} | {bakiye:.2f} TL")
        return jsonify({
            'success': True,
            'message': 'Cari borç e-fatura taslağına gönderildi',
            'bakiye': round(float(bakiye), 2)
        })
    except Exception as e:
        logger.error(f"Cari fatura oluşturma hatası: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cari/import_csv', methods=['POST'])
def import_cari_csv():
    """CSV dosyasından cari hesapları ve devreden bakiyeleri aktar."""
    if not USE_DATABASE:
        return jsonify({'success': False, 'error': 'Veri tabanı bağlantısı yok'}), 503

    upload = request.files.get('file')
    if not upload or not upload.filename:
        return jsonify({'success': False, 'error': 'CSV dosyası seçilmedi'}), 400

    raw = upload.read()
    if not raw:
        return jsonify({'success': False, 'error': 'CSV dosyası boş'}), 400

    text = _decode_csv_upload(raw)
    delimiter = _detect_csv_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        return jsonify({'success': False, 'error': 'CSV başlık satırı bulunamadı'}), 400
    if not _has_csv_column(reader.fieldnames, 'cari_isim'):
        return jsonify({
            'success': False,
            'error': 'CSV içinde müşteri adı kolonu bulunamadı. Örn: cari_isim, musteri_adi, isim, unvan'
        }), 400

    has_borc = _has_csv_column(reader.fieldnames, 'devreden_borc')
    has_alacak = _has_csv_column(reader.fieldnames, 'devreden_alacak')
    has_bakiye = _has_csv_column(reader.fieldnames, 'bakiye')

    imported = 0
    with_devir = 0
    skipped = 0
    errors = []

    for line_no, row in enumerate(reader, start=2):
        if not any(str(value or '').strip() for value in row.values()):
            skipped += 1
            continue

        cari_isim = _row_value(row, 'cari_isim')
        if not cari_isim:
            skipped += 1
            errors.append({'line': line_no, 'error': 'Müşteri adı boş'})
            continue

        telefon = _row_value(row, 'telefon') or None
        adres = _row_value(row, 'adres') or None
        vergi_no = _normalize_tax_id(_row_value(row, 'vergi_no')) or None

        if has_borc or has_alacak:
            devreden_bakiye = _parse_csv_money(_row_value(row, 'devreden_borc'))
            devreden_bakiye -= _parse_csv_money(_row_value(row, 'devreden_alacak'))
        elif has_bakiye:
            devreden_bakiye = _parse_csv_money(_row_value(row, 'bakiye'))
        else:
            devreden_bakiye = 0.0

        try:
            db.get_or_create_cari(cari_isim)
            if telefon or adres or vergi_no:
                db.update_cari_details(cari_isim, telefon, adres, vergi_no)
            if abs(devreden_bakiye) >= 0.01:
                islem = 'borc' if devreden_bakiye > 0 else 'odeme'
                db.save_cari_transaction(cari_isim, islem, round(devreden_bakiye, 2))
                with_devir += 1
            imported += 1
        except Exception as e:
            errors.append({'line': line_no, 'error': str(e)})

    logger.info(
        f"📥 Cari CSV aktarımı: {imported} hesap, {with_devir} devreden bakiye, "
        f"{skipped} atlanan satır, {len(errors)} hata"
    )
    return jsonify({
        'success': imported > 0,
        'imported': imported,
        'with_devir': with_devir,
        'skipped': skipped,
        'errors': errors[:20],
        'error_count': len(errors),
        'error': None if imported > 0 else 'Aktarılacak geçerli satır bulunamadı'
    }), 200 if imported > 0 else 400

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
    data = request.json or {}
    shift_id = data.get('shift_id')

    if not shift_id: return jsonify({'success': False, 'error': 'Vardiya ID gerekli'})
    try:
        result = server.close_shift_with_db_totals(shift_id, data)
        # Tüm bağlı istemcilere vardiya kapandığını bildir
        socketio.emit('vardiya_update', None)
        return jsonify(result)
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

    telefon = (data.get('telefon') or '').strip() or None
    adres = (data.get('adres') or '').strip() or None
    vergi_no = _normalize_tax_id(data.get('vergi_no'))
    if vergi_no and len(vergi_no) not in (10, 11):
        return jsonify({'success': False, 'error': 'VKN/TCKN 10 veya 11 haneli olmalı'}), 400
    raw_devreden = data.get('devreden_bakiye', '')
    raw_devreden_text = str(raw_devreden or '').strip()
    if raw_devreden_text and not re.search(r'\d', raw_devreden_text):
        return jsonify({'success': False, 'error': 'Geçerli devreden bakiye girin'}), 400
    devreden_bakiye = _parse_csv_money(raw_devreden_text) if raw_devreden_text else 0.0
    
    try:
        db.get_or_create_cari(cari_isim)
        if telefon or adres or vergi_no:
            db.update_cari_details(cari_isim, telefon, adres, vergi_no)
        if abs(devreden_bakiye) >= 0.01:
            islem = 'borc' if devreden_bakiye > 0 else 'odeme'
            db.save_cari_transaction(cari_isim, islem, round(devreden_bakiye, 2))
        logger.info(f"👤 Yeni cari hesap: {cari_isim}")
        return jsonify({'success': True, 'devreden_bakiye': devreden_bakiye})
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
                    'vergi_no': customer.get('vergi_no') or '',
                    'bakiye': bakiye
                },
                'history': [
                    {
                        'urun': h['urun'], 
                        'adet': server.coerce_order_quantity(h['adet']),
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
    if not data:
        return jsonify({'success': False, 'error': 'Geçersiz veri'}), 400
    cari_isim = data.get('cari_isim')
    telefon = data.get('telefon')
    adres = data.get('adres')
    vergi_no = _normalize_tax_id(data.get('vergi_no'))
    if vergi_no and len(vergi_no) not in (10, 11):
        return jsonify({'success': False, 'error': 'VKN/TCKN 10 veya 11 haneli olmalı'}), 400
    
    if not cari_isim:
        return jsonify({'success': False, 'error': 'Müşteri adı gerekli'})
        
    try:
        db.update_cari_details(cari_isim, telefon, adres, vergi_no)
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
            kategori=item.get('kategori') or item.get('category'),
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
        data = request.get_json(silent=True) or {}
        name = data.get('name', '').strip()
        pin = data.get('pin', '').strip()
        if not name or not pin:
            return jsonify({'success': False, 'error': 'İsim ve PIN gerekli'})
        
        server.waiters.append({'name': name, 'pin': pin})
        server.save_waiters()
        server.sync_staff_auth_user(name, pin, 'waiter', 'waiter')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/waiters/<int:idx>', methods=['DELETE'])
def delete_waiter_api(idx):
    try:
        if 0 <= idx < len(server.waiters):
            waiter = server.waiters.pop(idx)
            server.save_waiters()
            server.delete_staff_auth_user((waiter or {}).get('name'), 'waiter')
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
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        pin = (data.get('pin') or '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'İsim gerekli'})
        if not pin:
            return jsonify({'success': False, 'error': 'PIN gerekli'})
        server.cashiers.append({'name': name, 'pin': pin})
        server.save_cashiers()
        server.sync_staff_auth_user(name, pin, 'cashier', 'cashier')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/cashiers/<int:idx>', methods=['DELETE'])
def delete_cashier_api(idx):
    try:
        if 0 <= idx < len(server.cashiers):
            cashier = server.cashiers.pop(idx)
            server.save_cashiers()
            server.delete_staff_auth_user((cashier or {}).get('name'), 'cashier')
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
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        pin = (data.get('pin') or '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'İsim gerekli'}), 400
        if not pin:
            return jsonify({'success': False, 'error': 'PIN gerekli'}), 400
            
        server.kitchen.append({'name': name, 'pin': pin})
        server.save_kitchen()
        server.sync_staff_auth_user(name, pin, 'kitchen', 'kitchen')
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/kitchen/<int:idx>', methods=['DELETE'])
def delete_kitchen_api(idx):
    """Mutfak personelini sil"""
    try:
        if 0 <= idx < len(server.kitchen):
            kitchen_staff = server.kitchen.pop(idx)
            server.save_kitchen()
            server.delete_staff_auth_user((kitchen_staff or {}).get('name'), 'kitchen')
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
    data = request.get_json(silent=True) or {}
    name = data.get('name', '')
    pin = data.get('pin', '')
    user, err = server.authenticate_login(name, pin, requested_path='/waiter')
    if not user or not server.user_has_permission(user, 'waiter'):
        return jsonify({'success': False, 'error': err or 'Hatalı PIN!'}), 401
    token, max_age = server.create_auth_session(
        user,
        remember=True,
        device_name='Garson ekranı',
        ip=request.remote_addr or '',
        user_agent=request.headers.get('User-Agent', '')
    )
    response = make_response(jsonify({'success': True, 'user': server.public_user(user)}))
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        samesite='Lax'
    )
    return response

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
        paket_labels = None
        if isinstance(data, dict):
            paket_labels = data.get('paket_labels')
            data = data.get('salons')
        if not isinstance(data, list):
            return jsonify({'success': False, 'error': 'Geçersiz veri formatı'})
            
        with open(SALONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        # Sunucu cache'ini yenile
        global server
        server.salons = data
        if paket_labels is not None:
            server.paket_labels = server.sanitize_paket_labels(paket_labels)
            if not server.save_paket_labels():
                return jsonify({'success': False, 'error': 'Paket etiketleri kaydedilemedi'})
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
            kategori = str(it.get('kategori') or it.get('category') or '').strip()[:80]
        except Exception:
            continue
        if not urun or adet <= 0 or fiyat < 0:
            continue
        order_candidates.append({
            'urun': urun,
            'adet': adet,
            'fiyat': fiyat,
            'not': not_bilgisi,
            'kategori': kategori
        })

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
            kategori=item.get('kategori'),
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

    current_user = getattr(g, 'current_user', None)
    authorized = bool(current_user and server.user_has_permission(current_user, 'table_session'))
    if admin_password and admin_password == server.admin_password:
        authorized = True
    elif waiter_name and waiter_pin:
        user, _ = server.authenticate_login(waiter_name, waiter_pin, requested_path='/waiter/table-session')
        authorized = bool(user and server.user_has_permission(user, 'table_session'))
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

    current_user = getattr(g, 'current_user', None)
    authorized = bool(current_user and server.user_has_permission(current_user, 'table_session'))
    if admin_password and admin_password == server.admin_password:
        authorized = True
    elif waiter_name and waiter_pin:
        user, _ = server.authenticate_login(waiter_name, waiter_pin, requested_path='/waiter/table-session')
        authorized = bool(user and server.user_has_permission(user, 'table_session'))
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
            kategori = str(it.get('kategori') or it.get('category') or '').strip()[:80]
        except Exception:
            continue
        if not urun or adet <= 0 or fiyat < 0:
            continue
        order_candidates.append({
            'urun': urun,
            'adet': adet,
            'fiyat': fiyat,
            'not': item_note,
            'kategori': kategori
        })

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
            kategori=item.get('kategori'),
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
        
        # 1. menu.txt, varsa veritabanı ve sunucu cache'ini güncelle
        ok, error = server.save_menu_data(new_menu, daily_meal_categories)
        if not ok:
            return jsonify({'success': False, 'error': error or 'Menü kaydedilemedi'}), 500
        
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

@app.route('/api/order-menu')
def get_order_menu_api():
    """Sipariş girişlerinde kullanılan menüyü getir."""
    return jsonify(server.get_order_menu_data())

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

@app.route('/api/table-notes')
def get_table_notes():
    """Masa özel notlarını getir"""
    return jsonify({'success': True, 'table_notes': server.get_table_notes_payload()})

@app.route('/api/table-note/<masa_adi>', methods=['GET', 'POST'])
def table_note_api(masa_adi):
    """Belirli bir masa özel notunu getir veya güncelle."""
    if masa_adi not in server.adisyonlar:
        return jsonify({'success': False, 'error': 'Geçersiz masa'}), 404
    if request.method == 'GET':
        return jsonify({'success': True, 'masa': masa_adi, 'note': server.get_table_note(masa_adi)})

    data = request.get_json(silent=True) or {}
    note, err = server.set_table_note(masa_adi, data.get('note', ''))
    if err:
        return jsonify({'success': False, 'error': err}), 400
    socketio.emit('table_note_update', {'masa': masa_adi, 'note': note})
    return jsonify({'success': True, 'masa': masa_adi, 'note': note})

@app.route('/api/reservations', methods=['GET', 'POST'])
def reservations_api():
    """Masa rezervasyonlarını getir veya yeni rezervasyon oluştur."""
    if request.method == 'GET':
        return jsonify(server.get_reservations_payload())

    data = request.get_json(silent=True) or {}
    reservation, err = server.create_reservation(data)
    if err:
        return jsonify({'success': False, 'error': err}), 400
    payload = server.get_reservations_payload()
    socketio.emit('reservations_update', payload)
    server.notify_reservation_menu(reservation)
    return jsonify({'success': True, 'reservation': reservation, 'reservations': payload})

@app.route('/api/reservations/<reservation_id>', methods=['PUT', 'PATCH', 'DELETE'])
def reservation_detail_api(reservation_id):
    """Rezervasyon güncelle veya iptal et."""
    if request.method == 'DELETE':
        reservation, err = server.cancel_reservation(reservation_id)
    else:
        data = request.get_json(silent=True) or {}
        reservation, err = server.update_reservation(reservation_id, data)

    if err:
        status = 404 if err == "Rezervasyon bulunamadı" else 400
        return jsonify({'success': False, 'error': err}), status

    payload = server.get_reservations_payload()
    socketio.emit('reservations_update', payload)
    server.notify_reservation_menu(reservation)
    return jsonify({'success': True, 'reservation': reservation, 'reservations': payload})

@app.route('/api/adisyon/<masa_adi>')
def get_adisyon(masa_adi):
    """Belirli bir adisyonu getir"""
    items = server.adisyonlar.get(masa_adi, [])
    totals = server.calculate_adisyon_totals(items)
    return jsonify({
        'masa': masa_adi,
        'items': items,
        'note': server.get_table_note(masa_adi),
        **totals
    })

# ==================== SOCKETIO EVENTS ====================

def require_socket_permission(required_pages=None):
    user, err = server.get_socket_user(request.sid, required_pages=required_pages)
    if not user:
        emit('error', {'message': err or 'Oturum yetkisi yok'})
        return None
    return user


INVOICE_DOCUMENT_TYPES = {
    9005: "Matbu Fatura Bilgi Fişi",
    9006: "E-Fatura Bilgi Fişi",
    9007: "E-Arşiv Bilgi Fişi",
}


def normalize_invoice_info(data):
    """ÖKC bilgi fişi için gerekli fatura alanlarını normalize et."""
    try:
        document_type = int(data.get('invoice_document_type') or 9006)
    except (TypeError, ValueError):
        document_type = 9006
    if document_type not in INVOICE_DOCUMENT_TYPES:
        document_type = 9006

    tax_id = re.sub(r"\D", "", str(data.get('invoice_tax_id') or ""))[:11]
    serial_no = re.sub(r"[^0-9A-Za-z]", "", str(data.get('invoice_serial_no') or ""))[:32]
    note = str(data.get('invoice_note') or '').strip()[:160]
    return {
        'document_type': document_type,
        'document_label': INVOICE_DOCUMENT_TYPES[document_type],
        'tax_id': tax_id,
        'serial_no': serial_no,
        'note': note
    }


def validate_okc_invoice_info(invoice_info):
    if len(invoice_info.get('tax_id') or '') not in (10, 11):
        return "Fatura bilgi fişi için 10 haneli VKN veya 11 haneli TCKN girin."
    if not invoice_info.get('serial_no'):
        return "Fatura bilgi fişi için fatura/bilgi fişi seri no girin."
    return None


@socketio.on('connect')
def handle_connect():
    """Client bağlandı"""
    sid = request.sid
    client_ip = request.remote_addr
    user, err, status = server.validate_auth_token(request.cookies.get(AUTH_COOKIE_NAME, ""))
    if not user:
        logger.warning(f"🔒 Yetkisiz socket bağlantısı reddedildi: {client_ip} ({err})")
        return False
    server.active_connections[sid] = {
        'ip': client_ip,
        'connected_at': time.time(),
        'user_id': user.get('id'),
        'user_name': user.get('name'),
        'role': user.get('role')
    }
    logger.info(f"✅ Client bağlandı: {client_ip} ({sid}) - {user.get('name')}")
    
    # İlk verileri gönder
    emit('initial_data', server.get_initial_payload(sid))

@socketio.on('disconnect')
def handle_disconnect():
    """Client ayrıldı"""
    sid = request.sid
    if sid in server.active_connections:
        info = server.active_connections.pop(sid)
        staffing_changed = False
        # Garson session'larından temizle
        for waiter_name in list(server.waiter_sessions.keys()):
            if sid in server.waiter_sessions[waiter_name]:
                server.waiter_sessions[waiter_name].remove(sid)
                staffing_changed = True
                if not server.waiter_sessions[waiter_name]:
                    del server.waiter_sessions[waiter_name]
        logger.info(f"❌ Client ayrıldı: {info['ip']} ({sid})")
        if staffing_changed:
            socketio.emit('staffing_update', server.get_staffing_status())

@socketio.on('waiter_init')
def handle_waiter_init(data):
    """Garson oturumunu kaydet"""
    sid = request.sid
    user = require_socket_permission(['waiter', 'dashboard'])
    if not user:
        return
    waiter_name = str(data.get('name') or '').strip()
    if waiter_name:
        server.waiter_sessions[waiter_name].add(sid)
        logger.info(f"🤵 Garson oturumu kaydedildi: {waiter_name} ({sid})")
        socketio.emit('staffing_update', server.get_staffing_status())

@socketio.on('set_kasa')
def handle_set_kasa(data):
    """Kasa ID'sini bu session için ata"""
    sid = request.sid
    user = require_socket_permission(['dashboard', 'kasa'])
    if not user:
        return
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
    user = require_socket_permission()
    if not user:
        return
    masa_adi = data.get('masa')
    server.current_selections[sid] = masa_adi
    
    items = server.adisyonlar.get(masa_adi, [])
    totals = server.calculate_adisyon_totals(items)
    
    emit('masa_selected', {
        'masa': masa_adi,
        'items': items,
        'note': server.get_table_note(masa_adi),
        **totals
    })

@socketio.on('set_table_note')
def handle_set_table_note(data):
    """Masa özel notunu güncelle."""
    user = require_socket_permission()
    if not user:
        return
    masa_adi = data.get('masa')
    note, err = server.set_table_note(masa_adi, data.get('note', ''))
    if err:
        emit('error', {'message': err})
        return
    masa_adi = str(masa_adi or "").strip()
    payload = {
        'masa': masa_adi,
        'note': note,
        'updated_by': user.get('name') or ''
    }
    socketio.emit('table_note_update', payload)
    emit('success', {'message': 'Masa notu kaydedildi'})
    logger.info(f"📝 Masa notu güncellendi: {masa_adi} - {user.get('name')}")

@socketio.on('add_item')
def handle_add_item(data):
    """Sipariş ekle"""
    sid = request.sid
    user = require_socket_permission(['dashboard', 'waiter'])
    if not user:
        return
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
        adet=data.get('adet', 1),
        not_bilgisi=not_bilgisi,
        tip=data.get('tip', 'normal'),
        kategori=data.get('kategori') or data.get('category'),
        return_error=True
    )
    if not order_item:
        emit('error', {'message': err or 'Sipariş eklenemedi'})

@socketio.on('add_items')
def handle_add_items(data):
    """Birden çok sipariş kalemini tek akışta ekle."""
    sid = request.sid
    user = require_socket_permission(['dashboard', 'waiter'])
    if not user:
        return

    masa_adi = data.get('masa') or server.current_selections.get(sid)
    if not masa_adi or masa_adi not in server.adisyonlar:
        emit('error', {'message': 'Lütfen önce masa seçiniz'})
        return

    raw_items = data.get('items')
    if not isinstance(raw_items, list) or not raw_items:
        emit('error', {'message': 'Sipariş kalemi bulunamadı'})
        return

    order_items = []
    for raw in raw_items[:50]:
        if not isinstance(raw, dict):
            continue
        urun = str(raw.get('urun') or raw.get('name') or '').strip()
        if not urun:
            continue
        try:
            fiyat = float(raw.get('fiyat', raw.get('price', 0)))
        except Exception:
            fiyat = 0
        item = {
            'urun': urun,
            'fiyat': fiyat,
            'adet': raw.get('adet', raw.get('quantity', 1)),
            'not': str(raw.get('not') or raw.get('not_bilgisi') or '').strip()[:160],
            'tip': raw.get('tip', 'normal'),
            'kategori': str(raw.get('kategori') or raw.get('category') or '').strip()[:80],
            'garson': raw.get('garson') or data.get('garson', 'Bilinmiyor')
        }
        if 'prep_ticket_skipped' in raw or 'skip_prep_ticket' in raw:
            item['prep_ticket_skipped'] = bool(raw.get('prep_ticket_skipped') or raw.get('skip_prep_ticket'))
        plate_group = raw.get('plate_group')
        if isinstance(plate_group, dict):
            item['plate_group'] = {
                'id': str(plate_group.get('id') or '').strip()[:16],
                'label': str(plate_group.get('label') or '').strip()[:60],
                'note': str(plate_group.get('note') or '').strip()[:120]
            }
        order_items.append(item)

    added, err = server.add_order_items(
        masa_adi=masa_adi,
        order_items=order_items,
        garson=data.get('garson', 'Bilinmiyor'),
        terminal_id=f"waiter:{sid}",
        return_error=True
    )
    if not added:
        emit('error', {'message': err or 'Sipariş eklenemedi'})

@socketio.on('kitchen_order_ready')
def handle_kitchen_order_ready(data):
    """Mutfaktan sipariş hazır bildirimi"""
    user = require_socket_permission('kitchen')
    if not user:
        return
    masa = data.get('masa')
    waiters = data.get('waiters', [])
    items_uids = data.get('items_uids', []) # Mutfaktan gelen hazır ürün ID'leri
    items_uid_set = set(items_uids)
    if not items_uid_set:
        emit('error', {'message': 'Hazır yapılacak ürün seçilmedi'})
        return
    
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
                    'message': f"{masa or 'Hazırlık'} için {len(items_uids)} kalem hazır!"
                }, room=sid)
    
    # Değişen tüm masaları güncelle (toplu içecek onayı birden fazla masayı etkileyebilir)
    for changed_masa in changed_masas:
        items = server.adisyonlar.get(changed_masa, [])
        totals = server.calculate_adisyon_totals(items)
        socketio.emit('masa_update', {'masa': changed_masa, 'items': items, **totals})

@socketio.on('mark_order_served')
def handle_mark_order_served(data):
    """Garson hazır siparişi masaya servis etti olarak işaretler."""
    user = require_socket_permission(['dashboard', 'waiter'])
    if not user:
        return
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
    """Siparişi iptal eder"""
    sid = request.sid
    user = require_socket_permission(['dashboard', 'waiter', 'kasa'])
    if not user:
        return
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
            note_cleared = False
            if not items:
                note_cleared = server.clear_table_note(masa_adi)
            socketio.emit('masa_update', {
                'masa': masa_adi,
                'items': items,
                **totals
            })
            if note_cleared:
                socketio.emit('table_note_update', {'masa': masa_adi, 'note': ''})

@socketio.on('transfer_table')
def handle_transfer_table(data):
    """Bir masadaki siparişleri başka bir masaya taşı"""
    sid = request.sid
    user = require_socket_permission(['dashboard', 'waiter'])
    if not user:
        return
    source_masa = data.get('source_masa')
    target_masa = data.get('target_masa')
    garson = (data.get('garson') or data.get('waiter') or '').strip()
    
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
    source_note = server.get_table_note(source_masa)
    server.adisyonlar[target_masa].extend(items_to_move)
    server.adisyonlar[source_masa] = []
    if source_note:
        server.merge_table_note(target_masa, source_note, save=False)
        server.clear_table_note(source_masa, save=False)
        server.save_table_notes()
    server.current_selections[sid] = target_masa
    server.save_active_adisyonlar() # Persistence
    
    actor = f" - {garson}" if garson else ""
    logger.info(f"🔄 Masa taşıma: {source_masa} ➔ {target_masa} ({len(items_to_move)} ürün){actor}")
    
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
        socketio.emit('table_note_update', {
            'masa': masa_adi,
            'note': server.get_table_note(masa_adi)
        })
    
    emit('success', {
        'type': 'transfer_table',
        'message': f'{source_masa} masası {target_masa} masasına başarıyla taşındı',
        'source_masa': source_masa,
        'target_masa': target_masa
    })

@socketio.on('assign_courier')
def handle_assign_courier(data):
    """Siparişe kurye ata"""
    user = require_socket_permission(['dashboard', 'kurye'])
    if not user:
        return
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
    user = require_socket_permission(['dashboard', 'kurye'])
    if not user:
        return
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
    user = require_socket_permission(['dashboard', 'waiter'])
    if not user:
        return
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
            note_cleared = False
            if not items:
                note_cleared = server.clear_table_note(masa_adi)
            
            socketio.emit('masa_update', {
                'masa': masa_adi,
                'items': items,
                **totals
            })
            if note_cleared:
                socketio.emit('table_note_update', {'masa': masa_adi, 'note': ''})

@socketio.on('set_item_comp')
def handle_set_item_comp(data):
    """Seçili adisyon kalemlerini ikram/normal olarak işaretle."""
    sid = request.sid
    user = require_socket_permission(['dashboard', 'kasa'])
    if not user:
        return
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
    user = require_socket_permission(['dashboard', 'kasa'])
    if not user:
        return
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
    item_indices = data.get('item_indices', []) # Eski format: seçili ürünlerin indexleri
    item_quantities = data.get('item_quantities', []) # Yeni format: index + seçilen adet
    invoice_pending = bool(data.get('invoice_pending', False))
    invoice_info = normalize_invoice_info(data)
    invoice_note = invoice_info['note']

    # Hangi kalemlerin ödendiğini belirle
    selected_quantities = []
    if item_quantities or item_indices:
        selected_quantities, selection_error = server.normalize_selected_item_quantities(
            server.adisyonlar[masa_adi],
            item_quantities=item_quantities,
            item_indices=item_indices
        )
        if selection_error:
            emit('error', {'message': selection_error})
            return

        items_to_pay = server.selected_items_for_payment(
            server.adisyonlar[masa_adi],
            selected_quantities
        )

        if not selected_quantities or not items_to_pay:
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
    has_current_account_payment = any(p.get('type') == 'Açık Hesap' for p in payments)

    payment_total_cents = int(round(sum(p['amount'] for p in payments) * 100))
    payable_total_cents = int(round(payable_total * 100))
    if abs(payment_total_cents - payable_total_cents) > 1:
        emit('error', {
            'message': (
                f"Ödeme toplamı ({payment_total_cents / 100:.2f} TL), "
                f"ödenecek tutarla ({payable_total_cents / 100:.2f} TL) eşleşmeli"
            )
        })
        return
    if payment_total_cents != payable_total_cents:
        payment_cents = [int(round(p['amount'] * 100)) for p in payments]
        delta_cents = payable_total_cents - sum(payment_cents)
        adjust_index = max(range(len(payment_cents)), key=lambda idx: payment_cents[idx])
        adjusted_cents = payment_cents[adjust_index] + delta_cents
        if adjusted_cents <= 0:
            emit('error', {'message': 'Ödeme tutarları yuvarlanarak dengelenemedi'})
            return
        payment_cents[adjust_index] = adjusted_cents
        for idx, cents in enumerate(payment_cents):
            payments[idx]['amount'] = round(cents / 100, 2)
        payment_total_cents = payable_total_cents

    if invoice_pending and server.pos_enabled and not has_current_account_payment:
        token_bridge_enabled_for_invoice = server.pos_type in POSManager.TOKEN_BRIDGE_TYPES
        card_amount_for_invoice = sum(p['amount'] for p in payments if p.get('type') == 'Kredi Kartı')
        if token_bridge_enabled_for_invoice:
            invoice_error = validate_okc_invoice_info(invoice_info)
            if invoice_error:
                emit('error', {
                    'message': (
                        f"{invoice_error} Normal mali fiş basılmaması için ÖKC işlemi durduruldu."
                    )
                })
                return
        elif card_amount_for_invoice > 0:
            emit('error', {
                'message': (
                    "Bu POS/ÖKC tipi fatura bilgi fişi desteklemiyor. "
                    "Normal mali fiş basılmaması için işlem durduruldu."
                )
            })
            return
    
    # Aktif vardiya bilgisini al
    active_shift = server.get_sid_active_shift(sid)
    vardiya_id = active_shift['id'] if active_shift else None
    
    # Database'e kaydet
    try:
        timestamp = datetime.datetime.now()
        
        # POS/ÖKC işlemi
        if server.pos_enabled and not has_current_account_payment:
            card_amount = sum(p['amount'] for p in payments if p.get('type') == 'Kredi Kartı')
            token_bridge_enabled = server.pos_type in POSManager.TOKEN_BRIDGE_TYPES
            pos_amount = sum(p['amount'] for p in payments) if token_bridge_enabled else card_amount
            if pos_amount > 0:
                okc_started, busy_payload = server.try_start_okc_operation({
                    'masa': masa_adi,
                    'amount': round(float(pos_amount), 2),
                    'payment_count': len(payments),
                    'pos_type': server.pos_type,
                    'message': 'ÖKC işlemi devam ediyor, lütfen tamamlanmasını bekleyin.'
                })
                if not okc_started:
                    emit('error', {
                        'message': 'ÖKC işlemi devam ediyor, lütfen tamamlanmasını bekleyin.',
                        'okc_busy': busy_payload
                    })
                    return

                logger.info(f"💳 POS/ÖKC satış başlatılıyor: {pos_amount:.2f} TL | {server.pos_type}")
                try:
                    success, msg = server.pos_manager.sale(
                        pos_amount,
                        masa_adi,
                        items=payable_items,
                        payments=payments,
                        order_id=str(uuid.uuid4()),
                        invoice_pending=invoice_pending,
                        invoice_info=invoice_info if invoice_pending else None
                    )
                    if not success:
                        raise Exception(msg)
                    logger.info(f"✅ POS/ÖKC satış başarılı: {msg}")
                finally:
                    server.finish_okc_operation()
        elif server.pos_enabled and has_current_account_payment:
            logger.info("📝 Açık hesap ödemesi ÖKC'ye gönderilmedi; cari borç olarak kaydedilecek.")

        cari_adisyon_base = {
            'masa': masa_adi,
            'tarih': timestamp.isoformat(timespec='seconds'),
            'toplam': round(float(payable_total), 2),
            'ikram_toplam': round(float(ikram_total), 2),
            'odeme_tipi': 'Parçalı' if len(payments) > 1 else payments[0]['type'],
            'items': [
                {
                    'urun': item.get('urun', ''),
                    'adet': server.coerce_order_quantity(item.get('adet', 1)),
                    'fiyat': round(float(item.get('fiyat', 0) or 0), 2),
                    'tutar': round(
                        server.coerce_order_quantity(item.get('adet', 1))
                        * float(item.get('fiyat', 0) or 0),
                        2
                    ),
                    'tip': item.get('tip', 'normal'),
                    'not': item.get('not', '')
                }
                for item in items
            ],
            'payments': [
                {
                    'type': p.get('type', ''),
                    'amount': round(float(p.get('amount', 0) or 0), 2),
                    'customer': p.get('customer', '')
                }
                for p in payments
            ]
        }

        # Cari işlemleri POS/ÖKC başarılı olduktan sonra kaydet
        for p in payments:
            if p.get('type') == 'Açık Hesap' and USE_DATABASE:
                customer = p.get('customer', 'Genel Müşteri')
                amount = float(p.get('amount', 0))
                if amount > 0:
                    cari_adisyon_detay = dict(cari_adisyon_base)
                    cari_adisyon_detay['cari_tutar'] = round(amount, 2)
                    db.save_cari_transaction(customer, 'borc', amount, cari_adisyon_detay)
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
                'vardiya_id': vardiya_id,
                'invoice_pending': invoice_pending,
                'invoice_document_type': invoice_info['document_type'] if invoice_pending else None,
                'invoice_tax_id': invoice_info['tax_id'] if invoice_pending else None,
                'invoice_serial_no': invoice_info['serial_no'] if invoice_pending else None,
                'invoice_note': invoice_note if invoice_pending else None
            })
        
        if USE_DATABASE:
            db.save_sales_batch(sales_data)
        
        # Adisyonu temizle (Sadece ödenen kalemleri)
        is_partial = False
        if selected_quantities:
            server.remove_selected_item_quantities(server.adisyonlar[masa_adi], selected_quantities)

            # Eğer masada hala ürün varsa bu bir kısmi ödemedir
            if server.adisyonlar[masa_adi]:
                is_partial = True
        else:
            server.adisyonlar[masa_adi] = []

        note_cleared = False
        if not server.adisyonlar[masa_adi]:
            server.revoke_public_sessions_for_table(masa_adi)
            note_cleared = server.clear_table_note(masa_adi)
        
        server.save_active_adisyonlar() # Persistence
        
        # Tüm clientlara bildir
        socketio.emit('payment_completed', {
            'masa': masa_adi,
            'type': final_payment_label,
            'payments': payments,
            'invoice_pending': invoice_pending,
            'invoice_document_type': invoice_info['document_type'] if invoice_pending else None,
            'invoice_tax_id': invoice_info['tax_id'] if invoice_pending else '',
            'invoice_serial_no': invoice_info['serial_no'] if invoice_pending else '',
            'invoice_note': invoice_note if invoice_pending else '',
            'is_partial': is_partial
        })
        if note_cleared:
            socketio.emit('table_note_update', {'masa': masa_adi, 'note': ''})

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
        if invoice_pending:
            msg += " | Fatura bekliyor"
            
        emit('success', {'message': msg})
        
        # --- MUHASEBE ENTEGRASYONU ---
        if invoice_pending:
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
                    'invoice_pending': invoice_pending,
                    'invoice_document_type': invoice_info['document_type'],
                    'invoice_document_label': invoice_info['document_label'],
                    'invoice_tax_id': invoice_info['tax_id'],
                    'invoice_serial_no': invoice_info['serial_no'],
                    'invoice_note': invoice_note,
                    'default_tax_rate': server.default_kdv_rate,
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
    user = require_socket_permission(['dashboard', 'kasa'])
    if not user:
        return
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
        note_cleared = server.clear_table_note(masa_adi)
        server.save_active_adisyonlar()

        socketio.emit('payment_completed', {
            'masa': masa_adi,
            'type': 'İkram',
            'payments': [],
            'is_partial': False,
            'ikram_total': ikram_total
        })
        if note_cleared:
            socketio.emit('table_note_update', {'masa': masa_adi, 'note': ''})
        emit('success', {'message': f'Hesap ikram olarak kapatıldı: {ikram_total:.2f} TL'})
    except Exception as e:
        logger.error(f"İkram kapatma hatası: {e}")
        emit('error', {'message': str(e)})

@socketio.on('print_receipt')
def handle_print_receipt(data):
    """Fiş yazdır"""
    sid = request.sid
    user = require_socket_permission(['dashboard', 'kasa'])
    if not user:
        return
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
        fn = os.path.join(FIS_KLASORU, f"Fis_{sira}.txt")
        receipt_text = server.build_receipt_ticket_text(masa_adi, items, sira)

        with open(fn, "w", encoding="utf-8") as f:
            f.write(receipt_text)

        full_path = os.path.abspath(fn)
        sent_to_ip_printer = server.send_receipt_to_printer(receipt_text)
        
        # IP hesap yazıcısı tanımlı değilse eski yerel yazdırma yolunu kullan.
        if not sent_to_ip_printer and server.direct_print:
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
            server.beep_if_system_printer_is_barcode()
        elif not sent_to_ip_printer:
            # Direct print kapalıysa sadece dosyayı aç (izleme amaçlı)
            system = platform.system()
            if system == "Darwin":
                subprocess.run(["open", full_path])
            elif system == "Windows":
                os.startfile(full_path)
            else:
                subprocess.run(["xdg-open", full_path])

        emit('success', {'message': 'Hesap bilgisi oluşturuldu ve yazdırmaya gönderildi'})
        
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

    # Ayarlanan saate kadar kapatılmayan vardiyaları otomatik kapat
    server.start_shift_auto_close_scheduler()

    # Gün değişiminde otomatik sistem yedeği al
    server.start_auto_backup_scheduler()
    
    # Web sunucuyu başlat
    web_port = max(1, min(get_env_int("FASTFOOT_WEB_PORT", 8000), 65535))
    logger.info(f"🌐 Web sunucu başlatılıyor: http://{get_local_ip()}:{web_port}")
    
    socketio.run(app, host='0.0.0.0', port=web_port, debug=False, allow_unsafe_werkzeug=True)
