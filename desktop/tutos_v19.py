# Tutoriels locaux pour Windows, utilisables hors ligne.
import tkinter as tk
from tkinter import ttk
BG='#100f10';PANEL='#211d1a';RED='#ff493e';TEXT='#e9dac2'
GUIDES={
'Démarrage rapide':'''1. Lance mokteK Kaoss Studio. Sans matériel, le mode SIMULATION est normal.
2. Ouvre TRIBE SEQUENCER pour créer un rythme avec les six pistes.
3. Ouvre SYNTH FACTORY pour créer un son, puis exporte-le en WAV.
4. Dans SAMPLE LIBRARIAN, importe un WAV avant de l'utiliser dans le séquenceur.
5. Enregistre tes projets avant toute modification importante.''',
'MIDI et KP3 / KP3+':'''1. Branche ton Korg alimenté via USB-MIDI ou une interface compatible.
2. Ouvre KORG CONNECTION, actualise les ports et sélectionne les entrées/sorties.
3. Lance uniquement l'identification standard après vérification des ports.
4. Utilise les PROFILS MIDI pour adapter les contrôleurs X, Y, Touch et les banques.
5. Les transferts de samples et la mémoire interne ne sont pas encore pris en charge.
6. Exporte le rapport de l'assistant de tests pour signaler toute anomalie.''',
'Séquenceur et effets':'''1. Dans TRIBE SEQUENCER, sélectionne 16, 32 ou 64 pas.
2. Clique un pas pour le jouer; clic droit pour sa vélocité, sa probabilité et les roulements.
3. Ajuste le mixer et le swing; mémorise les variations A à D.
4. Dans FX MASTER, choisis un preset puis APPLIQUER PRESET.
5. Lance ARRANGEUR, ajoute les sections, puis écoute ou exporte en WAV.
6. Les FX de l'arrangeur utilisent les réglages actuels du séquenceur.''',
'Projets et Android':'''1. Enregistre tes patterns et sessions sur Windows.
2. Utilise PROJET COMMUN pour exporter une archive ZIP échangeable.
3. Sur Android, ouvre KORG FILE CENTER et importe uniquement les éléments compatibles.
4. Vérifie les samples, presets et patterns après import.
5. Certains paramètres du séquenceur Windows ne sont pas reproduits sur Android.
6. Une sauvegarde locale n'est jamais une sauvegarde matérielle Korg.''',
'Sauvegardes et dépannage':'''1. Utilise MES PROJETS pour exporter et dupliquer tes archives.
2. Conserve une copie des ZIP à l'extérieur du dossier de l'application.
3. En cas de MIDI absent, vérifie le câble, l'alimentation, le pilote et les ports.
4. Si un son manque, vérifie le fichier WAV dans Sample Librarian.
5. Si un rendu ne correspond pas entre PC et Android, exporte le WAV lui-même.
6. Pour un bug, note la version et exporte un diagnostic depuis KORG CONNECTION.'''
}
class Tutorials(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent)
        self.title('mokteK • TUTOS V19');self.geometry('840x575');self.minsize(640,430);self.configure(bg=BG)
        tk.Label(self,text='TUTOS  //  MODE D’EMPLOI',bg=BG,fg=RED,font=('Segoe UI',19,'bold'),pady=15).pack(fill='x')
        body=tk.Frame(self,bg=BG);body.pack(fill='both',expand=True,padx=14,pady=10)
        left=tk.Listbox(body,bg=PANEL,fg=TEXT,selectbackground='#7a2720',font=('Segoe UI',11),width=27,exportselection=False)
        left.pack(side='left',fill='y',padx=(0,12))
        for name in GUIDES:left.insert('end',name)
        right=tk.Frame(body,bg=PANEL);right.pack(fill='both',expand=True)
        title=tk.Label(right,text='',bg=PANEL,fg=RED,font=('Segoe UI',14,'bold'),anchor='w',padx=16,pady=12);title.pack(fill='x')
        content=tk.Text(right,bg=PANEL,fg=TEXT,font=('Segoe UI',11),wrap='word',relief='flat',padx=16,pady=12,spacing2=8)
        content.pack(fill='both',expand=True)
        def change(_=None):
            selection=left.curselection()
            if not selection:return
            name=list(GUIDES)[selection[0]];title.config(text=name);content.config(state='normal');content.delete('1.0','end');content.insert('1.0',GUIDES[name]);content.config(state='disabled')
        left.bind('<<ListboxSelect>>',change);left.selection_set(0);change()
