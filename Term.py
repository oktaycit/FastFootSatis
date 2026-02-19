import socket, json, threading
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup

# Uygulama Ayarları
APP_CONFIG = {"ip": "192.168.1.100", "terminal": "T-1", "sifre": "1234"}

class SiparisEkrani(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.siparis_listesi = []
        self.toplam = 0.0
        
        layout = BoxLayout(orientation='vertical', padding=10, spacing=15)
        
        # --- 1. ÜST PANEL: MASA VE AYARLAR ---
        ust = BoxLayout(size_hint_y=None, height=70, spacing=10)
        
        # Masa Seçimi (Büyük ve Okunaklı)
        self.masa_spin = Spinner(
            text="MASA SEÇ",
            values=[f"Masa {i}" for i in range(1, 31)],
            size_hint_x=0.7,
            font_size=32,
            background_color=(0.1, 0.5, 0.8, 1)
        )
        
        btn_ayar = Button(text="⚙ AYARLAR", size_hint_x=0.3, font_size=32)
        btn_ayar.bind(on_release=self.sifre_sor_ve_gec)
        
        ust.add_widget(self.masa_spin)
        ust.add_widget(btn_ayar)
        layout.add_widget(ust)

        # --- 2. ÜRÜN MENÜSÜ (BÜYÜTÜLMÜŞ BUTONLAR) ---
        layout.add_widget(Label(text="MENÜ LİSTESİ", size_hint_y=None, height=30, bold=True))
        self.menu_scroll = ScrollView(size_hint_y=0.45)
        # Sütun sayısını 3 yaparak butonları daha da büyüttük
        self.menu_grid = GridLayout(cols=5, spacing=5, size_hint_y=None)
        self.menu_grid.bind(minimum_height=self.menu_grid.setter('height'))
        self.menu_yukle()
        self.menu_scroll.add_widget(self.menu_grid)
        layout.add_widget(self.menu_scroll)

        # --- 3. SİPARİŞ ÖZETİ ---
        layout.add_widget(Label(text="SİPARİŞ ÖZETİ (Silmek için X'e bas)", size_hint_y=None, height=30, color=(0.9, 0.9, 0, 1)))
        self.ozet_scroll = ScrollView(size_hint_y=0.25)
        self.ozet_listesi = GridLayout(cols=1, spacing=8, size_hint_y=None)
        self.ozet_listesi.bind(minimum_height=self.ozet_listesi.setter('height'))
        self.ozet_scroll.add_widget(self.ozet_listesi)
        layout.add_widget(self.ozet_scroll)

        # --- 4. ALT PANEL: TOPLAM VE GÖNDER ---
        self.toplam_label = Label(text="TOPLAM: 0.00 TL", size_hint_y=None, height=50, font_size=32, bold=True, color=(0, 1, 0, 1))
        layout.add_widget(self.toplam_label)
        
        btn_gonder = Button(
            text="SİPARİŞİ ONAYLA VE GÖNDER", 
            size_hint_y=None, height=80, 
            background_color=(0, 0.7, 0.3, 1),
            font_size=24, bold=True
        )
        btn_gonder.bind(on_release=self.aktar)
        layout.add_widget(btn_gonder)

        self.add_widget(layout)

    def menu_yukle(self):
        try:
            with open("menu.txt", "r", encoding="utf-8") as f:
                for s in f:
                    p = s.strip().split(";")
                    if len(p) == 3:
                        # Buton boyutları height=150 yapılarak büyütüldü
                        btn = Button(
                            text=f"{p[1]}\n[b]{p[2]} TL[/b]", 
                            markup=True,
                            size_hint_y=None, height=200, 
                            halign='center', font_size=32,
                            background_color=(0.2, 0.2, 0.2, 1)
                        )
                        btn.bind(on_release=lambda x, u=p[1], f=p[2]: self.ekle(u, f))
                        self.menu_grid.add_widget(btn)
        except: self.menu_grid.add_widget(Label(text="menu.txt bulunamadı!"))

    def ekle(self, u, f):
        self.siparis_listesi.append({"urun": u, "fiyat": float(f)})
        self.ozet_yenile()

    def urun_sil(self, index):
        self.siparis_listesi.pop(index)
        self.ozet_yenile()

    def ozet_yenile(self):
        self.ozet_listesi.clear_widgets()
        self.toplam = 0.0
        for idx, i in enumerate(self.siparis_listesi):
            self.toplam += i['fiyat']
            row = BoxLayout(size_hint_y=None, height=50, spacing=10)
            row.add_widget(Label(text=f"• {i['urun']} ({i['fiyat']} TL)", halign='left', font_size=32))
            btn_sil = Button(text="X", size_hint_x=None, width=60, background_color=(0.8, 0, 0, 1), bold=True)
            btn_sil.bind(on_release=lambda x, index=idx: self.urun_sil(index))
            row.add_widget(btn_sil)
            self.ozet_listesi.add_widget(row)
        self.toplam_label.text = f"TOPLAM: {self.toplam:.2f} TL"

    def sifre_sor_ve_gec(self, instance):
        icerik = BoxLayout(orientation='vertical', padding=200, spacing=10)
        sifre_giris = TextInput(text='', password=True, multiline=False, halign='center', font_size=48)
        btn = Button(text="GİRİŞ", size_hint_y=None, height=60)
        popup = Popup(title="Yönetici Şifresi", content=icerik, size_hint=(0.7, 0.4))
        
        def kontrol(x):
            if sifre_giris.text == APP_CONFIG["sifre"]:
                popup.dismiss()
                self.manager.current = 'ayarlar'
        
        btn.bind(on_release=kontrol)
        icerik.add_widget(sifre_giris); icerik.add_widget(btn)
        popup.open()

    def aktar(self, instance):
        if self.masa_spin.text == "MASA SEÇ":
            self.toplam_label.text = "HATA: MASA SEÇİN!"
            return
        if not self.siparis_listesi: return
        
        veri = {"masa": self.masa_spin.text, "siparisler": self.siparis_listesi, "terminal": APP_CONFIG["terminal"]}
        paket = json.dumps(veri).encode('utf-8')
        
        # Hem Kasa (5555) hem Mutfak (5556)
        for port in [5555, 5556]:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.settimeout(2)
                s.connect((APP_CONFIG["ip"], port)); s.sendall(paket); s.close()
            except: print(f"Port {port} Kapalı")
            
        self.siparis_listesi = []; self.ozet_yenile()
        self.masa_spin.text = "MASA SEÇ"
        self.toplam_label.text = "SİPARİŞ GÖNDERİLDİ!"

class AyarlarEkrani(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        l = BoxLayout(orientation='vertical', padding=450, spacing=5)
        
        l.add_widget(Label(text="SİSTEM AYARLARI", font_size=32, bold=True))
       
        self.ip_in = TextInput(text=APP_CONFIG["ip"], multiline=False, font_size=32)
        l.add_widget(Label(text="Server IP:"))
        l.add_widget(self.ip_in)
        size_hint_y=None,
        height='40dp'
        self.term_in = TextInput(text=APP_CONFIG["terminal"], multiline=False, font_size=32)
        size_hint_y=None,
        height='40dp'
        l.add_widget(Label(text="Terminal Adı:"))
        l.add_widget(self.term_in)
        size_hint_y=None,
        height='40dp'
        self.sifre_in = TextInput(text=APP_CONFIG["sifre"], multiline=False, font_size=32)
        l.add_widget(Label(text="Yeni Giriş Şifresi:"))
        l.add_widget(self.sifre_in)
        size_hint_y=None,
        height='40dp'
        
        btn_kaydet = Button(text="KAYDET VE GERİ DÖN", background_color=(0, 0.5, 0.8, 1), font_size=32, bold=True)
        btn_kaydet.bind(on_release=self.kaydet)
        l.add_widget(btn_kaydet)
        
        self.add_widget(l)

    def kaydet(self, instance):
        APP_CONFIG["ip"] = self.ip_in.text
        APP_CONFIG["terminal"] = self.term_in.text
        APP_CONFIG["sifre"] = self.sifre_in.text
        self.manager.current = 'siparis'

class TerminalApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(SiparisEkrani(name='siparis'))
        sm.add_widget(AyarlarEkrani(name='ayarlar'))
        return sm

if __name__ == '__main__': TerminalApp().run()