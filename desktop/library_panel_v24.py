"""V24 visual library for the integrated Windows studio, local WAV only.
Drag an occupied A-D slot onto one of the six track targets. No hardware MIDI writes.
"""
import array
import json
import os
import unicodedata
import sys
import tkinter as tk
import wave
import threading
from sample_analysis_v26 import analyze_wav
import winsound
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from sample_bridge_v23 import store_pcm
from sequencer_engine import TRACKS, librarian_choices

BG='#211d1a'; DARK='#100f10'; RED='#ff493e'; TEXT='#e9dac2'; MUTED='#b9a99b'; STEEL='#887766'

class LibraryPanel:
    def __init__(self, workbench):
        self.w=workbench
        self.bank=tk.StringVar(value='TOUTES')
        self.selected=None
        self.search=tk.StringVar(value="")
        self.category=tk.StringVar(value="TOUS")
        self.favorites_only=tk.BooleanVar(value=False)
        self.favorites=self.load_favorites()
        self.visible_count=tk.StringVar(value="")
        self.drag=None
        self.canvas=None
        self.summary=tk.StringVar(value='Sélectionne un sample. Glisse-le sur une piste à droite.')
        self.analysis=tk.StringVar(value='FICHE SON · Sélectionne un WAV puis clique sur ANALYSER.')
        self.analysis_busy=False

    def build(self):
        w=self.w
        header=tk.Frame(w.content,bg=BG);header.pack(fill='x',pady=3)
        for bank in ('TOUTES','A','B','C','D'):
            w.button(header,bank,lambda b=bank:self.filter_bank(b))
        w.button(header,'IMPORTER WAV',self.import_wav)
        w.button(header,'ACTUALISER',self.refresh)
        filters=tk.Frame(w.content,bg=BG);filters.pack(fill='x',pady=4)
        tk.Label(filters,text='RECHERCHER',bg=BG,fg=TEXT).pack(side='left',padx=3)
        search_entry=tk.Entry(filters,textvariable=self.search,bg='#160e0e',fg=TEXT,insertbackground=RED,width=23)
        search_entry.pack(side='left',padx=4)
        self.search.trace_add('write',lambda *_:self.refresh())
        ttk.Combobox(filters,textvariable=self.category,values=('TOUS','KICK','SNARE','HAT','BASS','LEAD','PERC','AUTRES'),width=10,state='readonly').pack(side='left',padx=4)
        self.category.trace_add('write',lambda *_:self.refresh())
        tk.Checkbutton(filters,text='★ FAVORIS',variable=self.favorites_only,command=self.refresh,bg=BG,fg=TEXT,
                       selectcolor='#34251e',activebackground=BG).pack(side='left',padx=4)
        tk.Label(filters,textvariable=self.visible_count,bg=BG,fg=MUTED).pack(side='right',padx=4)
        body=tk.Frame(w.content,bg=BG);body.pack(fill='both',expand=True)
        left=tk.Frame(body,bg=DARK);left.pack(side='left',fill='both',expand=True,padx=(0,5))
        right=tk.Frame(body,bg=DARK,width=205);right.pack(side='right',fill='y');right.pack_propagate(False)
        tk.Label(left,text='BANQUES A–D · 32 EMPLACEMENTS',bg=DARK,fg=RED,font=('Segoe UI',10,'bold')).pack(anchor='w',padx=6,pady=5)
        self.list_canvas=tk.Canvas(left,bg=DARK,highlightthickness=0)
        scroll=tk.Scrollbar(left,orient='vertical',command=self.list_canvas.yview)
        self.list_canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');self.list_canvas.pack(side='left',fill='both',expand=True)
        self.rows=tk.Frame(self.list_canvas,bg=DARK)
        self.list_canvas.create_window((0,0),window=self.rows,anchor='nw')
        self.rows.bind('<Configure>',lambda e:self.list_canvas.configure(scrollregion=self.list_canvas.bbox('all')))
        self.list_canvas.bind('<Configure>',lambda e:self.list_canvas.itemconfigure(1,width=e.width))
        tk.Label(right,text='DESTINATIONS · 6 PISTES',bg=DARK,fg=RED,font=('Segoe UI',9,'bold'),wraplength=190).pack(pady=6)
        self.targets=[]
        for lane,title in enumerate(TRACKS):
            target=tk.Label(right,text=title+'\n'+w.seq_sounds[lane],bg='#34251e',fg=TEXT,
                            relief='ridge',bd=1,wraplength=186,height=3,cursor='hand2')
            target._moktek_lane=lane
            target.pack(fill='x',padx=7,pady=4)
            target.bind('<Button-1>',lambda e,l=lane:self.assign(l))
            self.targets.append(target)
        info=tk.Frame(w.content,bg=BG);info.pack(fill='x',pady=6)
        self.wave=tk.Canvas(info,bg='#17090d',height=85,highlightbackground=STEEL,highlightthickness=1)
        self.wave.pack(fill='x')
        self.wave.bind('<Configure>',lambda e:self.draw_wave())
        controls=tk.Frame(w.content,bg=BG);controls.pack(fill='x',pady=4)
        w.button(controls,'▶ PRÉÉCOUTER',self.preview)
        w.button(controls,'ANALYSER',self.analyze_selected)
        w.button(controls,'■ STOP',lambda:winsound.PlaySound(None,winsound.SND_PURGE))
        w.button(controls,'VERS PISTE CHOISIE',lambda:self.assign(TRACKS.index(w.target_lane.get())))
        tk.Label(controls,textvariable=self.summary,bg=BG,fg=MUTED,wraplength=340,anchor='w').pack(side='left',padx=5)
        tk.Label(w.content,textvariable=self.analysis,bg=BG,fg=TEXT,justify='left',anchor='w',wraplength=550).pack(fill='x',pady=5)
        self.refresh()

    def analyze_selected(self):
        if self.analysis_busy:return
        try:path=self.current_path()
        except ValueError as exc:
            self.summary.set(str(exc));return
        self.analysis_busy=True
        self.analysis.set('Analyse du WAV en cours…')
        def work():
            try:result=analyze_wav(path);error=None
            except Exception as exc:result=None;error=str(exc)
            def finish():
                self.analysis_busy=False
                if error:self.analysis.set('Analyse impossible : '+error);return
                bpm=(str(result['bpm_estimate'])+' BPM (indicatif)' if result['bpm_estimate'] else 'indéterminé')
                self.analysis.set(
                    f"FICHE SON · {result['name']}\n"
                    f"Durée {result['duration_seconds']:.2f} s  |  {result['sample_rate_hz']} Hz  |  "
                    f"{result['channels']} canal(aux) · PCM {result['bit_depth']} bits\n"
                    f"Pic {result['peak_dbfs']} dBFS  |  RMS {result['rms_dbfs']} dBFS  |  BPM {bpm}")
            try:self.w.after(0,finish)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start()

    def filter_bank(self,bank):
        self.bank.set(bank);self.refresh()

    def choices(self):
        return librarian_choices(self.w.data_dir)

    def _favorites_path(self):
        return Path(self.w.data_dir)/'sample_favorites_v25.json'

    def load_favorites(self):
        try:
            path=self._favorites_path()
            if path.stat().st_size>8192:return set()
            data=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data,list):return set()
            return {v for v in data if isinstance(v,str) and v in
                    {f'{b}{i}' for b in 'ABCD' for i in range(1,9)}}
        except (OSError,ValueError,TypeError):return set()

    def save_favorites(self):
        path=self._favorites_path();path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(sorted(self.favorites),ensure_ascii=False),encoding='utf-8')
        os.replace(temp,path)

    def toggle_favorite(self,slot):
        if slot in self.favorites:self.favorites.remove(slot)
        else:self.favorites.add(slot)
        try:self.save_favorites()
        except OSError as exc:messagebox.showerror('Favoris',str(exc),parent=self.w)
        self.refresh()

    @staticmethod
    def normalize(text):
        return ''.join(c for c in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(c))

    @staticmethod
    def guess_type(name):
        text=LibraryPanel.normalize(name)
        for group,words in [('KICK',('kick','bd','grosse caisse','bassdrum')),
                            ('SNARE',('snare','caisse claire','clap')),
                            ('HAT',('hat','hihat','charley','cymbal')),
                            ('BASS',('bass','basse','sub')),
                            ('LEAD',('lead','synth','melodie','acid')),
                            ('PERC',('perc','tom','rim','conga','shaker'))]:
            if any(word in text for word in words):return group
        return 'AUTRES'

    def refresh(self):
        if not hasattr(self,'rows'):return
        for child in self.rows.winfo_children():child.destroy()
        choices=self.choices();filter_by=self.bank.get()
        needle=self.normalize(self.search.get().strip());category=self.category.get();count=0
        for name,path in choices.items():
            if filter_by!='TOUTES' and not name.startswith('LIB '+filter_by):continue
            slot=name[4:];title=self.display_name(slot)
            if needle not in self.normalize(slot+' '+title):continue
            if category!='TOUS' and self.guess_type(title)!=category:continue
            if self.favorites_only.get() and slot not in self.favorites:continue
            count+=1
            line=tk.Frame(self.rows,bg='#362521' if name==self.selected else DARK)
            line.pack(fill='x',padx=4,pady=2)
            star=tk.Button(line,text='★' if slot in self.favorites else '☆',width=2,bg=line['bg'],fg=RED,
                           relief='flat',command=lambda slot=slot:self.toggle_favorite(slot))
            star.pack(side='left')
            label=tk.Label(line,text=f'{slot}   {title[:31]}',bg=line['bg'],fg=TEXT,
                           anchor='w',cursor='hand2',pady=6)
            label.pack(side='left',fill='x',expand=True)
            for target in (line,label):
                target.bind('<ButtonPress-1>',lambda e,n=name:self.begin_drag(n))
                target.bind('<ButtonRelease-1>',self.end_drag)
            label.bind('<Double-Button-1>',lambda e,n=name:self.choose(n))
        self.visible_count.set(f'{count}/{len(choices)} sons')
        if not count:
            tk.Label(self.rows,text='Aucun sample correspondant.\nChange le filtre ou importe un WAV.',bg=DARK,fg=MUTED).pack(pady=15)
        if self.selected not in choices:self.selected=None
        self.draw_wave()

    def display_name(self,slot):
        index=Path(self.w.data_dir)/'sample_librarian'/'library.json'
        try:
            if index.stat().st_size>200_000:return slot
            obj=json.loads(index.read_text(encoding='utf-8'))
            key=slot[0]+str(int(slot[1:])-1)
            return str(obj.get('slots',{}).get(key,{}).get('name',slot))[:80]
        except (OSError,ValueError,TypeError):return slot

    def choose(self,name):
        if name not in self.choices():return
        self.selected=name
        self.summary.set(f'{name} sélectionné. Glisse-le vers une piste ou clique sur sa destination.')
        self.analysis.set('FICHE SON · Clique sur ANALYSER pour obtenir les mesures du WAV.')
        self.refresh()

    def begin_drag(self,name):
        self.selected=name;self.drag=name
        self.summary.set(f'{name} : déposer sur KICK, SNARE, HAT, BASS, LEAD ou PERC')
        self.draw_wave()

    def end_drag(self,event):
        name=self.drag;self.drag=None
        if not name:return
        target=self.w.winfo_containing(self.w.winfo_pointerx(),self.w.winfo_pointery())
        while target is not None:
            lane=getattr(target,'_moktek_lane',None)
            if lane is not None:
                self.assign(lane,name);return
            target=target.master
        self.summary.set(f'{name} sélectionné : clique sur une piste pour l’affecter.')

    def assign(self,lane,name=None):
        sound=name or self.selected
        if sound not in self.choices():
            self.summary.set('Choisis d’abord un sample valide.');return
        if not 0<=lane<len(TRACKS):return
        self.w.seq_sounds[lane]=sound
        self.targets[lane].configure(text=TRACKS[lane]+'\n'+sound,bg='#68221d')
        self.w.state.set(f'V24 : {sound} affecté à {TRACKS[lane]} • ouvre SEQ pour écouter ou enregistrer le pattern')
        self.summary.set(f'{sound} → {TRACKS[lane]} • affectation locale uniquement')

    def current_path(self):
        path=self.choices().get(self.selected)
        if not path:raise ValueError('Sélectionne un sample dans la bibliothèque.')
        return Path(path)

    def preview(self):
        try:
            path=self.current_path()
            winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC)
        except Exception as exc:messagebox.showerror('Préécoute',str(exc),parent=self.w)

    def import_wav(self):
        file=filedialog.askopenfilename(parent=self.w,filetypes=[('WAV PCM 16 bits','*.wav')])
        if not file:return
        try:
            path=Path(file)
            if path.stat().st_size>80*1024*1024:raise ValueError('WAV supérieur à 80 Mo')
            with wave.open(str(path),'rb') as src:
                if src.getcomptype()!='NONE' or src.getsampwidth()!=2 or src.getnchannels()!=1:
                    raise ValueError('WAV PCM 16 bits mono requis (convertir dans Sample Studio avancé)')
                if src.getnframes()>src.getframerate()*180:
                    raise ValueError('Maximum 3 minutes pour cet import')
                sound=store_pcm(self.w.data_dir,src.readframes(src.getnframes()),src.getframerate(),path.stem)
            self.bank.set('TOUTES');self.selected=sound;self.refresh()
            self.summary.set(f'{sound} importé dans un emplacement libre')
        except Exception as exc:messagebox.showerror('Import WAV',str(exc),parent=self.w)

    def draw_wave(self):
        if self.wave is None:return
        c=self.wave;c.delete('all');w=max(1,c.winfo_width());h=max(1,c.winfo_height())
        c.create_line(0,h/2,w,h/2,fill=STEEL)
        try:
            path=self.current_path()
            if path.stat().st_size>80*1024*1024:return
            with wave.open(str(path),'rb') as f:
                if f.getsampwidth()!=2 or f.getnchannels() not in (1,2):return
                n=f.getnframes();channels=f.getnchannels()
                if n<=0:return
                # Bounded waveform preview: sample at most 1200 short slices, no huge full-file load.
                for x in range(0,w,2):
                    start=int(x*n/w);f.setpos(start)
                    raw=f.readframes(min(100,max(1,n-start)))
                    a=array.array('h');a.frombytes(raw)
                    if sys.byteorder!='little':a.byteswap()
                    if not a:continue
                    values=a[::channels]
                    hi=max(values)/32768;lo=min(values)/32768
                    c.create_line(x,h/2-hi*h*.44,x,h/2-lo*h*.44,fill=RED,width=2)
        except (OSError,ValueError,wave.Error):return
