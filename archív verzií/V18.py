import tkinter as tk
from tkinter import messagebox
import datetime
import csv
import os
import sys
import smtplib
from email.message import EmailMessage
import threading

# --- VERZIA ---
VERZIA = "18.0 (Fix Popup Okna)"

# --- FARBY MATERIAL DESIGN ---
COLOR_PRIMARY = "#263238"      # Hlavička
COLOR_SECONDARY = "#37474F"    # Pod-hlavička
COLOR_BG = "#ECEFF1"           # Pozadie
COLOR_CARD = "#FFFFFF"         # Karty
COLOR_TEXT_MAIN = "#212121"
COLOR_ACCENT = "#2196F3"       # Modrá

# Definícia odtieňov pre 3 pod-typy chýb
COLORS_OK = ["#A5D6A7", "#4CAF50", "#2E7D32"]       # Zelená škála
COLORS_WARN = ["#FFCC80", "#FF9800", "#EF6C00"]     # Oranžová škála
COLORS_CRIT = ["#EF9A9A", "#F44336", "#C62828"]     # Červená škála

# --- KONFIGURÁCIA CHÝB ---
SUB_TYPES = [
    {"label": "NEDOPENENÁ",   "filename": "nedopenena.png",   "id": 0},
    {"label": "PRESTRIEKANÁ", "filename": "prestriekana.png", "id": 1},
    {"label": "ROZTRHNUTÁ",   "filename": "roztrhnuta.png",   "id": 2}
]

# --- NASTAVENIA ---
SUBOR_HISTORIA = "historia_nepodarkov.csv"
MENO_VEDUCEHO = "Ing. Peter Manažér" 
LIMIT_VAROVANIA = 20

# EMAIL
ODOSIELATEL_EMAIL = "tvoj_email@gmail.com"
ODOSIELATEL_HESLO = "abcd efgh ijkl mnop" 
PRIJIMATEL_EMAIL = "veduci@firma.sk"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
POUZIT_EMAIL = False 

UZIVATELIA = {
    "1111": "Lukáš BENDÍK",
    "2222": "Miroslav GALLIK",
    "3333": "Radovan KOLLÁR",
    "4444": "Bartoš JAVOSKY", 
    "9999": "Technológ"
}

NAZVY_TLACIDIEL = [
    "BX726 Lateral",
    "BX726 Front",
    "BX726 Central",
    "M7",
    "VW380 LAT",
    "VW380 CEN",
    "VW380 ECER",
    "SK380 Lat",
    "Zlý rozmer",
    "Iná chyba 1",
    "Iná chyba 2",
]

KLAVESY_ZNAKY = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "+"]

LIMITY = {
    "warning": 10,  
    "critical": 25, 
    "max_scale": 35 
}
CAS_RESETU = ["06:00", "14:00", "22:00"]

class PocitadloApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Počítadlo Nepodarkov {VERZIA}")
        self.root.configure(bg=COLOR_BG)
        
        self.aktualny_uzivatel_meno = "Neprihlásený"
        self.aktualny_uzivatel_pin = "0000"
        
        # Dôležitá premenná: Ak je True, hlavná klávesnica nereaguje
        self.klavesnica_blokovana = False 
        
        self.stats = {} 
        
        self.root.attributes('-fullscreen', True)
        self.root.bind("<Key>", self.stlacenie_klavesy_hlavne)
        
        # DATA
        self.pocet_riadkov = len(NAZVY_TLACIDIEL)
        self.counters = [tk.IntVar(value=0) for _ in range(self.pocet_riadkov)]
        self.sub_counters = [[0, 0, 0] for _ in range(self.pocet_riadkov)]
        self.row_history = [[] for _ in range(self.pocet_riadkov)]
        self.undo_allowed = [False] * self.pocet_riadkov
        self.varovanie_zobrazene = [False] * self.pocet_riadkov
        
        # UI Elementy
        self.canvases = [] 
        self.rectangles = [] 
        self.texts = []
        self.back_buttons = []
        
        self.lbl_cas = None
        self.lbl_datum = None
        self.lbl_uzivatel = None
        
        # Načítanie obrázkov
        self.ikony_chyb = self.nacitaj_obrazky()

        self.skontroluj_csv()
        self.vytvor_header()
        self.vytvor_rozhranie()
        self.aktualizuj_cas()
        
        self.root.update() 
        for i in range(self.pocet_riadkov):
            self.prekresli_bar(i)
            self.aktualizuj_tlacidlo_spat(i)

        self.root.after(500, lambda: self.vyziadat_pin("PRIHLÁSENIE OBSLUHY", self.spracuj_prihlasenie))

    def nacitaj_obrazky(self):
        ikony = []
        for i in range(3):
            nazov_suboru = SUB_TYPES[i]["filename"]
            if os.path.exists(nazov_suboru):
                try:
                    img = tk.PhotoImage(file=nazov_suboru)
                    ikony.append(img)
                except Exception:
                    ikony.append(self.vytvor_zastupny_obrazok(COLORS_OK[i]))
            else:
                ikony.append(self.vytvor_zastupny_obrazok(COLORS_OK[i]))
        return ikony

    def vytvor_zastupny_obrazok(self, farba):
        img = tk.PhotoImage(width=64, height=64)
        img.put(farba, to=(0, 0, 63, 63))
        return img

    # --- OPRAVENÉ POPUP OKNO ---
    def otvorit_vyber_chyby(self, index_riadku):
        # Okamžite blokujeme, aby sa neotvorilo 10 okien naraz
        self.klavesnica_blokovana = True
        
        nazov_chyby = NAZVY_TLACIDIEL[index_riadku]
        
        popup = tk.Toplevel(self.root)
        popup.title(f"Výber chyby: {nazov_chyby}")
        popup.configure(bg=COLOR_BG)
        
        # Dôležité pre viditeľnosť nad fullscreenom
        popup.attributes('-topmost', True)
        popup.overrideredirect(True) # Bez rámu
        
        # Výpočet stredu obrazovky
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 900, 500
        x = (sw - w) // 2
        y = (sh - h) // 2
        popup.geometry(f"{w}x{h}+{x}+{y}")
        
        # Frame pre dizajn
        frame_shadow = tk.Frame(popup, bg="#333", padx=2, pady=2)
        frame_shadow.pack(fill=tk.BOTH, expand=True)
        content = tk.Frame(frame_shadow, bg="white")
        content.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(content, bg=COLOR_PRIMARY, height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text=f"DETAIL CHYBY: {nazov_chyby}", font=("Arial", 24, "bold"), bg=COLOR_PRIMARY, fg="white").pack(pady=20)

        btn_container = tk.Frame(content, bg="white")
        btn_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        btn_container.columnconfigure(0, weight=1)
        btn_container.columnconfigure(1, weight=1)
        btn_container.columnconfigure(2, weight=1)

        def potvrdit_vyber(sub_id):
            popup.destroy()
            self.klavesnica_blokovana = False
            self.pridat_kus(index_riadku, sub_id)
        
        def zrusit_akciu(event=None):
            popup.destroy()
            self.klavesnica_blokovana = False

        for i in range(3):
            f = tk.Frame(btn_container, bg="white")
            f.grid(row=0, column=i, sticky="nsew", padx=10)
            
            cfg = SUB_TYPES[i]
            
            btn = tk.Button(f, text=f"{cfg['label']}\n\nStlač ({i+1})", 
                            image=self.ikony_chyb[i], compound=tk.TOP,
                            font=("Arial", 16, "bold"), bg="#F5F5F5",
                            command=lambda s=i: potvrdit_vyber(s))
            btn.pack(fill=tk.BOTH, expand=True)

        btn_cancel = tk.Button(content, text="ZRUŠIŤ (ESC)", font=("Arial", 14), bg="#ddd", command=zrusit_akciu)
        btn_cancel.pack(side=tk.BOTTOM, fill=tk.X, pady=10, padx=20)

        # --- Väzba kláves bez oneskorenia, ale s wait_visibility ---
        def bind_keys(event=None):
            popup.bind("1", lambda e: potvrdit_vyber(0))
            popup.bind("2", lambda e: potvrdit_vyber(1))
            popup.bind("3", lambda e: potvrdit_vyber(2))
            # NumPad podpora
            popup.bind("<KP_1>", lambda e: potvrdit_vyber(0))
            popup.bind("<KP_2>", lambda e: potvrdit_vyber(1))
            popup.bind("<KP_3>", lambda e: potvrdit_vyber(2))
            popup.bind("<KP_End>", lambda e: potvrdit_vyber(0))
            popup.bind("<KP_Down>", lambda e: potvrdit_vyber(1))
            popup.bind("<KP_Next>", lambda e: potvrdit_vyber(2))
            
            popup.bind("<Escape>", zrusit_akciu)
        
        # Toto zabezpečí, že okno je naozaj vykreslené a na vrchu
        popup.wait_visibility()
        popup.grab_set() # Ukradne všetok vstup pre seba
        popup.lift()     # Vynúti si byť na vrchu
        popup.focus_force() # Vynúti si focus klávesnice
        
        bind_keys() # Nabindujeme klávesy

    # --- LOGIKA PRIDÁVANIA ---
    def pridat_kus(self, index_riadku, sub_id):
        aktualna = self.counters[index_riadku].get()
        nova_hodnota = aktualna + 1
        self.counters[index_riadku].set(nova_hodnota)
        
        self.sub_counters[index_riadku][sub_id] += 1
        self.row_history[index_riadku].append(sub_id)
        
        self.undo_allowed[index_riadku] = True
        self.prekresli_bar(index_riadku)
        self.aktualizuj_tlacidlo_spat(index_riadku)
        
        nazov = NAZVY_TLACIDIEL[index_riadku]
        popis_sub = SUB_TYPES[sub_id]['label']
        self.zapis_do_historie("PRIDANÉ", f"{nazov} - {popis_sub}", nova_hodnota)
        self.aktualizuj_statistiku(self.aktualny_uzivatel_meno, f"{nazov} ({popis_sub})", 1)

        if nova_hodnota >= LIMIT_VAROVANIA and not self.varovanie_zobrazene[index_riadku]:
            self.zobrazit_popup_varovanie(nazov, nova_hodnota)
            self.spustit_odosielanie_emailu(nazov, nova_hodnota)
            self.varovanie_zobrazene[index_riadku] = True

    # --- LOGIKA UBERANIA ---
    def odobrat_kus(self, index_riadku):
        if not self.undo_allowed[index_riadku]: return
        if not self.row_history[index_riadku]: return 
        
        last_sub_id = self.row_history[index_riadku].pop()
        
        self.sub_counters[index_riadku][last_sub_id] -= 1
        
        aktualna = self.counters[index_riadku].get()
        nova_hodnota = max(0, aktualna - 1)
        self.counters[index_riadku].set(nova_hodnota)
        
        if nova_hodnota == 0:
            self.undo_allowed[index_riadku] = False
            self.varovanie_zobrazene[index_riadku] = False
        
        self.prekresli_bar(index_riadku)
        self.aktualizuj_tlacidlo_spat(index_riadku)
        
        nazov = NAZVY_TLACIDIEL[index_riadku]
        popis_sub = SUB_TYPES[last_sub_id]['label']
        self.zapis_do_historie("ODSTRÁNENÉ", f"{nazov} - {popis_sub}", nova_hodnota)
        self.aktualizuj_statistiku(self.aktualny_uzivatel_meno, f"{nazov} ({popis_sub})", -1)

    # --- VYKRESLOVANIE BAROV ---
    def prekresli_bar(self, index):
        canvas = self.canvases[index]
        rects = self.rectangles[index]
        text_id = self.texts[index]
        
        total_count = self.counters[index].get()
        counts = self.sub_counters[index]
        
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width < 10: width = 300
        
        palette = COLORS_OK
        if total_count > LIMIT_VAROVANIA: palette = COLORS_WARN
        if total_count > LIMITY["critical"]: palette = COLORS_CRIT
        
        current_x = 0
        for i in range(3):
            sub_count = counts[i]
            if sub_count > 0:
                effective_total = max(total_count, 1)
                scale_factor = min(total_count / LIMITY["max_scale"], 1.0)
                total_bar_pixels = int(width * scale_factor)
                segment_width = int(total_bar_pixels * (sub_count / effective_total))
                
                canvas.coords(rects[i], current_x, 0, current_x + segment_width, height)
                canvas.itemconfig(rects[i], fill=palette[i], state="normal")
                current_x += segment_width
            else:
                canvas.itemconfig(rects[i], state="hidden")
        
        canvas.itemconfig(text_id, text=str(total_count))
        canvas.tag_raise(text_id)

    def aktualizuj_tlacidlo_spat(self, index):
        btn = self.back_buttons[index]
        if self.undo_allowed[index]:
            btn.config(state=tk.NORMAL, bg="#FFCDD2", fg=COLORS_CRIT[1])
        else:
            btn.config(state=tk.DISABLED, bg=COLOR_BG, fg="#B0BEC5")

    # --- OVLÁDANIE HLAVNOU KLÁVESNICOU ---
    def stlacenie_klavesy_hlavne(self, event):
        # Ak je otvorené popup okno, ignorujeme hlavnú klávesnicu
        if self.klavesnica_blokovana: return
        
        znak = event.char
        keysym = event.keysym
        
        index = -1
        
        if znak in ["1", "2", "3", "4", "5", "6", "7", "8", "9"]:
            index = int(znak) - 1
        elif znak == "0":
            index = 9
        elif znak == "+":
            index = 10
            
        if index == -1:
            if keysym == "KP_1": index = 0
            elif keysym == "KP_2": index = 1
            elif keysym == "KP_3": index = 2
            elif keysym == "KP_4": index = 3
            elif keysym == "KP_5": index = 4
            elif keysym == "KP_6": index = 5
            elif keysym == "KP_7": index = 6
            elif keysym == "KP_8": index = 7
            elif keysym == "KP_9": index = 8
            elif keysym == "KP_0": index = 9
            elif keysym == "KP_Add": index = 10

        if index != -1 and index < self.pocet_riadkov:
            self.otvorit_vyber_chyby(index)

    # --- OSTATNÉ FUNKCIE ---

    def poslat_email_vlakno(self, chyba, pocet, obsluha):
        if not POUZIT_EMAIL: return
        try:
            msg = EmailMessage()
            msg.set_content(f"ALARM!\nChyba: {chyba}\nPočet: {pocet}\nObsluha: {obsluha}")
            msg['Subject'] = f"ALARM: {chyba}"
            msg['From'] = ODOSIELATEL_EMAIL; msg['To'] = PRIJIMATEL_EMAIL
            s = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
            s.login(ODOSIELATEL_EMAIL, ODOSIELATEL_HESLO)
            s.send_message(msg); s.quit()
        except: pass

    def spustit_odosielanie_emailu(self, c, p):
        threading.Thread(target=self.poslat_email_vlakno, args=(c, p, self.aktualny_uzivatel_meno)).start()

    def zobrazit_popup_varovanie(self, nazov_chyby, pocet):
        self.klavesnica_blokovana = True
        popup = tk.Toplevel(self.root)
        popup.configure(bg=COLORS_CRIT[1])
        popup.attributes('-topmost', True)
        
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w, h = int(sw*0.8), int(sh*0.6)
        popup.geometry(f"{w}x{h}+{int((sw-w)/2)}+{int((sh-h)/2)}")
        popup.overrideredirect(True)
        
        tk.Label(popup, text="⚠ POZOR ⚠", font=("Arial", 40, "bold"), fg="yellow", bg=COLORS_CRIT[1]).pack(pady=20)
        tk.Label(popup, text=f"Limit prekročený: {nazov_chyby} ({pocet}ks)", font=("Arial", 25, "bold"), fg="white", bg=COLORS_CRIT[1]).pack()
        tk.Label(popup, text=MENO_VEDUCEHO, font=("Arial", 30, "bold"), fg="white", bg=COLORS_CRIT[1]).pack(pady=20)
        
        def zavriet():
            self.klavesnica_blokovana = False
            popup.destroy()

        tk.Button(popup, text="OK / RESET", font=("Arial", 20, "bold"), command=zavriet).pack(side=tk.BOTTOM, pady=40, fill=tk.X, padx=100)
        self.root.bell()

    def vyziadat_pin(self, nadpis, cb):
        self.klavesnica_blokovana = True
        w = tk.Toplevel(self.root)
        w.configure(bg="#222")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w.geometry(f"400x500+{int((sw-400)/2)}+{int((sh-500)/2)}")
        # Pri fullscreen apps je lepšie použiť topmost než transient
        w.attributes('-topmost', True)
        w.overrideredirect(True)
        
        def on_close():
            self.klavesnica_blokovana = False
            w.destroy()
        
        # Centrovanie obsahu
        content = tk.Frame(w, bg="#222")
        content.pack(expand=True, fill=tk.BOTH)

        tk.Label(content, text=nadpis, font=("Arial",16), fg="white", bg="#222").pack(pady=10)
        v = tk.StringVar()
        tk.Label(content, textvariable=v, font=("Arial",24), width=10).pack(pady=10)
        
        def add(x): 
            if len(v.get())<4: v.set(v.get()+x)
        def ok(): 
            if len(v.get())==4: 
                w.destroy()
                self.klavesnica_blokovana=False
                cb(v.get())
        
        bf = tk.Frame(content, bg="#222"); bf.pack(pady=10)
        keys = ['7','8','9','4','5','6','1','2','3','C','0','OK']
        r,c=0,0
        for k in keys:
            cmd = lambda x=k: add(x)
            col="#444"
            if k=='C': cmd=lambda:v.set(""); col="#d32f2f"
            if k=='OK': cmd=ok; col="#388e3c"
            tk.Button(bf, text=k, font=("Arial",18), width=5, height=2, bg=col, fg="white", command=cmd).grid(row=r, column=c, padx=5, pady=5)
            c+=1; 
            if c>2: c=0; r+=1
        
        # Exit tlačidlo pre prípad núdze
        tk.Button(content, text="Zrušiť", command=on_close, bg="#555", fg="white").pack(pady=10)

        w.bind("<Key>", lambda e: add(e.char) if e.char.isdigit() else ok() if e.keysym in ["Return","KP_Enter"] else v.set("") if e.keysym=="Escape" else None)
        
        w.wait_visibility()
        w.grab_set()
        w.focus_force()

    def spracuj_prihlasenie(self, pin):
        if pin in UZIVATELIA:
            self.aktualny_uzivatel_pin = pin; self.aktualny_uzivatel_meno = UZIVATELIA[pin]; self.aktualizuj_header_info()
        else:
            messagebox.showerror("Chyba", "Neznámy PIN kód!")
            self.root.after(100, lambda: self.vyziadat_pin("SKÚSTE ZNOVA", self.spracuj_prihlasenie))

    def overit_pin_pre_menu(self, pin):
        if pin in UZIVATELIA: self.otvorit_menu(UZIVATELIA[pin], pin)
        else: messagebox.showerror("Chyba", "Nesprávny PIN kód.")

    def skontroluj_csv(self):
        if not os.path.exists(SUBOR_HISTORIA):
            with open(SUBOR_HISTORIA, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f, delimiter=';').writerow(["Dátum", "Čas", "PIN", "Meno", "Typ", "Chyba", "Hodnota"])

    def zapis_do_historie(self, typ, chyba, val, user_name=None, user_pin=None):
        t = datetime.datetime.now()
        meno = user_name if user_name else self.aktualny_uzivatel_meno
        pin = user_pin if user_pin else self.aktualny_uzivatel_pin
        try:
            with open(SUBOR_HISTORIA, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f, delimiter=';').writerow([t.strftime("%Y-%m-%d"), t.strftime("%H:%M:%S"), pin, meno, typ, chyba, val])
        except: pass

    def aktualizuj_statistiku(self, meno, chyba, zmena):
        if meno not in self.stats: self.stats[meno] = {}
        if chyba not in self.stats[meno]: self.stats[meno][chyba] = 0
        self.stats[meno][chyba] += zmena

    def manualny_export(self, user, pin):
        t = datetime.datetime.now()
        fname = f"export_{t.strftime('%Y-%m-%d_%H-%M-%S')}.csv"
        try:
            with open(fname, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f, delimiter=';')
                w.writerow(["Export:", user]); w.writerow([])
                w.writerow(["--- SUMÁR ---"])
                for i in range(self.pocet_riadkov):
                    w.writerow([NAZVY_TLACIDIEL[i], self.counters[i].get()])
                w.writerow([])
                w.writerow(["--- DETAILY ---"])
                for m, d in self.stats.items():
                    for k, v in d.items(): 
                        if v>0: w.writerow([m, k, v])
            messagebox.showinfo("Export", fname)
        except Exception as e: messagebox.showerror("Err", str(e))

    def vytvor_header(self):
        hf = tk.Frame(self.root, bg=COLOR_PRIMARY, height=90); hf.pack(side=tk.TOP, fill=tk.X); hf.pack_propagate(False)
        tk.Label(hf, text="POČÍTADLO NEPODARKOV", font=("Roboto", 28, "bold"), fg="white", bg=COLOR_PRIMARY).pack(side=tk.LEFT, padx=30)
        rf = tk.Frame(hf, bg=COLOR_PRIMARY); rf.pack(side=tk.RIGHT, padx=30)
        self.lbl_cas = tk.Label(rf, text="00:00", font=("Roboto", 24), fg=COLORS_OK[1], bg=COLOR_PRIMARY); self.lbl_cas.pack(anchor="e")
        self.lbl_datum = tk.Label(rf, text="...", font=("Roboto", 12), fg="#B0BEC5", bg=COLOR_PRIMARY); self.lbl_datum.pack(anchor="e")
        self.lbl_uzivatel = tk.Label(hf, text="-", font=("Roboto", 16), fg="#FFC107", bg=COLOR_PRIMARY); self.lbl_uzivatel.pack(side=tk.RIGHT, padx=40)
        
        sh = tk.Frame(self.root, bg=COLOR_SECONDARY, height=40); sh.pack(side=tk.TOP, fill=tk.X); sh.pack_propagate(False)
        sh.columnconfigure(0, weight=1); sh.columnconfigure(1, weight=4); sh.columnconfigure(2, weight=5); sh.columnconfigure(3, weight=1)
        labels = ["KLÁVESA", "TYP CHYBY", "STAV (Nedopenená / Prestriekaná / Roztrhnutá)", "OPRAVA"]
        for i, txt in enumerate(labels):
            tk.Label(sh, text=txt, font=("Arial", 11, "bold"), fg="white", bg=COLOR_SECONDARY).grid(row=0, column=i, sticky="ew", pady=5)

    def aktualizuj_cas(self):
        t = datetime.datetime.now()
        if self.lbl_cas: self.lbl_cas.config(text=t.strftime("%H:%M"))
        if self.lbl_datum: self.lbl_datum.config(text=t.strftime("%d.%m.%Y"))
        if t.strftime("%H:%M:%S") in [x+":00" for x in CAS_RESETU]: self.reset_vsetko(automaticky=True)
        self.root.after(1000, self.aktualizuj_cas)

    def aktualizuj_header_info(self):
        self.lbl_uzivatel.config(text=self.aktualny_uzivatel_meno)

    def otvorit_menu(self, u, p):
        self.klavesnica_blokovana = True
        w = tk.Toplevel(self.root); w.geometry("600x650"); 
        w.attributes('-topmost', True); w.overrideredirect(True)
        w.configure(bg=COLOR_BG)
        
        # Center
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w.geometry(f"600x650+{int((sw-600)/2)}+{int((sh-650)/2)}")

        def close(): self.klavesnica_blokovana=False; w.destroy()
        
        tk.Label(w, text="MENU", font=("Arial", 18), bg=COLOR_BG).pack(pady=20)
        btns = [
            ("1. EXPORT", lambda: self.manualny_export(u,p), COLOR_ACCENT),
            ("2. RESET", lambda: [self.potvrdit_reset(u,p), close()], COLORS_WARN[1]),
            ("3. REŠTART", lambda: self.potvrdit_restart(u,p), COLORS_CRIT[1]),
            ("4. ZMENA OBSLUHY", lambda: [close(), self.vyziadat_pin("ZMENA", self.spracuj_prihlasenie)], "#607D8B"),
            ("5. UKONČIŤ", lambda: self.potvrdit_ukoncenie(u,p), "black")
        ]
        for t, c, col in btns:
            tk.Button(w, text=t, font=("Arial",14), bg=col, fg="white", command=c).pack(fill=tk.X, padx=50, pady=8)
        tk.Button(w, text="Zavrieť", command=close).pack(side=tk.BOTTOM, pady=20)
        
        w.wait_visibility()
        w.grab_set()
        w.focus_force()

    def potvrdit_ukoncenie(self, m, p):
        if messagebox.askyesno("Exit", "Vypnúť?"): 
            self.zapis_do_historie("UKONČENIE", "SYS", 0, m, p)
            self.root.destroy()
    def potvrdit_reset(self, m, p):
        if messagebox.askyesno("Reset", "Vymazať?"): self.reset_vsetko(False, m, p)
    def potvrdit_restart(self, m, p):
        if messagebox.askyesno("Reštart", "Reštartovať?"): 
            self.zapis_do_historie("RESTART", "SYS", 0, m, p)
            os.execl(sys.executable, sys.executable, *sys.argv)

    def centrovat_text(self, event, index):
        c = self.canvases[index]
        c.coords(self.texts[index], event.width/2, event.height/2)
        self.prekresli_bar(index)

    def reset_vsetko(self, automaticky=False, user_name=None, user_pin=None):
        meno = user_name if user_name else "AUTOMAT"
        pin = user_pin if user_pin else "0000"
        self.stats = {} 
        for i in range(self.pocet_riadkov):
            stara = self.counters[i].get()
            if stara > 0: self.zapis_do_historie("RESET_SAVE", NAZVY_TLACIDIEL[i], stara, user_name=meno, user_pin=pin)
            self.counters[i].set(0)
            self.sub_counters[i] = [0, 0, 0]
            self.row_history[i] = []
            self.undo_allowed[i] = False
            self.varovanie_zobrazene[i] = False
            self.prekresli_bar(i)
            self.aktualizuj_tlacidlo_spat(i)
        dovod = "AUTOMATICKÝ RESET" if automaticky else "MANUÁLNY RESET"
        self.zapis_do_historie(dovod, "Všetky", 0, user_name=meno, user_pin=pin)

    def vytvor_rozhranie(self):
        bf = tk.Frame(self.root, bg=COLOR_PRIMARY); bf.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Button(bf, text="MENU / MOŽNOSTI", font=("Arial",14,"bold"), bg=COLOR_ACCENT, fg="white", 
                  command=lambda: self.vyziadat_pin("PIN", self.overit_pin_pre_menu)).pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        mf = tk.Frame(self.root, bg=COLOR_BG); mf.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        mf.columnconfigure(0, weight=1); mf.columnconfigure(1, weight=4); mf.columnconfigure(2, weight=5); mf.columnconfigure(3, weight=1)

        for i in range(self.pocet_riadkov):
            mf.rowconfigure(i, weight=1)
            
            # Klávesa
            kt = KLAVESY_ZNAKY[i] if i<len(KLAVESY_ZNAKY) else ""
            tk.Label(mf, text=kt, font=("Arial",20,"bold"), fg="white", bg="#607D8B", width=3).grid(row=i, column=0, sticky="ns", padx=5, pady=4)
            
            # Tlačidlo - volá LEN OTVORENIE OKNA
            tk.Button(mf, text=NAZVY_TLACIDIEL[i], font=("Arial",18,"bold"), bg="white", relief="flat",
                      command=lambda x=i: self.otvorit_vyber_chyby(x)).grid(row=i, column=1, sticky="nsew", padx=5, pady=4)
            
            # Bar
            c = tk.Canvas(mf, bg="#E0E0E0", highlightthickness=0); c.grid(row=i, column=2, sticky="nsew", padx=5, pady=4)
            rects = []
            for _ in range(3):
                r = c.create_rectangle(0,0,0,0, outline="")
                rects.append(r)
            self.rectangles.append(rects)
            tid = c.create_text(0,0, text="0", font=("Arial",18,"bold"), fill="black")
            self.texts.append(tid)
            self.canvases.append(c)
            c.bind("<Configure>", lambda e, x=i: self.centrovat_text(e, x))
            
            # Späť
            b = tk.Button(mf, text="Späť", font=("Arial",11,"bold"), state=tk.DISABLED, command=lambda x=i: self.odobrat_kus(x))
            b.grid(row=i, column=3, sticky="nsew", padx=5, pady=4)
            self.back_buttons.append(b)

if __name__ == "__main__":
    root = tk.Tk()
    app = PocitadloApp(root)
    root.mainloop()