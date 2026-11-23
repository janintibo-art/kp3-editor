"""Local WAV sample librarian. Never writes to KP3 hardware."""
import json
import shutil
import tempfile
import uuid
import wave
import winsound
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

BG, PANEL, STEEL, RED, TEXT, MUTED = "#100f10", "#211d1a", "#887766", "#ff493e", "#e9dac2", "#b9a99b"
BANKS = "ABCD"
SLOTS = 8
MAX_BYTES = 80 * 1024 * 1024

def check_wav(path):
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Fichier supérieur à 80 Mo : import refusé")
    with wave.open(str(path), "rb") as f:
        if f.getcomptype() != "NONE" or f.getsampwidth() != 2 or f.getnchannels() not in (1, 2):
            raise ValueError("Format requis : WAV PCM 16 bits mono/stéréo")
        if f.getframerate() < 8000 or f.getframerate() > 192000 or f.getnframes() == 0:
            raise ValueError("Fréquence ou durée non valide")
        return f.getnframes() / f.getframerate(), f.getframerate(), f.getnchannels()

class SampleLibrarian(tk.Toplevel):
    def __init__(self, owner, data_dir, btn, panel, text):
        super().__init__(owner)
        self.title("mokteK // SAMPLE LIBRARIAN • Windows V4")
        self.geometry("1070x720")
        self.minsize(850, 610)
        self.configure(bg=BG)
        self.root_dir = Path(data_dir) / "sample_librarian"
        self.audio_dir = self.root_dir / "audio"
        self.index = self.root_dir / "library.json"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.entries = self._read_index()
        self.bank = tk.StringVar(value="A")
        self.slot = tk.IntVar(value=0)
        self.status = tk.StringVar(value="Bibliothèque locale, sans transfert vers le KP3.")
        self.selected = tk.StringVar(value="")
        self.bpm = tk.StringVar(value="")
        self.mode = tk.StringVar(value="One Shot")
        self.target_bank = tk.StringVar(value="B")
        self.target_slot = tk.IntVar(value=1)
        self.buttons = []
        self.btn, self.panel, self.text = btn, panel, text
        title = tk.Frame(self, bg="#332b25", padx=18, pady=14)
        title.pack(fill="x")
        tk.Label(title, text="SAMPLE LIBRARIAN  //  4 BANKS × 8 SLOTS", fg=RED, bg="#332b25", font=("Segoe UI", 19, "bold")).pack(side="left")
        tk.Label(title, text="LOCAL WAV  •  MIDI EXPÉRIMENTAL", fg=MUTED, bg="#332b25", font=("Segoe UI", 9)).pack(side="right")
        tk.Frame(self, bg=RED, height=3).pack(fill="x")
        shell = tk.Frame(self, bg=BG, padx=14, pady=12)
        shell.pack(fill="both", expand=True)
        banks = self.panel(shell, "BANQUES A — D")
        banks.pack(fill="x", pady=(0, 8))
        row = tk.Frame(banks, bg=PANEL)
        row.pack(fill="x")
        for name in BANKS:
            b = self.btn(row, "BANK " + name, lambda name=name: self.choose_bank(name))
            b.pack(side="left", fill="x", expand=True, padx=4)
        slots = self.panel(shell, "EMPLACEMENTS • 8 PAR BANQUE")
        slots.pack(fill="both", expand=True, pady=(0, 8))
        grid = tk.Frame(slots, bg=PANEL)
        grid.pack(fill="both", expand=True)
        for i in range(SLOTS):
            b = self.btn(grid, "", lambda i=i: self.choose_slot(i))
            b.grid(row=i//4, column=i%4, sticky="nsew", padx=5, pady=8)
            grid.columnconfigure(i%4, weight=1)
            grid.rowconfigure(i//4, weight=1)
            self.buttons.append(b)
        details = self.panel(shell, "ÉCHANTILLON SÉLECTIONNÉ")
        details.pack(fill="x", pady=(0, 8))
        tk.Label(details, textvariable=self.selected, bg=PANEL, fg=TEXT, justify="left", anchor="w").pack(fill="x", pady=3)
        settings = tk.Frame(details, bg=PANEL)
        settings.pack(fill="x", pady=5)
        tk.Label(settings, text="BPM (indicatif)", bg=PANEL, fg=MUTED).pack(side="left")
        tk.Entry(settings, textvariable=self.bpm, width=8).pack(side="left", padx=6)
        tk.Label(settings, text="Lecture", bg=PANEL, fg=MUTED).pack(side="left", padx=(16, 3))
        ttk.Combobox(settings, textvariable=self.mode, values=["One Shot", "Loop"], state="readonly", width=10).pack(side="left", padx=5)
        self.btn(settings, "ENREGISTRER INFOS", self.save_metadata).pack(side="left", padx=10)
        operations = self.panel(shell, "FICHIERS / COPIE / ÉCHANGE")
        operations.pack(fill="x")
        actions = tk.Frame(operations, bg=PANEL)
        actions.pack(fill="x", pady=3)
        for label, action in [("IMPORTER WAV", self.import_wav), ("▶ ÉCOUTER", self.preview), ("■ STOP", self.stop_preview), ("EXPORT WAV", self.export_wav), ("VIDER", self.clear_slot)]:
            self.btn(actions, label, action).pack(side="left", padx=4)
        actions2 = tk.Frame(operations, bg=PANEL)
        actions2.pack(fill="x", pady=(8, 1))
        tk.Label(actions2, text="Vers banque", fg=MUTED, bg=PANEL).pack(side="left")
        ttk.Combobox(actions2, textvariable=self.target_bank, values=list(BANKS), width=5, state="readonly").pack(side="left", padx=6)
        tk.Label(actions2, text="Slot", fg=MUTED, bg=PANEL).pack(side="left")
        tk.Spinbox(actions2, from_=1, to=SLOTS, textvariable=self.target_slot, width=4).pack(side="left", padx=6)
        self.btn(actions2, "COPIER", lambda: self.transfer(False)).pack(side="left", padx=4)
        self.btn(actions2, "ÉCHANGER", lambda: self.transfer(True)).pack(side="left", padx=4)
        tk.Label(self, textvariable=self.status, bg=BG, fg=MUTED, anchor="w", padx=18, pady=8).pack(fill="x")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()

    def _read_index(self):
        if not self.index.exists():
            return {}
        try:
            data = json.loads(self.index.read_text(encoding="utf-8"))
            if data.get("format") != "moktek-sample-library-v1" or not isinstance(data.get("slots"), dict):
                raise ValueError("Index non reconnu")
            return {k:v for k,v in data["slots"].items() if k[:1] in BANKS and k[1:].isdigit() and 0 <= int(k[1:]) < SLOTS and isinstance(v, dict)}
        except Exception as exc:
            messagebox.showwarning("Bibliothèque", f"Index illisible : {exc}. Les WAV sont conservés.", parent=self)
            return {}

    def persist(self):
        self.root_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"format":"moktek-sample-library-v1", "slots":self.entries}, ensure_ascii=False, indent=2)
        tmp = self.root_dir / "library.json.tmp"
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(self.index)

    def key(self):
        return f"{self.bank.get()}{self.slot.get()}"

    def current(self):
        return self.entries.get(self.key())

    def audio_path(self, entry):
        name = entry.get("file", "")
        if not isinstance(name, str) or not name.endswith(".wav") or Path(name).name != name:
            raise ValueError("Chemin WAV non valide")
        return self.audio_dir / name

    def choose_bank(self, name):
        self.bank.set(name)
        self.refresh()

    def choose_slot(self, slot):
        self.slot.set(slot)
        self.refresh()

    def refresh(self):
        for i, b in enumerate(self.buttons):
            entry = self.entries.get(f"{self.bank.get()}{i}")
            name = (entry.get("name", "") if entry else "VIDE")
            b.configure(text=f"{self.bank.get()}{i+1}  ·  {name[:21]}", bg="#651d1d" if i == self.slot.get() else "#392a28", highlightbackground=RED if i == self.slot.get() else STEEL)
        entry = self.current()
        if not entry:
            self.selected.set(f"Banque {self.bank.get()} • slot {self.slot.get()+1}  —  vide")
            self.bpm.set("")
            self.mode.set("One Shot")
            return
        try:
            path = self.audio_path(entry)
            duration, rate, channels = check_wav(path)
            meta = f"{duration:.2f} s  •  {rate} Hz  •  {channels} canal(aux)"
        except Exception:
            meta = "Fichier manquant ou endommagé"
        self.selected.set(f"{entry.get('name', 'Sans nom')}  •  {meta}")
        self.bpm.set(str(entry.get("bpm", "")))
        self.mode.set(entry.get("mode", "One Shot") if entry.get("mode") in ("One Shot", "Loop") else "One Shot")

    def import_wav(self):
        source = filedialog.askopenfilename(parent=self, title="Importer un sample WAV", filetypes=[("WAV PCM 16 bits", "*.wav")])
        if not source:
            return
        try:
            path = Path(source)
            check_wav(path)
            current = self.current()
            if current and not messagebox.askyesno("Remplacer", "Remplacer le sample de cet emplacement ?", parent=self):
                return
            filename = f"{uuid.uuid4().hex}.wav"
            dest = self.audio_dir / filename
            shutil.copyfile(path, dest)
            try:
                self.entries[self.key()] = {"file":filename, "name":path.stem[:80], "bpm":"", "mode":"One Shot"}
                self.persist()
            except Exception:
                dest.unlink(missing_ok=True)
                raise
            self.refresh()
            self.status.set(f"Import terminé : {path.name} — {self.key()}")
        except Exception as exc:
            messagebox.showerror("Import WAV", str(exc), parent=self)

    def save_metadata(self):
        entry = self.current()
        if not entry:
            return
        try:
            bpm = self.bpm.get().strip()
            if bpm and not (20 <= float(bpm) <= 300):
                raise ValueError("BPM doit être compris entre 20 et 300")
            entry["bpm"] = bpm
            entry["mode"] = self.mode.get()
            self.persist()
            self.status.set("Réglages descriptifs enregistrés (sans modification du WAV).")
        except Exception as exc:
            messagebox.showerror("Paramètres", str(exc), parent=self)

    def preview(self):
        entry = self.current()
        if not entry:
            return
        try:
            path = self.audio_path(entry)
            check_wav(path)
            winsound.PlaySound(None, winsound.SND_PURGE)
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            if entry.get("mode") == "Loop":
                self.status.set("Préécoute unique : le mode Loop est une métadonnée pour cette V4.")
            else:
                self.status.set("Préécoute en cours.")
        except Exception as exc:
            messagebox.showerror("Préécoute", str(exc), parent=self)

    def stop_preview(self):
        winsound.PlaySound(None, winsound.SND_PURGE)

    def export_wav(self):
        entry = self.current()
        if not entry:
            return
        try:
            source = self.audio_path(entry)
            check_wav(source)
            name = "".join(c for c in entry.get("name", "sample")[:60] if c.isalnum() or c in "-_ ").strip() or "sample"
            destination = filedialog.asksaveasfilename(parent=self, defaultextension=".wav", initialfile=name + ".wav", filetypes=[("WAV", "*.wav")])
            if not destination:
                return
            if Path(destination).resolve() == source.resolve():
                raise ValueError("Impossible d'écraser le sample de la bibliothèque")
            shutil.copyfile(source, destination)
            self.status.set("Sample WAV exporté.")
        except Exception as exc:
            messagebox.showerror("Export WAV", str(exc), parent=self)

    def clear_slot(self):
        if not self.current() or not messagebox.askyesno("Vider", "Vider cet emplacement ? (le fichier interne sera conservé)", parent=self):
            return
        self.entries.pop(self.key(), None)
        self.persist()
        self.refresh()

    def transfer(self, swap):
        origin = self.key()
        try:
            bank = self.target_bank.get()
            num = int(self.target_slot.get())
            if bank not in BANKS or num not in range(1, SLOTS+1):
                raise ValueError("Banque ou slot de destination invalide")
            dest = f"{bank}{num-1}"
            if dest == origin:
                return
            source = self.entries.get(origin)
            if not source:
                raise ValueError("L'emplacement source est vide")
            old = self.entries.get(dest)
            if old and not swap and not messagebox.askyesno("Remplacer", "Écraser le slot de destination ?", parent=self):
                return
            self.entries[dest] = dict(source)
            if swap:
                if old:
                    self.entries[origin] = old
                else:
                    self.entries.pop(origin, None)
            self.persist()
            self.status.set(f"{'Échange' if swap else 'Copie'} : {origin} → {dest}")
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Copie / échange", str(exc), parent=self)

    def close(self):
        self.stop_preview()
        self.destroy()
