"""Centre Korg : diagnostic MIDI non destructif (Windows).

Only one outbound SysEx is supported: universal identity request F0 7E 7F 06 01 F7.
There are no sample/memory write routines in this module.
"""
from collections import deque
from datetime import datetime
from pathlib import Path
import json
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import zipfile
import io
from midi_profiles import MidiProfileWindow
from korg_test_wizard import KorgTestWizard

try:
    import mido
except ImportError:
    mido = None

BG = '#100f10'
PANEL = '#211d1a'
STEEL = '#887766'
RED = '#ff493e'
TEXT = '#e9dac2'
MUTED = '#b9a99b'
IDENTITY_REQUEST = (0x7E, 0x7F, 0x06, 0x01)


def describe_identity(msg):
    """Parse universal identity response without assuming KP3/KP3+ compatibility."""
    if getattr(msg, 'type', None) != 'sysex':
        return None
    d = tuple(msg.data)
    if len(d) < 6 or d[0] != 0x7e or d[2:4] != (0x06, 0x02):
        return None
    offset = 4
    if d[offset] == 0:
        if len(d) < 7:
            return None
        maker = d[4:7]
        offset = 7
    else:
        maker = d[4:5]
        offset = 5
    if len(d) < offset + 8:
        return None
    family = d[offset:offset+2]
    member = d[offset+2:offset+4]
    revision = d[offset+4:offset+8]
    vendor = 'Korg (identifiant constructeur)' if maker == (0x42,) else 'Constructeur non identifié'
    return {'fabricant': vendor, 'id_fabricant': hexbytes(maker),
            'famille': hexbytes(family), 'membre': hexbytes(member),
            'revision': hexbytes(revision), 'modele_confirme': False}


def hexbytes(data):
    return ' '.join(f'{int(b):02X}' for b in data)


class KorgConnectionCenter(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title('mokteK // KORG AUTO DETECT  •  V27')
        self.geometry('950x720')
        self.minsize(760, 590)
        self.configure(bg=BG)
        self.output_port = None
        self.input_port = None
        self.queue = queue.Queue(maxsize=256)
        self.events = deque(maxlen=400)
        self.identity = None
        self.detected_level = tk.StringVar(value='NIVEAU 0 · Aucun appareil détecté')
        self.profiles_window = None
        self.test_wizard = None
        self.selected_input = tk.StringVar()
        self.selected_output = tk.StringVar()
        self.model_hint = tk.StringVar(value='Inconnu (non vérifié)')
        self.state = tk.StringVar(value='SIMULATION / NON CONNECTÉ')
        self.result = tk.StringVar(value='Aucune réponse MIDI Identity reçue')
        self._ui()
        self.refresh()
        self.after_id = self.after(100, self.drain)
        self.protocol('WM_DELETE_WINDOW', self.close)

    def label(self, parent, text, size=10, color=TEXT):
        return tk.Label(parent, text=text, font=('Segoe UI', size), bg=parent['bg'], fg=color, anchor='w')

    def button(self, parent, text, command):
        return tk.Button(parent, text=text, command=command, bg='#49201e', fg=TEXT,
                         activebackground=RED, activeforeground='white', relief='flat',
                         padx=12, pady=8, cursor='hand2')

    def _ui(self):
        header = tk.Frame(self, bg='#332b25', padx=15, pady=12)
        header.pack(fill='x')
        self.label(header, 'KORG CONNECTION CENTER', 20, RED).pack(side='left')
        self.label(header, 'V27  •  IDENTIFICATION NON DESTRUCTIVE', 10, MUTED).pack(side='right')
        tk.Frame(self, bg=RED, height=3).pack(fill='x')
        panel = tk.Frame(self, bg=PANEL, padx=16, pady=12)
        panel.pack(fill='x', padx=12, pady=10)
        self.label(panel, 'Ports MIDI Windows (entrée = réponses, sortie = requêtes)', 11).pack(anchor='w')
        self.label(panel, 'AUTO DETECT : vérification progressive, sans écritures matérielles', 10, RED).pack(anchor='w')
        for title, variable, key in [('ENTRÉE MIDI', self.selected_input, 'input'),
                                      ('SORTIE MIDI', self.selected_output, 'output')]:
            self.label(panel, title, 9, MUTED).pack(anchor='w', pady=(9, 3))
            combo = ttk.Combobox(panel, textvariable=variable, state='readonly')
            combo.pack(fill='x')
            setattr(self, key + '_combo', combo)
        controls = tk.Frame(panel, bg=PANEL)
        controls.pack(fill='x', pady=8)
        for title, command in [('ACTUALISER', self.refresh), ('CONNECTER', self.connect),
                               ('DÉCONNECTER', self.disconnect), ('IDENTIFIER SANS ÉCRITURE', self.request_identity)]:
            self.button(controls, title, command).pack(side='left', padx=(0, 6))
        self.button(panel, 'PROFILS MIDI KP3 / KP3+  •  V11', self.open_profiles).pack(anchor='w', pady=(4, 6))
        self.button(panel, 'ASSISTANT DE TESTS KORG  •  V12', self.open_test_wizard).pack(anchor='w', pady=(2, 6))
        self.label(panel, 'Sélection de modèle (indication manuelle, jamais preuve d’identification)', 9, MUTED).pack(anchor='w', pady=(7, 3))
        ttk.Combobox(panel, textvariable=self.model_hint,
                     values=['Inconnu (non vérifié)', 'KP3 (déclaré)', 'KP3+ (déclaré)'],
                     state='readonly').pack(anchor='w')
        self.label(panel, 'Les commandes qui écrivent des samples, programmes ou mémoires sont désactivées.', 10, RED).pack(anchor='w', pady=(10, 0))
        self.label(self, 'ÉTAT DE LA CONNEXION', 10, MUTED).pack(anchor='w', padx=18)
        tk.Label(self, textvariable=self.detected_level, bg=BG, fg=RED,
                 font=('Consolas', 11, 'bold'), anchor='w').pack(fill='x', padx=18, pady=(4, 2))
        tk.Label(self, textvariable=self.state, fg='#98dd9e', bg=BG,
                 font=('Consolas', 11, 'bold'), anchor='w').pack(fill='x', padx=18, pady=3)
        tk.Label(self, textvariable=self.result, fg=TEXT, bg=BG,
                 justify='left', wraplength=850, anchor='w').pack(fill='x', padx=18, pady=(3, 9))
        logs = tk.Frame(self, bg=PANEL, padx=9, pady=9)
        logs.pack(fill='both', expand=True, padx=12)
        self.label(logs, 'JOURNAL MIDI  •  400 ÉVÉNEMENTS MAXIMUM', 11).pack(anchor='w')
        self.logview = tk.Text(logs, height=10, bg='#140b0d', fg=TEXT, insertbackground=TEXT,
                               relief='flat', state='disabled', font=('Consolas', 10))
        self.logview.pack(fill='both', expand=True, pady=(8, 0))
        bottom = tk.Frame(self, bg=BG, pady=10, padx=12)
        bottom.pack(fill='x')
        self.button(bottom, 'EXPORTER RAPPORT ZIP', self.export_report).pack(side='left')
        self.button(bottom, 'EFFACER JOURNAL', self.clear_log).pack(side='left', padx=8)
        self.label(bottom, 'Aucun transfert de données internes Korg', 9, MUTED).pack(side='right')

    def append(self, direction, text):
        line = f'{datetime.now().isoformat(timespec="seconds")}  {direction:<7} {text}'
        self.events.append(line)
        self.logview.configure(state='normal')
        self.logview.insert('end', line + '\n')
        if int(self.logview.index('end-1c').split('.')[0]) > 400:
            self.logview.delete('1.0', '2.0')
        self.logview.see('end')
        self.logview.configure(state='disabled')

    def clear_log(self):
        self.events.clear()
        self.logview.configure(state='normal')
        self.logview.delete('1.0', 'end')
        self.logview.configure(state='disabled')

    def refresh(self):
        try:
            inputs = list(mido.get_input_names()) if mido else []
            outputs = list(mido.get_output_names()) if mido else []
            self.input_combo['values'] = inputs
            self.output_combo['values'] = outputs
            if self.selected_input.get() not in inputs:
                self.selected_input.set(inputs[0] if inputs else '')
            if self.selected_output.get() not in outputs:
                self.selected_output.set(outputs[0] if outputs else '')
            self.append('SCAN', f'{len(inputs)} entrée(s), {len(outputs)} sortie(s)')
            if self.input_port is None:
                self.detected_level.set('NIVEAU 1 · Ports MIDI détectés (modèle non confirmé)' if inputs or outputs else 'NIVEAU 0 · Aucun port MIDI détecté')
        except Exception as exc:
            self.state.set(f'Erreur de détection : {exc}')
            self.append('ERREUR', str(exc))

    def receive(self, msg):
        try:
            self.queue.put_nowait(msg)
        except queue.Full:
            pass

    def connect(self):
        self.disconnect()
        if not mido:
            self.state.set('Module mido indisponible')
            return
        ins = self.selected_input.get()
        outs = self.selected_output.get()
        if not ins or not outs:
            self.state.set('Sélectionner une entrée ET une sortie MIDI')
            return
        try:
            self.input_port = mido.open_input(ins, callback=self.receive)
            self.output_port = mido.open_output(outs)
        except Exception as exc:
            self.disconnect()
            self.state.set('Erreur MIDI : ' + str(exc))
            self.append('ERREUR', str(exc))
            return
        self.state.set('PORTS CONNECTÉS — modèle Korg non vérifié')
        self.detected_level.set('NIVEAU 2 · Ports ouverts, aucune identité confirmée')
        self.identity = None
        self.append('CONNECT', f'IN={ins} / OUT={outs}')

    def disconnect(self):
        for key in ('input_port', 'output_port'):
            port = getattr(self, key)
            if port is not None:
                try:
                    port.close()
                except Exception:
                    pass
                setattr(self, key, None)
        self.state.set('SIMULATION / NON CONNECTÉ')
        self.detected_level.set('NIVEAU 0 · Déconnecté')

    def request_identity(self):
        if self.output_port is None or self.input_port is None:
            self.state.set('Connecter les ports entrée et sortie avant la demande')
            return
        try:
            self.output_port.send(mido.Message('sysex', data=IDENTITY_REQUEST))
            self.append('OUT', 'F0 7E 7F 06 01 F7  (Universal Identity Request)')
            self.result.set('Demande standard envoyée ; attente de réponse. Absence de réponse ≠ incompatibilité.')
        except Exception as exc:
            self.append('ERREUR', f'Envoi identité : {exc}')
            self.state.set(f'Échec d’envoi : {exc}')

    def drain(self):
        for _ in range(40):
            try:
                msg = self.queue.get_nowait()
            except queue.Empty:
                break
            try:
                raw = hexbytes(msg.bytes())
            except Exception:
                raw = str(msg)
            self.append('IN', raw)
            info = describe_identity(msg)
            if info:
                self.identity = info
                self.result.set('Identité MIDI : ' + json.dumps(info, ensure_ascii=False)
                                + ' — KP3/KP3+ NON CONFIRMÉ')
                self.state.set('IDENTITÉ MIDI REÇUE — modèle exact non vérifié')
                self.detected_level.set('NIVEAU 3 · Fabricant Korg confirmé par SysEx ; modèle non confirmé' if info['id_fabricant'] == '42' else 'NIVEAU 3 · Identité MIDI reçue ; fabricant autre que Korg')
        self.after_id = self.after(100, self.drain)

    def open_profiles(self):
        if self.profiles_window is not None and self.profiles_window.winfo_exists():
            self.profiles_window.lift()
            return
        self.profiles_window = MidiProfileWindow(self)

    def open_test_wizard(self):
        if self.test_wizard is not None and self.test_wizard.winfo_exists():
            self.test_wizard.lift()
            return
        self.test_wizard = KorgTestWizard(self, self)

    def export_report(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.zip',
                    initialfile='moktek_korg_autodetect_v27.zip',
                    filetypes=[('Archive ZIP', '*.zip')])
        if not path:
            return
        report = {
            'application': 'mokteK Kaoss Studio Windows', 'module': 'Korg Auto Detect V27',
            'niveau_de_preuve': self.detected_level.get(),
            'date': datetime.now().isoformat(timespec='seconds'),
            'modele_declare': self.model_hint.get(), 'identite_midi': self.identity,
            'entree': self.selected_input.get(), 'sortie': self.selected_output.get(),
            'etat': self.state.get(), 'transfert_memoire': 'non supporté',
            'tests_materiels_valides': False,
            'protocole': 'Universal Non-Realtime Identity Request seulement', 'profils_midi': 'locaux, non vérifiés sur KP3/KP3+',
        }
        try:
            with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('diagnostic.json', json.dumps(report, indent=2, ensure_ascii=False))
                archive.writestr('journal_midi.txt', '\n'.join(self.events) + '\n')
                archive.writestr('LIRE_AVANT_PARTAGE.txt',
                    'Vérifier les noms de périphériques et le journal avant partage : ils peuvent contenir des informations locales.\n'
                    'Une réponse MIDI Korg valide ne prouve PAS à elle seule le modèle KP3/KP3+.\n')
            self.append('RAPPORT', 'Rapport ZIP enregistré')
        except Exception as exc:
            messagebox.showerror('Export impossible', str(exc), parent=self)

    def close(self):
        if self.test_wizard is not None and self.test_wizard.winfo_exists():
            self.test_wizard.destroy()
        if self.profiles_window is not None and self.profiles_window.winfo_exists():
            self.profiles_window.destroy()
        if self.after_id is not None:
            self.after_cancel(self.after_id)
            self.after_id = None
        self.disconnect()
        self.destroy()
