import tkinter as tk
from tkinter import messagebox, simpledialog, Listbox, Scrollbar
import datetime
import csv
import os
import sys
import smtplib
import json
import threading
import time
from email.message import EmailMessage

# --- SKÚSIME NAČÍTAŤ MYSQL (Ak je nainštalované) ---
try:
    import mysql.connector
    MYSQL_DOSTUPNE = True
except ImportError:
    MYSQL_DOSTUPNE = False
    print("INFO: Knižnica 'mysql-connector-python' nenájdená. Lokálna DB bude vypnutá.")

# --- SKÚSIME NAČÍTAŤ GOOGLE (Ak je nainštalované) ---
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GOOGLE_DOSTUPNE = True
except ImportError:
    GOOGLE_DOSTUPNE = False
    print("INFO: Knižnice pre Google nie sú nainštalované.")

# --- VERZIA ---
VERZIA = "28.1 (Final Fix: Window Priority)"

# --- SÚBORY ---
NAZOV_JSON_KLUCA = "credentials.json"
NAZOV_TABULKY = "VYROBA_DATA"

SUBOR_HISTORIA = "historia_nepodarkov.csv"
SUBOR_STAV = "stav_aplikacie.json"
SUBOR_OFFLINE = "offline_queue.json"
SUBOR_CONFIG = "config.json"

# --- NASTAVENIA DATABÁZY (MySQL - XAMPP) ---
DB_HOST = "127.0.0.1"  # Alebo IP servera napr. 192.168.1.50
DB_USER = "root"
DB_PASS = ""
DB_NAME = "vyroba"

# --- FARBY (Material Design) ---
COLOR_PRIMARY = "#263238"      
COLOR_SECONDARY = "#37474F"    
COLOR_BG = "#ECEFF1"           
COLOR_INFO_BTN = "#006064"     
COLOR_ACCENT = "#2196F3"
COLORS_OK = ["#A5D6A7", "#4CAF50", "#2E7D32"]       
COLORS_WARN = ["#FFCC80", "#FF9800", "#EF6C00"]     
COLORS_CRIT = ["#EF9A9A", "#F44336", "#C62828"]     

# --- TYPY CHÝB ---
SUB_TYPES = [
    {"label": "NEDOPENENÁ",   "filename": "nedopenena.png",   "id": 0},
    {"label": "PRESTRIEKANÁ", "filename": "prestriekana.png", "id": 1},
    {"label": "ROZTRHNUTÁ",   "filename": "roztrhnuta.png",   "id": 2}
]

MENO_VEDUCEHO = "Ing. Peter Manažér" 
LIMIT_VAROVANIA = 20

# EMAIL
ODOSIELATEL_EMAIL = "tvoj_email@gmail.com"
ODOSIELATEL_HESLO = "abcd efgh ijkl mnop" 
PRIJIMATEL_EMAIL = "veduci@firma.sk"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
POUZIT_EMAIL = False 

# --- UŽÍVATELIA ---
UZIVATELIA = {
    "1111": "Lukáš BENDÍK",
    "2222": "Štefan PIVOVAR",  # <--- Aktualizované meno
    "3333": "Radovan KOLLÁR",
    "4444": "Bartoš JAVOSKY", 
    "9999": "Technológ"
}

# PREDVOLENÉ TLAČIDLÁ (Použijú sa, ak neexistuje config.json)
DEFAULT_TLACIDLA = [
    "BX726 Lateral", "BX726 Front", "BX726 Central", "M7",
    "VW380 LAT", "VW380 CEN", "VW380 ECER", "SK380 Lat"
]
KLAVESY_ZNAKY = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "+"]
LIMITY = { "warning": 10, "critical": 25, "max_scale": 35 }
CAS_RESETU = ["06:00", "14:00", "22:00"]

class PocitadloApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Počítadlo {VERZIA}")
        self.root.configure(bg=COLOR_BG)
        self.root.attributes('-fullscreen', True)
        
        # 1. NAČÍTANIE KONFIGURÁCIE
        self.nazov_linky = "Neznáma"
        self.nazvy_tlacidiel = []
        self.nacitat_config()

        self.aktualny_uzivatel_meno = "Neprihlásený"
        self.aktualny_uzivatel_pin = "0000"
        self.klavesnica_blokovana = False 
        self.stats = {} 
        
        # Google & Offline
        self.google_client = None; self.google_sheet = None
        self.offline_queue = []
        self.nacitat_offline_frontu()

        if GOOGLE_DOSTUPNE:
            self.pripojit_k_google()
            threading.Thread(target=self.synchronizator_loop, daemon=True).start()

        self.root.bind("<Key>", self.stlacenie_klavesy_hlavne)
        
        # UI Elementy
        self.frame_buttons = None 
        self.canvases = []; self.rectangles = []; self.texts = []; self.back_buttons = []
        self.lbl_cas = None; self.lbl_datum = None; self.lbl_uzivatel = None; self.lbl_linka = None
        
        self.ikony_chyb = self.nacitaj_obrazky()
        self.skontroluj_csv()
        
        self.inicializovat_data() # Nastaví polia podľa počtu tlačidiel

        # VYKRESLENIE UI
        self.vytvor_header()
        self.vytvor_rozhranie_tlacidiel() 
        
        # OBNOVENIE STAVU
        uspesne = self.nacitat_stav_z_disku()
        self.aktualizuj_cas()
        
        self.root.update() 
        self.prekresli_vsetky_bary()

        if not uspesne: self.root.after(500, lambda: self.vyziadat_pin("PRIHLÁSENIE", self.spracuj_prihlasenie))
        else: self.aktualizuj_header_info()

    # --- CONFIG MANAGEMENT ---
    def nacitat_config(self):
        if os.path.exists(SUBOR_CONFIG):
            try:
                with open(SUBOR_CONFIG, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    self.nazov_linky = cfg.get("line_name", "Linka-X")
                    self.nazvy_tlacidiel = cfg.get("buttons", DEFAULT_TLACIDLA)
            except:
                self.nazov_linky = "Linka-X"; self.nazvy_tlacidiel = DEFAULT_TLACIDLA
        else:
            self.nazov_linky = "Linka-X"; self.nazvy_tlacidiel = DEFAULT_TLACIDLA
            self.ulozit_config()

    def ulozit_config(self):
        data = { "line_name": self.nazov_linky, "buttons": self.nazvy_tlacidiel }
        try:
            with open(SUBOR_CONFIG, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e: print(f"Config Save Error: {e}")

    def inicializovat_data(self):
        self.pocet_riadkov = len(self.nazvy_tlacidiel)
        self.counters = [tk.IntVar(value=0) for _ in range(self.pocet_riadkov)]
        self.sub_counters = [[0, 0, 0] for _ in range(self.pocet_riadkov)]
        self.row_history = [[] for _ in range(self.pocet_riadkov)]
        self.undo_allowed = [False] * self.pocet_riadkov
        self.varovanie_zobrazene = [False] * self.pocet_riadkov

    # --- TECHNOLÓG MENU (Pridávanie referencií) ---
    def otvorit_manazera_referencii(self):
        self.klavesnica_blokovana = True
        w = tk.Toplevel(self.root); w.title("Správa referencií"); w.geometry("600x700"); w.configure(bg=COLOR_BG); w.attributes('-topmost', True)
        
        tk.Label(w, text="MANAŽMENT REFERENCIÍ", font=("Arial", 18, "bold"), bg=COLOR_BG).pack(pady=10)
        
        frame_list = tk.Frame(w); frame_list.pack(fill=tk.BOTH, expand=True, padx=20)
        scrollbar = Scrollbar(frame_list); scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        lb = Listbox(frame_list, font=("Arial", 14), yscrollcommand=scrollbar.set, selectmode=tk.SINGLE)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); scrollbar.config(command=lb.yview)

        for btn in self.nazvy_tlacidiel: lb.insert(tk.END, btn)

        def pridat():
            novy = simpledialog.askstring("Nová referencia", "Zadajte názov modelu:", parent=w)
            if novy: lb.insert(tk.END, novy); ulozit_zmeny()
        
        def vymazat():
            sel = lb.curselection()
            if sel: lb.delete(sel); ulozit_zmeny()

        def posunut(smer):
            sel = lb.curselection()
            if not sel: return
            idx = sel[0]
            novy_idx = idx + smer
            if 0 <= novy_idx < lb.size():
                text = lb.get(idx); lb.delete(idx); lb.insert(novy_idx, text); lb.selection_set(novy_idx); ulozit_zmeny()

        def ulozit_zmeny():
            self.nazvy_tlacidiel = list(lb.get(0, tk.END))
            self.ulozit_config()

        btn_frame = tk.Frame(w, bg=COLOR_BG); btn_frame.pack(fill=tk.X, pady=20)
        tk.Button(btn_frame, text="▲ HORE", command=lambda: posunut(-1), bg=COLOR_ACCENT, fg="white", font=("Arial",12), width=10).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="▼ DOLE", command=lambda: posunut(1), bg=COLOR_ACCENT, fg="white", font=("Arial",12), width=10).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="+ PRIDAŤ", command=pridat, bg=COLORS_OK[1], fg="white", font=("Arial",12), width=10).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="- ZMAZAŤ", command=vymazat, bg=COLORS_CRIT[1], fg="white", font=("Arial",12), width=10).pack(side=tk.LEFT, padx=10)

        def zavriet_a_restartovat():
            if messagebox.askyesno("Reštart", "Pre aplikovanie zmien je potrebný reštart.\nReštartovať teraz?", parent=w):
                self.root.destroy(); os.execl(sys.executable, sys.executable, *sys.argv)
            else: self.klavesnica_blokovana = False; w.destroy()

        tk.Button(w, text="ULOŽIŤ A ZAVRIEŤ", command=zavriet_a_restartovat, font=("Arial", 14, "bold"), bg="#333", fg="white").pack(pady=10, fill=tk.X, padx=20)

    # --- ZMENA NÁZVU LINKY (OPRAVENÁ - Nezasekáva sa) ---
    def zmenit_nazov_linky(self):
        self.klavesnica_blokovana = True
        
        # Vytvoríme vlastné okno, ktoré bude NAZVYŠŠIE
        wd = tk.Toplevel(self.root)
        wd.title("Zmena názvu")
        wd.configure(bg=COLOR_BG)
        wd.attributes('-topmost', True) # KĽÚČOVÁ ZMENA: Toto zaručí, že bude nad všetkým
        wd.overrideredirect(True) # Bez rámčeka
        
        # Centrovanie okna
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        wd.geometry(f"500x350+{int((sw-500)/2)}+{int((sh-350)/2)}")
        
        tk.Label(wd, text="ZMENA NÁZVU LINKY", font=("Arial", 20, "bold"), bg=COLOR_BG).pack(pady=20)
        tk.Label(wd, text=f"Aktuálne: {self.nazov_linky}", font=("Arial", 14), bg=COLOR_BG, fg="#555").pack(pady=5)
        
        entry = tk.Entry(wd, font=("Arial", 24), justify='center')
        entry.pack(pady=20, padx=20, fill=tk.X)
        entry.focus_force() # Dáme kurzor hneď do poľa
        
        def potvrdit():
            nove_meno = entry.get()
            if nove_meno:
                self.nazov_linky = nove_meno
                self.ulozit_config()
                self.lbl_linka.config(text=f"Linka: {self.nazov_linky}")
            self.klavesnica_blokovana = False
            wd.destroy()
            
        def zrusit():
            self.klavesnica_blokovana = False
            wd.destroy()

        bf = tk.Frame(wd, bg=COLOR_BG); bf.pack(side=tk.BOTTOM, pady=20)
        tk.Button(bf, text="ZRUŠIŤ", font=("Arial", 14), bg=COLORS_CRIT[1], fg="white", width=10, command=zrusit).pack(side=tk.LEFT, padx=10)
        tk.Button(bf, text="ULOŽIŤ", font=("Arial", 14), bg=COLORS_OK[1], fg="white", width=10, command=potvrdit).pack(side=tk.LEFT, padx=10)
        
        wd.bind('<Return>', lambda e: potvrdit())
        wd.bind('<Escape>', lambda e: zrusit())
        wd.wait_visibility(); wd.grab_set()

    # --- DATA & SYNC ---
    def pripojit_k_google(self):
        if not os.path.exists(NAZOV_JSON_KLUCA): return
        def _connect():
            try:
                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                creds = ServiceAccountCredentials.from_json_keyfile_name(NAZOV_JSON_KLUCA, scope)
                self.google_client = gspread.authorize(creds)
                self.google_sheet = self.google_client.open(NAZOV_TABULKY).sheet1
                print("Google: Online")
            except Exception as e: print(f"Google Error: {e}")
        threading.Thread(target=_connect).start()

    def synchronizator_loop(self):
        while True:
            time.sleep(30)
            if self.offline_queue and self.google_sheet:
                copy_queue = list(self.offline_queue); cnt = 0
                for zaznam in copy_queue:
                    try: self.google_sheet.append_row(zaznam); cnt += 1
                    except: self.pripojit_k_google(); break 
                if cnt > 0:
                    self.offline_queue = self.offline_queue[cnt:]; self.ulozit_offline_frontu()

    def zapis_do_historie(self, typ, chyba, val, user_name=None, user_pin=None):
        t = datetime.datetime.now()
        m = user_name if user_name else self.aktualny_uzivatel_meno
        p = user_pin if user_pin else self.aktualny_uzivatel_pin
        d_str = t.strftime("%Y-%m-%d"); c_str = t.strftime("%H:%M:%S")
        
        # [Linka, Datum, Cas, PIN, Meno, Typ, Chyba, Hodnota]
        row_data = [self.nazov_linky, d_str, c_str, p, m, typ, chyba, val]

        # 1. Google (Offline Buffer)
        if GOOGLE_DOSTUPNE:
            def poslat():
                sent = False
                if not self.offline_queue and self.google_sheet:
                    try: self.google_sheet.append_row(row_data); sent = True
                    except: pass
                if not sent: self.offline_queue.append(row_data); self.ulozit_offline_frontu()
            threading.Thread(target=poslat).start()

        # 2. MySQL (Ak je dostupné)
        if MYSQL_DOSTUPNE:
            try:
                conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, connect_timeout=1)
                cursor = conn.cursor()
                sql = "INSERT INTO historia (linka, datum, cas, pin, meno, typ, chyba, hodnota) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, tuple(row_data))
                conn.commit(); cursor.close(); conn.close()
            except: pass 

        # 3. CSV (Vždy)
        try:
            with open(SUBOR_HISTORIA, 'a', newline='', encoding='utf-8-sig') as f:
                csv.writer(f, delimiter=';').writerow(row_data)
        except: pass

    # --- UI LAYOUT ---
    def vytvor_header(self):
        # Výška 100 aby sa zmestilo spodné menu
        hf = tk.Frame(self.root, bg=COLOR_PRIMARY, height=100); hf.pack(side=tk.TOP, fill=tk.X); hf.pack_propagate(False)
        
        self.lbl_linka = tk.Label(hf, text=f"Linka: {self.nazov_linky}", font=("Roboto", 14, "bold"), fg="#CFD8DC", bg=COLOR_PRIMARY)
        self.lbl_linka.pack(side=tk.TOP, anchor="nw", padx=10, pady=2)

        tk.Label(hf, text="POČÍTADLO NEPODARKOV", font=("Roboto", 24, "bold"), fg="white", bg=COLOR_PRIMARY).pack(side=tk.LEFT, padx=30)
        
        rf = tk.Frame(hf, bg=COLOR_PRIMARY); rf.pack(side=tk.RIGHT, padx=30)
        self.lbl_cas = tk.Label(rf, text="00:00", font=("Roboto", 36, "bold"), fg=COLORS_OK[1], bg=COLOR_PRIMARY); self.lbl_cas.pack(anchor="e")
        self.lbl_datum = tk.Label(rf, text="...", font=("Roboto", 14), fg="#B0BEC5", bg=COLOR_PRIMARY); self.lbl_datum.pack(anchor="e")
        self.lbl_uzivatel = tk.Label(hf, text="-", font=("Roboto", 24, "bold"), fg="#FFFF00", bg=COLOR_PRIMARY); self.lbl_uzivatel.pack(side=tk.RIGHT, padx=40)
        tk.Button(hf, text="AKTUÁLNY STAV", font=("Arial", 12, "bold"), bg=COLOR_INFO_BTN, fg="white", relief="raised", command=self.ukaz_aktualny_sumar).pack(side=tk.RIGHT, padx=10, ipady=5)
        
        sh = tk.Frame(self.root, bg=COLOR_SECONDARY, height=50); sh.pack(side=tk.TOP, fill=tk.X); sh.pack_propagate(False)
        sh.columnconfigure(0, weight=1); sh.columnconfigure(1, weight=4); sh.columnconfigure(2, weight=5); sh.columnconfigure(3, weight=1)
        for i, txt in enumerate(["KLÁVESA", "MODEL / REFERENCIA", "STAV", "OPRAVA"]): 
            tk.Label(sh, text=txt, font=("Arial", 14, "bold"), fg="white", bg=COLOR_SECONDARY).grid(row=0, column=i, sticky="ew", pady=10)

    def vytvor_rozhranie_tlacidiel(self):
        # 1. NAJPRV SPODNÉ MENU (Aby bolo viditeľné)
        bf = tk.Frame(self.root, bg=COLOR_PRIMARY); bf.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Button(bf, text="MENU / MOŽNOSTI", font=("Arial",14,"bold"), bg=COLOR_ACCENT, fg="white", 
                  command=lambda: self.vyziadat_pin("PIN", self.overit_pin_pre_menu)).pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # 2. POTOM HLAVNÝ OBSAH (Vyplní zvyšok)
        self.frame_buttons = tk.Frame(self.root, bg=COLOR_BG)
        self.frame_buttons.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.frame_buttons.columnconfigure(0, weight=1); self.frame_buttons.columnconfigure(1, weight=4); self.frame_buttons.columnconfigure(2, weight=5); self.frame_buttons.columnconfigure(3, weight=1)

        self.canvases = []; self.rectangles = []; self.texts = []; self.back_buttons = []
        pady_val = 4 if self.pocet_riadkov <= 8 else 1 

        for i in range(self.pocet_riadkov):
            self.frame_buttons.rowconfigure(i, weight=1)
            kt = KLAVESY_ZNAKY[i] if i<len(KLAVESY_ZNAKY) else ""
            nazov_btn = self.nazvy_tlacidiel[i]
            
            tk.Label(self.frame_buttons, text=kt, font=("Arial",20,"bold"), fg="white", bg="#607D8B", width=3).grid(row=i, column=0, sticky="ns", padx=5, pady=pady_val)
            tk.Button(self.frame_buttons, text=nazov_btn, font=("Arial",18,"bold"), bg="white", relief="flat", command=lambda x=i: self.otvorit_vyber_chyby(x)).grid(row=i, column=1, sticky="nsew", padx=5, pady=pady_val)
            
            c = tk.Canvas(self.frame_buttons, bg="#E0E0E0", highlightthickness=0); c.grid(row=i, column=2, sticky="nsew", padx=5, pady=pady_val)
            rects = []; 
            for _ in range(3): r = c.create_rectangle(0,0,0,0, outline=""); rects.append(r)
            self.rectangles.append(rects)
            tid = c.create_text(0,0, text="0", font=("Arial",18,"bold"), fill="black"); self.texts.append(tid)
            self.canvases.append(c); c.bind("<Configure>", lambda e, x=i: self.centrovat_text(e, x))
            
            b = tk.Button(self.frame_buttons, text="Späť", font=("Arial",11,"bold"), state=tk.DISABLED, command=lambda x=i: self.odobrat_kus(x)); b.grid(row=i, column=3, sticky="nsew", padx=5, pady=pady_val); self.back_buttons.append(b)

    def prekresli_vsetky_bary(self):
        for i in range(self.pocet_riadkov): self.prekresli_bar(i); self.aktualizuj_tlacidlo_spat(i)

    def otvorit_menu(self, u, p):
        self.klavesnica_blokovana = True
        w = tk.Toplevel(self.root); w.geometry("600x750"); w.attributes('-topmost', True); w.overrideredirect(True); w.configure(bg=COLOR_BG)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w.geometry(f"600x750+{int((sw-600)/2)}+{int((sh-750)/2)}")
        
        def close(): self.klavesnica_blokovana=False; w.destroy()
        tk.Label(w, text="MENU", font=("Arial", 18), bg=COLOR_BG).pack(pady=20)
        
        btns = [("1. EXPORT", lambda: self.manualny_export(u,p), COLOR_ACCENT), ("2. RESET", lambda: [self.potvrdit_reset(u,p, w), close()], COLORS_WARN[1]), ("3. REŠTART", lambda: self.potvrdit_restart(u,p, w), COLORS_CRIT[1]), ("4. ZMENA OBSLUHY", lambda: [close(), self.vyziadat_pin("ZMENA", self.spracuj_prihlasenie)], "#607D8B"), ("5. UKONČIŤ", lambda: self.potvrdit_ukoncenie(u,p, w), "black")]
        
        if p == "9999":
            btns.insert(0, ("⚙ SPRÁVA REFERENCIÍ", self.otvorit_manazera_referencii, "#9C27B0"))
            btns.insert(1, ("⚙ ZMENIŤ NÁZOV LINKY", self.zmenit_nazov_linky, "#7B1FA2"))

        for t, c, col in btns: tk.Button(w, text=t, font=("Arial",14), bg=col, fg="white", command=c).pack(fill=tk.X, padx=50, pady=8)
        tk.Button(w, text="Zavrieť", command=close).pack(side=tk.BOTTOM, pady=20)
        w.wait_visibility(); w.grab_set(); w.focus_force()

    # --- POMOCNÉ FUNKCIE ---
    def nacitat_offline_frontu(self):
        if os.path.exists(SUBOR_OFFLINE):
            try:
                with open(SUBOR_OFFLINE, 'r', encoding='utf-8') as f: self.offline_queue = json.load(f)
            except: self.offline_queue = []
    def ulozit_offline_frontu(self):
        try:
            with open(SUBOR_OFFLINE, 'w', encoding='utf-8') as f: json.dump(self.offline_queue, f, ensure_ascii=False)
        except: pass
    
    def zisti_id_smeny(self, dt=None):
        if dt is None: dt = datetime.datetime.now()
        h = dt.hour; datum = dt.date()
        if 6 <= h < 14: smena = "Ranna"
        elif 14 <= h < 22: smena = "Poobedna"
        else:
            smena = "Nocna"; 
            if h < 6: datum = datum - datetime.timedelta(days=1)
        return f"{datum}_{smena}"
    
    def ulozit_stav_na_disk(self):
        data = { "timestamp": datetime.datetime.now().isoformat(), "shift_id": self.zisti_id_smeny(), "user_name": self.aktualny_uzivatel_meno, "user_pin": self.aktualny_uzivatel_pin, "counters": [v.get() for v in self.counters], "sub_counters": self.sub_counters, "row_history": self.row_history, "stats": self.stats }
        try:
            with open(SUBOR_STAV, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)
        except: pass

    def nacitat_stav_z_disku(self):
        if not os.path.exists(SUBOR_STAV): return False
        try:
            with open(SUBOR_STAV, 'r', encoding='utf-8') as f: data = json.load(f)
            if self.zisti_id_smeny() != data.get("shift_id", ""): return False 
            self.aktualny_uzivatel_meno = data.get("user_name", "Neprihlásený")
            self.aktualny_uzivatel_pin = data.get("user_pin", "0000")
            self.stats = data.get("stats", {})
            self.row_history = data.get("row_history", [[] for _ in range(self.pocet_riadkov)])
            ulozene_counters = data.get("counters", [])
            self.sub_counters = data.get("sub_counters", [])
            for i in range(len(self.counters)):
                if i < len(ulozene_counters):
                    self.counters[i].set(ulozene_counters[i])
                    if self.counters[i].get() > 0 and self.row_history[i]: self.undo_allowed[i] = True 
            return True
        except: return False

    def vymazat_stav_z_disku(self):
        if os.path.exists(SUBOR_STAV):
            try: os.remove(SUBOR_STAV)
            except: pass

    def nacitaj_obrazky(self):
        ikony = []
        for i in range(3):
            nazov = SUB_TYPES[i]["filename"]
            if os.path.exists(nazov):
                try: ikony.append(tk.PhotoImage(file=nazov))
                except: ikony.append(self.vytvor_zastupny_obrazok(COLORS_OK[i]))
            else: ikony.append(self.vytvor_zastupny_obrazok(COLORS_OK[i]))
        return ikony
    
    def vytvor_zastupny_obrazok(self, farba):
        img = tk.PhotoImage(width=450, height=450); img.put(farba, to=(0, 0, 449, 449)); return img

    def generuj_report_text(self):
        text = ""; total = 0
        for i in range(self.pocet_riadkov):
            c = self.counters[i].get()
            if c > 0:
                text += f"► {self.nazvy_tlacidiel[i]}: CELKOM {c} ks\n"
                counts = self.sub_counters[i]
                for j in range(3):
                    if counts[j] > 0: text += f"    • {SUB_TYPES[j]['label']}: {counts[j]} ks\n"
                text += "-" * 35 + "\n"
                total += c
        if total == 0: text = "Žiadne nepodarky."
        return text, total

    def zobrazit_sumar_okno(self, nadpis, obsah, je_reset=False):
        self.klavesnica_blokovana = True
        w = tk.Toplevel(self.root); w.configure(bg=COLOR_BG); w.attributes('-topmost', True)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w.geometry(f"900x800+{int((sw-900)/2)}+{int((sh-800)/2)}"); w.overrideredirect(True)
        bg = COLOR_PRIMARY if je_reset else COLOR_INFO_BTN
        tk.Label(w, text=nadpis, font=("Arial", 24, "bold"), fg="white", bg=bg, pady=20).pack(fill=tk.X)
        cf = tk.Frame(w, bg="white", padx=20, pady=20); cf.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        tk.Label(cf, text=f"Obsluha: {self.aktualny_uzivatel_meno}", font=("Arial", 16, "bold"), bg="white").pack(anchor="w")
        tk.Label(cf, text=f"Čas: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", font=("Arial", 12), bg="white").pack(anchor="w", pady=10)
        ta = tk.Text(cf, font=("Courier New", 14, "bold"), height=15, relief="flat", bg="#f5f5f5")
        ta.insert(tk.END, obsah); ta.config(state=tk.DISABLED); ta.pack(fill=tk.BOTH, expand=True)
        def close(): self.klavesnica_blokovana = False; w.destroy()
        tk.Button(w, text="ZATVORIŤ", font=("Arial", 18, "bold"), command=close).pack(side=tk.BOTTOM, pady=20)
        w.wait_visibility(); w.grab_set()

    def ukaz_aktualny_sumar(self):
        rep, tot = self.generuj_report_text()
        self.zobrazit_sumar_okno("AKTUÁLNY STAV SMENY", f"CELKOM: {tot}\n================\n{rep}")

    def otvorit_vyber_chyby(self, idx):
        self.klavesnica_blokovana = True
        popup = tk.Toplevel(self.root); popup.configure(bg=COLOR_BG); popup.attributes('-topmost', True); popup.overrideredirect(True)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = 1600, 900
        popup.geometry(f"{w}x{h}+{int((sw-w)/2)}+{int((sh-h)/2)}")
        fs = tk.Frame(popup, bg="#333", padx=2, pady=2); fs.pack(fill=tk.BOTH, expand=True)
        c = tk.Frame(fs, bg="white"); c.pack(fill=tk.BOTH, expand=True)
        tk.Label(c, text=f"DETAIL CHYBY: {self.nazvy_tlacidiel[idx]}", font=("Arial", 32, "bold"), bg=COLOR_PRIMARY, fg="white", pady=25).pack(fill=tk.X)
        gc = tk.Frame(c, bg="white"); gc.pack(fill=tk.BOTH, expand=True, padx=20, pady=(60, 5))
        for i in range(3): gc.columnconfigure(i, weight=1)
        def ok(sub): popup.destroy(); self.klavesnica_blokovana=False; self.pridat_kus(idx, sub)
        def no(e=None): popup.destroy(); self.klavesnica_blokovana=False
        for i in range(3):
            cf = tk.Frame(gc, bg="white"); cf.grid(row=0, column=i, sticky="nsew", padx=10)
            tk.Button(cf, image=self.ikony_chyb[i], bg="#F5F5F5", relief="raised", bd=3, command=lambda s=i: ok(s)).pack(pady=(0,15))
            tk.Label(cf, text=SUB_TYPES[i]['label'], font=("Arial", 22, "bold"), bg="white").pack()
            tk.Label(cf, text=f"({i+1})", font=("Arial", 28, "bold"), bg="white", fg=COLOR_ACCENT).pack()
        tk.Button(c, text="ZRUŠIŤ (ESC)", font=("Arial", 18), bg="#ddd", command=no).pack(side=tk.BOTTOM, pady=15)
        def binds():
            for i in range(3): popup.bind(str(i+1), lambda e, x=i: ok(x)); popup.bind(f"<KP_{i+1}>", lambda e, x=i: ok(x))
            popup.bind("<Escape>", no)
        popup.wait_visibility(); popup.grab_set(); popup.lift(); popup.focus_force(); binds()

    def pridat_kus(self, idx, sub):
        self.counters[idx].set(self.counters[idx].get() + 1)
        self.sub_counters[idx][sub] += 1
        self.row_history[idx].append(sub)
        self.undo_allowed[idx] = True
        self.prekresli_bar(idx); self.aktualizuj_tlacidlo_spat(idx)
        self.ulozit_stav_na_disk()
        nazov = self.nazvy_tlacidiel[idx]; typ = SUB_TYPES[sub]['label']
        self.zapis_do_historie("PRIDANÉ", f"{nazov} - {typ}", self.counters[idx].get())
        self.aktualizuj_statistiku(self.aktualny_uzivatel_meno, f"{nazov} ({typ})", 1)
        if self.counters[idx].get() >= LIMIT_VAROVANIA and not self.varovanie_zobrazene[idx]:
            self.varovanie(nazov, self.counters[idx].get()); self.email(nazov, self.counters[idx].get()); self.varovanie_zobrazene[idx] = True

    def odobrat_kus(self, idx):
        if not self.undo_allowed[idx] or not self.row_history[idx]: return
        sub = self.row_history[idx].pop()
        self.sub_counters[idx][sub] -= 1
        self.counters[idx].set(max(0, self.counters[idx].get() - 1))
        self.undo_allowed[idx] = False 
        if self.counters[idx].get() == 0: self.varovanie_zobrazene[idx] = False
        self.prekresli_bar(idx); self.aktualizuj_tlacidlo_spat(idx)
        self.ulozit_stav_na_disk()
        nazov = self.nazvy_tlacidiel[idx]; typ = SUB_TYPES[sub]['label']
        self.zapis_do_historie("ODSTRÁNENÉ", f"{nazov} - {typ}", self.counters[idx].get())
        self.aktualizuj_statistiku(self.aktualny_uzivatel_meno, f"{nazov} ({typ})", -1)

    def prekresli_bar(self, idx):
        cv = self.canvases[idx]; r = self.rectangles[idx]; txt = self.texts[idx]
        tot = self.counters[idx].get(); cnt = self.sub_counters[idx]
        w = max(cv.winfo_width(), 300); h = cv.winfo_height()
        pal = COLORS_OK
        if tot > LIMIT_VAROVANIA: pal = COLORS_WARN
        if tot > LIMITY["critical"]: pal = COLORS_CRIT
        cx = 0
        for i in range(3):
            if cnt[i] > 0:
                sc = min(tot / LIMITY["max_scale"], 1.0)
                sw = int((w * sc) * (cnt[i] / max(tot, 1)))
                cv.coords(r[i], cx, 0, cx + sw, h)
                cv.itemconfig(r[i], fill=pal[i], state="normal")
                cx += sw
            else: cv.itemconfig(r[i], state="hidden")
        cv.itemconfig(txt, text=str(tot)); cv.tag_raise(txt)

    def aktualizuj_tlacidlo_spat(self, idx):
        b = self.back_buttons[idx]
        if self.undo_allowed[idx]: b.config(state=tk.NORMAL, bg="#FFCDD2", fg=COLORS_CRIT[1])
        else: b.config(state=tk.DISABLED, bg=COLOR_BG, fg="#B0BEC5")

    def stlacenie_klavesy_hlavne(self, event):
        if self.klavesnica_blokovana: return
        c = event.char; k = event.keysym; idx = -1
        if c in [str(i) for i in range(1,10)]: idx = int(c)-1
        elif c == "0": idx = 9
        elif c == "+": idx = 10
        if idx == -1 and k.startswith("KP_"):
            try: num = int(k.split("_")[1]); idx = num - 1 if num > 0 else 9
            except: idx = 10 if "Add" in k else -1
        if idx != -1 and idx < self.pocet_riadkov: self.otvorit_vyber_chyby(idx)

    def email(self, err, cnt):
        if not POUZIT_EMAIL: return
        def send():
            try:
                m = EmailMessage(); m.set_content(f"CHYBA: {err}\nPOČET: {cnt}\nOBSLUHA: {self.aktualny_uzivatel_meno}")
                m['Subject'] = f"ALARM: {err}"; m['From'] = ODOSIELATEL_EMAIL; m['To'] = PRIJIMATEL_EMAIL
                s = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT); s.login(ODOSIELATEL_EMAIL, ODOSIELATEL_HESLO)
                s.send_message(m); s.quit()
            except: pass
        threading.Thread(target=send).start()

    def varovanie(self, nazov, pocet):
        self.klavesnica_blokovana = True
        w = tk.Toplevel(self.root); w.configure(bg=COLORS_CRIT[1]); w.attributes('-topmost', True)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w.geometry(f"{int(sw*0.8)}x{int(sh*0.6)}+{int(sw*0.1)}+{int(sh*0.2)}"); w.overrideredirect(True)
        tk.Label(w, text="⚠ POZOR ⚠", font=("Arial", 40), fg="yellow", bg=COLORS_CRIT[1]).pack(pady=20)
        tk.Label(w, text=f"Limit: {nazov} ({pocet}ks)", font=("Arial", 25), fg="white", bg=COLORS_CRIT[1]).pack()
        tk.Label(w, text=MENO_VEDUCEHO, font=("Arial", 30, "bold"), fg="white", bg=COLORS_CRIT[1]).pack(pady=20)
        tk.Button(w, text="OK", font=("Arial", 20), command=lambda: [w.destroy(), setattr(self, 'klavesnica_blokovana', False)]).pack(side=tk.BOTTOM, pady=40)
        self.root.bell()

    def vyziadat_pin(self, nadpis, cb):
        self.klavesnica_blokovana = True
        w = tk.Toplevel(self.root); w.configure(bg="#222"); w.attributes('-topmost', True); w.overrideredirect(True)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w.geometry(f"400x500+{int((sw-400)/2)}+{int((sh-500)/2)}")
        def close(): self.klavesnica_blokovana = False; w.destroy()
        tk.Label(w, text=nadpis, font=("Arial",16), fg="white", bg="#222").pack(pady=10)
        v = tk.StringVar(); tk.Label(w, textvariable=v, font=("Arial",24), width=10).pack(pady=10)
        def add(x): 
            if len(v.get())<4: v.set(v.get()+x)
        def ok(): 
            if len(v.get())==4: w.destroy(); self.klavesnica_blokovana=False; cb(v.get())
        bf = tk.Frame(w, bg="#222"); bf.pack(pady=10)
        keys = ['7','8','9','4','5','6','1','2','3','C','0','OK']
        r,c=0,0
        for k in keys:
            cmd = lambda x=k: add(x)
            col="#444"; 
            if k=='C': cmd=lambda:v.set(""); col="#d32f2f"
            if k=='OK': cmd=ok; col="#388e3c"
            tk.Button(bf, text=k, font=("Arial",18), width=5, height=2, bg=col, fg="white", command=cmd).grid(row=r, column=c, padx=5, pady=5)
            c+=1; 
            if c>2: c=0; r+=1
        tk.Button(w, text="Zrušiť", command=close, bg="#555", fg="white").pack(pady=10)
        w.bind("<Key>", lambda e: add(e.char) if e.char.isdigit() else ok() if e.keysym in ["Return","KP_Enter"] else v.set("") if e.keysym=="Escape" else None)
        w.wait_visibility(); w.grab_set(); w.focus_force()

    def spracuj_prihlasenie(self, pin):
        if pin in UZIVATELIA:
            self.aktualny_uzivatel_pin = pin; self.aktualny_uzivatel_meno = UZIVATELIA[pin]; self.aktualizuj_header_info()
        else: messagebox.showerror("Chyba", "Neznámy PIN!"); self.root.after(100, lambda: self.vyziadat_pin("SKÚSTE ZNOVA", self.spracuj_prihlasenie))

    def overit_pin_pre_menu(self, pin):
        if pin in UZIVATELIA: self.otvorit_menu(UZIVATELIA[pin], pin)
        else: messagebox.showerror("Chyba", "Nesprávny PIN!")

    def skontroluj_csv(self):
        if not os.path.exists(SUBOR_HISTORIA):
            with open(SUBOR_HISTORIA, 'w', newline='', encoding='utf-8-sig') as f:
                csv.writer(f, delimiter=';').writerow(["Linka", "Dátum", "Čas", "PIN", "Meno", "Typ", "Chyba", "Hodnota"])

    def aktualizuj_statistiku(self, meno, chyba, zmena):
        if meno not in self.stats: self.stats[meno] = {}
        if chyba not in self.stats[meno]: self.stats[meno][chyba] = 0
        self.stats[meno][chyba] += zmena

    def manualny_export(self, user, pin):
        t = datetime.datetime.now(); fname = f"export_{t.strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        try:
            with open(fname, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f, delimiter=';'); w.writerow(["Export:", user]); w.writerow([])
                w.writerow(["--- SUMÁR ---"])
                for i in range(self.pocet_riadkov): w.writerow([self.nazvy_tlacidiel[i], self.counters[i].get()])
                w.writerow([]); w.writerow(["--- DETAILY ---"])
                for m, d in self.stats.items():
                    for k, v in d.items(): 
                        if v>0: w.writerow([m, k, v])
            messagebox.showinfo("Export", fname)
        except Exception as e: messagebox.showerror("Err", str(e))

    def aktualizuj_cas(self):
        t = datetime.datetime.now()
        if self.lbl_cas: self.lbl_cas.config(text=t.strftime("%H:%M"))
        if self.lbl_datum: self.lbl_datum.config(text=t.strftime("%d.%m.%Y"))
        if t.strftime("%H:%M:%S") in [x+":00" for x in CAS_RESETU]: self.reset_vsetko(automaticky=True)
        self.root.after(1000, self.aktualizuj_cas)

    def aktualizuj_header_info(self):
        self.lbl_uzivatel.config(text=self.aktualny_uzivatel_meno)

    def potvrdit_ukoncenie(self, m, p, pw):
        if messagebox.askyesno("Exit", "Vypnúť?", parent=pw): 
            self.zapis_do_historie("UKONČENIE", "SYS", 0, m, p); self.root.destroy()
    def potvrdit_reset(self, m, p, pw):
        if messagebox.askyesno("Reset", "Vymazať?", parent=pw): self.reset_vsetko(False, m, p)
    def potvrdit_restart(self, m, p, pw):
        if messagebox.askyesno("Reštart", "Reštartovať?", parent=pw): 
            self.zapis_do_historie("RESTART", "SYS", 0, m, p); os.execl(sys.executable, sys.executable, *sys.argv)

    def centrovat_text(self, event, index):
        c = self.canvases[index]
        c.coords(self.texts[index], event.width/2, event.height/2)
        self.prekresli_bar(index)

    def reset_vsetko(self, automaticky=False, user_name=None, user_pin=None):
        meno = user_name if user_name else "AUTOMAT"; pin = user_pin if user_pin else "0000"
        rep, _ = self.generuj_report_text(); full = f"REPORT UKONČENEJ SMENY\n==================\n{rep}"
        self.stats = {} 
        for i in range(self.pocet_riadkov):
            stara = self.counters[i].get()
            if stara > 0: self.zapis_do_historie("RESET_SAVE", self.nazvy_tlacidiel[i], stara, user_name=meno, user_pin=pin)
            self.counters[i].set(0); self.sub_counters[i] = [0, 0, 0]; self.row_history[i] = []; self.undo_allowed[i] = False; self.varovanie_zobrazene[i] = False
            self.prekresli_bar(i); self.aktualizuj_tlacidlo_spat(i)
        dovod = "AUTOMATICKÝ RESET" if automaticky else "MANUÁLNY RESET"
        self.zapis_do_historie(dovod, "Všetky", 0, user_name=meno, user_pin=pin)
        self.vymazat_stav_z_disku() 
        if automaticky: self.zobrazit_sumar_okno("KONIEC SMENY", full, je_reset=True)

if __name__ == "__main__":
    root = tk.Tk()
    app = PocitadloApp(root)
    root.mainloop()