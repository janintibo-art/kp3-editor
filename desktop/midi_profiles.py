"""Local, experimental KP3/KP3+ MIDI mappings and manual non-destructive test panel.

These are *candidate* assignments, not verified Korg specifications.
The module never sends MIDI without an explicit button click.
"""
from pathlib import Path
import json
import os
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import mido
except ImportError:
    mido = None

BG = '#100f10'
PANEL = '#211d1a'
RED = '#ff493e'
TEXT = '#e9dac2'
MUTED = '#b9a99b'
NAMES = ('X', 'Y', 'TOUCH', 'DEPTH', 'LEVEL', 'HOLD')
DEFAULT_CC = {'X': 12, 'Y': 13, 'TOUCH': 92, 'DEPTH': 94, 'LEVEL': 93, 'HOLD': 95}


def default_profile(model):
    if model not in ('KP3', 'KP3+'):
        raise ValueError('Modèle inconnu')
    return {'model': model, 'channel': 1, 'cc_enabled': True,
            'notes_enabled': True, 'program_enabled': True,
            'cc': dict(DEFAULT_CC), 'bank_notes': [36, 37, 38, 39]}


def _bounded_int(value, lo, hi, label):
    try:
        n = int(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(f'{label} doit être un nombre entier.')
    if n < lo or n > hi:
        raise ValueError(f'{label} doit être compris entre {lo} et {hi}.')
    return n


def validate_profile(raw, model):
    if not isinstance(raw, dict):
        raise ValueError('Profil mal formé.')
    result = default_profile(model)
    result['channel'] = _bounded_int(raw.get('channel', 1), 1, 16, 'Canal')
    for key in ('cc_enabled', 'notes_enabled', 'program_enabled'):
        value = raw.get(key, True)
        if type(value) is not bool:
            raise ValueError(f'Option {key} incorrecte.')
        result[key] = value
    entries = raw.get('cc', dict(DEFAULT_CC))
    if not isinstance(entries, dict):
        raise ValueError('Contrôleurs CC invalides.')
    for name in NAMES:
        result['cc'][name] = _bounded_int(entries.get(name, DEFAULT_CC[name]), 0, 127, f'CC {name}')
    notes = raw.get('bank_notes', [36, 37, 38, 39])
    if not isinstance(notes, list) or len(notes) != 4:
        raise ValueError('Quatre notes de banque requises.')
    result['bank_notes'] = [_bounded_int(n, 0, 127, f'Note {chr(65+i)}') for i, n in enumerate(notes)]
    return result


def profile_path():
    base = Path(os.environ.get('APPDATA', str(Path.home()))) / 'mokteK-Kaoss-Studio'
    return base / 'midi_profiles_v11.json'


def load_profiles(path=None):
    path = Path(path) if path is not None else profile_path()
    data = {}
    if path.is_file():
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(doc, dict):
                raise ValueError('Document JSON incorrect')
            if doc.get('schema') != 1:
                raise ValueError('Version de format non prise en charge')
            data = doc.get('profiles', {})
            if not isinstance(data, dict):
                raise ValueError('Profils invalides')
        except (ValueError, OSError) as exc:
            raise ValueError(f'Lecture des profils impossible : {exc}') from exc
    return {model: validate_profile(data.get(model, default_profile(model)), model)
            for model in ('KP3', 'KP3+')}


def save_profiles(profiles, path=None):
    path = Path(path) if path is not None else profile_path()
    validated = {m: validate_profile(profiles[m], m) for m in ('KP3', 'KP3+')}
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic save to avoid corrupting a working configuration on interruption.
    fd, temp = tempfile.mkstemp(prefix='.midi_', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'schema': 1, 'profiles': validated}, f, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return path


class MidiProfileWindow(tk.Toplevel):
    """Edits local profiles; sends only short, manual Note/CC/Program messages."""
    def __init__(self, center):
        super().__init__(center)
        self.center = center
        self.title('mokteK // PROFILS MIDI  •  V11')
        self.geometry('790x710')
        self.minsize(690, 620)
        self.configure(bg=BG)
        self.error = None
        try:
            self.profiles = load_profiles()
        except ValueError as exc:
            self.error = str(exc)
            self.profiles = {m: default_profile(m) for m in ('KP3', 'KP3+')}
        self.model = tk.StringVar(value='KP3')
        self.channel = tk.StringVar()
        self.cc_enabled = tk.BooleanVar()
        self.notes_enabled = tk.BooleanVar()
        self.program_enabled = tk.BooleanVar()
        self.cc_vars = {name: tk.StringVar() for name in NAMES}
        self.note_vars = [tk.StringVar() for _ in range(4)]
        self.test_value = tk.IntVar(value=64)
        self.test_program = tk.IntVar(value=0)
        self.test_cc = tk.StringVar(value='X')
        self.test_note = tk.StringVar(value='A')
        self.status = tk.StringVar(value='Profils locaux non validés sur KP3/KP3+')
        self._ui()
        self._populate('KP3')
        self.protocol('WM_DELETE_WINDOW', self.destroy)
        if self.error:
            self.after(100, lambda: messagebox.showwarning('Profils non chargés',
                self.error + '\nValeurs provisoires chargées ; fichier existant conservé jusqu’à une sauvegarde explicite.', parent=self))

    def _label(self, parent, text, color=TEXT):
        return tk.Label(parent, text=text, bg=parent['bg'], fg=color, anchor='w', font=('Segoe UI', 10))

    def _button(self, parent, text, command):
        return tk.Button(parent, text=text, command=command, bg='#49201e', fg=TEXT,
                         activebackground=RED, relief='flat', padx=10, pady=7)

    def _entry(self, parent, variable, width=7):
        return tk.Entry(parent, textvariable=variable, width=width, justify='center',
                        bg='#120d0f', fg=TEXT, insertbackground=TEXT, relief='solid')

    def _ui(self):
        header = tk.Frame(self, bg='#332b25', padx=12, pady=10)
        header.pack(fill='x')
        self._label(header, 'PROFILS MIDI  •  KP3 / KP3+', RED).pack(anchor='w')
        self._label(header, 'Affectations expérimentales : aucun contrôle physique confirmé', MUTED).pack(anchor='w')
        selector = tk.Frame(self, bg=BG, padx=12, pady=8)
        selector.pack(fill='x')
        self._label(selector, 'Profil à modifier').pack(side='left')
        model_combo = ttk.Combobox(selector, textvariable=self.model,
                                   values=('KP3', 'KP3+'), state='readonly', width=12)
        model_combo.pack(side='left', padx=12)
        model_combo.bind('<<ComboboxSelected>>', self._change_model)
        settings = tk.LabelFrame(self, text=' COMMANDES MIDI LOCALES ', bg=PANEL, fg=TEXT,
                                 padx=12, pady=8)
        settings.pack(fill='x', padx=12, pady=5)
        line = tk.Frame(settings, bg=PANEL)
        line.pack(fill='x')
        self._label(line, 'Canal (1–16)').pack(side='left')
        self._entry(line, self.channel).pack(side='left', padx=7)
        for text, variable in [('CC', self.cc_enabled), ('Notes', self.notes_enabled),
                               ('Program Change', self.program_enabled)]:
            tk.Checkbutton(settings, text='Autoriser les tests '+text, variable=variable,
                           bg=PANEL, fg=TEXT, selectcolor='#49201e', activebackground=PANEL,
                           activeforeground=TEXT).pack(anchor='w')
        cc_frame = tk.LabelFrame(self, text=' CONTRÔLEURS CC (0–127) ', bg=PANEL, fg=TEXT,
                                  padx=12, pady=8)
        cc_frame.pack(fill='x', padx=12, pady=5)
        for i, name in enumerate(NAMES):
            cell = tk.Frame(cc_frame, bg=PANEL)
            cell.grid(row=i//3, column=i%3, padx=15, pady=5, sticky='w')
            self._label(cell, name).pack(side='left')
            self._entry(cell, self.cc_vars[name]).pack(side='left', padx=8)
        notes = tk.LabelFrame(self, text=' NOTES DES BANQUES (0–127) ', bg=PANEL, fg=TEXT,
                               padx=12, pady=8)
        notes.pack(fill='x', padx=12, pady=5)
        for i, var in enumerate(self.note_vars):
            cell = tk.Frame(notes, bg=PANEL)
            cell.pack(side='left', padx=12)
            self._label(cell, chr(65+i)).pack(side='left')
            self._entry(cell, var).pack(side='left', padx=5)
        save = tk.Frame(self, bg=BG, padx=12, pady=7)
        save.pack(fill='x')
        self._button(save, 'ENREGISTRER LES 2 PROFILS', self.save).pack(side='left')
        self._button(save, 'VALEURS PROVISOIRES', self.reset).pack(side='left', padx=7)
        tests = tk.LabelFrame(self, text=' TESTS INDIVIDUELS — ENVOI MIDI MANUEL ', bg=PANEL,
                              fg=TEXT, padx=12, pady=10)
        tests.pack(fill='x', padx=12, pady=5)
        self._label(tests, 'Les tests n’envoient que CC, Note On/Off ou Program Change.').pack(anchor='w')
        row = tk.Frame(tests, bg=PANEL)
        row.pack(fill='x', pady=6)
        ttk.Combobox(row, textvariable=self.test_cc, values=NAMES, width=9,
                     state='readonly').pack(side='left')
        self._label(row, 'Valeur').pack(side='left', padx=8)
        tk.Spinbox(row, from_=0, to=127, textvariable=self.test_value, width=6).pack(side='left')
        self._button(row, 'ENVOYER CC', self.send_cc).pack(side='left', padx=10)
        row = tk.Frame(tests, bg=PANEL)
        row.pack(fill='x', pady=6)
        ttk.Combobox(row, textvariable=self.test_note, values=('A', 'B', 'C', 'D'),
                     state='readonly', width=7).pack(side='left')
        self._button(row, 'TEST NOTE (100 ms)', self.send_note).pack(side='left', padx=10)
        self._label(row, 'Programme 0–127').pack(side='left', padx=8)
        tk.Spinbox(row, from_=0, to=127, textvariable=self.test_program, width=5).pack(side='left')
        self._button(row, 'ENVOYER PC', self.send_program).pack(side='left', padx=10)
        self._label(self, 'Aucune écriture de sample, mémoire ou SysEx propriétaire.', RED).pack(anchor='w', padx=14, pady=5)
        tk.Label(self, textvariable=self.status, bg=BG, fg=TEXT, anchor='w',
                 wraplength=750).pack(fill='x', padx=14, pady=5)

    def _read(self, model):
        raw = {'channel': self.channel.get(), 'cc_enabled': self.cc_enabled.get(),
               'notes_enabled': self.notes_enabled.get(), 'program_enabled': self.program_enabled.get(),
               'cc': {name: var.get() for name, var in self.cc_vars.items()},
               'bank_notes': [var.get() for var in self.note_vars]}
        return validate_profile(raw, model)

    def _populate(self, model):
        p = self.profiles[model]
        self.channel.set(str(p['channel']))
        for key in ('cc_enabled', 'notes_enabled', 'program_enabled'):
            getattr(self, key).set(p[key])
        for name in NAMES:
            self.cc_vars[name].set(str(p['cc'][name]))
        for var, value in zip(self.note_vars, p['bank_notes']):
            var.set(str(value))

    def _change_model(self, _event=None):
        previous = getattr(self, '_last_model', 'KP3')
        try:
            self.profiles[previous] = self._read(previous)
        except ValueError as exc:
            self.model.set(previous)
            messagebox.showerror('Valeur incorrecte', str(exc), parent=self)
            return
        current = self.model.get()
        self._populate(current)
        self._last_model = current

    def current(self):
        model = self.model.get()
        p = self._read(model)
        self.profiles[model] = p
        return p

    def save(self):
        try:
            self.current()
            path = save_profiles(self.profiles)
        except (ValueError, OSError) as exc:
            messagebox.showerror('Enregistrement impossible', str(exc), parent=self)
            return
        self.status.set('Profils enregistrés localement : '+str(path))

    def reset(self):
        model = self.model.get()
        if not messagebox.askyesno('Valeurs provisoires', 'Réinitialiser le profil '+model+' ?\nPas de commande MIDI envoyée.', parent=self):
            return
        self.profiles[model] = default_profile(model)
        self._populate(model)
        self.status.set('Profil local réinitialisé — cliquer Enregistrer pour conserver.')

    def _output(self, enabled):
        if not enabled:
            self.status.set('Type de commande désactivé dans ce profil.')
            return None
        if mido is None or self.center.output_port is None:
            self.status.set('Connecter le port MIDI OUT dans le Korg Connection Center.')
            return None
        if not messagebox.askyesno('Test MIDI manuel',
            'Envoyer une commande MIDI sur le port actuellement connecté ?\n'
            'Ne pas tester pendant une prestation. Le comportement du matériel n’est pas encore validé.',
            parent=self):
            return None
        return self.center.output_port

    def _send(self, msg):
        try:
            self.center.output_port.send(msg)
            self.center.append('TEST', ' '.join(f'{b:02X}' for b in msg.bytes()))
            self.status.set('Commande MIDI envoyée ; réaction physique non vérifiée.')
        except Exception as exc:
            self.status.set('Échec MIDI : '+str(exc))
            self.center.append('ERREUR', 'Test V11 : '+str(exc))

    def send_cc(self):
        try:
            p = self.current()
            value = _bounded_int(self.test_value.get(), 0, 127, 'Valeur')
            name = self.test_cc.get()
            if name not in NAMES:
                raise ValueError('Contrôleur incorrect')
        except (ValueError, tk.TclError) as exc:
            self.status.set(str(exc)); return
        if self._output(p['cc_enabled']):
            self._send(mido.Message('control_change', channel=p['channel']-1,
                                    control=p['cc'][name], value=value))

    def send_note(self):
        try:
            p = self.current()
            idx = 'ABCD'.index(self.test_note.get())
        except (ValueError, tk.TclError) as exc:
            self.status.set('Note incorrecte : '+str(exc)); return
        if self._output(p['notes_enabled']):
            note = p['bank_notes'][idx]
            channel = p['channel']-1
            self._send(mido.Message('note_on', channel=channel, note=note, velocity=100))
            self.after(100, lambda: self._send(mido.Message('note_off', channel=channel,
                                                             note=note, velocity=0)) if self.winfo_exists() else None)

    def send_program(self):
        try:
            p = self.current()
            number = _bounded_int(self.test_program.get(), 0, 127, 'Programme')
        except (ValueError, tk.TclError) as exc:
            self.status.set(str(exc)); return
        if self._output(p['program_enabled']):
            self._send(mido.Message('program_change', channel=p['channel']-1, program=number))
