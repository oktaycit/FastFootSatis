import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import os
import pandas as pd
from datetime import datetime
import threading
import socket
import json
import subprocess

# --- VERİ TABANI MODÜLÜ ---
try:
    from database import db
    USE_DATABASE = True
    print("✓ PostgreSQL veri tabanı modülü yüklendi")
except Exception as e:
    USE_DATABASE = False
    print(f"⚠ Veri tabanı bağlantısı yapılamadı, Excel modu kullanılıyor: {e}")
# --- PDF VE TÜRKÇE FONT DESTEĞİ ---
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from PIL import Image, ImageTk
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
TERMINAL_ID = " Ana Sunucu"
MENU_FILE = "menu.txt"
CONFIG_FILE = "config.txt"
SERVER_PORT = 5555
KALEMLER_FILE = "islem_kalemleri.txt"
FIS_AYAR_FILE = "fis_ayarlar.txt"
USB_DRIVE = "S:/"  
BASE_DIR = USB_DRIVE if os.path.exists(USB_DRIVE) else ""

# Dosyaları artık bu yolun altına kaydedeceğiz
CARI_FILE = os.path.join(BASE_DIR, "cari_kayitlar.xlsx")
SATIS_FILE = os.path.join(BASE_DIR, "satislar.xlsx")
FIS_KLASORU = os.path.join(BASE_DIR, "Fisler")
COUNTER_FILE = os.path.join(BASE_DIR, "sira_no.txt")

# Eğer USB takılıysa ve klasör yoksa oluştur
if BASE_DIR != "" and not os.path.exists(FIS_KLASORU): 
    os.makedirs(FIS_KLASORU)



if not os.path.exists(FIS_KLASORU): os.makedirs(FIS_KLASORU)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        return ip
    except:
        return "127.0.0.1"

def get_password():
    if not os.path.exists(CONFIG_FILE): return "1234"
    with open(CONFIG_FILE, "r") as f: return f.read().strip()

# --- ANA UYGULAMA ---
class RestaurantApp:
    def check_network_status(self):
        current_ip = get_local_ip()
        is_lan_active = False

        # Eğer IP 127.0.0.1 değilse, cihaz LAN’a bağlıdır
        if current_ip != "127.0.0.1" and current_ip != "":
            is_lan_active = True

        if is_lan_active:
            self.status_ip_label.config(
                text=f"🏠 LOCAL AĞ AKTİF - IP: {current_ip}",
                fg="#2ecc71", bg="#2c3e50"
            )
        else:
            self.status_ip_label.config(
                text="❌ YEREL AĞ KOPUK (LAN YOK)",
                fg="#ffffff", bg="#e74c3c"
            )

        # 1 dakika sonra tekrar kontrol et
        self.root.after(60000, self.check_network_status)
        return is_lan_active

    def check_excel_files(self):
        """Gerekli Excel dosyalarının varlığını ve sütunlarını kontrol eder."""
        STOK_FILE = os.path.join(BASE_DIR, "stoklar.xlsx")
        if not os.path.exists(STOK_FILE):
            # Ürün Adı, Mevcut Miktar, Birim, Alış Fiyatı, Kritik Seviye
            df = pd.DataFrame(columns=['Malzeme', 'Miktar', 'Birim', 'Alis_Fiyati', 'Kritik_Seviye'])
            df.to_excel(STOK_FILE, index=False)
            print("Stok dosyası oluşturuldu.")
    def show_fancy_notification(self, terminal_adi, masa_adi):
        """Görseldeki tasarıma uygun modern bildirim penceresi."""
        notify_win = tk.Toplevel(self.root)
        notify_win.title("Yeni Sipariş")
        
        # Pencere boyutları ve konumlandırma
        p_width, p_height = 450, 250
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w // 2) - (p_width // 2)
        y = (screen_h // 2) - (p_height // 2)
        
        notify_win.geometry(f"{p_width}x{p_height}+{x}+{y}")
        notify_win.overrideredirect(True) # Kenarlıkları kaldır (Görseldeki gibi saf görünüm)
        notify_win.attributes("-topmost", True) # Her zaman üstte
        
        # Ana Arka Plan (Görseldeki Turkuaz/Mavi Gradyan Esintisi)
        main_bg = "#16a085" # Koyu turkuaz
        notify_win.config(bg=main_bg, highlightbackground="#ffffff", highlightthickness=2)
        
        # İçerik Çerçevesi
        content_frame = tk.Frame(notify_win, bg=main_bg)
        content_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)
        
        # İkon Kısmı (Görseldeki Megafon simgesini temsil eder)
        try:
            # Eğer bir megafon ikonu varsa buraya eklenebilir, yoksa emoji kullanalım
            icon_label = tk.Label(content_frame, text="📢", font=("Segoe UI Emoji", 50), 
                                 fg="white", bg=main_bg)
            icon_label.pack(side=tk.LEFT, padx=10)
        except:
            pass

        # Metin Alanı
        text_frame = tk.Frame(content_frame, bg=main_bg)
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        tk.Label(text_frame, text="Yeni Sipariş", font=("Arial", 22, "bold"), 
                 fg="white", bg=main_bg).pack(anchor="w")
        
        tk.Label(text_frame, text=f"{terminal_adi} terminalinden", 
                 font=("Arial", 12), fg="#ecf0f1", bg=main_bg).pack(anchor="w", pady=(10,0))
        
        tk.Label(text_frame, text=f"{masa_adi} için yeni sipariş geldi!", 
                 font=("Arial", 12, "bold"), fg="#ffffff", bg=main_bg).pack(anchor="w")

        # Buton (Görseldeki yuvarlatılmış 'TAMAM' butonu)
        btn_close = tk.Button(notify_win, text="TAMAM", bg="#ecf0f1", fg="#2c3e50",
                             font=("Arial", 10, "bold"), bd=0, padx=25, pady=8,
                             cursor="hand2", command=notify_win.destroy)
        btn_close.pack(side=tk.BOTTOM, pady=20)
        
        # 10 saniye sonra otomatik kapanma (opsiyonel)
        self.root.after(10000, lambda: notify_win.destroy() if notify_win.winfo_exists() else None)
    def load_fis_settings(self):
        defaults = {
            "genislik": "21",
            "baslik_bosluk": "1",
            "alt_mesaj": "Afiyet Olsun",
            "alt_bosluk_satir": "5",
            "ayrac_karakter": "="
        }
        if os.path.exists(FIS_AYAR_FILE):
            with open(FIS_AYAR_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if ":" in line:
                        key, val = line.strip().split(":", 1)
                        defaults[key] = val
        return defaults 
    def __init__(self, root):
        self.root = root
        self.terminal_id = "1" 
        self.company_name = "RESTORAN"
        self.admin_password = "1234"
        self.masa_sayisi = 0
        self.paket_sayisi = 0
        self.direct_print = False
        self._after_id = None
        self.last_width = 0
        self.check_excel_files()
        self.load_all_configs() 
        self.root.title(f"{self.company_name} - Masa Takip")
        self.load_window_geometry() 
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.status_ip_label = tk.Label(self.root, text="Ağ durumu kontrol ediliyor...", bg="#2c3e50", fg="white")
        self.status_ip_label.pack(side="bottom", fill="x")
        self.cat_colors = ["#3498db", "#e67e22", "#2ecc71", "#9b59b6", "#f1c40f", "#1abc9c", "#e74c3c", "#34495e"]
        
        self.buttons_ref = {}
        self.refresh_adisyonlar()
        self.menu_data = self.load_menu_data()
        
        self.update_current_masa_selection()
        self.setup_ui()
        self.start_server()

    def on_closing(self):
        if messagebox.askokcancel("Çıkış", "Uygulamadan çıkmak istiyor musunuz?"):
            try:
                self.save_window_geometry()
                self.save_all_configs()
                # Buraya varsa açık soket bağlantılarını kapatacak bir bayrak eklenebilir
                self.root.quit()
                self.root.destroy()
                os._exit(0) # Tüm threadleri zorla sonlandırır
            except:
                os._exit(0)
    def load_islem_kalemleri(self):
        varsayilan = ["Mal Alımı", "Fatura", "Maaş", "Kira", "Vergi", "Diğer"]
        if not os.path.exists(KALEMLER_FILE):
            # Dosya yoksa oluştur ve varsayılanları yaz
            with open(KALEMLER_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(varsayilan))
            return varsayilan
    
        with open(KALEMLER_FILE, "r", encoding="utf-8") as f:
            # Boş satırları filtreleyerek listeyi al
            kalemler = [line.strip() for line in f if line.strip()]
            return kalemler if kalemler else varsayilan 
    def load_all_configs(self):
        """config.txt dosyasından tüm sistem parametrelerini yükler."""
        defaults = {
            "password": "1234", 
            "direct_print": "HAYIR",
            "masa_sayisi": "30",
            "paket_sayisi": "5",
            "firma_ismi": "RESTORAN OTOMASYON",
            "terminal_id": "1", 
            "print_nakit": "HAYIR", 
            "print_kart": "HAYIR",   
            "print_cari": "EVET",
            "kitchen_ip": "192.168.1.150", 
            "kitchen_port": "5556",
            "mutfak_varmi": "HAYIR" #
        }
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if ":" in line:
                        key, value = line.strip().split(":", 1)
                        defaults[key] = value
        
        self.admin_password = defaults["password"]
        self.direct_print = (defaults["direct_print"] == "EVET")
        self.masa_sayisi = int(defaults["masa_sayisi"])
        self.paket_sayisi = int(defaults["paket_sayisi"])
        self.company_name = defaults["firma_ismi"]
        self.terminal_id = defaults["terminal_id"]
        self.print_nakit = (defaults["print_nakit"] == "EVET")
        self.print_kart = (defaults["print_kart"] == "EVET")
        self.print_cari = (defaults["print_cari"] == "EVET")
        self.kitchen_ip = defaults["kitchen_ip"]
        self.mutfak_varmi = (defaults["mutfak_varmi"] == "EVET")
        self.kitchen_port = int(defaults["kitchen_port"])
        
    def save_all_configs(self):
        """Tüm ayarları tek seferde config.txt dosyasına kaydeder."""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(f"kitchen_ip:{self.kitchen_ip}\n")
                f.write(f"kitchen_port:{self.kitchen_port}\n")
                f.write(f"password:{self.admin_password}\n")
                f.write(f"direct_print:{'EVET' if self.direct_print else 'HAYIR'}\n")
                f.write(f"masa_sayisi:{self.masa_sayisi}\n")
                f.write(f"paket_sayisi:{self.paket_sayisi}\n")
                f.write(f"firma_ismi:{self.company_name}\n")
                f.write(f"terminal_id:{self.terminal_id}\n")
                f.write(f"print_nakit:{'EVET' if self.print_nakit else 'HAYIR'}\n")
                f.write(f"print_kart:{'EVET' if self.print_kart else 'HAYIR'}\n")
                f.write(f"print_cari:{'EVET' if self.print_cari else 'HAYIR'}\n")
                f.write(f"mutfak_varmi:{'EVET' if self.mutfak_varmi else 'HAYIR'}\n")
        except Exception as e:
            print(f"Konfigürasyon yazma hatası: {e}")

    def save_window_geometry(self):
        """Pencere boyutlarını ve konumunu dosyaya kaydeder."""
        try:
            self.root.update_idletasks()
            state = self.root.state()
            geometry = self.root.geometry()

            sash_pos = ""
            if hasattr(self, 'main_pane'):
                try:
                    # İlk bölmenin (Masa/Paket paneli) X koordinatını alıyoruz
                    sash_pos = f"|{self.main_pane.sash_coord(0)[0]}"
                except:
                    pass
            with open("window_config.txt", "w", encoding="utf-8") as f:
                f.write(f"{state}|{geometry}{sash_pos}")
                
        except Exception as e:
            print(f"Kayıt Hatası: {e}") 
    def load_window_geometry(self):
        """Kaydedilmiş yerleşimi geri yükler."""
        if os.path.exists("window_config.txt"):
            try:
                 with open("window_config.txt", "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    parts = content.split("|")
                    if len(parts) >= 2:
                        state, geometry = parts[0], parts[1]
                        self.root.geometry(geometry)
                        
                        if state == "zoomed":
                            self.root.after(100, lambda: self.root.state("zoomed"))
                        
                        # Eğer bölme konumu (sash) kaydedilmişse
                        if len(parts) == 3:
                            saved_sash = parts[2]
                            # Arayüzün tam oluşması için kısa bir gecikme ile konumu uygula
                            self.root.after(500, lambda: self.main_pane.sash_place(0, int(saved_sash), 0))
            except Exception as e:
                print(f"Yükleme Hatası: {e}")
                self.root.state('zoomed')
        
    def log_to_satislar(self, islem_adi, tutar, odeme_tipi="Nakit"):
        islem_tipi = "cari_tahsilat" if tutar > 0 else "cari_odeme"
        data = [{
            "urun": islem_adi,
            "adet": 1,
            "fiyat": tutar,
            "odeme": odeme_tipi,
            "tip": islem_tipi,
            "Tarih_Saat": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        }]
        self.save_sale_to_excel(data)    

    def change_password(self):
        new_pass = simpledialog.askstring("Şifre Değiştir", "Yeni şifreyi giriniz:", show="*")
        if new_pass:
            try:
                self.admin_password = new_pass.strip()
                self.save_all_configs()
                messagebox.showinfo("Başarılı", "Giriş şifresi başarıyla güncellendi.")
            except Exception as e:
                messagebox.showerror("Hata", f"Şifre kaydedilemedi: {e}")

    def load_setting(self, file_path, default):
        if not os.path.exists(file_path): return default
        with open(file_path, "r", encoding="utf-8") as f: return f.read().strip()

    def load_capacity(self, file_path, default):
        try:
            if not os.path.exists(file_path): return default
            with open(file_path, "r") as f: return int(f.read().strip())
        except: return default

    def refresh_adisyonlar(self):
        self.adisyonlar = {}
        if self.masa_sayisi > 0:
            for i in range(1, self.masa_sayisi + 1): self.adisyonlar[f"Masa {i}"] = []
        if self.paket_sayisi > 0:
            for i in range(1, self.paket_sayisi + 1): self.adisyonlar[f"Paket {i}"] = []
        if not self.adisyonlar: self.adisyonlar["Genel"] = []

    def update_current_masa_selection(self):
        if self.masa_sayisi > 0: self.current_masa = "Masa 1"
        elif self.paket_sayisi > 0: self.current_masa = "Paket 1"
        else: self.current_masa = "Genel"

    def load_menu_data(self):
        data = {}
        if not os.path.exists(MENU_FILE): return {"Genel": [["Örnek Ürün", 100.0]]}
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(";")
                if len(parts) == 3:
                    cat, item, price = parts[0].strip(), parts[1].strip(), parts[2].strip()
                    if cat not in data: data[cat] = []
                    data[cat].append([item, float(price)])
        return data
    def open_stock_entry(self):
        """Yeni stok girişi veya güncelleme ekranı."""
        top = self.open_modal("Depo Mal Girişi", "350x450")
    
        tk.Label(top, text="Malzeme Adı (Domates, Un, vb.):").pack(pady=5)
        e_ad = tk.Entry(top, font=("Arial", 12)); e_ad.pack(pady=5)
    
        tk.Label(top, text="Miktar (Sayısal):").pack(pady=5)
        e_mik = tk.Entry(top, font=("Arial", 12)); e_mik.pack(pady=5)
    
        tk.Label(top, text="Birim (KG, Adet, Paket):").pack(pady=5)
        e_birim = tk.Entry(top, font=("Arial", 12)); e_birim.pack(pady=5)
    
        tk.Label(top, text="Birim Alış Fiyatı (TL):").pack(pady=5)
        e_fiyat = tk.Entry(top, font=("Arial", 12)); e_fiyat.pack(pady=5)
    def stok_dususu_yap(self, urun_adi, miktar):
        """Ürün satıldığında stoktaki hammaddeyi azaltır."""
        STOK_FILE = os.path.join(BASE_DIR, "stoklar.xlsx")
        if not os.path.exists(STOK_FILE): return

        # ÖRNEK REÇETELER (Bunu daha sonra bir dosyadan da okutabiliriz)
        receteler = {
            "KÖFTE": [("ET", 0.150), ("EKMEK", 1)],
            "AYRAN": [("AYRAN", 1)],
            "KOLA": [("KOLA", 1)]
        }

        if urun_adi.upper() in receteler:
            df = pd.read_excel(STOK_FILE)
            for hammadde, sarfiyat in receteler[urun_adi.upper()]:
                if hammadde in df['Malzeme'].values:
                    # Stoğu düşür
                    df.loc[df['Malzeme'] == hammadde, 'Miktar'] -= (sarfiyat * miktar)
            df.to_excel(STOK_FILE, index=False)
        def kaydet():
            try:
                ad = e_ad.get().strip().upper()
                mik = float(e_mik.get().replace(",", "."))
                fiyat = float(e_fiyat.get().replace(",", "."))
                birim = e_birim.get().strip()
            
                STOK_FILE = os.path.join(BASE_DIR, "stoklar.xlsx")
                df = pd.read_excel(STOK_FILE)
            
                if ad in df['Malzeme'].values:
                    # Varsa miktar ekle, fiyatı güncelle
                    df.loc[df['Malzeme'] == ad, ['Miktar', 'Alis_Fiyati']] = [df.loc[df['Malzeme'] == ad, 'Miktar'].values[0] + mik, fiyat]
                else:
                # Yoksa yeni satır ekle
                    yeni = pd.DataFrame([[ad, mik, birim, fiyat, 5.0]], columns=df.columns)
                    df = pd.concat([df, yeni], ignore_index=True)
                
                df.to_excel(STOK_FILE, index=False)
                messagebox.showinfo("Başarılı", f"{ad} stoka eklendi.")
                top.destroy()
            except:
                messagebox.showerror("Hata", "Lütfen sayısal değerleri kontrol edin!")

        tk.Button(top, text="💾 STOKU GÜNCELLE", bg="#27ae60", fg="white", 
                  font=("Arial", 11, "bold"), height=2, command=kaydet).pack(fill=tk.X, padx=20, pady=20)
    def cari_odeme_yap(self, parent_top, isim):
        pay_top = self.open_modal(f"Cari İşlem: {isim}", "350x550")
        
        tk.Label(pay_top, text="Yapılacak İşlemi Seçiniz:", font=("Arial", 10, "bold")).pack(pady=10)
        
        islem_turu = tk.StringVar(value="BORÇLAN")
        
        # Seçenekler
        f_radio = tk.Frame(pay_top); f_radio.pack(pady=5)
        tk.Radiobutton(f_radio, text="📌 BORÇLAN (Kasayı Etkilemez)", variable=islem_turu, 
                       value="BORÇLAN", font=("Arial", 10), fg="#c0392b").pack(anchor="w")
        tk.Radiobutton(f_radio, text="💸 ÖDE (Kasadan Nakit Düşer)", variable=islem_turu, 
                       value="ÖDE", font=("Arial", 10), fg="#27ae60").pack(anchor="w")
        
        tk.Label(pay_top, text="\nİşlem Kalemi:", font=("Arial", 10, "bold")).pack()
        odeme_turleri = self.load_islem_kalemleri() 
    
        secilen_kalem = tk.StringVar(value=odeme_turleri[0] if odeme_turleri else "")
        combo = ttk.Combobox(pay_top, textvariable=secilen_kalem, values=odeme_turleri, state="readonly")
        combo.pack(pady=5)
        tk.Label(pay_top, text="\nTutar (TL):", font=("Arial", 10, "bold")).pack()
        e_tutar = tk.Entry(pay_top, font=("Arial", 14), width=15, justify="center"); e_tutar.pack(pady=5); e_tutar.focus_set()

        def onayla():
            try:
                tutar = float(e_tutar.get().replace(",", "."))
                if tutar <= 0: raise ValueError
                
                tur = islem_turu.get()
                kalem = secilen_kalem.get()
                
                if tur == "BORÇLAN":
                    # Borçlanma: Cari eksiye gider (-), Kasa DEĞİŞMEZ.
                    if self.save_to_cari(isim, f"{kalem} (Borçlanıldı)", -tutar):
                        messagebox.showinfo("Başarılı", f"{isim} hesabına borç kaydedildi.\nKasadan para çıkışı yapılmadı.")
                        pay_top.destroy()
                else:
                    # Ödeme: Cari artıya gider (+), KASADAN DÜŞER (-).
                    # 1. Cariyi kapat (Borcu azalt)
                    if self.save_to_cari(isim, f"{kalem} (Ödendi)", tutar):
                        # 2. Kasadan düş (Satislar.xlsx'e gider olarak ekle)
                        self.log_to_satislar(f"Cari Ödeme: {isim} ({kalem})", -tutar, "Nakit")
                        
                        messagebox.showinfo("Başarılı", f"Ödeme yapıldı!\n{tutar:.2f} TL tutarı kasadan düşüldü.")
                        pay_top.destroy()
                    
            except ValueError:
                messagebox.showerror("Hata", "Lütfen geçerli bir tutar giriniz!")

        tk.Button(pay_top, text="💾 İŞLEMİ ONAYLA", bg="#2c3e50", fg="white", 
                  font=("Arial", 11, "bold"), height=2, command=onayla).pack(fill=tk.X, padx=40, pady=30)
    def start_server(self):
        def run_server():
            try:
                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind(('0.0.0.0', SERVER_PORT))
                server.listen(10)
                print(f"Server Dinlemede: {get_local_ip()}:{SERVER_PORT}")
                while True:
                    client_sock, addr = server.accept()
                    threading.Thread(target=self.handle_remote_data, args=(client_sock,), daemon=True).start()
            except Exception as e:
                print(f"Server Hatası: {e}")
        t = threading.Thread(target=run_server, daemon=True)
        t.start()
    def handle_remote_data(self, client_sock):
        try:
            raw_data = client_sock.recv(4096).decode('utf-8')
            if not raw_data: return
            incoming_json = json.loads(raw_data)
            
            masa_adi = incoming_json.get("masa")
            yeni_urunler = incoming_json.get("siparisler", [])
            terminal_adi = incoming_json.get("terminal", "Bilinmeyen")
            
            if masa_adi in self.adisyonlar:
                for item in yeni_urunler:
                    siparis_obj = {"urun": item['urun'], "adet": 1, "fiyat": float(item['fiyat']), "tip": "normal"}
                    self.adisyonlar[masa_adi].append(siparis_obj)
                
                # UI Güncellemeleri
                self.root.after(0, self.update_masa_status)
                if self.current_masa == masa_adi:
                    self.root.after(0, self.update_order_display)
                
                # --- YENİ: EKRANDA BİLGİ MESAJI GÖSTER ---
                self.root.after(0, lambda: self.show_fancy_notification(terminal_adi, masa_adi))
        except Exception as e:
            print(f"Veri işleme hatası: {e}")
        finally:
            client_sock.close()
   
    def send_to_kitchen(self, masa_adi, urun_adi, adet):
        def task():
            try:                         
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.settimeout(3) # Zaman aşımını 3 saniye yapalım
                client.connect((self.kitchen_ip, self.kitchen_port))
                
            
                payload = {
                    "islem": "yeni_siparis",
                    "masa": masa_adi,
                    "urun": urun_adi,
                    "adet": adet,
                    "saat": datetime.now().strftime("%H:%M:%S"),
                    "terminal": self.terminal_id
                }
            
                client.send(json.dumps(payload).encode('utf-8'))
                client.close()
                print(f"Mutfak onayladı: {urun_adi} -> {masa_adi}")
            except Exception as e:
               print(f"Mutfak ekranına ({self.kitchen_ip}) bağlanılamadı.") 
                
        # Arayüzü kilitlememek için arka planda çalıştır
        threading.Thread(target=task, daemon=True).start()
    def get_and_inc_counter(self):
        sira = 1
        if os.path.exists(COUNTER_FILE):
            with open(COUNTER_FILE, "r") as f:
                try: sira = int(f.read().strip()) + 1
                except: sira = 1
        with open(COUNTER_FILE, "w") as f:
            f.write(str(sira))
        return sira

    def open_modal(self, title, geom):
        top = tk.Toplevel(self.root)
        top.title(title); top.geometry(geom); top.transient(self.root); top.grab_set(); top.focus_set()
        return top

    def setup_ui(self):
        if hasattr(self, 'main_pane'): self.main_pane.destroy()
        
        # Ana taşıyıcı panel
        self.main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        # --- KOŞULLU PANEL YÖNETİMİ ---
        # Masa ve Paket sayısı 0 ise sol paneli (Salon) hiç oluşturma
        if self.masa_sayisi > 0 or self.paket_sayisi > 0:
            self.left_frame = tk.Frame(self.main_pane)
            self.center_frame = self.left_frame # setup_tables_ui için referans
            self.setup_tables_ui()
            self.main_pane.add(self.left_frame, minsize=500, width=300, stretch="always")
        else:
            # Masa ve Paket yoksa bu değişkenleri None yapıyoruz ki hataları önleyelim
            self.left_frame = None
            self.center_frame = None

        # --- ÜRÜN MENÜSÜ PANELİ ---
        # Eğer salon kapalıysa bu panel merkeze yayılacak
        self.center_content = tk.Frame(self.main_pane)
        tk.Label(self.center_content, text="ÜRÜN LİSTESİ", font=("Arial", 12, "bold"), fg="#2c3e50").pack(pady=5)
        
        cont = tk.Frame(self.center_content); cont.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(cont, bg="#f5f6fa", highlightthickness=0)
        sb = ttk.Scrollbar(cont, orient="vertical", command=self.canvas.yview)
        
        self.scroll_items = tk.Frame(self.canvas, bg="#f5f6fa")
        self.scroll_items.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        # Eğer salon kapalıysa menü genişliğini artır (Daha fazla ürün yan yana)
        canvas_width = 800 if not self.left_frame else 450
        self.canvas.create_window((0, 0), window=self.scroll_items, anchor="nw", width=canvas_width)
        
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        
        self.main_pane.add(self.center_content, minsize=300, stretch="always")
        self.refresh_menu_display()

        # --- SAĞ PANEL: KASA İŞLEMLERİ ---
        self.setup_order_ui()
        self.main_pane.add(self.order_frame, width=380, minsize=380, stretch="never")
        
        self.select_masa(self.current_masa)
        self.center_content.bind("<Configure>", lambda e: self.on_resize())

    def setup_tables_ui(self):
        for w in self.center_frame.winfo_children(): w.destroy()
        self.buttons_ref = {}
        if self.paket_sayisi > 0:
            pf = tk.LabelFrame(self.center_frame, text=" 🛵 Paket Servis ", fg="#d35400", font=("Arial", 11, "bold"))
            pf.pack(fill=tk.X, padx=5, pady=5)
            for i in range(1, self.paket_sayisi + 1):
                n = f"Paket {i}"; btn = tk.Button(pf, text=n, bg="#ff9f43", fg="white", width=11, height=3 ,command=lambda m=n: self.select_masa(m))
                btn.grid(row=(i-1)//5, column=(i-1)%5, padx=3, pady=3); self.buttons_ref[n] = btn
        if self.masa_sayisi > 0:
            sf = tk.LabelFrame(self.center_frame, text=" 🪑 Salon ", fg="#2c3e50", font=("Arial", 11, "bold"))
            sf.pack(fill=tk.BOTH, expand=True, padx=5, pady=10)
            for i in range(self.masa_sayisi):
                n = f"Masa {i+1}"; btn = tk.Button(sf, text=n, bg="#1abc9c", fg="white", font=("Segoe UI", 10, "bold"), width=10, height=3, relief="flat", command=lambda m=n: self.select_masa(m))
                btn.grid(row=i//5, column=i%5, padx=3, pady=3, sticky="nsew"); self.buttons_ref[n] = btn
        if os.path.exists("logo.png"):
            self.logo_label = tk.Label(self.center_frame, bg=self.center_frame.cget("bg"))
            self.logo_label.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=10)
            self.logo_label.bind("<Configure>", self.resize_logo)          
        self.update_masa_status()

    def resize_logo(self, event):
        if not hasattr(self, 'logo_label'): return
        label_w = event.width
        label_h = event.height
        if label_w < 20 or label_h < 20: return 
        try:
            img = Image.open("logo.png")
            img_w, img_h = img.size
            ratio = min(label_w / img_w, label_h / img_h)
            new_w = int(img_w * ratio * 0.9)
            new_h = int(img_h * ratio * 0.9)
            if new_w > 0 and new_h > 0:
                resized_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                self.tk_logo = ImageTk.PhotoImage(resized_img)
                self.logo_label.config(image=self.tk_logo)
        except Exception as e:
            print(f"Logo hatası: {e}")

    def setup_order_ui(self):
        self.order_frame = tk.LabelFrame(self.main_pane, text="Kasa İşlemleri", padx=10, pady=10)
        self.order_label = tk.Label(self.order_frame, text=self.current_masa, font=("Arial", 16, "bold"), fg="#e67e22")
        self.order_label.pack()
        vp = tk.PanedWindow(self.order_frame, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=4)
        vp.pack(fill=tk.BOTH, expand=True)
        self.order_listbox = tk.Listbox(vp, font=("Courier New", 10), height=20)
        vp.add(self.order_listbox, minsize=100)
        self.order_listbox.bind("<Double-1>", self.remove_item_from_order)
        self.ctx = tk.Menu(self.root, tearoff=0)
        self.ctx.add_command(label="🎁 İkram Yap / İptal", command=self.toggle_ikram)
        self.order_listbox.bind("<Button-3>", lambda e: self.ctx.post(e.x_root, e.y_root))
        ctrl = tk.Frame(vp); vp.add(ctrl, minsize=250)
        self.total_label = tk.Label(ctrl, text="0.00 TL", font=("Arial", 26, "bold"), fg="#c0392b"); self.total_label.pack(pady=5)
        tk.Button(ctrl, text="🖨 FİŞ YAZDIR", bg="#3498db", fg="white", height=2, command=self.manual_print_fis).pack(fill=tk.X, pady=2)
        self.btn_kapat = tk.Button(ctrl, text="🔒 MASA KAPAT",anchor="center", 
                           bg="#464646", fg="white", font=("Arial", 10, "bold"), height=3)
        self.btn_kapat.pack(fill=tk.X, pady=5)
        self.btn_kapat.bind("<Button-1>", self.handle_payment_click) # Sol Tık
        self.btn_kapat.bind("<Button-3>", self.handle_payment_click) # Sağ Tık
        self.btn_kapat.bind("<Shift-Button-1>", self.handle_payment_click) # Shift + Sol Tık
        tk.Button(ctrl, text="🎁 TİP", bg="#f1c40f", font=("Arial", 9, "bold"), height=2, command=self.add_independent_tip).pack(fill=tk.X, pady=2)
        tk.Button(ctrl, text="💰 YÖNETİM", bg="#f39c12", height=2, command=self.show_cari_management).pack(fill=tk.X, pady=2)
        tk.Button(ctrl, text="📊 GÜN SONU PDF", bg="#c0392b", fg="white", height=2, command=self.generate_advanced_pdf).pack(fill=tk.X, pady=2)
        tk.Button(ctrl, text="⚙ AYARLAR", bg="#34495e", fg="white", height=2, command=self.check_admin).pack(fill=tk.X, pady=2)
        tk.Button(ctrl, text="ℹ️ HAKKINDA", bg="#95a5a6", fg="white", height=2, command=self.show_about).pack(fill=tk.X, pady=2)
        footer_frame = tk.Frame(self.order_frame, bg="#2c3e50", bd=2, relief=tk.RIDGE)
        footer_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        tk.Label(footer_frame, text=f"📡 IP: {get_local_ip()}", font=("Consolas", 12, "bold"), fg="#ecf0f1", bg="#2c3e50", padx=10, pady=5).pack(side=tk.LEFT)
        tk.Label(footer_frame, text=f"🆔 {TERMINAL_ID}", font=("Consolas", 8, "bold"), fg="#3498db", bg="#2c3e50", padx=10, pady=5).pack(side=tk.RIGHT)              
    def get_grouped_items_text(self, items):
        """Ürün listesini gruplar: '3x Köfte, 2x Ayran' formatına getirir."""
        from collections import Counter
        counts = Counter(items)
        # Örn: "3x Köfte, 2x Ayran"
        return ", ".join([f"{adet}x {isim}" for isim, adet in counts.items()])
    def save_to_cari(self, cari_isim, islem, tutar):
        try:
            tarih = datetime.now().strftime("%d.%m.%Y %H:%M")
            yeni_veri = pd.DataFrame([[tarih, islem, tutar]], columns=['Tarih', 'İşlem', 'Tutar'])
        
            if os.path.exists(CARI_FILE):
            # Dosyanın başka bir programda açık olup olmadığını kontrol et
                try:
                    with pd.ExcelWriter(CARI_FILE, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                        try:
                            df_eski = pd.read_excel(CARI_FILE, sheet_name=cari_isim)
                            df_son = pd.concat([df_eski, yeni_veri], ignore_index=True)
                            df_son.to_excel(writer, sheet_name=cari_isim, index=False)
                        except: 
                        # Sayfa yoksa sıfırdan oluştur
                            yeni_veri.to_excel(writer, sheet_name=cari_isim, index=False)
                except PermissionError:
                    messagebox.showerror("Hata", "Excel dosyası şu an başka bir programda açık! Lütfen kapatıp tekrar deneyin.")
                    return False
            else:
                yeni_veri.to_excel(CARI_FILE, sheet_name=cari_isim, index=False)
            return True
        except Exception as e:
            messagebox.showerror("Hata", f"Beklenmedik bir hata oluştu: {e}")
            return False    
    def show_cari_management(self):
        """Eski Cari Yönetimi yerine Profesyonel Finans ve Stok Paneli."""
        top = self.open_modal("İşletme Yönetim Paneli (Finans & Stok)", "900x700")
        notebook = ttk.Notebook(top)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- SEKME 1: MÜŞTERİ CARİLERİ ---
        cari_tab = tk.Frame(notebook, bg="#f5f6fa")
        notebook.add(cari_tab, text=" 👥 Müşteri Carileri ")
        
        lb_frame = tk.Frame(cari_tab, bg="#f5f6fa")
        lb_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        lb = tk.Listbox(lb_frame, font=("Arial", 11)); lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(lb_frame, orient="vertical", command=lb.yview); sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb.config(yscrollcommand=sb.set)

        def refresh_list():
            lb.delete(0, tk.END)
            if os.path.exists(CARI_FILE):
                try:
                    xls = pd.ExcelFile(CARI_FILE)
                    for name in xls.sheet_names: lb.insert(tk.END, name)
                except: pass

        refresh_list()

        # Butonlar (Cari İşlemleri)
        btn_f = tk.Frame(cari_tab, bg="#f5f6fa")
        btn_f.pack(fill=tk.X, padx=10, pady=5)

        # 1. BAKİYE BUTONU
        def bakiye_araci():
            sel = lb.curselection()
            if sel:
                isim = lb.get(sel[0])
                df = pd.read_excel(CARI_FILE, sheet_name=isim)
                toplam = df['Tutar'].sum()
                messagebox.showinfo(isim, f"Güncel Bakiye: {toplam:.2f} TL", parent=top)

        tk.Button(btn_f, text="🔍 BAKİYE", bg="#3498db", fg="white", width=12, 
                  command=bakiye_araci).grid(row=0, column=0, padx=2)

        # 2. TAHSİLAT BUTONU
        def tahsilat_araci():
            sel = lb.curselection()
            if sel:
                isim = lb.get(sel[0])
                miktar = simpledialog.askfloat("Tahsilat", "Alınan Nakit Tutarı:", parent=top)
                if miktar:
                    if self.save_to_cari(isim, "Tahsilat (Nakit)", -miktar):
                        self.log_to_satislar(f"Cari Tahsilat: {isim}", miktar)
                        messagebox.showinfo("Başarılı", "Tahsilat kaydedildi ve kasaya işlendi.")
                        # Dashboard'u güncellemek için dashboard sekmesini render etmeyi düşünebilirsin

        tk.Button(btn_f, text="💸 TAHSİLAT", bg="#27ae60", fg="white", width=12, 
                  command=tahsilat_araci).grid(row=0, column=1, padx=2)

        # 3. ÖDE/BORÇ BUTONU
        def odeme_araci():
            sel = lb.curselection()
            if sel:
                self.cari_odeme_yap(top, lb.get(sel[0]))

        tk.Button(btn_f, text="💳 ÖDE/BORÇ", bg="#e67e22", fg="white", width=12, 
                  command=odeme_araci).grid(row=0, column=2, padx=2)

        # 4. YENİ CARİ BUTONU
        def yeni_cari_araci():
            isim = simpledialog.askstring("Yeni Cari", "Müşteri Adı / Ünvan:", parent=top)
            if isim:
                self.save_to_cari(isim, "Hesap Açılışı", 0)
                refresh_list()

        tk.Button(btn_f, text="➕ YENİ CARİ", bg="#9b59b6", fg="white", width=12, 
                  command=yeni_cari_araci).grid(row=0, column=3, padx=2)
        # --- SEKME 2: STOK VE ENVANTER ---
        stock_tab = tk.Frame(notebook, bg="#f5f6fa")
        notebook.add(stock_tab, text=" 📦 Stok / Envanter ")
        
        # Stok Listesi (Treeview)
        cols = ("Malzeme", "Miktar", "Birim", "Maliyet", "Durum")
        stree = ttk.Treeview(stock_tab, columns=cols, show="headings", height=15)
        for col in cols: stree.heading(col, text=col); stree.column(col, width=100, anchor="center")
        stree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def refresh_stock():
            for i in stree.get_children(): stree.delete(i)
            STOK_FILE = os.path.join(BASE_DIR, "stoklar.xlsx")
            if os.path.exists(STOK_FILE):
                df = pd.read_excel(STOK_FILE)
                for _, r in df.iterrows():
                    durum = "OK" if r['Miktar'] > r.get('Kritik_Seviye', 5) else "⚠️ KRİTİK"
                    stree.insert("", tk.END, values=(r['Malzeme'], f"{r['Miktar']:.2f}", r['Birim'], f"{r['Alis_Fiyati']:.2f}", durum))

        refresh_stock()
        tk.Button(stock_tab, text="➕ YENİ STOK / MAL ALIMI", bg="#27ae60", fg="white", height=2, 
                  command=lambda: [self.open_stock_entry(), refresh_stock()]).pack(fill=tk.X, padx=10, pady=5)

        # --- SEKME 3: GELİR-GİDER (DASHBOARD) ---
        report_tab = tk.Frame(notebook, bg="#ffffff")
        notebook.add(report_tab, text=" 📊 Finansal Durum Tablosu ")
        self.render_dashboard(report_tab)

    def render_dashboard(self, parent):
        """Finansal özet grafiksel olmayan dashboard."""
        try:
            df = pd.read_excel(SATIS_FILE) if os.path.exists(SATIS_FILE) else pd.DataFrame()
            if df.empty: 
                tk.Label(parent, text="Henüz veri bulunmuyor.", font=("Arial", 12)).pack(pady=50)
                return

            ciro = df[df['tip'] == 'normal']['fiyat'].sum()
            gider = abs(df[df['tip'] == 'cari_odeme']['fiyat'].sum())
            tahsilat = df[df['tip'] == 'cari_tahsilat']['fiyat'].sum()
            net_nakit = (ciro - gider) + tahsilat # Basit kasa hesabı

            # Kart Tasarımı
            f_cards = tk.Frame(parent, bg="#ffffff"); f_cards.pack(pady=20)
            
            def create_card(p, title, val, color):
                f = tk.Frame(p, bg=color, width=200, height=100, padx=10, pady=10)
                f.pack(side=tk.LEFT, padx=10)
                tk.Label(f, text=title, bg=color, fg="white", font=("Arial", 10, "bold")).pack()
                tk.Label(f, text=f"{val:.2f} TL", bg=color, fg="white", font=("Arial", 16, "bold")).pack(pady=5)

            create_card(f_cards, "TOPLAM SATIŞ", ciro, "#3498db")
            create_card(f_cards, "TOPLAM GİDER", gider, "#e74c3c")
            create_card(f_cards, "KASA DURUMU", net_nakit, "#2ecc71")
            
            # Alt Liste: Son İşlemler
            tk.Label(parent, text="Son Finansal Hareketler", font=("Arial", 12, "bold")).pack(pady=10)
            cols = ("Tarih", "İşlem", "Tutar")
            tree = ttk.Treeview(parent, columns=cols, show="headings", height=10)
            for col in cols: tree.heading(col, text=col); tree.column(col, width=150)
            tree.pack(padx=20, pady=5)
            
            for _, r in df.tail(10).iterrows():
                tree.insert("", 0, values=(r['Tarih_Saat'], r['urun'], f"{r['fiyat']:.2f}"))
        except Exception as e:
            tk.Label(parent, text=f"Dashboard hatası: {e}").pack()
    def open_cari_selector(self):
        order = self.adisyonlar.get(self.current_masa, [])
        if not order: return
        top = self.open_modal("Cari Seç", "300x500")
        lb = tk.Listbox(top); lb.pack(fill=tk.BOTH, expand=True, padx=10)
        if os.path.exists(CARI_FILE):
            try:
                xls = pd.ExcelFile(CARI_FILE)
                for name in xls.sheet_names: lb.insert(tk.END, name)
            except: pass
        def aktar():
            sel = lb.curselection()
            if not sel: return
            secilen_cari = lb.get(sel[0])
            urun_listesi = [i['urun'] for i in order]
            urun_detayli_metin = self.get_grouped_items_text(urun_listesi)
            toplam = sum(i['adet'] * i['fiyat'] for i in order)
            if self.save_to_cari(secilen_cari, f"{urun_detayli_metin}", toplam): 
                self.finalize_payment("Açık Hesap")
                top.destroy()
        tk.Button(top, text="BORCU AKTAR", bg="#8e44ad", fg="white", command=aktar).pack(fill=tk.X, padx=10, pady=10)

    def select_masa(self, n):
        if n in self.adisyonlar:
            self.current_masa = n; self.order_label.config(text=n); self.update_order_display()

    def update_order_display(self):
        self.order_listbox.delete(0, tk.END); tot = 0
        for i in self.adisyonlar.get(self.current_masa, []):
            ik = " (IK)" if i.get("tip")=="ikram" else ""
            self.order_listbox.insert(tk.END, f"{i['adet']}x {i['urun']+ik:<15} {i['adet']*i['fiyat']:>7.2f}")
            tot += i['adet']*i['fiyat']
        self.total_label.config(text=f"{tot:.2f} TL")

    def update_masa_status(self):
        if not self.buttons_ref: return
        for n, btn in self.buttons_ref.items():
            if n in self.adisyonlar:
                b = sum(i['adet']*i['fiyat'] for i in self.adisyonlar[n])
                btn.config(bg="#e74c3c" if b > 0 else "#1abc9c", text=f"{n}\n{b:.2f} TL" if b > 0 else n)

    def add_item(self, n, p):
        self.adisyonlar[self.current_masa].append({"urun": n, "adet": 1, "fiyat": p, "tip": "normal"})
        self.update_order_display(); self.update_masa_status()
        if self.mutfak_varmi:
            self.send_to_kitchen(self.current_masa, n, 1)
    def handle_payment_click(self, event):
        # Hangi tuşa basıldığını kontrol et
        # event.num == 1 -> Sol Tık
        # event.num == 3 -> Sağ Tık (Windows/Linux)
        # event.state & 0x0001 -> Shift tuşu basılı mı?
    
        is_shift = event.state & 0x0001
    
        if is_shift and event.num == 1:
            # SHIFT + SOL TIK -> CARI / HESAP
            self.open_cari_selector()
        
        elif event.num == 3:
        # SAĞ TIK -> NAKİT
            self.finalize_payment("Nakit")
        
        elif event.num == 1:
        # SADECE SOL TIK -> KREDİ KARTI
            self.finalize_payment("Kredi Kartı")


    def finalize_payment(self, pt):
        order = self.adisyonlar.get(self.current_masa, [])
        if not order: return
        yazdirilsin_mi = False
        if pt == "Nakit" and self.print_nakit: yazdirilsin_mi = True
        elif pt == "Kredi Kartı" and self.print_kart: yazdirilsin_mi = True
        elif pt == "Açık Hesap" and self.print_cari: yazdirilsin_mi = True

        if yazdirilsin_mi:
            self.manual_print_fis()
        df_list = [{"urun":i['urun'], "adet":i['adet'], "fiyat":i['fiyat'], "odeme":pt, 
                    "tip":i.get("tip","normal"), "Tarih_Saat":datetime.now().strftime("%d-%m-%Y %H:%M:%S")} 
                   for i in order]
        
        if self.save_sale_to_excel(df_list):
            self.adisyonlar[self.current_masa] = []
            self.update_order_display()
            self.update_masa_status()    
        
    def save_sale_to_excel(self, data):
        try:
            df = pd.DataFrame(data); old = pd.read_excel(SATIS_FILE) if os.path.exists(SATIS_FILE) else pd.DataFrame()
            pd.concat([old, df]).to_excel(SATIS_FILE, index=False); return True
        except: return False
    def manual_print_fis(self):
        order = [i for i in self.adisyonlar.get(self.current_masa, []) if i.get('tip') != 'tip']
        if not order: return
        
        # AYARLARI DIŞARIDAN AL
        f_set = self.load_fis_settings()
        C_WIDTH = int(f_set["genislik"])
        SEPARATOR = f_set["ayrac_karakter"] * C_WIDTH
        
        sira = self.get_and_inc_counter()
        now = datetime.now().strftime("%d-%m-%Y   %H:%M")
        fn = os.path.join(FIS_KLASORU, f"Fis_{sira}.txt")
        total = sum(i['adet'] * i['fiyat'] for i in order)

        with open(fn, "w", encoding="utf-8") as f:
            # Başlık Boşluğu
            f.write("\n" * int(f_set["baslik_bosluk"]))
            
            # Başlık ve Masa Bilgisi
            f.write(f"{self.company_name[:C_WIDTH]:^{C_WIDTH}}\n")
            f.write(f"{'SIPARIS FISI':^{C_WIDTH}}\n")
            f.write(f"{SEPARATOR}\n")
            f.write(f"{now}\n")
            f.write(f"{self.current_masa[:10]:<10}   No:{sira:>3}\n")
            f.write(f"{'-'*C_WIDTH}\n")
            
            # Ürünler (Hizalamayı genişliğe göre ayarlar)
            f.write(f"{'Ad':<2} {'Urun':<{C_WIDTH-8}} {'Tut':>5}\n")
            f.write(f"{'-'*C_WIDTH}\n")
            
            for i in order:
                ik = "*" if i.get("tip") == "ikram" else ""
                urun_adi = (i['urun'][:C_WIDTH-11] + ik) # Dinamik genişlik koruması
                f.write(f"{i['adet']:<2} {urun_adi:<{C_WIDTH-9}} {i['adet']*i['fiyat']:>5.0f}\n")
            
            # Alt Toplam ve Kapanış
            f.write(f"{SEPARATOR}\n")
            f.write(f"{'TOPLAM:':<{C_WIDTH-9}}{total:>9.0f}\n")
            f.write(f"{SEPARATOR}\n")
            f.write(f"{f_set['alt_mesaj']:^{C_WIDTH}}\n")
            
            # Kesme Boşluğu (Rulonun yırtılma payı)
            f.write("\n" * int(f_set["alt_bosluk_satir"]))

        # Yazdırma tetikleme kodun aynı kalacak...
        full_path = os.path.abspath(fn)
        if self.direct_print:
            try: subprocess.run(['notepad.exe', '/p', full_path], check=True)
            except: os.startfile(full_path)
        else:
            os.startfile(full_path) 
    def generate_advanced_pdf(self):
        if not PDF_SUPPORT or not os.path.exists(SATIS_FILE):
            messagebox.showwarning("Uyarı", "PDF desteği kurulu değil veya satış kaydı bulunamadı.")
            return
        try:
            df = pd.read_excel(SATIS_FILE)
            today = datetime.now().strftime("%d-%m-%Y")
            tdf = df[df['Tarih_Saat'].astype(str).str.startswith(today)].copy()
            
            if tdf.empty:
                messagebox.showinfo("Bilgi", "Bugün için herhangi bir kasa hareketi bulunmuyor.")
                return

            fn = f"Detayli_Gun_Sonu_{today}.pdf"
            doc = SimpleDocTemplate(fn, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            for s in styles.byName.values():
                if hasattr(s, 'fontName'): s.fontName = PDF_FONT
            
            elements.append(Paragraph(f"<b>{self.company_name}</b>", styles['Title']))
            elements.append(Paragraph(f"Gün Sonu Detaylı Finansal Rapor - {today}", styles['Heading2']))
            elements.append(Spacer(1, 0.2 * inch))

            # --- VERİ GRUPLAMA (Hata buradaydı, ikramlar eklendi) ---
            satislar = tdf[tdf['tip'] == 'normal']
            ikramlar = tdf[tdf['tip'] == 'ikram'] # <--- EKLENEN SATIR
            bahsisler = tdf[tdf['tip'] == 'tip']
            c_tahsilat = tdf[tdf['tip'] == 'cari_tahsilat']
            c_odeme = tdf[tdf['tip'] == 'cari_odeme']

            # --- HESAPLAMALAR ---
            toplam_ciro = satislar['fiyat'].sum()
            nakit_satis = satislar[satislar['odeme'] == 'Nakit']['fiyat'].sum()
            kart_satis = satislar[satislar['odeme'] == 'Kredi Kartı']['fiyat'].sum()
            acik_hesap_satis = satislar[satislar['odeme'] == 'Açık Hesap']['fiyat'].sum()
            
            top_bahsis = bahsisler['fiyat'].sum()
            top_c_tahsilat = c_tahsilat['fiyat'].sum()
            top_c_odeme = abs(c_odeme['fiyat'].sum())

            fiili_giris = nakit_satis + top_bahsis + top_c_tahsilat
            net_kasa = fiili_giris - top_c_odeme

            # --- 1. GENEL KASA ÖZETİ TABLOSU ---
            summary_data = [
                ["AÇIKLAMA", "TUTAR"],
                ["TOPLAM CİRO (Genel Satış)", f"{toplam_ciro:.2f} TL"],
                ["Nakit Satışlar", f"{nakit_satis:.2f} TL"],
                ["Kredi Kartı Satışları", f"{kart_satis:.2f} TL"],
                ["Açık Hesap (Cari) Satışlar", f"{acik_hesap_satis:.2f} TL"],
                ["Bahşişler (Nakit Giriş)", f"{top_bahsis:.2f} TL"],
                ["Cari Tahsilatlar (Nakit Giriş)", f"{top_c_tahsilat:.2f} TL"],
                ["Cari Ödemeler / Giderler (Nakit Çıkış)", f"-{top_c_odeme:.2f} TL"],
                ["FİİLİ KASA GİRİŞİ (Toplam Giren)", f"{fiili_giris:.2f} TL"],
                ["NET KASA (Eldeki Nakit)", f"{net_kasa:.2f} TL"]
            ]

            ts = Table(summary_data, colWidths=[3.5*inch, 1.5*inch])
            ts.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), PDF_FONT),
                ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('ALIGN', (1,0), (1,-1), 'RIGHT'),
                ('BACKGROUND', (0,-1), (-1,-1), colors.lightgreen),
                ('FONTSIZE', (0, -1), (-1, -1), 12),
                ('FONTSIZE', (0, 1), (-1, 1), 12),
                ('TEXTCOLOR', (0, 1), (-1, 1), colors.darkblue),
            ]))
            elements.append(ts)
            elements.append(Spacer(1, 0.3 * inch))

            # --- 2. SATILAN ÜRÜN DETAYLARI ---
            elements.append(Paragraph("<b>2. Satılan Ürün Detayları</b>", styles['Normal']))
            u_data = [["Ürün Adı", "Adet", "Toplam"]]
            u_grubu = satislar.groupby('urun').agg({'adet':'sum', 'fiyat':'sum'}).reset_index()
            for _, r in u_grubu.iterrows():
                u_data.append([str(r['urun']), str(int(r['adet'])), f"{r['fiyat']:.2f} TL"])
            
            ut = Table(u_data, colWidths=[3*inch, 0.8*inch, 1.2*inch])
            ut.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), PDF_FONT), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('ALIGN', (1,0), (2,-1), 'CENTER')]))
            elements.append(ut)
            elements.append(Spacer(1, 0.3 * inch))

            # --- 3. İKRAMLAR (Hata veren kısım burasıydı) ---
            if not ikramlar.empty:
                elements.append(Paragraph("<b>3. İkram Edilen Ürünler</b>", styles['Normal']))
                i_data = [["İkram Edilen Ürün", "Adet"]]
                i_grubu = ikramlar.groupby('urun')['adet'].sum().reset_index()
                for _, r in i_grubu.iterrows():
                    i_data.append([str(r['urun']), str(int(r['adet']))])
                it = Table(i_data, colWidths=[3.8*inch, 1.2*inch])
                it.setStyle(TableStyle([
                    ('FONTNAME', (0,0), (-1,-1), PDF_FONT),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.darkred),
                    ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
                    ('TEXTCOLOR', (0,1), (0,-1), colors.darkred)
                ]))
                elements.append(it)
                elements.append(Spacer(1, 0.3 * inch))

            # --- 4. CARİ HAREKETLER ---
            c_hareket = tdf[tdf['tip'].isin(['cari_tahsilat', 'cari_odeme'])]
            if not c_hareket.empty:
                elements.append(Paragraph("<b>4. Cari Tahsilat ve Ödeme Detayları</b>", styles['Normal']))
                ch_data = [["Açıklama / Cari", "İşlem Türü", "Tutar"]]
                for _, r in c_hareket.iterrows():
                    tur = "Tahsilat (+)" if r['tip'] == "cari_tahsilat" else "Ödeme (-)"
                    ch_data.append([str(r['urun']), tur, f"{abs(r['fiyat']):.2f} TL"])
                cht = Table(ch_data, colWidths=[3*inch, 1*inch, 1*inch])
                cht.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), PDF_FONT), ('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
                elements.append(cht)

            doc.build(elements)
            os.startfile(os.path.abspath(fn))
        except Exception as e: 
            messagebox.showerror("Hata", f"PDF Hatası: {e}")
    
    def open_settings(self):
        # 1. Ekran Boyutuna Göre Dinamik Pencere Hesaplama
        ekran_genislik = self.root.winfo_screenwidth()
        ekran_yukseklik = self.root.winfo_screenheight()
        pencere_genislik = int(ekran_genislik * 0.45)
        pencere_yukseklik = int(ekran_yukseklik * 0.90)
        x_koordinat = (ekran_genislik // 2) - (pencere_genislik // 2)
        y_koordinat = (ekran_yukseklik // 2) - (pencere_yukseklik // 2)

        sw = self.open_modal("Sistem Ayarları & Menü Yönetimi", f"{pencere_genislik}x{pencere_yukseklik}+{x_koordinat}+{y_koordinat}")

        # 2. Scrollbar (Kaydırma Çubuğu) Mekanizması Oluşturma
        canvas = tk.Canvas(sw, highlightthickness=0)
        scrollbar = ttk.Scrollbar(sw, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=pencere_genislik-25)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- İÇERİK: ÜST PANEL (Genel ve Bağlantı Ayarları Yan Yana) ---
        top_settings_frame = tk.Frame(scrollable_frame)
        top_settings_frame.pack(fill=tk.X, padx=20, pady=5)

        # 1. GENEL AYARLAR
        genel_frame = tk.LabelFrame(top_settings_frame, text=" Genel Ayarlar ", padx=10, pady=10)
        genel_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        top_settings_frame.grid_columnconfigure(0, weight=1)

        tk.Label(genel_frame, text="Firma:").grid(row=0, column=0, sticky="w")
        e_f = tk.Entry(genel_frame, width=35); e_f.insert(0, self.company_name); e_f.grid(row=0, column=1,columnspan=3, padx=5, sticky="w")
        
        tk.Label(genel_frame, text="Masa:").grid(row=1, column=0, sticky="w")
        e_m = tk.Entry(genel_frame, width=8); e_m.insert(0, str(self.masa_sayisi)); e_m.grid(row=1, column=1, sticky="w", pady=2, padx=5)
        
        tk.Label(genel_frame, text="Paket:").grid(row=1, column=2, sticky="w")
        e_p = tk.Entry(genel_frame, width=8); e_p.insert(0, str(self.paket_sayisi)); e_p.grid(row=1, column=3, sticky="w", pady=2, padx=5)

        tk.Label(genel_frame, text="Term. ID:").grid(row=2, column=0, sticky="w")
        e_t = tk.Entry(genel_frame, width=5); e_t.insert(0, self.terminal_id); e_t.grid(row=2, column=1, sticky="w", pady=5, padx=5)
 
        # 2. BAĞLANTI AYARLARI
        net_frame = tk.LabelFrame(top_settings_frame, text=" Bağlantı Ayarları ", padx=10, pady=10)
        net_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        top_settings_frame.grid_columnconfigure(1, weight=1)

        tk.Label(net_frame, text="Mutfak IP:").grid(row=0, column=0, sticky="w")
        e_kip = tk.Entry(net_frame, width=15); e_kip.insert(0, self.kitchen_ip); e_kip.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        tk.Label(net_frame, text="Port:").grid(row=1, column=0, sticky="w")
        e_kport = tk.Entry(net_frame, width=10); e_kport.insert(0, str(self.kitchen_port)); e_kport.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        self.var_mutfak_aktif = tk.BooleanVar(value=self.mutfak_varmi)
        chk_mutfak = tk.Checkbutton(net_frame, text="Mutfak Aktif", variable=self.var_mutfak_aktif)
        chk_mutfak.grid(row=2, column=0, columnspan=2, sticky="w", pady=5)

             # --- 3. FİŞ AYARLARI ---
        yazdir_frame = tk.LabelFrame(scrollable_frame, text=" Direkt Yazdırma Ayarları ", padx=10, pady=10)
        yazdir_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.var_direct_print = tk.BooleanVar(value=self.direct_print)
        tk.Checkbutton(yazdir_frame, text=" Fişler", variable=self.var_direct_print).grid(row=0, column=0, sticky="w")
        
        self.var_print_nakit = tk.BooleanVar(value=self.print_nakit)
        tk.Checkbutton(yazdir_frame, text="Nakit", variable=self.var_print_nakit).grid(row=0, column=1, padx=10)

        self.var_print_kart = tk.BooleanVar(value=self.print_kart)
        tk.Checkbutton(yazdir_frame, text="Kart ", variable=self.var_print_kart).grid(row=0, column=2, padx=10)

        self.var_print_cari = tk.BooleanVar(value=self.print_cari)
        tk.Checkbutton(yazdir_frame, text="Hesap ", variable=self.var_print_cari).grid(row=0, column=3, padx=10)

        # --- 4. CARİ KALEMLER ---
       # --- CARİ VE ŞİFRE AYARLARI TAŞIYICI (YAN YANA) ---
        cari_sifre_container = tk.Frame(scrollable_frame)
        cari_sifre_container.pack(fill=tk.X, padx=20, pady=5)

        # --- 4. CARİ İŞLEM KALEMLERİ (SOL) ---
        kalem_frame = tk.LabelFrame(cari_sifre_container, text=" Cari İşlem Kalemleri Yönetimi ", padx=10, pady=10)
        kalem_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        cari_sifre_container.grid_columnconfigure(0, weight=3) # Cari kısmı daha geniş olsun

        tk.Label(kalem_frame, text="Kalem Adı:").grid(row=0, column=0, sticky="w")
        e_yeni_kalem = tk.Entry(kalem_frame, width=25)
        e_yeni_kalem.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        list_frame = tk.Frame(kalem_frame)
        list_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        kalem_listbox = tk.Listbox(list_frame, height=4, font=("Arial", 10))
        kalem_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        mevcut_kalemler = self.load_islem_kalemleri()
        for k in mevcut_kalemler: kalem_listbox.insert(tk.END, k)

        def kalem_ekle():
            k = e_yeni_kalem.get().strip()
            if k and k not in kalem_listbox.get(0, tk.END):
                kalem_listbox.insert(tk.END, k)
                e_yeni_kalem.delete(0, tk.END)

        def kalem_sil():
            sel = kalem_listbox.curselection()
            if sel: kalem_listbox.delete(sel)

        btn_f_kalem = tk.Frame(kalem_frame)
        btn_f_kalem.grid(row=1, column=2, padx=10)
        tk.Button(btn_f_kalem, text="➕ EKLE", bg="#2ecc71", width=8, command=kalem_ekle).pack(pady=2)
        tk.Button(btn_f_kalem, text="🗑️ SİL", bg="#e74c3c", fg="white", width=8, command=kalem_sil).pack(pady=2)

        # --- 5. ŞİFRE DEĞİŞTİRME (SAĞ) ---
        sifre_frame = tk.LabelFrame(cari_sifre_container, text=" Güvenlik Ayarları ", padx=10, pady=10)
        sifre_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        cari_sifre_container.grid_columnconfigure(1, weight=1)

        tk.Label(sifre_frame, text="Yönetici Şifresi", font=("Arial", 9, "bold")).pack(pady=(5, 0))
        tk.Label(sifre_frame, text="Ayarlar ve kritik işlemler\niçin kullanılır.", font=("Arial", 8), fg="gray").pack(pady=5)
        
        tk.Button(sifre_frame, text="🔑 ŞİFREYİ DEĞİŞTİR", bg="#7f8c8d", fg="white", 
                  height=2, command=self.change_password).pack(fill=tk.X, pady=10, padx=10)         # --- 5. MENÜ LİSTESİ ---
        menu_frame = tk.LabelFrame(scrollable_frame, text=" Menü Listesi ", padx=10, pady=10)
        menu_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        cols = ("Kategori", "Ürün Adı", "Fiyat")
        tree = ttk.Treeview(menu_frame, columns=cols, show="headings", height=10)
        for col in cols: tree.heading(col, text=col); tree.column(col, width=150)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        for cat, items in self.menu_data.items():
            for it, pr in items: tree.insert("", tk.END, values=(cat, it, f"{pr:.2f}"))

        islem_frame = tk.Frame(scrollable_frame)
        islem_frame.pack(fill=tk.X, padx=20, pady=5)
        e_cat = tk.Entry(islem_frame, width=15); e_cat.grid(row=0, column=0, padx=2)
        e_urun = tk.Entry(islem_frame, width=20); e_urun.grid(row=0, column=1, padx=2)
        e_fiyat = tk.Entry(islem_frame, width=10); e_fiyat.grid(row=0, column=2, padx=2)

        def tası(yon):
            sel = tree.selection()
            if sel:
                for item in sel:
                    idx = tree.index(item)
                    tree.move(item, tree.parent(item), idx + yon)

        def on_tree_select(event):
            sel = tree.selection()
            if sel:
                v = tree.item(sel[0])["values"]
                e_cat.delete(0, tk.END); e_cat.insert(0, v[0])
                e_urun.delete(0, tk.END); e_urun.insert(0, v[1])
                e_fiyat.delete(0, tk.END); e_fiyat.insert(0, v[2])

        tree.bind("<<TreeviewSelect>>", on_tree_select)

        def ekle():
            try:
                p = float(e_fiyat.get().replace(",", "."))
                tree.insert("", tk.END, values=(e_cat.get(), e_urun.get(), f"{p:.2f}"))
            except: messagebox.showwarning("Hata", "Fiyat geçersiz!")

        def guncelle():
            sel = tree.selection()
            if sel:
                try:
                    p = float(e_fiyat.get().replace(",", "."))
                    tree.item(sel[0], values=(e_cat.get(), e_urun.get(), f"{p:.2f}"))
                except: pass

        tk.Button(islem_frame, text="➕ EKLE", bg="#2ecc71", width=8, command=ekle).grid(row=0, column=3, padx=2)
        tk.Button(islem_frame, text="🔄 GÜN.", bg="#3498db", fg="white", width=8, command=guncelle).grid(row=0, column=4, padx=2)
        tk.Button(islem_frame, text="🗑️ SİL", bg="#e74c3c", fg="white", width=8, command=lambda: tree.delete(tree.selection())).grid(row=0, column=5, padx=2)
        tk.Button(islem_frame, text="▲", width=4, command=lambda: tası(-1)).grid(row=0, column=6)
        tk.Button(islem_frame, text="▼", width=4, command=lambda: tası(1)).grid(row=0, column=7)

        # --- 6. KAYDET BUTONU ---
        def final_save():
            try:
                with open(MENU_FILE, "w", encoding="utf-8") as f:
                    for item_id in tree.get_children():
                        v = tree.item(item_id)["values"]
                        f.write(f"{v[0]};{v[1]};{v[2]}\n")
                
                with open(KALEMLER_FILE, "w", encoding="utf-8") as f:
                    f.write("\n".join(kalem_listbox.get(0, tk.END)))

                self.company_name = e_f.get()
                self.masa_sayisi = int(e_m.get())
                self.paket_sayisi = int(e_p.get())
                self.terminal_id = e_t.get()
                self.kitchen_ip = e_kip.get()
                self.kitchen_port = int(e_kport.get())
                self.direct_print = self.var_direct_print.get()
                self.print_nakit = self.var_print_nakit.get()
                self.print_kart = self.var_print_kart.get()
                self.print_cari = self.var_print_cari.get()
                self.mutfak_varmi = self.var_mutfak_aktif.get()
                self.save_all_configs()
                self.menu_data = self.load_menu_data()
                self.refresh_adisyonlar()
                self.setup_ui()
                messagebox.showinfo("Başarılı", "Ayarlar kaydedildi.")
                sw.destroy()
            except Exception as e:
                messagebox.showerror("Hata", f"Değerleri kontrol edin: {e}")

        tk.Button(scrollable_frame, text="💾 TÜMÜNÜ KAYDET", bg="#2c3e50", fg="white", height=2, font=("Arial", 12, "bold"), command=final_save).pack(fill=tk.X, padx=20, pady=20)
        
    def toggle_ikram(self):
        sel = self.order_listbox.curselection()
        if not sel: return
        item = self.adisyonlar[self.current_masa][sel[0]]
        if item.get("tip") == "ikram":
            item["tip"] = "normal"; item["fiyat"] = item.get("old_pr", 0)
        else:
            item["tip"] = "ikram"; item["old_pr"] = item["fiyat"]; item["fiyat"] = 0.0
        self.update_order_display(); self.update_masa_status()

    def remove_item_from_order(self, e):
        sel = self.order_listbox.curselection()
        if sel: self.adisyonlar[self.current_masa].pop(sel[0]); self.update_order_display(); self.update_masa_status()

    def add_independent_tip(self):
        v = simpledialog.askfloat("Tip", "Tutar:")
        if v: self.save_sale_to_excel([{"urun":"TİP","adet":1,"fiyat":v,"odeme":"Nakit","tip":"tip","Tarih_Saat":datetime.now().strftime("%d-%m-%Y %H:%M:%S")}])

    def check_admin(self):
        input_pass = simpledialog.askstring("Giriş", "Şifre:", show="*")
        if input_pass == self.admin_password:
            self.open_settings()
        else:
            messagebox.showerror("Hata", "Hatalı şifre!")
    

    def on_resize(self):
        if self._after_id: self.root.after_cancel(self._after_id)
        self._after_id = self.root.after(200, self.refresh_menu_display)

    def refresh_menu_display(self):
        self._after_id = None
        current_width = self.canvas.winfo_width()
        if current_width < 100: current_width = 380
        if abs(current_width - self.last_width) < 10: return
        self.last_width = current_width
        tags = self.canvas.find_withtag("all")
        if tags: self.canvas.itemconfig(tags[0], width=current_width)
        for w in self.scroll_items.winfo_children(): w.destroy()
        btn_px_width = 100
        num_cols = max(1, current_width // btn_px_width)
        ANA_MAVI = "#3498db"; BASILI_KIRMIZI = "#ff4d4d"
        for idx, (cat, items) in enumerate(self.menu_data.items()):
            cat_header_color = self.cat_colors[idx % len(self.cat_colors)]
            tk.Label(self.scroll_items, text=f" {cat.upper()} ", bg=cat_header_color, fg="white", font=("Arial", 10, "bold")).pack(fill=tk.X, pady=(10,2))
            f = tk.Frame(self.scroll_items, bg="#f5f6fa"); f.pack(fill=tk.X, padx=5, anchor="w")
            for i, (it, pr) in enumerate(items):
                btn = tk.Button(f, text=f"{it}\n{pr:.2f} TL", width=12, bg=ANA_MAVI, fg="white", activebackground=BASILI_KIRMIZI, font=("Segoe UI", 9, "bold"), relief="flat", command=lambda n=it, p=pr: self.add_item(n, p))
                btn.grid(row=i // num_cols, column=i % num_cols, padx=3, pady=3, sticky="nw")

    def show_about(self):
        disclaimer_text = (
            f"{self.company_name}\nSipariş & Kasa Terminali v2.0\n"
            "⚠️ ÖNEMLİ YASAL UYARI:\n1- Bu yazılım EĞİTİM AMAÇLI geliştirilmiştir.\n"
            "2- Yazılımcının mali, ticari sorumluluğu yoktur.\n"
            "3- Tüm sorumluluk KULLANICIYA aittir.\n4- Ticari bir garanti verilmez.\n5- Para ile satılmaz."
        )
        messagebox.showinfo("Hakkında / Sorumluluk Reddi", disclaimer_text)

if __name__ == "__main__":
    root = tk.Tk()
    app = RestaurantApp(root)
    root.mainloop()
