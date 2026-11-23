"""Assistant de validation matérielle KP3/KP3+.
Tous les résultats sont saisis manuellement. Aucune commande MIDI envoyée.
"""
from datetime import datetime
from pathlib import Path
import json
import os
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import zipfile

BG = '#100f10'
PANEL = '#211d1a'
RED = '#ff493e'
TEXT = '#e9dac2'
MUTED = '#b9a99b'
DATA_DIR = Path(os.environ.get('APPDATA') or str(Path.home())) / 'mokteK-Kaoss-Studio'
TESTS = [
 ('PREP', 'Préparation', 'Noter le modèle inscrit sur le boîtier et vérifier alimentation, câbles et prises MIDI.', 'Observation uniquement, sans manipulation de mémoire.'),
 ('PORTS', 'Détection des ports', 'Ouvrir KORG CONNECTION puis Actualiser. Vérifier les ports Windows d’entrée et sortie.', 'Si aucun port ne s’affiche, vérifier pilote/interface/câble.'),
 ('CONNECT', 'Connexion', 'Sélectionner les ports entrée/sortie correspondant à l’appareil, puis cliquer Connecter.', 'Un port affiché ne prouve pas la compatibilité KP3/KP3+.'),
 ('IDENTITY', 'Identification MIDI', 'Cliquer Demander identité dans le centre de connexion. Noter la réponse et le constructeur.', 'La demande universelle est non destructive. Absence de réponse ≠ incompatibilité.'),
 ('XY', 'Pad XY', 'Après accord du propriétaire, tester X puis Y séparément depuis les commandes LIVE, à faible volume.', 'Les messages CC peuvent modifier temporairement un effet. Aucune écriture mémoire.'),
 ('TOUCH', 'Touch / Hold', 'Tester manuellement Touch et Hold ; vérifier la réaction de l’appareil.', 'Régler le volume bas avant le test.'),
 ('PROGRAM', 'Changement de programme', 'Tester un seul changement de programme et vérifier la sélection sur le boîtier.', 'Peut modifier le programme actif ; noter la valeur initiale.'),
 ('BANKS', 'Banques A–D', 'Tester une banque à la fois, vérifier déclenchement et relâchement des notes.', 'Les notes MIDI des profils sont expérimentales et ajustables.'),
 ('STABILITY', 'Stabilité / reconnexion', 'Déconnecter logiciellement, reconnecter puis surveiller le journal pendant quelques minutes.', 'Éviter de débrancher pendant une manipulation sensible.'),
 ('SAMPLES', 'Transfert de samples', 'Vérifier que le transfert matériel reste marqué non disponible dans cette version.', 'NE PAS essayer de restauration ou écriture mémoire propriétaire.'),
]
STATUSES = ['Non testé', 'Réussi', 'Échec', 'Bloqué', 'Non applicable']


def new_results():
    return {code: {'statut': 'Non testé', 'note': ''} for code, *_ in TESTS}


def package_report(model, results, context, include_device_names):
    cleaned = dict(context)
    if not include_device_names:
        cleaned['entree'] = '(masqué)'
        cleaned['sortie'] = '(masqué)'
        # Logs peuvent contenir les noms des périphériques ; ne pas les inclure sans accord.
        cleaned['journal_midi'] = '(exclu pour confidentialité)'
    return {
        'application': 'mokteK Kaoss Studio Windows V12',
        'date': datetime.now().isoformat(timespec='seconds'),
        'plateforme': 'Windows',
        'modele_declare_manuellement': model,
        'identite_midi': cleaned.get('identite_midi'),
        'verification_automatique_kp3': False,
        'aucune_ecriture_memoire': True,
        'contexte': cleaned,
        'tests': [{'code': code, 'titre': title,
                   'statut': results.get(code, {}).get('statut', 'Non testé'),
                   'note': results.get(code, {}).get('note', '')}
                  for code, title, *_ in TESTS],
    }


class KorgTestWizard(tk.Toplevel):
    def __init__(self, master, connection):
        super().__init__(master)
        self.connection = connection
        self.title('mokteK // ASSISTANT TEST KORG V12')
        self.geometry('900x680')
        self.minsize(700, 550)
        self.configure(bg=BG)
        self.resizable(True, True)
        self.results = new_results()
        self.model = tk.StringVar(value=connection.model_hint.get())
        self.index = 0
        self.status = tk.StringVar(value='Non testé')
        self.progress = tk.StringVar()
        self.safe_names = tk.BooleanVar(value=False)
        self._ui()
        self.show_test()
        self.protocol('WM_DELETE_WINDOW', self.destroy)

    def _label(self, parent, value, color=TEXT, size=10):
        return tk.Label(parent, text=value, bg=parent.cget('bg'), fg=color,
                        justify='left', anchor='w', wraplength=790,
                        font=('Segoe UI', size))

    def _button(self, parent, label, cmd):
        return tk.Button(parent, text=label, command=cmd,
                         bg='#49201e', fg=TEXT, activebackground=RED,
                         activeforeground='white', relief='flat', padx=11, pady=8)

    def _ui(self):
        head = tk.Frame(self, bg='#332b25', padx=16, pady=12)
        head.pack(fill='x')
        self._label(head, 'ASSISTANT DE TESTS KORG', RED, 19).pack(anchor='w')
        self._label(head, 'V12 • résultats déclarés par le testeur • aucune commande MIDI automatique', MUTED).pack(anchor='w')
        tk.Frame(self, bg=RED, height=3).pack(fill='x')
        top = tk.Frame(self, bg=BG, padx=14, pady=11)
        top.pack(fill='x')
        self._label(top, 'Modèle réellement inscrit sur la machine :').pack(anchor='w')
        ttk.Combobox(top, textvariable=self.model, state='readonly',
                     values=['Inconnu (non vérifié)', 'KP3 (déclaré)', 'KP3+ (déclaré)']).pack(anchor='w', pady=5)
        self._label(top, 'Ne pas utiliser sur scène pendant les tests. Abaisser le volume et sauvegarder ses données par les méthodes officielles avant tout essai.', RED).pack(fill='x', pady=(5,0))
        pane = tk.Frame(self, bg=PANEL, padx=17, pady=15)
        pane.pack(fill='both', expand=True, padx=12, pady=4)
        self._label(pane, 'PROGRESSION', MUTED).pack(anchor='w')
        self._label(pane, self.progress).pack_forget() if False else None
        tk.Label(pane, textvariable=self.progress, bg=PANEL, fg=RED,
                 font=('Consolas', 12, 'bold')).pack(anchor='w')
        self.title_label = self._label(pane, '', TEXT, 16)
        self.title_label.pack(anchor='w', pady=(10,6))
        self.instructions = self._label(pane, '')
        self.instructions.pack(anchor='w', pady=5, fill='x')
        self.warning = self._label(pane, '', RED)
        self.warning.pack(anchor='w', pady=(5,12), fill='x')
        self._label(pane, 'Résultat constaté (choisir manuellement)', MUTED).pack(anchor='w')
        ttk.Combobox(pane, textvariable=self.status, values=STATUSES,
                     state='readonly').pack(anchor='w', pady=(4,12))
        self._label(pane, 'Observation / message d’erreur / réaction du Kaoss Pad', MUTED).pack(anchor='w')
        self.notes = tk.Text(pane, height=6, bg='#140b0d', fg=TEXT,
                             insertbackground=TEXT, relief='flat', wrap='word')
        self.notes.pack(fill='both', expand=True, pady=(4,3))
        nav = tk.Frame(self, bg=BG, padx=12, pady=10)
        nav.pack(fill='x')
        self._button(nav, '← PRÉCÉDENT', self.previous).pack(side='left', padx=3)
        self._button(nav, 'SUIVANT →', self.next).pack(side='left', padx=3)
        self._button(nav, 'SAUVEGARDER LOCAL', self.save_local).pack(side='left', padx=3)
        self._button(nav, 'RECHARGER', self.load_local).pack(side='left', padx=3)
        foot = tk.Frame(self, bg=BG, padx=14, pady=7)
        foot.pack(fill='x')
        tk.Checkbutton(foot, text='Inclure noms de périphériques et journal MIDI dans le ZIP (vérifier avant partage)',
                       variable=self.safe_names, bg=BG, fg=TEXT, selectcolor=PANEL,
                       activebackground=BG, activeforeground=TEXT).pack(anchor='w')
        self._button(foot, 'EXPORTER LE RAPPORT ZIP', self.export).pack(anchor='w', pady=(8,2))

    def store(self):
        code = TESTS[self.index][0]
        self.results[code] = {'statut': self.status.get(),
                              'note': self.notes.get('1.0', 'end-1c')[:4000]}

    def show_test(self):
        code, title, instruction, warning = TESTS[self.index]
        completed = sum(self.results[t[0]]['statut'] != 'Non testé' for t in TESTS)
        self.progress.set(f'ÉTAPE {self.index+1}/{len(TESTS)}   •   {completed} réponses renseignées')
        self.title_label.configure(text=title)
        self.instructions.configure(text=instruction)
        self.warning.configure(text='PRÉCAUTION : ' + warning)
        self.status.set(self.results[code]['statut'])
        self.notes.delete('1.0', 'end')
        self.notes.insert('1.0', self.results[code]['note'])

    def previous(self):
        self.store()
        self.index = max(0, self.index-1)
        self.show_test()

    def next(self):
        self.store()
        self.index = min(len(TESTS)-1, self.index+1)
        self.show_test()

    def local_path(self):
        return DATA_DIR / 'korg_validation_v12.json'

    def save_local(self):
        self.store()
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            path = self.local_path()
            tmp = path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'schema': 1, 'model': self.model.get(), 'tests': self.results},
                                      ensure_ascii=False, indent=2), encoding='utf-8')
            tmp.replace(path)
            messagebox.showinfo('Tests sauvegardés', f'Fichier local :\n{path}', parent=self)
        except OSError as exc:
            messagebox.showerror('Sauvegarde impossible', str(exc), parent=self)

    def load_local(self):
        if not self.local_path().exists():
            messagebox.showinfo('Aucune sauvegarde', 'Aucun test enregistré localement.', parent=self)
            return
        if not messagebox.askyesno('Recharger', 'Remplacer les réponses actuelles par les réponses sauvegardées ?', parent=self):
            return
        try:
            data = json.loads(self.local_path().read_text(encoding='utf-8'))
            for code, *_ in TESTS:
                old = data.get('tests', {}).get(code, {})
                self.results[code] = {'statut': old.get('statut') if old.get('statut') in STATUSES else 'Non testé',
                                      'note': str(old.get('note', ''))[:4000]}
            self.model.set(data.get('model') if data.get('model') in ['Inconnu (non vérifié)', 'KP3 (déclaré)', 'KP3+ (déclaré)'] else 'Inconnu (non vérifié)')
            self.show_test()
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror('Fichier illisible', str(exc), parent=self)

    def export(self):
        self.store()
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.zip',
                   initialfile='moktek_validation_korg_v12.zip', filetypes=[('Archives ZIP','*.zip')])
        if not path:
            return
        context = {'entree': self.connection.selected_input.get(),
                   'sortie': self.connection.selected_output.get(),
                   'etat': self.connection.state.get(),
                   'identite_midi': self.connection.identity,
                   'journal_midi': '\n'.join(self.connection.events)}
        report = package_report(self.model.get(), self.results, context, self.safe_names.get())
        try:
            with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr('resultats_tests.json', json.dumps(report, ensure_ascii=False, indent=2))
                lines = ['mokteK Kaoss Studio — tests KP3 / KP3+ V12',
                         f'Modèle déclaré : {self.model.get()}',
                         'Les résultats ci-dessous ne sont pas des validations automatiques.', '']
                for t in report['tests']:
                    lines.extend([f"[{t['statut']}] {t['titre']}", t['note'] or '(pas de commentaire)', ''])
                z.writestr('rapport_lisible.txt', '\n'.join(lines))
                if self.safe_names.get():
                    z.writestr('journal_midi.txt', context['journal_midi'] + '\n')
                z.writestr('AVANT_PARTAGE.txt',
                    'Vérifier les commentaires et les informations de matériel avant partage.\n'
                    'Les noms des périphériques MIDI et le journal sont exclus sauf accord explicite.\n'
                    'Aucun test n’a été exécuté automatiquement par cet assistant.\n'
                    'Aucune compatibilité matérielle n’est certifiée par ce rapport.\n')
            messagebox.showinfo('Rapport prêt', f'Archive enregistrée :\n{path}', parent=self)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Export impossible', str(exc), parent=self)
