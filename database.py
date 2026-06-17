# -*- coding: utf-8 -*-
"""
PostgreSQL Veri Tabanı Yönetim Modülü
Restoran Projesi
"""

import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import Json, RealDictCursor
from datetime import datetime
from contextlib import contextmanager
from decimal import Decimal
from db_config import DB_CONFIG

class Database:
    """PostgreSQL veri tabanı işlemleri için singleton sınıf"""
    
    _instance = None
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance

    @staticmethod
    def _normalize_timestamp(value):
        """PostgreSQL'e gidecek tarih değerini güvenli datetime'a çevir."""
        if value is None:
            return datetime.now()
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return datetime.now()
            for fmt in (
                "%d-%m-%Y %H:%M:%S",
                "%d-%m-%Y %H:%M",
                "%d.%m.%Y %H:%M:%S",
                "%d.%m.%Y %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
            ):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    pass
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return value
        return value
    
    def _initialize_pool(self):
        """Connection pool oluştur"""
        try:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                **DB_CONFIG
            )
            print("✓ PostgreSQL bağlantı havuzu oluşturuldu")
        except Exception as e:
            print(f"✗ PostgreSQL bağlantı hatası: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Bağlantı context manager'ı"""
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)
    
    @contextmanager
    def get_cursor(self, dict_cursor=True):
        """Cursor context manager'ı"""
        with self.get_connection() as conn:
            cursor_factory = RealDictCursor if dict_cursor else None
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()
    
    def init_database(self):
        """Veri tabanı şemasını oluştur"""
        with self.get_cursor(dict_cursor=False) as cursor:
            # SATIŞLAR TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS satislar (
                    id SERIAL PRIMARY KEY,
                    urun TEXT NOT NULL,
                    adet DECIMAL(10, 3) NOT NULL,
                    fiyat DECIMAL(10, 2) NOT NULL,
                    odeme TEXT NOT NULL,
                    tip TEXT DEFAULT 'normal',
                    tarih_saat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    masa TEXT,
                    terminal_id TEXT,
                    vardiya_id INTEGER,
                    invoice_pending BOOLEAN DEFAULT FALSE,
                    invoice_document_type INTEGER,
                    invoice_tax_id TEXT,
                    invoice_serial_no TEXT,
                    invoice_note TEXT
                )
            """)
            cursor.execute("ALTER TABLE satislar ADD COLUMN IF NOT EXISTS vardiya_id INTEGER")
            cursor.execute("ALTER TABLE satislar ADD COLUMN IF NOT EXISTS invoice_pending BOOLEAN DEFAULT FALSE")
            cursor.execute("ALTER TABLE satislar ADD COLUMN IF NOT EXISTS invoice_document_type INTEGER")
            cursor.execute("ALTER TABLE satislar ADD COLUMN IF NOT EXISTS invoice_tax_id TEXT")
            cursor.execute("ALTER TABLE satislar ADD COLUMN IF NOT EXISTS invoice_serial_no TEXT")
            cursor.execute("ALTER TABLE satislar ADD COLUMN IF NOT EXISTS invoice_note TEXT")
            cursor.execute("""
                ALTER TABLE satislar
                ALTER COLUMN adet TYPE DECIMAL(10, 3)
                USING adet::DECIMAL(10, 3)
            """)
            
            # CARİ HESAPLAR TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cari_hesaplar (
                    id SERIAL PRIMARY KEY,
                    cari_isim TEXT NOT NULL UNIQUE,
                    telefon TEXT,
                    adres TEXT,
                    vergi_no TEXT,
                    olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tablo zaten varsa kolonları ekle (migration)
            cursor.execute("ALTER TABLE cari_hesaplar ADD COLUMN IF NOT EXISTS telefon TEXT")
            cursor.execute("ALTER TABLE cari_hesaplar ADD COLUMN IF NOT EXISTS adres TEXT")
            cursor.execute("ALTER TABLE cari_hesaplar ADD COLUMN IF NOT EXISTS vergi_no TEXT")
            
            # CARİ HAREKETLER TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cari_hareketler (
                    id SERIAL PRIMARY KEY,
                    cari_id INTEGER NOT NULL,
                    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    islem TEXT NOT NULL,
                    tutar DECIMAL(10, 2) NOT NULL,
                    adisyon_detay JSONB,
                    FOREIGN KEY (cari_id) REFERENCES cari_hesaplar(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("ALTER TABLE cari_hareketler ADD COLUMN IF NOT EXISTS adisyon_detay JSONB")
            
            # STOKLAR TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stoklar (
                    id SERIAL PRIMARY KEY,
                    malzeme TEXT NOT NULL UNIQUE,
                    miktar DECIMAL(10, 2) NOT NULL DEFAULT 0,
                    birim TEXT,
                    alis_fiyati DECIMAL(10, 2),
                    kritik_seviye DECIMAL(10, 2) DEFAULT 5.0,
                    son_guncelleme TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # MENU TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS menu (
                    id SERIAL PRIMARY KEY,
                    kategori TEXT NOT NULL,
                    urun_adi TEXT NOT NULL,
                    fiyat DECIMAL(10, 2) NOT NULL,
                    sira INTEGER DEFAULT 0,
                    oran_ys DECIMAL(5, 2) DEFAULT 0,
                    oran_ty DECIMAL(5, 2) DEFAULT 0,
                    oran_gt DECIMAL(5, 2) DEFAULT 0,
                    oran_mg DECIMAL(5, 2) DEFAULT 0,
                    image_url TEXT,
                    menu_visible BOOLEAN DEFAULT TRUE
                )
            """)
            
            # Migrations for existing menu table
            cursor.execute("ALTER TABLE menu ADD COLUMN IF NOT EXISTS oran_ys DECIMAL(5, 2) DEFAULT 0")
            cursor.execute("ALTER TABLE menu ADD COLUMN IF NOT EXISTS oran_ty DECIMAL(5, 2) DEFAULT 0")
            cursor.execute("ALTER TABLE menu ADD COLUMN IF NOT EXISTS oran_gt DECIMAL(5, 2) DEFAULT 0")
            cursor.execute("ALTER TABLE menu ADD COLUMN IF NOT EXISTS oran_mg DECIMAL(5, 2) DEFAULT 0")
            cursor.execute("ALTER TABLE menu ADD COLUMN IF NOT EXISTS image_url TEXT")
            cursor.execute("ALTER TABLE menu ADD COLUMN IF NOT EXISTS menu_visible BOOLEAN DEFAULT TRUE")
            
            # KASALAR TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kasalar (
                    id SERIAL PRIMARY KEY,
                    ad TEXT NOT NULL UNIQUE
                )
            """)
            
            # VARDIYALAR TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vardiyalar (
                    id SERIAL PRIMARY KEY,
                    kasa_id INTEGER NOT NULL,
                    kasiyer TEXT NOT NULL,
                    acilis_zamani TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    kasiyer_adi TEXT,
                    acilma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    kapanma_tarihi TIMESTAMP,
                    acilis_bakiyesi DECIMAL(10, 2) DEFAULT 0,
                    kapanis_bakiyesi DECIMAL(10, 2),
                    kapanis_zamani TIMESTAMP,
                    kapanis_nakit DECIMAL(10, 2) DEFAULT 0,
                    kapanis_kart DECIMAL(10, 2) DEFAULT 0,
                    durum TEXT DEFAULT 'acik'
                )
            """)
            cursor.execute("ALTER TABLE vardiyalar ADD COLUMN IF NOT EXISTS kasiyer TEXT")
            cursor.execute("ALTER TABLE vardiyalar ADD COLUMN IF NOT EXISTS acilis_zamani TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            cursor.execute("ALTER TABLE vardiyalar ADD COLUMN IF NOT EXISTS kasiyer_adi TEXT")
            cursor.execute("ALTER TABLE vardiyalar ADD COLUMN IF NOT EXISTS acilma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            cursor.execute("ALTER TABLE vardiyalar ADD COLUMN IF NOT EXISTS kapanma_tarihi TIMESTAMP")
            cursor.execute("ALTER TABLE vardiyalar ADD COLUMN IF NOT EXISTS acilis_bakiyesi DECIMAL(10, 2) DEFAULT 0")
            cursor.execute("ALTER TABLE vardiyalar ADD COLUMN IF NOT EXISTS kapanis_bakiyesi DECIMAL(10, 2)")
            cursor.execute("ALTER TABLE vardiyalar ADD COLUMN IF NOT EXISTS kapanis_zamani TIMESTAMP")
            cursor.execute("ALTER TABLE vardiyalar ADD COLUMN IF NOT EXISTS kapanis_nakit DECIMAL(10, 2) DEFAULT 0")
            cursor.execute("ALTER TABLE vardiyalar ADD COLUMN IF NOT EXISTS kapanis_kart DECIMAL(10, 2) DEFAULT 0")
            cursor.execute("ALTER TABLE vardiyalar ADD COLUMN IF NOT EXISTS durum TEXT DEFAULT 'acik'")

            # KURYELER VE TESLİMATLAR
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kurye_firmalari (
                    id SERIAL PRIMARY KEY,
                    ad TEXT NOT NULL UNIQUE,
                    api_key TEXT,
                    ayarlar JSONB DEFAULT '{}'::jsonb,
                    aktif BOOLEAN DEFAULT TRUE,
                    olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kuryeler (
                    id SERIAL PRIMARY KEY,
                    ad TEXT NOT NULL,
                    telefon TEXT,
                    plaka TEXT,
                    firma_id INTEGER,
                    aktif BOOLEAN DEFAULT TRUE,
                    durum TEXT DEFAULT 'musait'
                )
            """)
            cursor.execute("ALTER TABLE kuryeler ADD COLUMN IF NOT EXISTS plaka TEXT")
            cursor.execute("ALTER TABLE kuryeler ADD COLUMN IF NOT EXISTS firma_id INTEGER")
            cursor.execute("ALTER TABLE kuryeler ADD COLUMN IF NOT EXISTS aktif BOOLEAN DEFAULT TRUE")
            cursor.execute("ALTER TABLE kuryeler ADD COLUMN IF NOT EXISTS durum TEXT DEFAULT 'musait'")

            # PUBLIC QR NONCES (Replay attack protection)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS public_qr_nonces (
                    nonce TEXT PRIMARY KEY,
                    table_name TEXT,
                    shift_id INTEGER,
                    expires_at TIMESTAMP NOT NULL,
                    used_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("ALTER TABLE public_qr_nonces ADD COLUMN IF NOT EXISTS table_name TEXT")
            cursor.execute("ALTER TABLE public_qr_nonces ADD COLUMN IF NOT EXISTS shift_id INTEGER")
            cursor.execute("ALTER TABLE public_qr_nonces ADD COLUMN IF NOT EXISTS used_at TIMESTAMP")
            cursor.execute("ALTER TABLE public_qr_nonces ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

            # PUBLIC TABLE SESSIONS
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS public_table_sessions (
                    id TEXT PRIMARY KEY,
                    session_token TEXT UNIQUE,
                    table_name TEXT NOT NULL,
                    shift_id INTEGER,
                    verify_method TEXT,
                    device_fingerprint TEXT,
                    ip TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    status TEXT DEFAULT 'active'
                )
            """)
            cursor.execute("ALTER TABLE public_table_sessions ADD COLUMN IF NOT EXISTS id TEXT")
            cursor.execute("ALTER TABLE public_table_sessions ADD COLUMN IF NOT EXISTS session_token TEXT")
            cursor.execute("ALTER TABLE public_table_sessions ADD COLUMN IF NOT EXISTS verify_method TEXT")
            cursor.execute("ALTER TABLE public_table_sessions ADD COLUMN IF NOT EXISTS device_fingerprint TEXT")
            cursor.execute("ALTER TABLE public_table_sessions ADD COLUMN IF NOT EXISTS ip TEXT")
            cursor.execute("""
                UPDATE public_table_sessions
                SET id = session_token
                WHERE id IS NULL AND session_token IS NOT NULL
            """)

            # NFC TABLE TAGS
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS table_nfc_tags (
                    table_name TEXT PRIMARY KEY,
                    tag_uid_hash TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # PUANTAJ TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS puantaj (
                    id SERIAL PRIMARY KEY,
                    personel_adi TEXT NOT NULL,
                    rol TEXT DEFAULT 'garson',
                    tarih DATE DEFAULT CURRENT_DATE,
                    giris_saati TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    cikis_saati TIMESTAMP,
                    toplam_dakika INTEGER DEFAULT 0,
                    notlar TEXT
                )
            """)
            cursor.execute("ALTER TABLE puantaj ADD COLUMN IF NOT EXISTS tarih DATE DEFAULT CURRENT_DATE")
            cursor.execute("ALTER TABLE puantaj ADD COLUMN IF NOT EXISTS toplam_dakika INTEGER DEFAULT 0")

            # İNDEKSLER
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cari_hareketler_cari ON cari_hareketler(cari_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_menu_kategori ON menu(kategori)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vardiyalar_durum ON vardiyalar(durum)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_public_qr_nonces_exp ON public_qr_nonces(expires_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_public_qr_nonces_used ON public_qr_nonces(used_at)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_public_sessions_id_unique ON public_table_sessions(id) WHERE id IS NOT NULL")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_public_sessions_token_unique ON public_table_sessions(session_token) WHERE session_token IS NOT NULL")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_public_sessions_table ON public_table_sessions(table_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_public_sessions_shift ON public_table_sessions(shift_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_public_sessions_status_exp ON public_table_sessions(status, expires_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_puantaj_tarih ON puantaj(tarih)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_puantaj_personel ON puantaj(personel_adi)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_kuryeler_firma ON kuryeler(firma_id)")

            # ONLINE SİPARİŞLER TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS online_orders (
                    id SERIAL PRIMARY KEY,
                    musteri_adi TEXT NOT NULL,
                    telefon TEXT,
                    adres TEXT NOT NULL,
                    not_bilgisi TEXT,
                    items JSONB DEFAULT '[]',
                    odeme_tipi TEXT DEFAULT 'nakit',
                    adisyon_adi TEXT,
                    durum TEXT DEFAULT 'bekliyor',
                    olusturma TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_online_orders_durum ON online_orders(durum)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_online_orders_olusturma ON online_orders(olusturma)")
            
            # SESLİ ASİSTAN KARALİSTE TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voice_agent_blacklist (
                    id SERIAL PRIMARY KEY,
                    telefon TEXT NOT NULL UNIQUE,
                    sebep TEXT,
                    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # AYARLAR TABLOSUNA SESLİ ASİSTAN ALANLARI (Eğer varsa)
            # Mevcut sistemde ayarlar dosyadan okunuyor olabilir, 
            # ancak blacklist tablo olarak kalmalı.

            print("✓ Veri tabanı şeması güncellendi")
    
    # ==================== SATIŞ İŞLEMLERİ ====================
    
    def save_sale(self, urun, adet, fiyat, odeme, tip='normal', masa=None, terminal_id=None, vardiya_id=None,
                  invoice_pending=False, invoice_note=None, invoice_document_type=None, invoice_tax_id=None,
                  invoice_serial_no=None):
        """Satış kaydı ekle"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO satislar (
                    urun, adet, fiyat, odeme, tip, masa, terminal_id, vardiya_id,
                    invoice_pending, invoice_document_type, invoice_tax_id, invoice_serial_no, invoice_note
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                urun, adet, fiyat, odeme, tip, masa, terminal_id, vardiya_id,
                bool(invoice_pending), invoice_document_type, invoice_tax_id, invoice_serial_no, invoice_note
            ))
            return cursor.fetchone()['id']
    
    def save_sales_batch(self, sales_list):
        """Toplu satış kaydı ekle"""
        with self.get_cursor() as cursor:
            for sale in sales_list:
                cursor.execute("""
                    INSERT INTO satislar (
                        urun, adet, fiyat, odeme, tip, tarih_saat, masa, terminal_id, vardiya_id,
                        invoice_pending, invoice_document_type, invoice_tax_id, invoice_serial_no, invoice_note
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    sale.get('urun'),
                    sale.get('adet', 1),
                    sale.get('fiyat'),
                    sale.get('odeme', 'Nakit'),
                    sale.get('tip', 'normal'),
                    self._normalize_timestamp(sale.get('Tarih_Saat')),
                    sale.get('masa'),
                    sale.get('terminal_id'),
                    sale.get('vardiya_id'),
                    bool(sale.get('invoice_pending', False)),
                    sale.get('invoice_document_type'),
                    sale.get('invoice_tax_id'),
                    sale.get('invoice_serial_no'),
                    sale.get('invoice_note')
                ))
    
    def get_sales_by_date(self, tarih=None):
        """Tarihe göre satışları getir"""
        if tarih is None:
            tarih = datetime.now().strftime("%Y-%m-%d")
        
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM satislar
                WHERE DATE(tarih_saat) = %s
                ORDER BY tarih_saat DESC
            """, (tarih,))
            return cursor.fetchall()
    
    def get_daily_summary(self, tarih=None):
        """Günlük özet rapor"""
        if tarih is None:
            tarih = datetime.now().strftime("%Y-%m-%d")
        
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    odeme,
                    tip,
                    SUM(CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN 0 ELSE fiyat * adet END) as toplam,
                    SUM(CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN fiyat * adet ELSE 0 END) as ikram_toplam,
                    SUM(CASE WHEN invoice_pending THEN 1 ELSE 0 END) as fatura_bekleyen_adet,
                    COUNT(*) as adet
                FROM satislar
                WHERE DATE(tarih_saat) = %s
                GROUP BY odeme, tip
            """, (tarih,))
            return cursor.fetchall()

    def get_item_totals_by_date(self, tarih=None):
        """Gün sonu için ürün bazlı kalem toplamlarını getir."""
        if tarih is None:
            tarih = datetime.now().strftime("%Y-%m-%d")

        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    COALESCE(NULLIF(TRIM(urun), ''), 'Ürün') AS urun,
                    SUM(adet) AS adet,
                    SUM(CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN 0 ELSE adet END) AS satis_adet,
                    SUM(CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN adet ELSE 0 END) AS ikram_adet,
                    SUM(CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN 0 ELSE fiyat * adet END) AS toplam,
                    SUM(CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN fiyat * adet ELSE 0 END) AS ikram_toplam,
                    CASE
                        WHEN SUM(adet) > 0 THEN SUM(fiyat * adet) / NULLIF(SUM(adet), 0)
                        ELSE 0
                    END AS ortalama_fiyat
                FROM satislar
                WHERE DATE(tarih_saat) = %s
                GROUP BY COALESCE(NULLIF(TRIM(urun), ''), 'Ürün')
                ORDER BY toplam DESC, satis_adet DESC, urun ASC
            """, (tarih,))
            return cursor.fetchall()

    def get_invoice_requests_by_date(self, tarih=None):
        """Gün sonu için e-fatura/e-arşiv isteklerini adisyon bazında grupla."""
        if tarih is None:
            tarih = datetime.now().strftime("%Y-%m-%d")

        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    MIN(id) AS ilk_satis_id,
                    tarih_saat,
                    COALESCE(NULLIF(TRIM(masa), ''), 'Kasa') AS masa,
                    COALESCE(NULLIF(TRIM(odeme), ''), 'Diğer') AS odeme,
                    terminal_id,
                    vardiya_id,
                    invoice_document_type,
                    invoice_tax_id,
                    invoice_serial_no,
                    invoice_note,
                    COALESCE(SUM(CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN 0 ELSE adet END), 0) AS satis_adet,
                    COALESCE(SUM(CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN 0 ELSE fiyat * adet END), 0) AS toplam,
                    COUNT(*) AS kalem_sayisi,
                    STRING_AGG(
                        CONCAT(
                            COALESCE(NULLIF(TRIM(urun), ''), 'Ürün'),
                            ' x ',
                            TRIM(TRAILING '.' FROM TRIM(TRAILING '0' FROM adet::TEXT))
                        ),
                        ', ' ORDER BY urun
                    ) AS urunler
                FROM satislar
                WHERE DATE(tarih_saat) = %s
                  AND invoice_pending = TRUE
                GROUP BY
                    tarih_saat,
                    COALESCE(NULLIF(TRIM(masa), ''), 'Kasa'),
                    COALESCE(NULLIF(TRIM(odeme), ''), 'Diğer'),
                    terminal_id,
                    vardiya_id,
                    invoice_document_type,
                    invoice_tax_id,
                    invoice_serial_no,
                    invoice_note
                ORDER BY tarih_saat DESC, ilk_satis_id DESC
            """, (tarih,))
            return cursor.fetchall()

    def get_operational_reports(self, baslangic=None, bitis=None):
        """Talep, yoğunluk ve zaman odaklı operasyon raporlarını getir."""
        today = datetime.now().strftime("%Y-%m-%d")
        baslangic = baslangic or today
        bitis = bitis or baslangic

        revenue_expr = "CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN 0 ELSE fiyat * adet END"
        comp_value_expr = "CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN fiyat * adet ELSE 0 END"
        channel_expr = """
            CASE
                WHEN COALESCE(masa, '') ILIKE 'Paket%%' THEN 'Paket'
                WHEN COALESCE(masa, '') ILIKE 'Online%%' THEN 'Online'
                WHEN COALESCE(masa, '') ILIKE 'Masa%%' THEN 'Salon'
                WHEN COALESCE(masa, '') = '' THEN 'Kasa'
                ELSE 'Diğer'
            END
        """

        with self.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM({revenue_expr}), 0) AS ciro,
                    COALESCE(SUM(adet), 0) AS adet,
                    COALESCE(SUM(CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN adet ELSE 0 END), 0) AS ikram_adet,
                    COALESCE(SUM({comp_value_expr}), 0) AS ikram_toplam,
                    COUNT(*) AS satir_sayisi,
                    COUNT(DISTINCT DATE(tarih_saat)) AS gun_sayisi,
                    COUNT(DISTINCT DATE_TRUNC('hour', tarih_saat)) AS aktif_saat_sayisi
                FROM satislar
                WHERE DATE(tarih_saat) BETWEEN %s AND %s
            """, (baslangic, bitis))
            totals = cursor.fetchone()

            cursor.execute(f"""
                SELECT
                    COALESCE(NULLIF(TRIM(urun), ''), 'Ürün') AS urun,
                    COALESCE(SUM(adet), 0) AS adet,
                    COALESCE(SUM(CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN 0 ELSE adet END), 0) AS satis_adet,
                    COALESCE(SUM(CASE WHEN COALESCE(tip, 'normal') = 'ikram' THEN adet ELSE 0 END), 0) AS ikram_adet,
                    COALESCE(SUM({revenue_expr}), 0) AS ciro,
                    COALESCE(SUM({comp_value_expr}), 0) AS ikram_toplam
                FROM satislar
                WHERE DATE(tarih_saat) BETWEEN %s AND %s
                GROUP BY COALESCE(NULLIF(TRIM(urun), ''), 'Ürün')
                ORDER BY adet DESC, ciro DESC, urun ASC
                LIMIT 20
            """, (baslangic, bitis))
            product_demand = cursor.fetchall()

            cursor.execute(f"""
                SELECT
                    EXTRACT(HOUR FROM tarih_saat)::int AS saat,
                    COALESCE(SUM(adet), 0) AS adet,
                    COALESCE(SUM({revenue_expr}), 0) AS ciro,
                    COUNT(*) AS satir_sayisi
                FROM satislar
                WHERE DATE(tarih_saat) BETWEEN %s AND %s
                GROUP BY EXTRACT(HOUR FROM tarih_saat)::int
                ORDER BY saat ASC
            """, (baslangic, bitis))
            hourly_load = cursor.fetchall()

            cursor.execute(f"""
                SELECT
                    {channel_expr} AS kanal,
                    COALESCE(SUM(adet), 0) AS adet,
                    COALESCE(SUM({revenue_expr}), 0) AS ciro,
                    COUNT(*) AS satir_sayisi
                FROM satislar
                WHERE DATE(tarih_saat) BETWEEN %s AND %s
                GROUP BY {channel_expr}
                ORDER BY ciro DESC, adet DESC
            """, (baslangic, bitis))
            channel_mix = cursor.fetchall()

            cursor.execute(f"""
                SELECT
                    DATE(tarih_saat) AS tarih,
                    COALESCE(SUM(adet), 0) AS adet,
                    COALESCE(SUM({revenue_expr}), 0) AS ciro,
                    COUNT(*) AS satir_sayisi
                FROM satislar
                WHERE DATE(tarih_saat) BETWEEN %s AND %s
                GROUP BY DATE(tarih_saat)
                ORDER BY tarih ASC
            """, (baslangic, bitis))
            day_trend = cursor.fetchall()

        return {
            "totals": totals,
            "product_demand": product_demand,
            "hourly_load": hourly_load,
            "channel_mix": channel_mix,
            "day_trend": day_trend,
        }
    
    # ==================== CARİ İŞLEMLERİ ====================
    
    def get_or_create_cari(self, cari_isim):
        """Cari hesap getir veya oluştur"""
        with self.get_cursor() as cursor:
            # Önce kontrol et
            cursor.execute("SELECT id FROM cari_hesaplar WHERE cari_isim = %s", (cari_isim,))
            result = cursor.fetchone()
            
            if result:
                return result['id']
            
            # Yoksa oluştur
            cursor.execute("""
                INSERT INTO cari_hesaplar (cari_isim)
                VALUES (%s)
                RETURNING id
            """, (cari_isim,))
            return cursor.fetchone()['id']
    
    def update_cari_details(self, cari_isim, telefon=None, adres=None, vergi_no=None):
        """Cari detaylarını güncelle"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE cari_hesaplar
                SET telefon = COALESCE(%s, telefon),
                    adres = COALESCE(%s, adres),
                    vergi_no = COALESCE(%s, vergi_no)
                WHERE cari_isim = %s
            """, (telefon, adres, vergi_no, cari_isim))

    def get_cari_by_phone(self, telefon):
        """Telefon numarasına göre cari getir"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM cari_hesaplar WHERE telefon = %s", (telefon,))
            return cursor.fetchone()
    
    def get_customer_order_history(self, cari_isim, limit=5):
        """Müşterinin geçmiş siparişlerini getir"""
        with self.get_cursor() as cursor:
            # Cari ismin adisyonlardaki masa veya paket adı olarak geçebileceği veya 
            # satışlar tablosunda bir şekilde (masa alanında olabilir) saklanmış olabileceği 
            # varsayımıyla satislar tablosuna bakıyoruz.
            # Not: Mevcut sistemde paket servisler 'Paket 1' vb. olarak tutuluyor.
            # Eğer ödeme aşamasında 'Açık Hesap' seçildiyse cari_hareketler'e bakabiliriz.
            # Ancak ürün bazlı geçmiş için satislar tablosunda 'masa' alanında cari ismi
            # saklamak daha mantıklı olacaktır.
            cursor.execute("""
                SELECT urun, adet, fiyat, tarih_saat, odeme
                FROM satislar
                WHERE masa = %s
                ORDER BY tarih_saat DESC
                LIMIT %s
            """, (cari_isim, limit))
            return cursor.fetchall()
    
    def save_cari_transaction(self, cari_isim, islem, tutar, adisyon_detay=None):
        """Cari hesap hareketi ekle"""
        with self.get_cursor() as cursor:
            cari_id = self.get_or_create_cari(cari_isim)
            cursor.execute("""
                INSERT INTO cari_hareketler (cari_id, islem, tutar, adisyon_detay)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (cari_id, islem, tutar, Json(adisyon_detay) if adisyon_detay else None))
            return cursor.fetchone()['id']
    
    def get_cari_balance(self, cari_isim):
        """Cari bakiyesini getir"""
        with self.get_cursor() as cursor:
            cari_id = self.get_or_create_cari(cari_isim)
            cursor.execute("""
                SELECT COALESCE(SUM(tutar), 0) as bakiye
                FROM cari_hareketler
                WHERE cari_id = %s
            """, (cari_id,))
            return float(cursor.fetchone()['bakiye'])
    
    def get_all_cari_accounts(self):
        """Tüm cari hesapları listele"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    ch.id,
                    ch.cari_isim,
                    ch.telefon,
                    ch.adres,
                    ch.vergi_no,
                    ch.olusturma_tarihi,
                    COALESCE(SUM(chr.tutar), 0) as bakiye
                FROM cari_hesaplar ch
                LEFT JOIN cari_hareketler chr ON ch.id = chr.cari_id
                GROUP BY ch.id, ch.cari_isim, ch.telefon, ch.adres, ch.vergi_no, ch.olusturma_tarihi
                ORDER BY ch.cari_isim
            """)
            return cursor.fetchall()
    
    def get_cari_transactions(self, cari_isim):
        """Cari hesap hareketlerini getir"""
        with self.get_cursor() as cursor:
            cari_id = self.get_or_create_cari(cari_isim)
            cursor.execute("""
                SELECT * FROM cari_hareketler
                WHERE cari_id = %s
                ORDER BY tarih DESC
            """, (cari_id,))
            return cursor.fetchall()
    
    def delete_cari_account(self, cari_isim):
        """Cari hesabı sil (CASCADE ile hareketler de silinir)"""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM cari_hesaplar WHERE cari_isim = %s", (cari_isim,))
    
    # ==================== STOK İŞLEMLERİ ====================
    
    def update_stock(self, malzeme, miktar, birim=None, alis_fiyati=None, kritik_seviye=None):
        """Stok ekle veya güncelle"""
        with self.get_cursor() as cursor:
            # Önce kontrol et
            cursor.execute("SELECT miktar FROM stoklar WHERE malzeme = %s", (malzeme,))
            result = cursor.fetchone()
            
            if result:
                # Varsa miktarı artır
                cursor.execute("""
                    UPDATE stoklar
                    SET miktar = miktar + %s,
                        alis_fiyati = COALESCE(%s, alis_fiyati),
                        son_guncelleme = CURRENT_TIMESTAMP
                    WHERE malzeme = %s
                """, (miktar, alis_fiyati, malzeme))
            else:
                # Yoksa yeni kayıt
                cursor.execute("""
                    INSERT INTO stoklar (malzeme, miktar, birim, alis_fiyati, kritik_seviye)
                    VALUES (%s, %s, %s, %s, %s)
                """, (malzeme, miktar, birim, alis_fiyati, kritik_seviye or 5.0))
    
    def reduce_stock(self, malzeme, miktar):
        """Stok azalt"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE stoklar
                SET miktar = miktar - %s,
                    son_guncelleme = CURRENT_TIMESTAMP
                WHERE malzeme = %s
            """, (miktar, malzeme))
    
    def get_all_stocks(self):
        """Tüm stokları getir"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM stoklar ORDER BY malzeme")
            return cursor.fetchall()
    
    def get_low_stocks(self):
        """Kritik seviyenin altındaki stoklar"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM stoklar
                WHERE miktar <= kritik_seviye
                ORDER BY miktar ASC
            """)
            return cursor.fetchall()
    
    # ==================== MENÜ İŞLEMLERİ ====================
    
    def load_menu_from_file(self, menu_file="menu.txt"):
        """menu.txt dosyasından menüyü yükle"""
        import os
        if not os.path.exists(menu_file):
            return
        
        with self.get_cursor() as cursor:
            # Önce mevcut menüyü temizle
            cursor.execute("DELETE FROM menu")
            
            # Dosyadan oku ve ekle
            sira = 0
            with open(menu_file, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split(";")
                    if len(parts) >= 3:
                        kategori, urun_adi, fiyat = parts[:3]
                        # Parse platform percentages if they exist
                        oran_ys = float(parts[3]) if len(parts) > 3 else 0
                        oran_ty = float(parts[4]) if len(parts) > 4 else 0
                        oran_gt = float(parts[5]) if len(parts) > 5 else 0
                        oran_mg = float(parts[6]) if len(parts) > 6 else 0
                        image_url = parts[7].strip() if len(parts) > 7 else ""
                        visible_raw = parts[8].strip().lower() if len(parts) > 8 else "1"
                        menu_visible = visible_raw not in ("0", "false", "hayir", "hayır", "no", "off")

                        cursor.execute("""
                            INSERT INTO menu
                                (kategori, urun_adi, fiyat, sira, oran_ys, oran_ty, oran_gt, oran_mg, image_url, menu_visible)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            kategori.strip(),
                            urun_adi.strip(),
                            float(fiyat.strip()),
                            sira,
                            oran_ys,
                            oran_ty,
                            oran_gt,
                            oran_mg,
                            image_url,
                            menu_visible
                        ))
                        sira += 1
            
            print(f"✓ {sira} ürün menu.txt'den yüklendi")
    
    def get_menu_by_category(self):
        """Kategoriye göre menüyü getir (dictionary)"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT kategori, urun_adi, fiyat, oran_ys, oran_ty, oran_gt, oran_mg, image_url, menu_visible
                FROM menu
                ORDER BY sira
            """)
            rows = cursor.fetchall()
            
            menu_dict = {}
            for row in rows:
                kategori = row['kategori']
                if kategori not in menu_dict:
                    menu_dict[kategori] = []
                menu_dict[kategori].append([
                    row['urun_adi'], 
                    float(row['fiyat']),
                    float(row.get('oran_ys', 0)),
                    float(row.get('oran_ty', 0)),
                    float(row.get('oran_gt', 0)),
                    float(row.get('oran_mg', 0)),
                    (row.get('image_url') or ""),
                    bool(row.get('menu_visible', True))
                ])
            
            return menu_dict
    
    def save_menu_to_file(self, menu_file="menu.txt"):
        """Menüyü menu.txt dosyasına kaydet"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT kategori, urun_adi, fiyat, oran_ys, oran_ty, oran_gt, oran_mg, image_url, menu_visible
                FROM menu
                ORDER BY sira
            """)
            rows = cursor.fetchall()
            
            with open(menu_file, "w", encoding="utf-8") as f:
                for row in rows:
                    image_url = (row.get('image_url') or '').replace(';', '')
                    menu_visible = "1" if row.get('menu_visible', True) else "0"
                    line = f"{row['kategori']};{row['urun_adi']};{row['fiyat']};{row['oran_ys']};{row['oran_ty']};{row['oran_gt']};{row['oran_mg']};{image_url};{menu_visible}\n"
                    f.write(line)

    # ==================== KASA VE VARDIYA İŞLEMLERİ ====================

    def get_kasalar(self):
        """Tüm kasaları getir"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM kasalar ORDER BY ad")
            return cursor.fetchall()

    def add_kasa(self, ad):
        """Yeni kasa ekle"""
        with self.get_cursor() as cursor:
            cursor.execute("INSERT INTO kasalar (ad) VALUES (%s) RETURNING id", (ad,))
            return cursor.fetchone()['id']

    def delete_kasa(self, kasa_id):
        """Kasayı sil"""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM kasalar WHERE id = %s", (kasa_id,))

    def get_active_shift_by_kasa(self, kasa_id):
        """Bir kasanın aktif vardiyasını getir"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM vardiyalar WHERE kasa_id = %s AND durum = 'acik'", (kasa_id,))
            return cursor.fetchone()

    def open_shift(self, kasa_id, kasiyer, acilis_bakiyesi):
        """Vardiya aç"""
        # Önce aktif vardiya var mı kontrol et
        active = self.get_active_shift_by_kasa(kasa_id)
        if active:
            raise Exception("Bu kasa için zaten açık bir vardiya var")
        
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO vardiyalar (kasa_id, kasiyer, acilis_bakiyesi, durum)
                VALUES (%s, %s, %s, 'acik')
                RETURNING id
            """, (kasa_id, kasiyer, acilis_bakiyesi))
            return cursor.fetchone()['id']

    def close_shift(self, shift_id, kapanis_nakit, kapanis_kart, kapanis_bakiyesi=None):
        """Vardiya kapat"""
        if kapanis_bakiyesi is None:
            kapanis_bakiyesi = kapanis_nakit + kapanis_kart
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE vardiyalar
                SET kapanis_zamani = CURRENT_TIMESTAMP,
                    kapanis_nakit = %s,
                    kapanis_kart = %s,
                    kapanis_bakiyesi = %s,
                    durum = 'kapali'
                WHERE id = %s
            """, (kapanis_nakit, kapanis_kart, kapanis_bakiyesi, shift_id))

    def get_shift_totals(self, shift_id):
        """Vardiya toplamlarını hesapla"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    odeme,
                    SUM(fiyat * adet) as toplam
                FROM satislar
                WHERE vardiya_id = %s
                  AND COALESCE(tip, 'normal') <> 'ikram'
                GROUP BY odeme
            """, (shift_id,))
            return cursor.fetchall()

    def get_shift_closing_totals(self, shift_id):
        """Vardiya kapama için nakit/kart toplamlarını hesapla."""
        totals = {
            'nakit': Decimal('0'),
            'kart': Decimal('0'),
            'diger': Decimal('0'),
            'toplam': Decimal('0'),
        }
        for row in self.get_shift_totals(shift_id):
            payment = (row.get('odeme') or '').strip().lower()
            amount = row.get('toplam') or Decimal('0')
            totals['toplam'] += amount
            if 'nakit' in payment:
                totals['nakit'] += amount
            elif 'kart' in payment or 'kredi' in payment:
                totals['kart'] += amount
            else:
                totals['diger'] += amount
        return totals
    
    def get_shift_by_id(self, shift_id):
        """ID'ye göre vardiya bilgilerini getir"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT v.*, k.ad as kasa_adi 
                FROM vardiyalar v 
                JOIN kasalar k ON v.kasa_id = k.id 
                WHERE v.id = %s
            """, (shift_id,))
            return cursor.fetchone()

    def get_all_shifts(self, limit=50):
        """Tüm vardiyaları getir"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT v.*, k.ad as kasa_adi 
                FROM vardiyalar v 
                JOIN kasalar k ON v.kasa_id = k.id 
                ORDER BY acilis_zamani DESC 
                LIMIT %s
            """, (limit,))
            return cursor.fetchall()

    # ==================== PUBLIC QR OTURUM İŞLEMLERİ ====================

    def cleanup_public_security_state(self):
        """Süresi dolan nonce ve session kayıtlarını temizle"""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM public_qr_nonces WHERE expires_at < CURRENT_TIMESTAMP OR used_at IS NOT NULL")
            cursor.execute("DELETE FROM public_table_sessions WHERE expires_at < CURRENT_TIMESTAMP OR status <> 'active'")

    def create_public_nonce(self, nonce, table_name, shift_id, expires_at):
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO public_qr_nonces (nonce, table_name, shift_id, expires_at)
                VALUES (%s, %s, %s, %s)
            """, (nonce, table_name, shift_id, expires_at))

    def get_public_nonce(self, nonce):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM public_qr_nonces WHERE nonce = %s", (nonce,))
            return cursor.fetchone()

    def mark_public_nonce_used(self, nonce):
        with self.get_cursor() as cursor:
            cursor.execute("UPDATE public_qr_nonces SET used_at = CURRENT_TIMESTAMP WHERE nonce = %s", (nonce,))

    def create_public_session(self, session_id, table_name, shift_id, verify_method, device_fingerprint, ip, expires_at):
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO public_table_sessions
                    (id, session_token, table_name, shift_id, verify_method, device_fingerprint, ip, status, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', %s)
            """, (session_id, session_id, table_name, shift_id, verify_method, device_fingerprint, ip, expires_at))

    def get_public_session(self, session_id):
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM public_table_sessions
                WHERE id = %s OR session_token = %s
            """, (session_id, session_id))
            return cursor.fetchone()

    def update_public_session_expiry(self, session_id, expires_at):
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE public_table_sessions
                SET expires_at = %s
                WHERE (id = %s OR session_token = %s) AND status = 'active'
            """, (expires_at, session_id, session_id))

    def revoke_public_sessions_for_table(self, table_name):
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE public_table_sessions
                SET status = 'revoked'
                WHERE table_name = %s AND status = 'active'
            """, (table_name,))

    def revoke_public_sessions_for_shift(self, shift_id):
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE public_table_sessions
                SET status = 'revoked'
                WHERE shift_id = %s AND status = 'active'
            """, (shift_id,))

    def save_nfc_tag_hash(self, table_name, tag_uid_hash):
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO table_nfc_tags (table_name, tag_uid_hash, is_active, updated_at)
                VALUES (%s, %s, TRUE, CURRENT_TIMESTAMP)
                ON CONFLICT (table_name)
                DO UPDATE SET
                    tag_uid_hash = EXCLUDED.tag_uid_hash,
                    is_active = TRUE,
                    updated_at = CURRENT_TIMESTAMP
            """, (table_name, tag_uid_hash))

    def get_nfc_tag_hash(self, table_name):
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT tag_uid_hash
                FROM table_nfc_tags
                WHERE table_name = %s AND is_active = TRUE
            """, (table_name,))
            row = cursor.fetchone()
            return row['tag_uid_hash'] if row else None
    
    # ==================== KURYE İŞLEMLERİ ====================

    def get_all_kuryeler(self):
        """Tüm kuryeleri getir"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT k.*, f.ad as firma_adi 
                FROM kuryeler k 
                LEFT JOIN kurye_firmalari f ON k.firma_id = f.id
                ORDER BY k.ad
            """)
            return cursor.fetchall()

    def add_kurye(self, ad, telefon=None, plaka=None, firma_id=None):
        """Yeni kurye ekle"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO kuryeler (ad, telefon, plaka, firma_id)
                VALUES (%s, %s, %s, %s) RETURNING id
            """, (ad, telefon, plaka, firma_id))
            return cursor.fetchone()['id']

    def update_kurye(self, kurye_id, ad=None, telefon=None, plaka=None, firma_id=None, aktif=None):
        """Kurye bilgilerini güncelle"""
        with self.get_cursor() as cursor:
            updates = []
            params = []
            if ad is not None:
                updates.append("ad = %s")
                params.append(ad)
            if telefon is not None:
                updates.append("telefon = %s")
                params.append(telefon)
            if plaka is not None:
                updates.append("plaka = %s")
                params.append(plaka)
            if firma_id is not None:
                updates.append("firma_id = %s")
                params.append(firma_id)
            if aktif is not None:
                updates.append("aktif = %s")
                params.append(aktif)
            
            if not updates: return False
            
            params.append(kurye_id)
            cursor.execute(f"UPDATE kuryeler SET {', '.join(updates)} WHERE id = %s", tuple(params))
            return True

    def delete_kurye(self, kurye_id):
        """Kuryeyi sil"""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM kuryeler WHERE id = %s", (kurye_id,))
            return True

    def get_kurye_firmalari(self):
        """Tüm kurye firmalarını getir"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM kurye_firmalari ORDER BY ad")
            return cursor.fetchall()

    def add_kurye_firmasi(self, ad, api_key=None, ayarlar=None):
        """Yeni kurye firması ekle"""
        with self.get_cursor() as cursor:
            import json
            cursor.execute("""
                INSERT INTO kurye_firmalari (ad, api_key, ayarlar)
                VALUES (%s, %s, %s) RETURNING id
            """, (ad, api_key, json.dumps(ayarlar or {})))
            return cursor.fetchone()['id']

    # ==================== ONLINE SİPARİŞ İŞLEMLERİ ====================

    def save_online_order(self, musteri_adi, telefon, adres, not_bilgisi, items, adisyon_adi, odeme_tipi='nakit'):
        """Online siparis kaydini olustur"""
        import json
        items_data = json.dumps([
            {
                'urun': it.get('urun'), 
                'adet': it.get('adet', 1), 
                'fiyat': float(it.get('fiyat', 0)),
                'not': it.get('not', '') # Ürün bazlı not (Örn: Ketçapsız)
            }
            for it in items
        ])
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO online_orders
                    (musteri_adi, telefon, adres, not_bilgisi, items, odeme_tipi, adisyon_adi, durum)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, 'bekliyor')
                RETURNING id
            """, (musteri_adi, telefon, adres, not_bilgisi, items_data, odeme_tipi, adisyon_adi))
            return cursor.fetchone()['id']

    def get_online_orders(self, durum=None, limit=50):
        """Online siparisleri listele"""
        with self.get_cursor() as cursor:
            if durum:
                cursor.execute("""
                    SELECT * FROM online_orders WHERE durum = %s
                    ORDER BY olusturma DESC LIMIT %s
                """, (durum, limit))
            else:
                cursor.execute("""
                    SELECT * FROM online_orders
                    ORDER BY olusturma DESC LIMIT %s
                """, (limit,))
            return cursor.fetchall()

    def update_online_order_status(self, order_id, durum):
        """Online siparis durumunu guncelle"""
        with self.get_cursor() as cursor:
            cursor.execute(
                "UPDATE online_orders SET durum = %s WHERE id = %s",
                (durum, order_id)
            )

    # ==================== SESLİ ASİSTAN İŞLEMLERİ ====================

    def add_to_blacklist(self, telefon, sebep='Belirtilmedi'):
        """Telefon numarasını karalisteye ekle"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO voice_agent_blacklist (telefon, sebep)
                VALUES (%s, %s)
                ON CONFLICT (telefon) DO UPDATE SET sebep = %s
            """, (telefon, sebep, sebep))

    def remove_from_blacklist(self, telefon):
        """Telefon numarasını karalisteden çıkar"""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM voice_agent_blacklist WHERE telefon = %s", (telefon,))

    def is_blacklisted(self, telefon):
        """Telefon numarası karalistede mi?"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT 1 FROM voice_agent_blacklist WHERE telefon = %s", (telefon,))
            return cursor.fetchone() is not None

    def get_blacklist(self):
        """Tüm karalisteyi getir"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM voice_agent_blacklist ORDER BY tarih DESC")
            return cursor.fetchall()

    def add_puantaj_record(self, personel_adi, rol='garson', giris_saati=None, notlar=None):
        """Yeni çalışan giriş kaydı ekle"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO puantaj (personel_adi, rol, tarih, giris_saati, notlar)
                VALUES (%s, %s, %s::timestamp::date, %s, %s)
                RETURNING id
            """, (
                personel_adi,
                rol,
                giris_saati or datetime.now(),
                giris_saati or datetime.now(),
                notlar
            ))
            return cursor.fetchone()['id']

    def update_puantaj_checkout(self, record_id, cikis_saati=None, notlar=None):
        """Çalışan çıkış saatini güncelle, toplam dakikayı hesapla"""
        with self.get_cursor() as cursor:
            cikis = cikis_saati or datetime.now()
            cursor.execute("""
                UPDATE puantaj
                SET cikis_saati = %s,
                    toplam_dakika = EXTRACT(EPOCH FROM (%s - giris_saati))::INTEGER / 60,
                    notlar = COALESCE(%s, notlar)
                WHERE id = %s
            """, (cikis, cikis, notlar, record_id))

    def get_puantaj_records(self, tarih_baslangic=None, tarih_bitis=None, personel_adi=None):
        """Puantaj kayıtlarını filtreli getir"""
        with self.get_cursor() as cursor:
            conditions = []
            params = []
            if tarih_baslangic:
                conditions.append("tarih >= %s")
                params.append(tarih_baslangic)
            if tarih_bitis:
                conditions.append("tarih <= %s")
                params.append(tarih_bitis)
            if personel_adi:
                conditions.append("personel_adi ILIKE %s")
                params.append(f"%{personel_adi}%")
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cursor.execute(f"""
                SELECT * FROM puantaj {where}
                ORDER BY tarih DESC, giris_saati DESC
            """, tuple(params))
            return cursor.fetchall()

    def get_puantaj_monthly_summary(self, yil, ay):
        """Aylık kişi bazlı puantaj özeti (toplam gün ve dakika)"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT
                    personel_adi,
                    rol,
                    COUNT(DISTINCT tarih) AS toplam_gun,
                    COALESCE(SUM(toplam_dakika), 0) AS toplam_dakika
                FROM puantaj
                WHERE EXTRACT(YEAR FROM tarih) = %s
                  AND EXTRACT(MONTH FROM tarih) = %s
                GROUP BY personel_adi, rol
                ORDER BY personel_adi
            """, (yil, ay))
            return cursor.fetchall()

    def delete_puantaj_record(self, record_id):
        """Puantaj kaydını sil"""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM puantaj WHERE id = %s", (record_id,))

    # ==================== GENEL ====================

    def close_pool(self):
        """Bağlantı havuzunu kapat"""
        if self._pool:
            self._pool.closeall()
            print("✓ PostgreSQL bağlantı havuzu kapatıldı")


# Singleton instance
db = Database()


# Test fonksiyonu
if __name__ == "__main__":
    try:
        # Veri tabanını başlat
        db.init_database()
        
        # Test: Menü yükle
        db.load_menu_from_file()
        menu = db.get_menu_by_category()
        print("\nMenü kategorileri:", list(menu.keys()))
        
        # Test: Satış kaydet
        sale_id = db.save_sale("Test Ürün", 2, 50.0, "Nakit", masa="Masa 1")
        print(f"\nSatış kaydedildi, ID: {sale_id}")
        
        # Test: Cari işlem
        db.save_cari_transaction("Test Müşteri", "Test Borç", -100.0)
        bakiye = db.get_cari_balance("Test Müşteri")
        print(f"Test Müşteri bakiyesi: {bakiye} TL")
        
        print("\n✓ Tüm testler başarılı!")
        
    except Exception as e:
        print(f"\n✗ Hata: {e}")
        import traceback
        traceback.print_exc()
