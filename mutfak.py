import tkinter as tk
from tkinter import ttk
import socket
import json
import threading
from datetime import datetime

# --- AYARLAR ---
MUTFAK_PORT = 5556  # Ana terminalden farklı bir port kullanıyoruz

class MutfakEkrani:
    def __init__(self, root):
        self.root = root
        self.root.title("👨‍🍳 MUTFAK SİPARİŞ TAKİP SİSTEMİ")
        self.root.state('zoomed')
        self.root.configure(bg="#2c3e50")

        self.siparisler = [] # Aktif siparişleri tutar

        # Üst Başlık
        header = tk.Frame(self.root, bg="#1abc9c", height=60)
        header.pack(fill=tk.X)
        tk.Label(header, text="AKTİF MUTFAK SİPARİŞLERİ", font=("Arial", 20, "bold"), 
                 fg="white", bg="#1abc9c").pack(pady=10)

        # Sipariş Kartlarının Dizileceği Alan
        self.main_container = tk.Frame(self.root, bg="#2c3e50")
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Alt Bilgi Barı
        self.footer = tk.Frame(self.root, bg="#34495e", height=30)
        self.footer.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = tk.Label(self.footer, text="Sunucu Dinleniyor...", 
                                     fg="#ecf0f1", bg="#34495e", font=("Consolas", 10))
        self.status_label.pack(side=tk.LEFT, padx=10)

        # Server'ı Başlat
        self.start_listener()

    def start_listener(self):
        def listen():
            try:
                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind(('0.0.0.0', MUTFAK_PORT))
                server.listen(5)
                while True:
                    client, addr = server.accept()
                    data = client.recv(4096).decode('utf-8')
                    if data:
                        self.yeni_siparis_islem(json.loads(data))
                    client.close()
            except Exception as e:
                print(f"Mutfak Server Hatası: {e}")

        threading.Thread(target=listen, daemon=True).start()

    def yeni_siparis_islem(self, veri):
        """ Gelen veriyi listeye ekler ve ekranı tazeler """
        # Veri: {"masa": "Masa 5", "siparisler": [...], "saat": "14:30"}
        veri["giris_saati"] = datetime.now().strftime("%H:%M")
        self.siparisler.append(veri)
        self.root.after(0, self.ekrani_tazele)

    def ekrani_tazele(self):
        """ Mevcut siparişleri kart şeklinde ekrana dizer """
        # Önce eski kartları temizle
        for widget in self.main_container.winfo_children():
            widget.destroy()

        # Her sipariş için bir 'Kart' oluştur (4 sütunlu grid)
        for idx, siparis in enumerate(self.siparisler):
            self.kart_olustur(siparis, idx)

    def kart_olustur(self, veri, index):
        # Kart Çerçevesi
        kart = tk.Frame(self.main_container, bg="#ecf0f1", bd=2, relief=tk.RAISED, padx=10, pady=10)
        kart.grid(row=index // 4, column=index % 4, padx=10, pady=10, sticky="nsew")

        # Masa ve Saat Bilgisi
        ust_bilgi = tk.Frame(kart, bg="#ecf0f1")
        ust_bilgi.pack(fill=tk.X)
        tk.Label(ust_bilgi, text=veri['masa'], font=("Arial", 14, "bold"), bg="#ecf0f1", fg="#c0392b").pack(side=tk.LEFT)
        tk.Label(ust_bilgi, text=veri['giris_saati'], font=("Arial", 10), bg="#ecf0f1", fg="#7f8c8d").pack(side=tk.RIGHT)

        tk.Frame(kart, height=2, bg="#bdc3c7").pack(fill=tk.X, pady=5)

        # Ürün Listesi
        for urun in veri['siparisler']:
            # Kivy'den gelen yapıda urun['urun'] kullanılır
            u_ad = urun.get('urun', 'Bilinmeyen')
            tk.Label(kart, text=f"• {u_ad}", font=("Arial", 12), bg="#ecf0f1", anchor="w").pack(fill=tk.X)

        # "HAZIR" Butonu
        btn_hazir = tk.Button(kart, text="TAMAMLANDI / HAZIR", bg="#27ae60", fg="white", 
                              font=("Arial", 11, "bold"), height=2,
                              command=lambda s=veri: self.siparis_tamamla(s))
        btn_hazir.pack(fill=tk.X, pady=(10, 0))

    def siparis_tamamla(self, siparis_obj):
        """ Siparişi listeden kaldırır """
        if siparis_obj in self.siparisler:
            self.siparisler.remove(siparis_obj)
            self.ekrani_tazele()

if __name__ == "__main__":
    root = tk.Tk()
    app = MutfakEkrani(root)
    root.mainloop()
