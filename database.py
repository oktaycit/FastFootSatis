# -*- coding: utf-8 -*-
"""
PostgreSQL Veri Tabanı Yönetim Modülü
FastFootSatış Projesi
"""

import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
from datetime import datetime
from contextlib import contextmanager
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
                    adet INTEGER NOT NULL,
                    fiyat DECIMAL(10, 2) NOT NULL,
                    odeme TEXT NOT NULL,
                    tip TEXT DEFAULT 'normal',
                    tarih_saat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    masa TEXT,
                    terminal_id TEXT
                )
            """)
            
            # CARİ HESAPLAR TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cari_hesaplar (
                    id SERIAL PRIMARY KEY,
                    cari_isim TEXT NOT NULL UNIQUE,
                    telefon TEXT,
                    adres TEXT,
                    olusturma_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tablo zaten varsa kolonları ekle (migration)
            cursor.execute("ALTER TABLE cari_hesaplar ADD COLUMN IF NOT EXISTS telefon TEXT")
            cursor.execute("ALTER TABLE cari_hesaplar ADD COLUMN IF NOT EXISTS adres TEXT")
            
            # CARİ HAREKETLER TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cari_hareketler (
                    id SERIAL PRIMARY KEY,
                    cari_id INTEGER NOT NULL,
                    tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    islem TEXT NOT NULL,
                    tutar DECIMAL(10, 2) NOT NULL,
                    FOREIGN KEY (cari_id) REFERENCES cari_hesaplar(id) ON DELETE CASCADE
                )
            """)
            
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
                    oran_mg DECIMAL(5, 2) DEFAULT 0
                )
            """)
            
            # Migrations for existing menu table
            cursor.execute("ALTER TABLE menu ADD COLUMN IF NOT EXISTS oran_ys DECIMAL(5, 2) DEFAULT 0")
            cursor.execute("ALTER TABLE menu ADD COLUMN IF NOT EXISTS oran_ty DECIMAL(5, 2) DEFAULT 0")
            cursor.execute("ALTER TABLE menu ADD COLUMN IF NOT EXISTS oran_gt DECIMAL(5, 2) DEFAULT 0")
            cursor.execute("ALTER TABLE menu ADD COLUMN IF NOT EXISTS oran_mg DECIMAL(5, 2) DEFAULT 0")
            
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
                    kapanis_zamani TIMESTAMP,
                    acilis_bakiyesi DECIMAL(10, 2) NOT NULL DEFAULT 0,
                    kapanis_nakit DECIMAL(10, 2),
                    kapanis_kart DECIMAL(10, 2),
                    durum TEXT NOT NULL DEFAULT 'acik',
                    FOREIGN KEY (kasa_id) REFERENCES kasalar(id) ON DELETE CASCADE
                )
            """)

            # KURYELER TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kuryeler (
                    id SERIAL PRIMARY KEY,
                    ad TEXT NOT NULL,
                    telefon TEXT,
                    plaka TEXT,
                    aktif BOOLEAN DEFAULT TRUE,
                    firma_id INTEGER
                )
            """)

            # KURYE FIRMALARI TABLOSU
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kurye_firmalari (
                    id SERIAL PRIMARY KEY,
                    ad TEXT NOT NULL UNIQUE,
                    api_key TEXT,
                    ayarlar JSONB DEFAULT '{}'
                )
            """)

            # SATIŞLAR TABLOSUNA VARDIYA_ID VE KURYE_ID EKLE
            cursor.execute("ALTER TABLE satislar ADD COLUMN IF NOT EXISTS vardiya_id INTEGER")
            cursor.execute("ALTER TABLE satislar ADD COLUMN IF NOT EXISTS kurye_id INTEGER")
            
            # İNDEXLER
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_satislar_tarih ON satislar(tarih_saat)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_satislar_tip ON satislar(tip)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_satislar_vardiya ON satislar(vardiya_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_satislar_kurye ON satislar(kurye_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cari_hareketler_cari ON cari_hareketler(cari_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_menu_kategori ON menu(kategori)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vardiyalar_durum ON vardiyalar(durum)")
            
            print("✓ Veri tabanı şeması oluşturuldu")
    
    # ==================== SATIŞ İŞLEMLERİ ====================
    
    def save_sale(self, urun, adet, fiyat, odeme, tip='normal', masa=None, terminal_id=None, vardiya_id=None):
        """Satış kaydı ekle"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO satislar (urun, adet, fiyat, odeme, tip, masa, terminal_id, vardiya_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (urun, adet, fiyat, odeme, tip, masa, terminal_id, vardiya_id))
            return cursor.fetchone()['id']
    
    def save_sales_batch(self, sales_list):
        """Toplu satış kaydı ekle"""
        with self.get_cursor() as cursor:
            for sale in sales_list:
                cursor.execute("""
                    INSERT INTO satislar (urun, adet, fiyat, odeme, tip, tarih_saat, masa, terminal_id, vardiya_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    sale.get('urun'),
                    sale.get('adet', 1),
                    sale.get('fiyat'),
                    sale.get('odeme', 'Nakit'),
                    sale.get('tip', 'normal'),
                    sale.get('Tarih_Saat', datetime.now()),
                    sale.get('masa'),
                    sale.get('terminal_id'),
                    sale.get('vardiya_id')
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
                    SUM(fiyat * adet) as toplam,
                    COUNT(*) as adet
                FROM satislar
                WHERE DATE(tarih_saat) = %s
                GROUP BY odeme, tip
            """, (tarih,))
            return cursor.fetchall()
    
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
    
    def update_cari_details(self, cari_isim, telefon=None, adres=None):
        """Cari detaylarını güncelle"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE cari_hesaplar
                SET telefon = COALESCE(%s, telefon),
                    adres = COALESCE(%s, adres)
                WHERE cari_isim = %s
            """, (telefon, adres, cari_isim))

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
    
    def save_cari_transaction(self, cari_isim, islem, tutar):
        """Cari hesap hareketi ekle"""
        with self.get_cursor() as cursor:
            cari_id = self.get_or_create_cari(cari_isim)
            cursor.execute("""
                INSERT INTO cari_hareketler (cari_id, islem, tutar)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (cari_id, islem, tutar))
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
                    ch.olusturma_tarihi,
                    COALESCE(SUM(chr.tutar), 0) as bakiye
                FROM cari_hesaplar ch
                LEFT JOIN cari_hareketler chr ON ch.id = chr.cari_id
                GROUP BY ch.id, ch.cari_isim, ch.telefon, ch.adres, ch.olusturma_tarihi
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

                        cursor.execute("""
                            INSERT INTO menu (kategori, urun_adi, fiyat, sira, oran_ys, oran_ty, oran_gt, oran_mg)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (kategori.strip(), urun_adi.strip(), float(fiyat.strip()), sira, oran_ys, oran_ty, oran_gt, oran_mg))
                        sira += 1
            
            print(f"✓ {sira} ürün menu.txt'den yüklendi")
    
    def get_menu_by_category(self):
        """Kategoriye göre menüyü getir (dictionary)"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT kategori, urun_adi, fiyat, oran_ys, oran_ty, oran_gt, oran_mg FROM menu ORDER BY sira")
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
                    float(row.get('oran_mg', 0))
                ])
            
            return menu_dict
    
    def save_menu_to_file(self, menu_file="menu.txt"):
        """Menüyü menu.txt dosyasına kaydet"""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT kategori, urun_adi, fiyat, oran_ys, oran_ty, oran_gt, oran_mg FROM menu ORDER BY sira")
            rows = cursor.fetchall()
            
            with open(menu_file, "w", encoding="utf-8") as f:
                for row in rows:
                    line = f"{row['kategori']};{row['urun_adi']};{row['fiyat']};{row['oran_ys']};{row['oran_ty']};{row['oran_gt']};{row['oran_mg']}\n"
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

    def close_shift(self, shift_id, kapanis_nakit, kapanis_kart):
        """Vardiya kapat"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE vardiyalar
                SET kapanis_zamani = CURRENT_TIMESTAMP,
                    kapanis_nakit = %s,
                    kapanis_kart = %s,
                    durum = 'kapali'
                WHERE id = %s
            """, (kapanis_nakit, kapanis_kart, shift_id))

    def get_shift_totals(self, shift_id):
        """Vardiya toplamlarını hesapla"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT 
                    odeme,
                    SUM(fiyat * adet) as toplam
                FROM satislar
                WHERE vardiya_id = %s
                GROUP BY odeme
            """, (shift_id,))
            return cursor.fetchall()
    
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
