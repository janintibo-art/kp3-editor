"""mokteK KAOSS STUDIO Windows – first native desktop companion.
MIDI features are experimental and require physical testing on KP3/KP3+.
"""
import json
import os
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

VERSION = "2.0"
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
        self.geometry("1200x760")
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

    def close(self):
        self.stop()
        self.disconnect()
        self.destroy()

if __name__ == "__main__":
    Studio().mainloop()
