import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import os
import pandas as pd
from datetime import datetime
import threading
import socket
import json

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

# --- GLOBAL SİSTEM AYARLARI ---
TERMINAL_ID = " Ana Sunucu"
MENU_FILE = "menu.txt"
CARI_FILE = "cari_kayitlar.xlsx"
SATIS_FILE = "satislar.xlsx"
CONFIG_FILE = "config.txt"
FIS_KLASORU = "Fisler"
COUNTER_FILE = "sira_no.txt"
SERVER_PORT = 5555

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
        
        self.load_all_configs() # Ayarları buradan yükler
        self.root.title(f"{self.company_name} - Sipariş & Kasa PRO")
        self.load_window_geometry() 
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.cat_colors = ["#3498db", "#e67e22", "#2ecc71", "#9b59b6", "#f1c40f", "#1abc9c", "#e74c3c", "#34495e"]
        
        self.buttons_ref = {}
        self.refresh_adisyonlar()
        self.menu_data = self.load_menu_data()
        
        self.update_current_masa_selection()
        self.setup_ui()
        self.start_server()

    def on_closing(self):
        try:
            self.save_window_geometry()
            self.root.quit()
            self.root.destroy()
        except:
            self.root.destroy()   

    def load_all_configs(self):
        """config.txt dosyasından tüm sistem parametrelerini yükler."""
        defaults = {
            "password": "1234", 
            "direct_print": "HAYIR",
            "masa_sayisi": "30",
            "paket_sayisi": "5",
            "firma_ismi": "RESTORAN OTOMASYON",
            "terminal_id": "1"
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

    def save_all_configs(self):
        """Tüm ayarları tek seferde config.txt dosyasına kaydeder."""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(f"password:{self.admin_password}\n")
                f.write(f"direct_print:{'EVET' if self.direct_print else 'HAYIR'}\n")
                f.write(f"masa_sayisi:{self.masa_sayisi}\n")
                f.write(f"paket_sayisi:{self.paket_sayisi}\n")
                f.write(f"firma_ismi:{self.company_name}\n")
                f.write(f"terminal_id:{self.terminal_id}\n")
        except Exception as e:
            print(f"Konfigürasyon yazma hatası: {e}")

    def save_window_geometry(self):
        """Pencere boyutlarını ve konumunu dosyaya kaydeder."""
        try:
            self.root.update_idletasks()
            state = self.root.state()
            geometry = self.root.geometry()
            with open("window_config.txt", "w", encoding="utf-8") as f:
                f.write(f"{state}|{geometry}")
        except Exception as e:
            print(f"Kayıt Hatası: {e}") 

    def load_window_geometry(self):
        """Kaydedilmiş boyutları yükler."""
        if os.path.exists("window_config.txt"):
            try:
                with open("window_config.txt", "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if "|" in content:
                        state, geometry = content.split("|")
                        self.root.geometry(geometry)
                        if state == "zoomed":
                            self.root.after(100, lambda: self.root.state("zoomed"))
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
        """Menüyü yükle - Önce DB'den, yoksa dosyadan"""
        if USE_DATABASE:
            try:
                menu_dict = db.get_menu_by_category()
                if menu_dict:  # DB'de menu varsa
                    return menu_dict
                else:  # DB boşsa dosyadan yükle ve DB'ye kaydet
                    db.load_menu_from_file(MENU_FILE)
                    return db.get_menu_by_category()
            except Exception as e:
                print(f"DB Menu hatası: {e}, dosyadan yükleniyor...")
        
        # Excel/Dosya modu (fallback)
        data = {}
        if not os.path.exists(MENU_FILE):
            return {"Genel": [["Örnek Ürün", 100.0]]}
        
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(";")
                if len(parts) == 3:
                    cat, item, price = parts[0].strip(), parts[1].strip(), parts[2].strip()
                    if cat not in data:
                        data[cat] = []
                    data[cat].append([item, float(price)])
        return data

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
        odeme_turleri = ["Mal Alımı", "Fatura", "Maaş", "Kira", "Vergi", "Diğer"]
        secilen_kalem = tk.StringVar(value=odeme_turleri[0])
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
                self.root.after(0, self.update_masa_status)
                if self.current_masa == masa_adi:
                    self.root.after(0, self.update_order_display)
                print(f"Sipariş Geldi: {terminal_adi} -> {masa_adi}")
        except Exception as e:
            print(f"Veri işleme hatası: {e}")
        finally:
            client_sock.close()

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
        self.main_pane = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6)
        self.main_pane.pack(fill=tk.BOTH, expand=True)
        self.left_frame = tk.Frame(self.main_pane)
        tk.Label(self.left_frame, text="MENÜ", font=("Arial", 12, "bold"), fg="#2c3e50").pack(pady=5)
        cont = tk.Frame(self.left_frame); cont.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(cont, bg="#f5f6fa", highlightthickness=0)
        sb = ttk.Scrollbar(cont, orient="vertical", command=self.canvas.yview)
        self.scroll_items = tk.Frame(self.canvas, bg="#f5f6fa")
        self.scroll_items.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scroll_items, anchor="nw", width=380)
        self.canvas.configure(yscrollcommand=sb.set); self.canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        self.main_pane.add(self.left_frame, minsize=300, stretch="always")
        self.refresh_menu_display()

        if self.masa_sayisi > 0 or self.paket_sayisi > 0:
            self.center_frame = tk.Frame(self.main_pane)
            self.setup_tables_ui()
            self.main_pane.add(self.center_frame, minsize=400, stretch="always")
        else:
            self.center_frame = None

        self.setup_order_ui()
        self.main_pane.add(self.order_frame, width=380, minsize=380, stretch="never")
        self.select_masa(self.current_masa)
        self.left_frame.bind("<Configure>", lambda e: self.on_resize())

    def setup_tables_ui(self):
        for w in self.center_frame.winfo_children(): w.destroy()
        self.buttons_ref = {}
        if self.paket_sayisi > 0:
            pf = tk.LabelFrame(self.center_frame, text=" 🛵 Paket Servis ", fg="#d35400", font=("Arial", 11, "bold"))
            pf.pack(fill=tk.X, padx=5, pady=5)
            for i in range(1, self.paket_sayisi + 1):
                n = f"Paket {i}"; btn = tk.Button(pf, text=n, bg="#ff9f43", fg="white", width=11, height=3 ,command=lambda m=n: self.select_masa(m))
                btn.grid(row=(i-1)//5, column=(i-1)%5, padx=5, pady=10); self.buttons_ref[n] = btn
        if self.masa_sayisi > 0:
            sf = tk.LabelFrame(self.center_frame, text=" 🪑 Salon ", fg="#2c3e50", font=("Arial", 11, "bold"))
            sf.pack(fill=tk.BOTH, expand=True, padx=5, pady=10)
            for i in range(self.masa_sayisi):
                n = f"Masa {i+1}"; btn = tk.Button(sf, text=n, bg="#1abc9c", fg="white", font=("Segoe UI", 10, "bold"), width=10, height=3, relief="flat", command=lambda m=n: self.select_masa(m))
                btn.grid(row=i//5, column=i%5, padx=5, pady=5, sticky="nsew"); self.buttons_ref[n] = btn
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
        self.order_listbox = tk.Listbox(vp, font=("Courier New", 10), height=25)
        vp.add(self.order_listbox, minsize=200)
        self.order_listbox.bind("<Double-1>", self.remove_item_from_order)
        self.ctx = tk.Menu(self.root, tearoff=0)
        self.ctx.add_command(label="🎁 İkram Yap / İptal", command=self.toggle_ikram)
        self.order_listbox.bind("<Button-3>", lambda e: self.ctx.post(e.x_root, e.y_root))
        ctrl = tk.Frame(vp); vp.add(ctrl, minsize=300)
        self.total_label = tk.Label(ctrl, text="0.00 TL", font=("Arial", 26, "bold"), fg="#c0392b"); self.total_label.pack(pady=5)
        tk.Button(ctrl, text="🖨 FİŞ YAZDIR", bg="#3498db", fg="white", height=2, command=self.manual_print_fis).pack(fill=tk.X, pady=2)
        p_f = tk.Frame(ctrl); p_f.pack(fill=tk.X)
        tk.Button(p_f, text="NAKİT", bg="#27ae60", fg="white", width=11, height=2, command=lambda: self.finalize_payment("Nakit")).grid(row=0, column=0, padx=2)
        tk.Button(p_f, text="KART", bg="#2980b9", fg="white", width=11, height=2, command=lambda: self.finalize_payment("Kredi Kartı")).grid(row=0, column=1, padx=2)
        tk.Button(p_f, text="AÇIK", bg="#8e44ad", fg="white", width=11, height=2, command=self.open_cari_selector).grid(row=0, column=2, padx=2)
        tk.Button(p_f, text="🎁 TİP", bg="#f1c40f", font=("Arial", 9, "bold"), width=10, height=2, command=self.add_independent_tip).grid(row=0, column=3, padx=2)
        tk.Button(ctrl, text="💰 CARİ YÖNETİMİ", bg="#f39c12", height=2, command=self.show_cari_management).pack(fill=tk.X, pady=2)
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
        """Cari hesap hareketi kaydetme - Otomatik olarak DB veya Excel kullanır"""
        if USE_DATABASE:
            try:
                db.save_cari_transaction(cari_isim, islem, tutar)
                return True
            except Exception as e:
                print(f"DB Hatası: {e}, Excel'e geçiliyor...")
                # Hata varsa Excel'e fallback
        
        # Excel modu
        try:
            tarih = datetime.now().strftime("%d.%m.%Y %H:%M")
            yeni_veri = pd.DataFrame([[tarih, islem, tutar]], columns=['Tarih', 'İşlem', 'Tutar'])
            
            if os.path.exists(CARI_FILE):
                with pd.ExcelWriter(CARI_FILE, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                    try:
                        df_eski = pd.read_excel(CARI_FILE, sheet_name=cari_isim)
                        df_son = pd.concat([df_eski, yeni_veri], ignore_index=True)
                        df_son.to_excel(writer, sheet_name=cari_isim, index=False)
                    except: 
                        yeni_veri.to_excel(writer, sheet_name=cari_isim, index=False)
            else:
                yeni_veri.to_excel(CARI_FILE, sheet_name=cari_isim, index=False)
            return True
        except Exception as e:
            messagebox.showerror("Hata", f"Kayıt Hatası: {e}")
            return False
    def show_cari_management(self):
        top = self.open_modal("Cari Hesap Yönetimi", "600x750")
        lb = tk.Listbox(top, font=("Arial", 11))
        lb.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        def refresh_list():
            lb.delete(0, tk.END)
            
            if USE_DATABASE:
                try:
                    accounts = db.get_all_cari_accounts()
                    for acc in accounts:
                        lb.insert(tk.END, acc['cari_isim'])
                    return
                except Exception as e:
                    print(f"DB Hatası: {e}, Excel moduna geçiliyor...")
            
            # Excel modu
            if os.path.exists(CARI_FILE):
                try:
                    xls = pd.ExcelFile(CARI_FILE)
                    for name in xls.sheet_names:
                        lb.insert(tk.END, name)
                except:
                    pass
        
        def bakiye_sorgula():
            sel = lb.curselection()
            if not sel:
                return
            isim = lb.get(sel[0])
            
            if USE_DATABASE:
                try:
                    bakiye = db.get_cari_balance(isim)
                    messagebox.showinfo(isim, f"Güncel Bakiye: {bakiye:.2f} TL", parent=top)
                    return
                except Exception as e:
                    print(f"DB Hatası: {e}")
            
            # Excel modu
            df = pd.read_excel(CARI_FILE, sheet_name=isim)
            toplam = df['Tutar'].sum()
            messagebox.showinfo(isim, f"Güncel Bakiye: {toplam:.2f} TL", parent=top)
        
        def tahsilat_yap():
            sel = lb.curselection()
            if not sel:
                return
            isim = lb.get(sel[0])
            miktar = simpledialog.askfloat("Tahsilat", "Alınan Nakit Tutarı:", parent=top)
            if miktar:
                if self.save_to_cari(isim, "Tahsilat (Nakit)", -miktar):
                    self.log_to_satislar(f"Cari Tahsilat: {isim}", miktar)
                    messagebox.showinfo("Başarılı", "Tahsilat kaydedildi ve kasaya işlendi.")
                    refresh_list()
        
        def cari_sil():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning("Uyarı", "Lütfen silmek için bir cari seçin!", parent=top)
                return
            isim = lb.get(sel[0])
            
            onay = messagebox.askyesno("Onay", f"{isim} adlı cari hesabı ve TÜM GEÇMİŞİNİ silmek istediğinize emin misiniz?", parent=top)
            if onay:
                if USE_DATABASE:
                    try:
                        db.delete_cari_account(isim)
                        messagebox.showinfo("Başarılı", f"{isim} kaydı silindi.", parent=top)
                        refresh_list()
                        return
                    except Exception as e:
                        print(f"DB Hatası: {e}")
                
                # Excel modu
                try:
                    xls = pd.ExcelFile(CARI_FILE)
                    sheets_dict = {name: pd.read_excel(CARI_FILE, sheet_name=name) 
                                   for name in xls.sheet_names if name != isim}
                    
                    if not sheets_dict:
                        os.remove(CARI_FILE)
                    else:
                        with pd.ExcelWriter(CARI_FILE, engine='openpyxl') as writer:
                            for sheet_name, df in sheets_dict.items():
                                df.to_excel(writer, sheet_name=sheet_name, index=False)
                    
                    messagebox.showinfo("Başarılı", f"{isim} kaydı silindi.", parent=top)
                    refresh_list()
                except Exception as e:
                    messagebox.showerror("Hata", f"Silme işlemi başarısız: {e}", parent=top) 
        def yeni_cari():
            isim = simpledialog.askstring("Yeni Cari", "Müşteri Adı / Ünvan:", parent=top)
            if isim:
                self.save_to_cari(isim, "Hesap Açılışı", 0)
                refresh_list()
        refresh_list()
        btn_f = tk.Frame(top); btn_f.pack(fill=tk.X, padx=20, pady=10)
        tk.Button(btn_f, text="🔍 BAKİYE", bg="#3498db", fg="white", width=12, command=bakiye_sorgula).grid(row=0, column=0, padx=2)
        tk.Button(btn_f, text="💸 TAHSİLAT", bg="#27ae60", fg="white", width=12, command=tahsilat_yap).grid(row=0, column=1, padx=2)
        def odeme_tetikle():
            sel = lb.curselection()
            if not sel: 
                messagebox.showwarning("Uyarı", "Lütfen listeden bir cari seçiniz!", parent=top)
                return
            self.cari_odeme_yap(top, lb.get(sel[0]))
        tk.Button(btn_f, text="🗑️ SİL", bg="#e74c3c", fg="white", width=11, command=cari_sil).grid(row=0, column=4, padx=2)
        tk.Button(btn_f, text="💳 ÖDE/BORÇLAN", bg="#e67e22", fg="white", width=11, command=odeme_tetikle).grid(row=0, column=2, padx=2)    
        tk.Button(btn_f, text="➕ YENİ CARİ", bg="#9b59b6", fg="white", width=12, command=yeni_cari).grid(row=0, column=3, padx=2)
        tk.Button(top, text="📂 CARİ EXCEL DOSYASINI AÇ", bg="#2c3e50", fg="white", command=lambda: os.startfile(os.path.abspath(CARI_FILE)) if os.path.exists(CARI_FILE) else None).pack(fill=tk.X, padx=20, pady=5)

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

    def finalize_payment(self, pt):
        order = self.adisyonlar.get(self.current_masa, [])
        if not order: return
        df_list = [{"urun":i['urun'], "adet":i['adet'], "fiyat":i['fiyat'], "odeme":pt, "tip":i.get("tip","normal"), "Tarih_Saat":datetime.now().strftime("%d-%m-%Y %H:%M:%S")} for i in order]
        if self.save_sale_to_excel(df_list):
            self.adisyonlar[self.current_masa] = []; self.update_order_display(); self.update_masa_status()

    def save_sale_to_excel(self, data):
        """Satış kaydetme - Otomatik olarak DB veya Excel kullanır"""
        if USE_DATABASE:
            try:
                db.save_sales_batch(data)
                return True
            except Exception as e:
                print(f"DB Hatası: {e}, Excel'e geçiliyor...")
                # Hata varsa Excel'e fallback
        
        # Excel modu
        try:
            df = pd.DataFrame(data)
            old = pd.read_excel(SATIS_FILE) if os.path.exists(SATIS_FILE) else pd.DataFrame()
            pd.concat([old, df]).to_excel(SATIS_FILE, index=False)
            return True
        except:
            return False

    def manual_print_fis(self):
        order = [i for i in self.adisyonlar.get(self.current_masa, []) if i.get('tip') != 'tip']
        if not order: return
        sira = self.get_and_inc_counter()
        now = datetime.now().strftime("%d-%m-%Y      %H:%M")
        fn = os.path.join(FIS_KLASORU, f"Fis_{sira}.txt")
        total = sum(i['adet'] * i['fiyat'] for i in order)
        C_WIDTH = 19 
        with open(fn, "w", encoding="utf-8") as f:
            f.write(f"{self.company_name[:C_WIDTH]:^{C_WIDTH}}\n")
            f.write(f"{'SİPARİŞ FİŞİ':^{C_WIDTH}}\n")
            f.write(f"{'='*C_WIDTH}\n")
            f.write(f"{now}\n")
            f.write(f"Fiş No:{sira:<8} {self.current_masa}\n")
            f.write(f"{'-'*C_WIDTH}\n")
            f.write(f"{'Ürün':<10} {'Ad.':<5} {'Tutar':}\n")
            f.write(f"{'-'*C_WIDTH}\n")
            for i in order:
                ik = " (IK)" if i.get("tip") == "ikram" else ""
                urun_adi = (i['urun'] + ik)[:14]
                f.write(f"{urun_adi:<12} {i['adet']:<1} {i['adet']*i['fiyat']:>6.2f}TL\n")
            f.write(f"{'='*C_WIDTH}\n")
            f.write(f"{'TOPLAM:':<10}{total:>11.2f}TL \n")
            f.write(f"{'='*C_WIDTH}\n")
            f.write(f"{'Afiyet Olsun':^{C_WIDTH}}\n")
            f.write("\n\n\n")

        full_path = os.path.abspath(fn)
        if self.direct_print:
            try:
                os.startfile(full_path, "print")
            except Exception as e:
                os.startfile(full_path)
                print(f"Yazdırma hatası: {e}")
        else:
            try:
                os.startfile(full_path)
            except: pass

    def generate_advanced_pdf(self):
        """Gün sonu PDF raporu oluştur - DB veya Excel'den"""
        if not PDF_SUPPORT:
            messagebox.showwarning("Uyarı", "PDF desteği kurulu değil.")
            return
        
        today = datetime.now().strftime("%d-%m-%Y")
        
        # Veri kaynağını belirle
        if USE_DATABASE:
            try:
                # DB'den günlük satışları çek
                sales_data = db.get_sales_by_date()
                if not sales_data:
                    messagebox.showinfo("Bilgi", "Bugün için herhangi bir kayıt bulunmuyor.")
                    return
                
                # Dict list'ten DataFrame'e çevir
                df = pd.DataFrame(sales_data)
                df['Tarih_Saat'] = pd.to_datetime(df['tarih_saat'])
                df = df.rename(columns={'tarih_saat': 'Tarih_Saat'})
                tdf = df
            except Exception as e:
                print(f"DB Hatası: {e}, Excel'e geçiliyor...")
                USE_DATABASE = False  # Fallback
        
        if not USE_DATABASE:
            # Excel modu
            if not os.path.exists(SATIS_FILE):
                messagebox.showwarning("Uyarı", "Satış kaydı bulunamadı.")
                return
            
            df = pd.read_excel(SATIS_FILE)
            tdf = df[df['Tarih_Saat'].astype(str).str.startswith(today)].copy()
            
            if tdf.empty:
                messagebox.showinfo("Bilgi", "Bugün için herhangi bir kasa hareketi bulunmuyor.")
                return
        
        # PDF oluşturma (veri kaynağından bağımsız)
        try:
            fn = f"Detayli_Gun_Sonu_{today}.pdf"
            doc = SimpleDocTemplate(fn, pagesize=letter)
            elements = []
            styles = getSampleStyleSheet()
            for s in styles.byName.values():
                if hasattr(s, 'fontName'): s.fontName = PDF_FONT
            elements.append(Paragraph(f"<b>{self.company_name}</b>", styles['Title']))
            elements.append(Paragraph(f"Gün Sonu Detaylı Finansal Rapor - {today}", styles['Heading2']))
            elements.append(Spacer(1, 0.2 * inch))
            satislar = tdf[tdf['tip'] == 'normal']
            ikramlar = tdf[tdf['tip'] == 'ikram']
            bahsisler = tdf[tdf['tip'] == 'tip']
            c_tahsilat = tdf[tdf['tip'] == 'cari_tahsilat']
            c_odeme = tdf[tdf['tip'] == 'cari_odeme']
            elements.append(Paragraph("<b>1. Genel Kasa Özeti</b>", styles['Normal']))
            summary_data = [["Açıklama", "Tutar"]]
            siparis_ozet = satislar.groupby('odeme')['fiyat'].sum()
            for odeme_tipi, toplam in siparis_ozet.items():
                summary_data.append([f"{odeme_tipi} ", f"{toplam:.2f} TL"])
            toplam_bahsis = bahsisler['fiyat'].sum()
            toplam_c_tahsilat = c_tahsilat['fiyat'].sum()
            toplam_c_odeme = abs(c_odeme['fiyat'].sum())
            summary_data.append(["Bahşişler (Tip)", f"{toplam_bahsis:.2f} TL"])
            summary_data.append(["Cari Tahsilatlar (+)", f"{toplam_c_tahsilat:.2f} TL"])
            summary_data.append(["Cari Ödemeler / Giderler (-)", f"{toplam_c_odeme:.2f} TL"])
            fiili_tahsilat = satislar[satislar['odeme'] != 'Açık Hesap']['fiyat'].sum()
            net_kasa = (fiili_tahsilat + toplam_bahsis + toplam_c_tahsilat) - toplam_c_odeme
            summary_data.append(["NET KASA (Eldeki Toplam)", f"{net_kasa:.2f} TL"])
            ts = Table(summary_data, colWidths=[3.5*inch, 1.5*inch])
            ts.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), PDF_FONT),
                ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
                ('ALIGN', (1,0), (1,-1), 'RIGHT'),
                ('BACKGROUND', (0,-1), (-1,-1), colors.lightgrey),
                ('FONTSIZE', (0, -1), (-1, -1), 12)
            ]))
            elements.append(ts); elements.append(Spacer(1, 0.3 * inch))
            elements.append(Paragraph("<b>2. Satılan Ürün Detayları</b>", styles['Normal']))
            u_data = [["Ürün Adı", "Adet", "Toplam"]]
            u_grubu = satislar.groupby('urun').agg({'adet':'sum', 'fiyat':'sum'}).reset_index()
            for _, r in u_grubu.iterrows():
                u_data.append([str(r['urun']), str(int(r['adet'])), f"{r['fiyat']:.2f} TL"])
            ut = Table(u_data, colWidths=[3*inch, 0.8*inch, 1.2*inch])
            ut.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), PDF_FONT), ('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('ALIGN', (1,0), (2,-1), 'CENTER')]))
            elements.append(ut); elements.append(Spacer(1, 0.3 * inch))
            if not ikramlar.empty:
                elements.append(Paragraph("<b>3. İkram Edilen Ürünler (Maliyet Paneli)</b>", styles['Normal']))
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
                elements.append(it); elements.append(Spacer(1, 0.3 * inch))
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
        sw = self.open_modal("Sistem Ayarları & Menü Yönetimi", "800x900")
        genel_frame = tk.LabelFrame(sw, text=" Genel Ayarlar ", padx=10, pady=10)
        genel_frame.pack(fill=tk.X, padx=20, pady=10)
        tk.Label(genel_frame, text="Firma İsmi:").grid(row=0, column=0, sticky="w")
        e_f = tk.Entry(genel_frame, width=40)
        e_f.insert(0, self.company_name)
        e_f.grid(row=0, column=1, pady=5, sticky="w")
        tk.Label(genel_frame, text="Terminal ID:").grid(row=4, column=0, sticky="w")
        e_t = tk.Entry(genel_frame, width=10)
        e_t.insert(0, self.terminal_id)
        e_t.grid(row=4, column=1, sticky="w", pady=5)
        tk.Label(genel_frame, text="Masa Sayısı:").grid(row=1, column=0, sticky="w")
        e_m = tk.Entry(genel_frame, width=10); e_m.insert(0, str(self.masa_sayisi)); e_m.grid(row=1, column=1, sticky="w", pady=2, padx=5)
        tk.Label(genel_frame, text="Paket Sayısı:").grid(row=2, column=0, sticky="w")
        e_p = tk.Entry(genel_frame, width=10); e_p.insert(0, str(self.paket_sayisi)); e_p.grid(row=2, column=1, sticky="w", pady=2, padx=5)
        tk.Button(genel_frame, text="🔑 ŞİFREYİ DEĞİŞTİR", bg="#7f8c8d", fg="white", command=self.change_password).grid(row=3, column=1, sticky="w", pady=5, padx=5)
        self.var_direct_print = tk.BooleanVar(value=self.direct_print)
        chk_print = tk.Checkbutton(genel_frame, text=" Direkt Yazdır", variable=self.var_direct_print, font=("Arial", 10))
        chk_print.grid(row=5, column=0, columnspan=2, sticky="w", pady=5)
        menu_frame = tk.LabelFrame(sw, text=" Menü Listesi ", padx=10, pady=10)
        menu_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        cols = ("Kategori", "Ürün Adı", "Fiyat")
        tree = ttk.Treeview(menu_frame, columns=cols, show="headings", height=12)
        for col in cols: tree.heading(col, text=col); tree.column(col, width=150)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        for cat, items in self.menu_data.items():
            for it, pr in items: tree.insert("", tk.END, values=(cat, it, f"{pr:.2f}"))
        islem_frame = tk.Frame(sw); islem_frame.pack(fill=tk.X, padx=20, pady=10)
        e_cat = tk.Entry(islem_frame, width=15); e_cat.grid(row=0, column=0, padx=2)
        e_urun = tk.Entry(islem_frame, width=20); e_urun.grid(row=0, column=1, padx=2)
        e_fiyat = tk.Entry(islem_frame, width=10); e_fiyat.grid(row=0, column=2, padx=2)

        def tası(yon):
            selected = tree.selection()
            if not selected: return
            for item in selected:
                index = tree.index(item)
                tree.move(item, tree.parent(item), index + yon)

        def on_tree_select(event):
            selected = tree.selection()
            if selected:
                v = tree.item(selected[0])["values"]
                e_cat.delete(0, tk.END); e_cat.insert(0, v[0])
                e_urun.delete(0, tk.END); e_urun.insert(0, v[1])
                e_fiyat.delete(0, tk.END); e_fiyat.insert(0, v[2])

        tree.bind("<<TreeviewSelect>>", on_tree_select)

        def ekle():
            try:
                p = float(e_fiyat.get().replace(",", "."))
                tree.insert("", tk.END, values=(e_cat.get(), e_urun.get(), f"{p:.2f}"))
            except: messagebox.showwarning("Hata", "Geçerli bir fiyat girin!")

        def guncelle():
            selected = tree.selection()
            if selected:
                try:
                    p = float(e_fiyat.get().replace(",", "."))
                    tree.item(selected[0], values=(e_cat.get(), e_urun.get(), f"{p:.2f}"))
                except: pass

        def final_save():
            try:
                with open(MENU_FILE, "w", encoding="utf-8") as f:
                    for item_id in tree.get_children():
                        v = tree.item(item_id)["values"]
                        f.write(f"{v[0]};{v[1]};{v[2]}\n")
                self.company_name = e_f.get()
                self.masa_sayisi = int(e_m.get())
                self.paket_sayisi = int(e_p.get())
                self.terminal_id = e_t.get()
                self.direct_print = self.var_direct_print.get()
                self.menu_data = self.load_menu_data()
                self.refresh_adisyonlar()
                self.setup_ui() 
                self.save_all_configs()
                messagebox.showinfo("Başarılı", "Ayarlar ve sıralama kalıcı olarak kaydedildi.")
                sw.destroy()
            except Exception as e:
                messagebox.showerror("Hata", "Lütfen masa ve paket sayılarını rakam olarak girin!")

        tk.Button(islem_frame, text="➕ EKLE", bg="#2ecc71", width=10, command=ekle).grid(row=1, column=0, pady=5)
        tk.Button(islem_frame, text="🔄 GÜNCELLE", bg="#3498db", fg="white", width=10, command=guncelle).grid(row=1, column=1, pady=5)
        tk.Button(islem_frame, text="🗑️ SİL", bg="#e74c3c", fg="white", width=10, command=lambda: tree.delete(tree.selection()) if tree.selection() else None).grid(row=1, column=2, pady=5)
        tk.Button(islem_frame, text="▲ YUKARI", bg="#f39c12", fg="white", width=10, command=lambda: tası(-1)).grid(row=1, column=3, pady=5, padx=2)
        tk.Button(islem_frame, text="▼ AŞAĞI", bg="#f39c12", fg="white", width=10, command=lambda: tası(1)).grid(row=1, column=4, pady=5, padx=2)
        tk.Button(sw, text="💾 TÜMÜNÜ KALICI OLARAK KAYDET", bg="#2c3e50", fg="white", height=2, command=final_save).pack(fill=tk.X, padx=20, pady=20)

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
