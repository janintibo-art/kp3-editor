"""mokteK KAOSS STUDIO Windows – first native desktop companion.
MIDI features are experimental and require physical testing on KP3/KP3+.
"""
import json
import array
import wave
import tempfile
import struct
import math
import winsound
from librarian import SampleLibrarian
from project_exchange import export_exchange, import_exchange
from common_project_v16 import export_project, inspect_project
from project_library_v17 import ProjectLibrary
from synth_factory import SynthFactory
from sequencer_ui import TribeSequencer
from korg_connection import KorgConnectionCenter
import os
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

VERSION = "17.0"
BG, PANEL, STEEL, RED, TEXT, MUTED = "#100f10", "#211d1a", "#887766", "#ff493e", "#e9dac2", "#b9a99b"
DARK_RED, GLOW, RACK, GRID = "#381315", "#ff8272", "#332b25", "#702126"
DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "mokteK-Kaoss-Studio"
try:
    import mido
except ImportError:
    mido = None

class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"mokteK • KAOSS STUDIO Windows V{VERSION}")
        self.geometry("1240x790")
        self.minsize(950, 640)
        self.configure(bg=BG)
        self.port = None
        self.recording = False
        self.playing = False
        self.motion = []
        self.record_start = 0.0
        self.play_start = 0.0
        self.play_index = 0
        self.gate = False
        self.last_xy = (64, 64)
        self.taps = []
        self.program = 0
        self.model = tk.StringVar(value="KP3+")
        self.channel = tk.IntVar(value=1)
        self.bpm = tk.IntVar(value=174)
        self.hold = tk.BooleanVar(value=False)
        self.loop = tk.BooleanVar(value=False)
        self.port_name = tk.StringVar(value="")
        self.status = tk.StringVar(value="SIMULATION · Aucun port MIDI connecté")
        self.coords = tk.StringVar(value="X 64   Y 64")
        self.program_label = tk.StringVar(value="P.001")
        self.motion_info = tk.StringVar(value="Aucun mouvement enregistré")
        self.message = tk.StringVar(value="Les fonctions MIDI nécessitent un essai sur le matériel réel.")
        self.option_add("*Font", "Segoe UI 10")
        self.option_add("*TCombobox*Listbox.background", PANEL)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground="#1a1515", background=RACK, foreground=TEXT, arrowcolor=RED, bordercolor=STEEL)
        self._ui()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(50, self.tick)
        self.refresh_ports()

    def text(self, parent, value, size=10, fg=TEXT, bold=False):
        return tk.Label(parent, text=value, fg=fg, bg=parent.cget("bg"), font=("Segoe UI", size, "bold" if bold else "normal"))

    def btn(self, parent, label, command, width=None):
        return tk.Button(parent, text=label, command=command, bg="#392a28", fg=TEXT,
                         activebackground="#75201c", activeforeground="white",
                         relief="flat", borderwidth=1, highlightthickness=1, highlightbackground=STEEL,
                         padx=10, pady=10, cursor="hand2", width=width)

    def panel(self, parent, title):
        f = tk.Frame(parent, bg=PANEL, highlightbackground=STEEL, highlightthickness=2, padx=12, pady=12)
        self.text(f, title, 11, TEXT, True).pack(anchor="w", pady=(0, 10))
        tk.Frame(f, bg=RED, height=2).pack(fill="x", pady=(0, 9))
        return f

    def _ui(self):
        top = tk.Frame(self, bg=RACK, padx=18, pady=12)
        top.pack(fill="x")
        self.text(top, "mokteK  //  KAOSS STUDIO", 23, RED, True).pack(side="left")
        self.text(top, f"WINDOWS V{VERSION}  •  LIVE", 11, MUTED, True).pack(side="right")
        tk.Frame(self, bg=RED, height=3).pack(fill="x")
        tk.Label(self, textvariable=self.status, bg=BG, fg="#8fe49a", anchor="w", padx=18, pady=7, font=("Consolas", 10, "bold")).pack(fill="x")

        body = tk.Frame(self, bg=BG, padx=12, pady=10)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=1, minsize=200)
        body.grid_columnconfigure(1, weight=4, minsize=420)
        body.grid_columnconfigure(2, weight=1, minsize=200)
        body.grid_rowconfigure(0, weight=1)
        left = self.panel(body, "APPAREIL / PROGRAMME")
        left.grid(row=0, column=0, sticky="nsew", padx=5)
        tk.OptionMenu(left, self.model, "KP3", "KP3+").pack(fill="x")
        self.text(left, "Programme MIDI", 10, MUTED).pack(anchor="w", pady=(18, 3))
        self.text(left, self.program_label, 27, RED, True).pack(anchor="w") if False else None
        tk.Label(left, textvariable=self.program_label, font=("Consolas", 25, "bold"), fg=RED, bg=PANEL).pack(anchor="w")
        line = tk.Frame(left, bg=PANEL)
        line.pack(fill="x")
        self.btn(line, "−", lambda: self.change_program(-1)).pack(side="left", expand=True, fill="x")
        self.btn(line, "+", lambda: self.change_program(1)).pack(side="left", expand=True, fill="x")
        self.text(left, "BPM local (pas d'horloge MIDI)", 10, MUTED).pack(anchor="w", pady=(18, 3))
        tk.Label(left, textvariable=self.bpm, font=("Consolas", 25, "bold"), fg=RED, bg=PANEL).pack(anchor="w")
        line = tk.Frame(left, bg=PANEL)
        line.pack(fill="x")
        self.btn(line, "−", lambda: self.bpm.set(max(40, self.bpm.get()-1))).pack(side="left", expand=True, fill="x")
        self.btn(line, "+", lambda: self.bpm.set(min(300, self.bpm.get()+1))).pack(side="left", expand=True, fill="x")
        self.btn(left, "TAP TEMPO", self.tap).pack(fill="x", pady=(8, 0))
        self.btn(left, "SAUVER SESSION", self.save_session).pack(fill="x", pady=(28, 4))
        self.btn(left, "OUVRIR SESSION", self.open_session).pack(fill="x")
        self.btn(left, "🎵 SAMPLE STUDIO", self.open_sample_studio).pack(fill="x", pady=(18, 0))
        self.btn(left, "▦ SAMPLE LIBRARIAN", self.open_librarian).pack(fill="x", pady=(7, 0))
        self.btn(left, "♫ SYNTH FACTORY", self.open_synth_factory).pack(fill="x", pady=(7, 0))
        self.btn(left, "▦ TRIBE SEQUENCER", self.open_sequencer).pack(fill="x", pady=(7, 0))
        self.btn(left, "◉ KORG CONNECTION", self.open_korg_center).pack(fill="x", pady=(7, 0))
        self.btn(left, "⇄ ÉCHANGES ANDROID / PC", self.open_exchange).pack(fill="x", pady=(7, 0))
        self.btn(left, "▣ PROJET COMMUN V16", self.open_common_project).pack(fill="x", pady=(7, 0))
        self.btn(left, "▣ MES PROJETS V17", self.open_project_library).pack(fill="x", pady=(7, 0))

        center = self.panel(body, "◉  TOUCH PAD   •   LIVE CONTROL")
        center.grid(row=0, column=1, sticky="nsew", padx=5)
        center.grid_rowconfigure(1, weight=1)
        center.grid_columnconfigure(0, weight=1)
        self.text(center, "Contrôle XY expérimental • CC 12 / CC 13 / Touch CC 92", 9, MUTED).grid(row=0, column=0, sticky="w")
        self.canvas = tk.Canvas(center, bg="#19090c", highlightbackground=RED, highlightthickness=3, cursor="crosshair", relief="flat")
        self.canvas.grid(row=1, column=0, sticky="nsew", pady=8)
        self.canvas.bind("<Configure>", lambda e: self.draw_pad())
        self.canvas.bind("<ButtonPress-1>", self.xy_down)
        self.canvas.bind("<B1-Motion>", self.xy_move)
        self.canvas.bind("<ButtonRelease-1>", self.xy_up)
        bottom = tk.Frame(center, bg=PANEL)
        bottom.grid(row=2, column=0, sticky="ew")
        tk.Label(bottom, textvariable=self.coords, fg=TEXT, bg=PANEL).pack(side="left")
        tk.Checkbutton(bottom, text="HOLD", variable=self.hold, command=self.hold_change,
                       bg=PANEL, fg=TEXT, activebackground=PANEL, selectcolor=BG).pack(side="right")
        banks = tk.Frame(center, bg=PANEL)
        banks.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        for i, name in enumerate("ABCD"):
            b = self.btn(banks, name, lambda: None)
            b.configure(bg="#651d1d", activebackground=RED, font=("Segoe UI", 17, "bold"), pady=12)
            b.pack(side="left", expand=True, fill="x", padx=4)
            b.bind("<ButtonPress-1>", lambda e, note=36+i: self.note(note, True))
            b.bind("<ButtonRelease-1>", lambda e, note=36+i: self.note(note, False))
            b.bind("<Leave>", lambda e, note=36+i: self.note(note, False))

        right = self.panel(body, "FX / MIDI / MOTION")
        right.grid(row=0, column=2, sticky="nsew", padx=5)
        self.depth = tk.IntVar(value=100)
        self.level = tk.IntVar(value=100)
        for title, variable, cc in [("FX DEPTH", self.depth, 94), ("LEVEL", self.level, 93)]:
            self.text(right, title, 10, MUTED).pack(anchor="w", pady=(8, 0))
            tk.Scale(right, from_=0, to=127, orient="horizontal", variable=variable,
                     command=lambda value, controller=cc: self.send_cc(controller, int(float(value))),
                     bg=PANEL, fg=TEXT, troughcolor="#54211e", highlightthickness=0,
                     activebackground=RED).pack(fill="x")
        self.text(right, "MIDI OUT", 10, MUTED, True).pack(anchor="w", pady=(12, 4))
        self.device_combo = ttk.Combobox(right, textvariable=self.port_name, state="readonly")
        self.device_combo.pack(fill="x")
        self.btn(right, "ACTUALISER PORTS", self.refresh_ports).pack(fill="x", pady=(4, 2))
        self.btn(right, "CONNECTER", self.connect).pack(fill="x", pady=2)
        self.btn(right, "DÉCONNECTER", self.disconnect).pack(fill="x", pady=2)
        self.text(right, "CANAL MIDI", 10, MUTED).pack(anchor="w", pady=(10, 2))
        tk.Spinbox(right, from_=1, to=16, textvariable=self.channel, width=5).pack(anchor="w")
        self.text(right, "XY MOTION", 10, MUTED, True).pack(anchor="w", pady=(12, 4))
        actions = tk.Frame(right, bg=PANEL)
        actions.pack(fill="x")
        self.btn(actions, "REC", self.toggle_record).pack(side="left", expand=True, fill="x")
        self.btn(actions, "▶", self.play).pack(side="left", expand=True, fill="x")
        self.btn(actions, "■", self.stop).pack(side="left", expand=True, fill="x")
        tk.Checkbutton(right, text="Boucle", variable=self.loop, bg=PANEL, fg=TEXT,
                       selectcolor=BG, activebackground=PANEL).pack(anchor="w")
        tk.Label(right, textvariable=self.motion_info, bg=PANEL, fg=MUTED, wraplength=180).pack(anchor="w")
        footer = tk.Frame(self, bg=BG, padx=18, pady=8)
        footer.pack(fill="x")
        tk.Label(footer, textvariable=self.message, bg=BG, fg=MUTED, anchor="w").pack(fill="x")
        self.text(footer, "mokteK  /  KAOSS STUDIO  •  Windows  •  MIDI EXPÉRIMENTAL  •  non affilié à Korg", 9, STEEL).pack(anchor="e")

    def send(self, typ, **data):
        if self.port is None or mido is None:
            return
        try:
            chan = min(16, max(1, int(self.channel.get()))) - 1
            self.port.send(mido.Message(typ, channel=chan, **data))
        except Exception as exc:
            self.message.set(f"Erreur MIDI : {exc}")
            self.disconnect()

    def send_cc(self, control, value):
        self.send("control_change", control=control, value=min(127, max(0, value)))

    def note(self, n, on):
        self.send("note_on" if on else "note_off", note=n, velocity=127 if on else 0)

    def change_program(self, delta):
        cap = 127 if self.model.get() == "KP3" else 149
        self.program = min(cap, max(0, self.program + delta))
        self.program_label.set(f"P.{self.program+1:03d}")
        if self.program <= 127:
            self.send("program_change", program=self.program)
        else:
            self.message.set("Programmes 129–150 KP3+ : protocole MIDI non validé, aucun envoi.")

    def tap(self):
        now = time.monotonic()
        if self.taps and now - self.taps[-1] > 3:
            self.taps.clear()
        self.taps.append(now)
        self.taps = self.taps[-5:]
        if len(self.taps) > 1:
            elapsed = self.taps[-1] - self.taps[0]
            if elapsed > 0:
                self.bpm.set(min(300, max(40, round(60 * (len(self.taps)-1) / elapsed))))

    def draw_pad(self):
        c = self.canvas
        c.delete("all")
        w, h = max(1, c.winfo_width()), max(1, c.winfo_height())
        import math
        # Maillage rouge comme le pad Android Compose.
        for i in range(1, 8):
            gx = w*i/8
            gy = h*i/8
            c.create_line(gx, 0, gx, h, fill=GRID, width=1)
            c.create_line(0, gy, w, gy, fill=GRID, width=1)
        # Motif circulaire/spirale discret au centre, visible au repos.
        points = []
        radius = min(w, h) * .40
        for i in range(151):
            t = i/150
            angle = t*15.7
            points.extend((w/2+math.cos(angle)*radius*t, h/2+math.sin(angle)*radius*t))
        c.create_line(*points, fill="#512022", width=2, smooth=False)
        px = self.last_xy[0]/127*w
        py = (127-self.last_xy[1])/127*h
        c.create_line(px, 0, px, h, fill="#a62b2b", width=2)
        c.create_line(0, py, w, py, fill="#a62b2b", width=2)
        c.create_oval(px-40, py-40, px+40, py+40, outline="#77262c", width=2)
        c.create_oval(px-27, py-27, px+27, py+27, outline="#a83136", width=2)
        c.create_oval(px-17, py-17, px+17, py+17, outline=RED, width=3)
        c.create_oval(px-7, py-7, px+7, py+7, fill=TEXT, outline="")
        c.create_rectangle(1, 1, w-2, h-2, outline=STEEL, width=2)

    def set_xy(self, x, y, gate=None, record=True):
        self.last_xy = (x, y)
        self.coords.set(f"X {x:03d}   Y {y:03d}")
        self.draw_pad()
        self.send_cc(12, x)
        self.send_cc(13, y)
        if gate is not None:
            self.send_cc(92, 127 if gate else 0)
        if record and self.recording and len(self.motion) < 10000:
            self.motion.append([round(time.monotonic()-self.record_start, 3), x, y, gate])
            self.motion_info.set(f"{len(self.motion)} événements")

    def cursor_xy(self, event, gate=None):
        w, h = max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height())
        x = min(127, max(0, round(event.x/w*127)))
        y = min(127, max(0, round((1-event.y/h)*127)))
        self.set_xy(x, y, gate)

    def xy_down(self, event):
        self.stop()
        self.gate = True
        self.cursor_xy(event, True)

    def xy_move(self, event):
        if self.gate:
            self.cursor_xy(event)

    def xy_up(self, event):
        if self.gate:
            self.gate = False
            if not self.hold.get():
                self.set_xy(*self.last_xy, gate=False)

    def hold_change(self):
        self.send_cc(95, 127 if self.hold.get() else 0)
        if not self.hold.get() and not self.gate:
            self.send_cc(92, 0)

    def refresh_ports(self):
        try:
            ports = list(mido.get_output_names()) if mido else []
        except Exception as exc:
            ports = []
            self.message.set(f"MIDI indisponible : {exc}")
        self.device_combo["values"] = ports
        if ports and self.port_name.get() not in ports:
            self.port_name.set(ports[0])
        if not ports:
            self.port_name.set("")
            if not mido:
                self.message.set("MIDI nécessite mido et python-rtmidi ; la simulation reste utilisable.")

    def connect(self):
        if not self.port_name.get() or not mido:
            self.message.set("Aucun port MIDI sélectionné.")
            return
        self.disconnect()
        try:
            self.port = mido.open_output(self.port_name.get())
            self.status.set(f"MIDI CONNECTÉ  •  {self.port_name.get()}")
        except Exception as exc:
            self.message.set(f"Connexion impossible : {exc}")

    def disconnect(self):
        if self.port:
            try:
                self.port.close()
            except Exception:
                pass
        self.port = None
        self.status.set("SIMULATION · Aucun port MIDI connecté")

    def toggle_record(self):
        if self.recording:
            self.recording = False
            self.message.set("Enregistrement XY terminé.")
        else:
            self.stop()
            self.motion = []
            self.recording = True
            self.record_start = time.monotonic()
            self.motion_info.set("REC • 0 événements")
            self.message.set("REC • Bouge sur la surface XY.")

    def play(self):
        if self.recording:
            self.recording = False
        if not self.motion:
            self.message.set("Aucun mouvement XY à rejouer.")
            return
        self.stop()
        self.playing = True
        self.play_index = 0
        self.play_start = time.monotonic()
        self.message.set("Lecture XY en cours.")

    def stop(self):
        self.playing = False
        self.send_cc(92, 0)

    def tick(self):
        if self.playing:
            elapsed = time.monotonic() - self.play_start
            while self.play_index < len(self.motion) and self.motion[self.play_index][0] <= elapsed:
                _, x, y, gate = self.motion[self.play_index]
                self.set_xy(x, y, gate, record=False)
                self.play_index += 1
            if self.play_index == len(self.motion):
                self.send_cc(92, 0)
                if self.loop.get():
                    self.play_index = 0
                    self.play_start = time.monotonic()
                else:
                    self.playing = False
        self.after(30, self.tick)

    def save_session(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        dest = filedialog.asksaveasfilename(initialdir=str(DATA_DIR), defaultextension=".json",
             filetypes=[("Session mokteK JSON", "*.json")], initialfile="session-moktek.json")
        if not dest:
            return
        payload = {"format": "moktek-windows-session-v1", "model": self.model.get(),
                   "program": self.program, "bpm": self.bpm.get(), "channel": self.channel.get(),
                   "depth": self.depth.get(), "level": self.level.get(), "motion": self.motion}
        try:
            Path(dest).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            self.message.set("Session sauvegardée sur le PC.")
        except Exception as exc:
            messagebox.showerror("Sauvegarde", str(exc))

    def open_session(self):
        path = filedialog.askopenfilename(initialdir=str(DATA_DIR), filetypes=[("Session mokteK JSON", "*.json")])
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            if payload.get("format") != "moktek-windows-session-v1":
                raise ValueError("Format de session PC non reconnu")
            self.stop()
            self.recording = False
            self.model.set(payload["model"] if payload["model"] in ("KP3", "KP3+") else "KP3")
            self.program = min(149 if self.model.get()=="KP3+" else 127, max(0,int(payload["program"])))
            self.program_label.set(f"P.{self.program+1:03d}")
            self.bpm.set(min(300, max(40, int(payload["bpm"]))))
            self.channel.set(min(16, max(1, int(payload["channel"]))))
            self.depth.set(min(127, max(0, int(payload["depth"]))))
            self.level.set(min(127, max(0, int(payload["level"]))))
            clean = []
            for item in payload.get("motion", [])[:10000]:
                if len(item) != 4:
                    raise ValueError("Mouvement invalide")
                t, x, y, gate = item
                clean.append([max(0.0,float(t)), min(127,max(0,int(x))), min(127,max(0,int(y))), gate if gate in (True,False,None) else None])
            self.motion = sorted(clean, key=lambda p:p[0])
            self.motion_info.set(f"{len(self.motion)} événements")
            self.message.set("Session restaurée localement, sans envoi de programme MIDI.")
        except Exception as exc:
            messagebox.showerror("Session invalide", str(exc))


    def open_exchange(self):
        win=tk.Toplevel(self)
        win.title("mokteK • Échanges Android / Windows V14")
        win.geometry("760x390")
        win.configure(bg=BG)
        body=self.panel(win,"ÉCHANGES DE PROJETS • SANS ÉCRITURE SUR KORG")
        body.pack(fill="both",expand=True,padx=15,pady=14)
        self.text(body,"Transfert WAV et conversion réelle du rythme 6 pistes (BPM, pas, volumes). Les paramètres avancés sont préservés dans les fichiers originaux.",10,MUTED).pack(anchor="w",pady=5)
        self.text(body,"Android → PC : importer une sauvegarde mokteK Android V14–V18 ou un ZIP V13.",10,MUTED).pack(anchor="w",pady=5)
        self.text(body,"PC → Android : exporter un ZIP V13, puis l'importer dans Korg File Center.",10,MUTED).pack(anchor="w",pady=5)
        def export():
            dest=filedialog.asksaveasfilename(parent=win,defaultextension=".zip",initialfile="moktek_echange_v14.zip",filetypes=[("Archive ZIP","*.zip")])
            if not dest:return
            try:
                session=None;pattern=None
                if messagebox.askyesno("Session PC", "Ajouter une session Windows JSON au ZIP ?", parent=win):
                    session=filedialog.askopenfilename(parent=win,filetypes=[("Sessions JSON","*.json")])
                    if not session:return
                if messagebox.askyesno("Pattern PC", "Ajouter un pattern Windows JSON au ZIP ?", parent=win):
                    pattern=filedialog.askopenfilename(parent=win,filetypes=[("Patterns JSON","*.json")])
                    if not pattern:return
                number=export_exchange(DATA_DIR,dest,session=session,pattern=pattern)
                messagebox.showinfo("Export terminé",f"{number} samples WAV exportés. Aucun transfert matériel.",parent=win)
            except Exception as exc:messagebox.showerror("Export impossible",str(exc),parent=win)
        def importer():
            src=filedialog.askopenfilename(parent=win,filetypes=[("Archives ZIP","*.zip")])
            if not src:return
            if not messagebox.askyesno("Importer sans remplacer", "Les samples seront ajoutés aux emplacements libres. Aucun emplacement existant ne sera remplacé. Continuer ?",parent=win):return
            try:
                result=import_exchange(DATA_DIR,src)
                messagebox.showinfo("Import terminé",f"{result['samples']} samples ajoutés ; {result['preserved']} fichiers de métadonnées conservés dans exchange_inbox.\nRouvrir Sample Librarian pour rafraîchir.",parent=win)
            except Exception as exc:messagebox.showerror("Import annulé",str(exc),parent=win)
        self.btn(body,"EXPORTER POUR ANDROID • ZIP V14",export).pack(fill="x",pady=8)
        self.btn(body,"IMPORTER DEPUIS ANDROID • ZIP",importer).pack(fill="x",pady=8)
        self.text(body,"Pattern converti : disponible dans exchange_inbox, puis OUVRIR PATTERN dans Tribe Sequencer. Sons/swing/rolls Android non pris en charge.",9,MUTED).pack(anchor="w",pady=6)

    def open_project_library(self):
        win=tk.Toplevel(self)
        win.title('mokteK • MES PROJETS V17')
        win.geometry('890x590');win.configure(bg=BG)
        library=ProjectLibrary(DATA_DIR)
        head=self.panel(win,'BIBLIOTHÈQUE DE PROJETS  •  V17')
        head.pack(fill='both',expand=True,padx=14,pady=12)
        self.text(head,'Archives ZIP vérifiées • aucune modification du matériel Korg • récupération locale',10,MUTED).pack(anchor='w')
        browser=tk.Listbox(head,bg='#1b1515',fg=TEXT,selectbackground='#75201c',selectforeground='white',height=13,font=('Consolas',11))
        browser.pack(fill='both',expand=True,pady=12)
        status=tk.StringVar(value='Sélectionne un projet pour l’exporter ou le dupliquer.')
        tk.Label(head,textvariable=status,fg=MUTED,bg=PANEL,wraplength=780,justify='left').pack(fill='x')
        selected=[]
        def refresh(select_id=None):
            selected[:]=library.list()
            browser.delete(0,'end')
            for i,rec in enumerate(selected):
                browser.insert('end',f"{rec['title'][:39]:39}  {rec['created'][:10]}   {rec['samples']:2} WAV")
                if rec['id']==select_id:browser.selection_set(i)
            status.set(f'{len(selected)} projet(s) sauvegardé(s) sur ce PC.')
        def chosen():
            cur=browser.curselection()
            if not cur:raise ValueError('Sélectionne un projet')
            return selected[cur[0]]
        def execute(fn):
            try:fn()
            except Exception as exc:messagebox.showerror('Opération interrompue',str(exc),parent=win)
        def add():
            src=filedialog.askopenfilename(parent=win,title='Importer un projet commun V16',filetypes=[('Projets ZIP','*.zip')])
            if not src:return
            rec=library.archive(src);refresh(rec['id'])
        def export():
            r=chosen();target=filedialog.asksaveasfilename(parent=win,defaultextension='.zip',initialfile='moktek_'+r['id'][:8]+'.zip',filetypes=[('ZIP','*.zip')])
            if target:library.export(r['id'],target);status.set('Copie exportée : '+target)
        def duplicate():
            rec=library.duplicate(chosen()['id']);refresh(rec['id'])
        def remove():
            r=chosen()
            if messagebox.askyesno('Retirer du catalogue','Retirer ce projet ? Une copie restera dans le dossier recovery.',parent=win):
                library.remove_from_catalogue(r['id']);refresh()
        def restore():
            r=chosen();path=library.locate(r['id'])
            info=inspect_project(path)
            if messagebox.askyesno('Récupération du projet',
                f"{info['title']} • {info['samples']} WAV.\n\nImporter les WAV dans les emplacements libres ? Les patterns et presets seront conservés dans la boîte de réception pour import manuel. Aucun écrasement des banques existantes.",parent=win):
                result=import_exchange(DATA_DIR,path)
                status.set(f"Récupération : {result['samples']} WAV ajoutés ; {result['preserved']} fichiers préservés.")
        buttons=tk.Frame(head,bg=PANEL);buttons.pack(fill='x',pady=8)
        for label,fn in [('AJOUTER ZIP',add),('EXPORTER',export),('DUPLIQUER',duplicate),('RÉCUPÉRER',restore),('RETIRER',remove)]:
            self.btn(buttons,label,lambda f=fn:execute(f)).pack(side='left',expand=True,fill='x',padx=3)
        refresh()

    def open_common_project(self):
        win=tk.Toplevel(self)
        win.title("mokteK • Projet commun Windows / Android V16")
        win.geometry("740x440")
        win.configure(bg=BG)
        body=self.panel(win,"PROJET COMMUN V16  •  ARCHIVE SÉCURISÉE")
        body.pack(fill="both",expand=True,padx=16,pady=15)
        self.text(body,"Un ZIP regroupe les WAV, un pattern, un preset et les informations du morceau.",10,MUTED).pack(anchor="w",pady=6)
        self.text(body,"Import sans écrasement • les réglages Windows avancés restent conservés dans les JSON.",10,MUTED).pack(anchor="w",pady=6)
        title=tk.StringVar(value="Mon projet mokteK")
        tk.Entry(body,textvariable=title,bg="#1b1515",fg=TEXT,insertbackground=TEXT).pack(fill="x",pady=8)
        def pick(label):
            if messagebox.askyesno(label,"Ajouter un fichier JSON "+label+" au projet ?",parent=win):
                return filedialog.askopenfilename(parent=win,filetypes=[("Preset ZIP / JSON","*.zip *.json")] if "Synth Factory" in label else [("JSON","*.json")])
            return None
        def export():
            dest=filedialog.asksaveasfilename(parent=win,defaultextension=".zip",initialfile="moktek_projet_v16.zip",filetypes=[("ZIP","*.zip")])
            if not dest:return
            try:
                session=pick("session Windows")
                pattern=pick("pattern Windows")
                synth=pick("preset portable Synth Factory V15 (ZIP ou JSON)")
                report=export_project(DATA_DIR,dest,title.get(),session=session,pattern=pattern,synth=synth)
                ProjectLibrary(DATA_DIR).archive(dest)
                messagebox.showinfo("Projet exporté",f"{report['samples']} WAV inclus. Pattern : {report['pattern']}. Preset : {report['synth']}.\nAucun envoi au Korg.",parent=win)
            except Exception as exc:messagebox.showerror("Export impossible",str(exc),parent=win)
        def importer():
            src=filedialog.askopenfilename(parent=win,filetypes=[("ZIP","*.zip")])
            if not src:return
            try:
                info=inspect_project(src)
                preview=f"{info['title']} ({info['origin']})\nWAV : {info['samples']} • Pattern : {info['pattern']} • Preset : {info['synth']}\nImporter les WAV dans les emplacements libres et conserver les JSON en boîte de réception ?"
                if not messagebox.askyesno("Prévisualisation V16",preview,parent=win):return
                result=import_exchange(DATA_DIR,src)
                ProjectLibrary(DATA_DIR).archive(src)
                messagebox.showinfo("Import terminé",f"{result['samples']} WAV ajoutés et {result['preserved']} documents conservés dans exchange_inbox.\nLes patterns doivent être ouverts manuellement. Aucun écrasement.",parent=win)
            except Exception as exc:messagebox.showerror("Projet non importé",str(exc),parent=win)
        self.btn(body,"EXPORTER PROJET WINDOWS → ANDROID (ZIP V16)",export).pack(fill="x",pady=10)
        self.btn(body,"IMPORTER PROJET ANDROID → WINDOWS (ZIP V16)",importer).pack(fill="x",pady=6)
        self.text(body,"Le format commun n'est pas une sauvegarde de mémoire Korg et ne lance aucun transfert matériel.",9,MUTED).pack(anchor="w",pady=8)

    def open_sample_studio(self):
        """Local 16-bit PCM WAV editor; never sends proprietary data to hardware."""
        if hasattr(self, "sample_window") and self.sample_window.winfo_exists():
            self.sample_window.lift()
            return
        win = tk.Toplevel(self)
        self.sample_window = win
        win.title("mokteK // SAMPLE STUDIO • Windows V3")
        win.geometry("1000x650")
        win.minsize(760, 570)
        win.configure(bg=BG)
        win.transient(self)
        state = {"samples": None, "rate": 44100, "channels": 1, "frames": 0, "filename": None, "preview": None}
        title = tk.Frame(win, bg=RACK, padx=18, pady=13)
        title.pack(fill="x")
        self.text(title, "SAMPLE STUDIO  //  WAV LAB", 21, RED, True).pack(side="left")
        self.text(title, "ÉDITION LOCALE • AUCUN TRANSFERT KP3", 9, MUTED).pack(side="right")
        tk.Frame(win, bg=RED, height=3).pack(fill="x")
        details = tk.StringVar(value="Ouvre un WAV PCM 16 bits (mono ou stéréo) pour commencer.")
        info = tk.Label(win, textvariable=details, bg=BG, fg=TEXT, anchor="w", padx=18, pady=12)
        info.pack(fill="x")
        frame = self.panel(win, "FORME D’ONDE  •  APERÇU")
        frame.pack(fill="both", expand=True, padx=15, pady=8)
        waveview = tk.Canvas(frame, bg="#19090c", highlightthickness=2, highlightbackground=RED, height=230)
        waveview.pack(fill="both", expand=True, pady=(0, 10))
        begin = tk.DoubleVar(value=0.0)
        end = tk.DoubleVar(value=100.0)
        reverse = tk.BooleanVar(value=False)
        normalize = tk.BooleanVar(value=False)
        status = tk.StringVar(value="Aucun échantillon chargé")
        def selection():
            if state["samples"] is None:
                return 0, 0
            n=state["frames"]
            return round(min(begin.get(),end.get())/100*n), round(max(begin.get(),end.get())/100*n)
        def render():
            waveview.delete("all")
            w=max(1,waveview.winfo_width());h=max(1,waveview.winfo_height())
            for k in range(1,8):
                xx=k*w/8
                waveview.create_line(xx,0,xx,h,fill=GRID)
            waveview.create_line(0,h/2,w,h/2,fill=STEEL)
            if state["samples"] is None:return
            arr=state["samples"];ch=state["channels"];frames=state["frames"]
            # bounded overview cost independent of input duration
            bins=min(int(w),900)
            for i in range(bins):
                lo=i*frames//bins;hi=max(lo+1,(i+1)*frames//bins)
                stride=max(1,(hi-lo)//45)
                peak=0
                for f in range(lo,hi,stride):
                    for c in range(ch):
                        peak=max(peak,abs(arr[f*ch+c]))
                ph=(h*.46)*peak/32768
                px=(i+.5)*w/bins
                waveview.create_line(px,h/2-ph,px,h/2+ph,fill=RED)
            a,b=selection()
            x1=a/max(1,frames)*w;x2=b/max(1,frames)*w
            waveview.create_rectangle(0,0,x1,h,fill=BG,stipple="gray50",outline="")
            waveview.create_rectangle(x2,0,w,h,fill=BG,stipple="gray50",outline="")
            waveview.create_line(x1,0,x1,h,fill="#f2da91",width=2)
            waveview.create_line(x2,0,x2,h,fill="#f2da91",width=2)
        def selection_update(_=None):
            if state["samples"] is not None:
                a,b=selection()
                status.set(f"Sélection : {a/state['rate']:.2f}s – {b/state['rate']:.2f}s  ({(b-a)/state['rate']:.2f}s)")
            render()
        def load_file():
            path=filedialog.askopenfilename(parent=win,filetypes=[("WAV audio", "*.wav")])
            if not path:return
            try:
                with wave.open(path,"rb") as wav:
                    if wav.getcomptype()!="NONE" or wav.getsampwidth()!=2 or wav.getnchannels() not in (1,2):
                        raise ValueError("Format requis : WAV PCM 16 bits mono ou stéréo")
                    frames=wav.getnframes();channels=wav.getnchannels();rate=wav.getframerate()
                    if not 8000<=rate<=192000:raise ValueError("Fréquence d’échantillonnage non prise en charge")
                    if frames==0:raise ValueError("Fichier WAV vide")
                    if frames*channels>30_000_000:raise ValueError("WAV trop volumineux pour cette version (30 M échantillons maximum)")
                    raw=wav.readframes(frames)
                samples=array.array("h")
                samples.frombytes(raw)
                if sys.byteorder!="little":samples.byteswap()
                if len(samples)!=frames*channels:raise ValueError("Données audio incomplètes")
                state.update(samples=samples,rate=rate,channels=channels,frames=frames,filename=path)
                begin.set(0);end.set(100)
                details.set(f"{Path(path).name}  •  {rate} Hz  •  {channels} canal(aux)  •  {frames/rate:.2f} s")
                selection_update()
            except Exception as exc:messagebox.showerror("Import WAV",str(exc),parent=win)
        def processed_audio():
            arr=state["samples"]
            if arr is None:raise ValueError("Importer d’abord un WAV")
            a,b=selection();ch=state["channels"]
            if b<=a:raise ValueError("La sélection est vide")
            # array slicing preserves contiguous interleaved channels
            sub=arr[a*ch:b*ch]
            if reverse.get():
                ordered=array.array("h")
                for frame in range(b-a-1,-1,-1):ordered.extend(sub[frame*ch:(frame+1)*ch])
                sub=ordered
            if normalize.get():
                peak=max((abs(int(v)) for v in sub),default=0)
                if peak>0:
                    factor=32767.0/peak
                    sub=array.array("h",(max(-32768,min(32767,round(int(v)*factor))) for v in sub))
            if sys.byteorder!="little":sub.byteswap()
            return sub.tobytes()
        def write_wav(path,raw):
            with wave.open(str(path),"wb") as wav:
                wav.setnchannels(state["channels"])
                wav.setsampwidth(2)
                wav.setframerate(state["rate"])
                wav.writeframes(raw)
        def preview():
            if state["samples"] is None:return
            try:
                raw=processed_audio()
                if len(raw)>state["rate"]*state["channels"]*2*30:
                    raw=raw[:state["rate"]*state["channels"]*2*30]
                    status.set("Préécoute limitée aux 30 premières secondes de la sélection")
                winsound.PlaySound(None,winsound.SND_PURGE)
                if state["preview"]:
                    try:Path(state["preview"]).unlink(missing_ok=True)
                    except OSError:pass
                with tempfile.NamedTemporaryFile(suffix=".wav",delete=False) as f:path=Path(f.name)
                state["preview"]=str(path)
                write_wav(path,raw)
                winsound.PlaySound(str(path),winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception as exc:messagebox.showerror("Écoute",str(exc),parent=win)
        def stop_preview():
            winsound.PlaySound(None,winsound.SND_PURGE)
        def export():
            if state["samples"] is None:return
            name=Path(state["filename"]).stem+"_moktek.wav"
            path=filedialog.asksaveasfilename(parent=win,defaultextension=".wav",initialfile=name,filetypes=[("WAV PCM 16 bits","*.wav")])
            if not path:return
            try:
                write_wav(path,processed_audio())
                status.set(f"Export WAV terminé : {Path(path).name}")
            except Exception as exc:messagebox.showerror("Export WAV",str(exc),parent=win)
        sliders=tk.Frame(frame,bg=PANEL)
        sliders.pack(fill="x")
        for label,var in (("Début (%)",begin),("Fin (%)",end)):
            row=tk.Frame(sliders,bg=PANEL)
            row.pack(fill="x",pady=3)
            self.text(row,label,10,MUTED).pack(side="left")
            tk.Scale(row,from_=0,to=100,resolution=.1,orient="horizontal",variable=var,
                     command=selection_update,bg=PANEL,fg=TEXT,troughcolor=DARK_RED,
                     activebackground=RED,highlightthickness=0).pack(side="right",fill="x",expand=True)
        toggles=tk.Frame(frame,bg=PANEL)
        toggles.pack(fill="x",pady=8)
        for label,var in (("Inverser l’extrait",reverse),("Normaliser le volume",normalize)):
            tk.Checkbutton(toggles,text=label,variable=var,bg=PANEL,fg=TEXT,selectcolor=BG,
                           activebackground=PANEL).pack(side="left",padx=(0,20))
        actions=tk.Frame(win,bg=BG,padx=14,pady=7)
        actions.pack(fill="x")
        for label,fn in (("IMPORTER WAV",load_file),("▶ ÉCOUTER",preview),("■ STOP",stop_preview),("EXPORTER WAV",export)):
            self.btn(actions,label,fn).pack(side="left",padx=5)
        tk.Label(win,textvariable=status,bg=BG,fg=MUTED,padx=18,pady=10,anchor="w").pack(fill="x")
        def close_sample():
            stop_preview()
            if state["preview"]:
                try:Path(state["preview"]).unlink(missing_ok=True)
                except OSError:pass
            win.destroy()
        win.protocol("WM_DELETE_WINDOW",close_sample)
        waveview.bind("<Configure>",lambda _:render())

    def open_librarian(self):
        if hasattr(self, "librarian_window") and self.librarian_window.winfo_exists():
            self.librarian_window.lift()
            return
        self.librarian_window = SampleLibrarian(self, DATA_DIR, self.btn, self.panel, self.text)

    def open_synth_factory(self):
        if hasattr(self, "synth_window") and self.synth_window.winfo_exists():
            self.synth_window.lift()
            return
        self.synth_window = SynthFactory(self, DATA_DIR, self.btn, self.panel, self.text)

    def open_sequencer(self):
        if hasattr(self, "sequencer_window") and self.sequencer_window.winfo_exists():
            self.sequencer_window.lift()
            return
        self.sequencer_window = TribeSequencer(self, DATA_DIR)

    def open_korg_center(self):
        if hasattr(self, "korg_window") and self.korg_window.winfo_exists():
            self.korg_window.lift()
            return
        self.korg_window = KorgConnectionCenter(self)

    def close(self):
        if hasattr(self, "korg_window") and self.korg_window.winfo_exists():
            self.korg_window.close()
        self.stop()
        self.disconnect()
        self.destroy()

if __name__ == "__main__":
    Studio().mainloop()
