"""Integrated, local-only V22 workbench tools; full legacy editors remain available.
No MIDI command or hardware write is issued from this module.
"""
import json
import wave
import winsound
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from synth_factory import generate, PRESETS, save_wav
from sequencer_engine import TRACKS, DEFAULT_SOUNDS, default_pattern, render, export_wav
from sample_bridge_v23 import store_pcm, available_sounds
from library_panel_v24 import LibraryPanel

BG='#100f10'; PANEL='#211d1a'; RED='#ff493e'; TEXT='#e9dac2'; MUTED='#b9a99b'; STEEL='#887766'

class Workbench(tk.Frame):
    def __init__(self, parent, data_dir, open_full):
        super().__init__(parent,bg=PANEL)
        self.data_dir=Path(data_dir)
        self.open_full=open_full
        self.current=None
        self.player_file=None
        self.sample_path=None
        self.sample_pcm=None
        self.sample_rate=44100
        self.sample_selection=(0,1)
        self.seq_pattern=default_pattern('TRIBE',16)
        self.seq_sounds=list(DEFAULT_SOUNDS)
        self.target_lane=tk.StringVar(value=TRACKS[0])
        self.seq_bpm=tk.IntVar(value=174)
        self.seq_style=tk.StringVar(value='TRIBE')
        self.synth_preset=tk.StringVar(value='TRIBE KICK')
        self.synth_pitch=tk.DoubleVar(value=55)
        self.synth_duration=tk.DoubleVar(value=.65)
        self.synth_drive=tk.DoubleVar(value=.20)
        self.synth_color=tk.DoubleVar(value=.40)
        self.synth_volume=tk.DoubleVar(value=.73)
        self.synth_kind='Kick'
        self.state=tk.StringVar(value='Atelier intégré • traitement local uniquement')
        self.library_panel=None
        self.header=tk.Frame(self,bg=PANEL)
        self.header.pack(fill='x',pady=4)
        self.content=tk.Frame(self,bg=PANEL)
        self.content.pack(fill='both',expand=True)
        tk.Label(self,textvariable=self.state,bg=PANEL,fg=MUTED,anchor='w',wraplength=550).pack(fill='x',pady=6)

    def button(self,parent,label,action):
        b=tk.Button(parent,text=label,command=action,bg='#392a28',fg=TEXT,activebackground='#75201c',activeforeground='white',pady=7,relief='flat',highlightbackground=STEEL,highlightthickness=1)
        b.pack(side='left',padx=3,pady=2)
        return b

    def label(self,parent,text):
        return tk.Label(parent,text=text,bg=PANEL,fg=TEXT)

    def show(self,tool):
        self.current=tool
        winsound.PlaySound(None,winsound.SND_PURGE)
        for child in self.header.winfo_children():child.destroy()
        for child in self.content.winfo_children():child.destroy()
        title={'sample':'SAMPLE STUDIO','synth':'SYNTH FACTORY','seq':'TRIBE SEQUENCER','library':'BIBLIOTHÈQUE VISUELLE V24'}[tool]
        tk.Label(self.header,text=title,bg=PANEL,fg=RED,font=('Segoe UI',16,'bold')).pack(side='left')
        self.button(self.header,'ÉDITEUR AVANCÉ',lambda:self.open_full(tool)).pack_configure(side='right')
        if tool=='sample':self.build_sample()
        elif tool=='synth':self.build_synth()
        elif tool=='library':
            self.library_panel=LibraryPanel(self)
            self.library_panel.build()
        else:self.build_sequencer()
        self.state.set('Atelier intégré : '+title+' • aucune écriture vers le KP3')

    def build_sample(self):
        row=tk.Frame(self.content,bg=PANEL);row.pack(fill='x')
        self.button(row,'IMPORTER WAV',self.load_sample)
        self.button(row,'▶ ÉCOUTER',self.preview_sample)
        self.button(row,'■ STOP',self.stop_audio)
        self.button(row,'EXPORTER SÉLECTION',self.export_sample)
        self.button(row,'→ BANQUE + SEQ',self.send_sample_to_seq)
        self.sample_info=tk.StringVar(value='WAV PCM 16 bits mono • importer un fichier pour commencer')
        self.label(self.content,'Déplacer la souris sur la forme d’onde pour sélectionner un passage.').pack(anchor='w',pady=6)
        self.sample_canvas=tk.Canvas(self.content,bg='#19090c',highlightbackground=RED,highlightthickness=2,height=260,cursor='crosshair')
        self.sample_canvas.pack(fill='both',expand=True,pady=7)
        self.sample_canvas.bind('<Configure>',lambda _:self.draw_sample())
        self.sample_canvas.bind('<Button-1>',self.sample_start)
        self.sample_canvas.bind('<B1-Motion>',self.sample_drag)
        self.label(self.content,'').pack()
        tk.Label(self.content,textvariable=self.sample_info,bg=PANEL,fg=MUTED,anchor='w').pack(fill='x')

    def load_sample(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('WAV','*.wav')]);
        if not path:return
        try:
            with wave.open(path,'rb') as src:
                if src.getcomptype()!='NONE' or src.getsampwidth()!=2 or src.getnchannels()!=1:
                    raise ValueError('WAV PCM 16 bits mono requis. Convertis le fichier dans Sample Studio avancé.')
                if src.getnframes()>44100*180:raise ValueError('WAV trop long (maximum 3 min dans l’atelier intégré).')
                self.sample_rate=src.getframerate();self.sample_pcm=src.readframes(src.getnframes())
            self.sample_path=Path(path);self.sample_selection=(0,1)
            self.sample_info.set(f'{self.sample_path.name} • {len(self.sample_pcm)/2/self.sample_rate:.2f} s • {self.sample_rate} Hz')
            self.draw_sample()
        except Exception as exc:messagebox.showerror('Sample Studio',str(exc),parent=self)

    def sample_start(self,e):
        if self.sample_pcm is None:return
        x=min(1,max(0,e.x/max(1,self.sample_canvas.winfo_width())))
        self.sample_selection=(x,x)
        self.draw_sample()
    def sample_drag(self,e):
        if self.sample_pcm is None:return
        x=min(1,max(0,e.x/max(1,self.sample_canvas.winfo_width())))
        self.sample_selection=(self.sample_selection[0],x)
        self.draw_sample()
    def selection_pcm(self):
        if self.sample_pcm is None:raise ValueError('Importe un WAV.')
        a,b=sorted(self.sample_selection)
        if b-a<.001:return self.sample_pcm
        frames=len(self.sample_pcm)//2
        start=int(a*frames)*2;end=max(start+2,int(b*frames)*2)
        return self.sample_pcm[start:end]
    def draw_sample(self):
        if not hasattr(self,'sample_canvas'):return
        c=self.sample_canvas;c.delete('all')
        w=max(1,c.winfo_width());h=max(1,c.winfo_height())
        for x in range(0,w,40):c.create_line(x,0,x,h,fill='#382127')
        c.create_line(0,h//2,w,h//2,fill=STEEL)
        if self.sample_pcm is None:return
        import array,sys
        samples=array.array('h');samples.frombytes(self.sample_pcm)
        if sys.byteorder!='little':samples.byteswap()
        frames=len(samples)
        for x in range(w):
            begin=int(x*frames/w);end=min(frames,max(begin+1,int((x+1)*frames/w)))
            if begin>=frames:break
            # Drawing uses envelope sampling, not a 1:1 raster of every audio sample.
            stride=max(1,(end-begin)//60)
            chunk=samples[begin:end:stride];lo=min(chunk)/32768;hi=max(chunk)/32768
            c.create_line(x,h/2-hi*h*.43,x,h/2-lo*h*.43,fill=RED)
        a,b=sorted(self.sample_selection)
        if b-a>.001:c.create_rectangle(a*w,0,b*w,h,fill='#603a28',stipple='gray50',outline='#f9b7a4')
    def preview_sample(self):
        try:
            pcm=self.selection_pcm()
            path=self.data_dir/'preview_sample_v22.wav';path.parent.mkdir(parents=True,exist_ok=True)
            save_wav(path,pcm,self.sample_rate)
            self.player_file=path
            winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC)
        except Exception as exc:messagebox.showerror('Préécoute',str(exc),parent=self)
    def stop_audio(self):winsound.PlaySound(None,winsound.SND_PURGE)
    def export_sample(self):
        try:
            pcm=self.selection_pcm()
            target=filedialog.asksaveasfilename(parent=self,defaultextension='.wav',filetypes=[('WAV','*.wav')]);
            if target:save_wav(target,pcm,self.sample_rate);self.state.set('Sample exporté : '+Path(target).name)
        except Exception as exc:messagebox.showerror('Export',str(exc),parent=self)

    def send_sample_to_seq(self):
        try:
            sound=store_pcm(self.data_dir,self.selection_pcm(),self.sample_rate,
                            self.sample_path.stem if self.sample_path else 'Extrait WAV')
            self.assign_sound(sound)
        except Exception as exc:messagebox.showerror('Bibliothèque',str(exc),parent=self)

    def assign_sound(self,sound):
        lane=TRACKS.index(self.target_lane.get())
        self.seq_sounds[lane]=sound
        self.state.set(f'{sound} affecté à {TRACKS[lane]} • nouveau sample ajouté à une banque libre')
        self.show('seq')

    def send_synth_to_seq(self):
        try:
            sound=store_pcm(self.data_dir,self.synth_pcm(),44100,self.synth_preset.get())
            self.assign_sound(sound)
        except Exception as exc:messagebox.showerror('Bibliothèque',str(exc),parent=self)

    def build_synth(self):
        row=tk.Frame(self.content,bg=PANEL);row.pack(fill='x',pady=5)
        self.label(row,'PRESET').pack(side='left',padx=4)
        ttk.Combobox(row,textvariable=self.synth_preset,values=list(PRESETS),state='readonly',width=23).pack(side='left',padx=6)
        self.button(row,'CHARGER',self.load_preset)
        for title,var,low,high,step in [
            ('FRÉQUENCE Hz',self.synth_pitch,25,1000,1),('DURÉE s',self.synth_duration,.05,3,.05),
            ('DRIVE',self.synth_drive,0,1,.01),('COULEUR',self.synth_color,0,1,.01),('VOLUME',self.synth_volume,0,1,.01)]:
            line=tk.Frame(self.content,bg=PANEL);line.pack(fill='x',pady=4)
            self.label(line,title).pack(side='left')
            tk.Scale(line,from_=low,to=high,resolution=step,variable=var,orient='horizontal',bg=PANEL,fg=TEXT,
                     troughcolor='#54211e',highlightthickness=0,length=300).pack(side='right',fill='x',expand=True)
        row=tk.Frame(self.content,bg=PANEL);row.pack(fill='x',pady=10)
        self.button(row,'▶ PRÉÉCOUTE',self.preview_synth)
        self.button(row,'■ STOP',self.stop_audio)
        self.button(row,'EXPORT WAV',self.export_synth)
        self.button(row,'→ BANQUE + SEQ',self.send_synth_to_seq)
        self.load_preset()
        self.label(self.content,'Moteur audio local • le rendu peut différer de celui d’Android.').pack(anchor='w')

    def load_preset(self):
        self.synth_kind,frequency,duration,volume,drive,color=PRESETS[self.synth_preset.get()]
        for var,value in [(self.synth_pitch,frequency),(self.synth_duration,duration),(self.synth_volume,volume),(self.synth_drive,drive),(self.synth_color,color)]:var.set(value)
    def synth_pcm(self):
        return generate(self.synth_kind,float(self.synth_pitch.get()),float(self.synth_duration.get()),float(self.synth_volume.get()),float(self.synth_drive.get()),float(self.synth_color.get()))
    def preview_synth(self):
        try:
            pcm=self.synth_pcm();path=self.data_dir/'preview_synth_v22.wav';path.parent.mkdir(parents=True,exist_ok=True)
            save_wav(path,pcm);winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC)
        except Exception as exc:messagebox.showerror('Synth Factory',str(exc),parent=self)
    def export_synth(self):
        try:
            pcm=self.synth_pcm();path=filedialog.asksaveasfilename(parent=self,defaultextension='.wav',filetypes=[('WAV','*.wav')])
            if path:save_wav(path,pcm);self.state.set('Synth WAV exporté : '+Path(path).name)
        except Exception as exc:messagebox.showerror('Export synthé',str(exc),parent=self)

    def build_sequencer(self):
        row=tk.Frame(self.content,bg=PANEL);row.pack(fill='x',pady=(4,10))
        self.label(row,'STYLE').pack(side='left')
        ttk.Combobox(row,values=['TRIBE','JUNGLE','GABBER','BREAKCORE'],textvariable=self.seq_style,width=12,state='readonly').pack(side='left',padx=4)
        self.button(row,'CHARGER STYLE',self.load_seq_style)
        self.label(row,'BPM').pack(side='left',padx=(14,3))
        tk.Spinbox(row,from_=40,to=300,textvariable=self.seq_bpm,width=5,bg=BG,fg=TEXT).pack(side='left')
        self.button(row,'▶ LIRE',self.preview_sequence)
        self.button(row,'■ STOP',self.stop_audio)
        library_row=tk.Frame(self.content,bg=PANEL);library_row.pack(fill='x',pady=5)
        self.label(library_row,'DESTINATION').pack(side='left',padx=4)
        ttk.Combobox(library_row,textvariable=self.target_lane,values=TRACKS,state='readonly',width=10).pack(side='left',padx=4)
        self.button(library_row,'ACTUALISER BANQUES',self.refresh_sequencer)
        self.button(library_row,'BIBLIOTHÈQUE VISUELLE',lambda:self.show('library'))
        self.label(library_row,'Choisir un son par piste : presets ou banques A–D').pack(side='left',padx=8)
        grid=tk.Frame(self.content,bg=PANEL);grid.pack(fill='both',expand=True)
        self.seq_buttons=[]
        for lane,name in enumerate(TRACKS):
            self.label(grid,name).grid(row=lane,column=0,sticky='w',padx=(0,4),pady=5)
            choices=available_sounds(self.data_dir)
            if self.seq_sounds[lane] not in choices:self.seq_sounds[lane]=DEFAULT_SOUNDS[lane]
            selected=tk.StringVar(value=self.seq_sounds[lane])
            selector=ttk.Combobox(grid,textvariable=selected,values=choices,state='readonly',width=16)
            selector.grid(row=lane,column=1,padx=3,sticky='ew')
            selector.bind('<<ComboboxSelected>>',lambda _e,lane=lane,selected=selected:self.set_track_sound(lane,selected.get()))
            buttons=[]
            for step in range(16):
                b=tk.Button(grid,text='●' if self.seq_pattern[lane][step] else '·',width=2,bg=RED if self.seq_pattern[lane][step] else '#34251e',fg=TEXT,
                            activebackground='#ff8272',relief='flat',command=lambda lane=lane,step=step:self.toggle_seq(lane,step))
                b.grid(row=lane,column=step+2,sticky='nsew',padx=1,pady=4)
                buttons.append(b)
            self.seq_buttons.append(buttons)
        for col in range(2,18):grid.grid_columnconfigure(col,weight=1)
        row=tk.Frame(self.content,bg=PANEL);row.pack(fill='x',pady=8)
        self.button(row,'ENREGISTRER PATTERN',self.save_sequence)
        self.button(row,'OUVRIR PATTERN',self.load_sequence)
        self.button(row,'EXPORT WAV',self.export_sequence)
        self.label(self.content,'V24 : bibliothèque visuelle intégrée • banques A–D par piste • 16 pas intégrés. Éditeur avancé pour 32/64 pas, swing et FX.').pack(anchor='w')
    def set_track_sound(self,lane,name):
        if name in available_sounds(self.data_dir):
            self.seq_sounds[lane]=name
            self.state.set(f'Piste {TRACKS[lane]} : {name}')

    def refresh_sequencer(self):
        self.build_seq_again()
        self.state.set('Banques actualisées • 32 emplacements possibles')

    def toggle_seq(self,lane,step):
        active=not self.seq_pattern[lane][step];self.seq_pattern[lane][step]=active
        self.seq_buttons[lane][step].configure(bg=RED if active else '#34251e',text='●' if active else '·')
    def load_seq_style(self):
        self.seq_pattern=default_pattern(self.seq_style.get(),16)
        self.build_seq_again()
    def build_seq_again(self):
        for child in self.content.winfo_children():child.destroy()
        self.build_sequencer()
    def seq_audio(self):
        return render(self.seq_pattern,int(self.seq_bpm.get()),16,self.seq_sounds,[.8]*6,1,data_dir=self.data_dir)
    def preview_sequence(self):
        try:
            pcm=self.seq_audio();path=self.data_dir/'preview_seq_v22.wav';path.parent.mkdir(parents=True,exist_ok=True)
            export_wav(path,pcm);winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC)
        except Exception as exc:messagebox.showerror('Séquenceur',str(exc),parent=self)
    def export_sequence(self):
        try:
            pcm=self.seq_audio();path=filedialog.asksaveasfilename(parent=self,defaultextension='.wav',filetypes=[('WAV','*.wav')])
            if path:export_wav(path,pcm);self.state.set('Pattern WAV exporté : '+Path(path).name)
        except Exception as exc:messagebox.showerror('Séquenceur',str(exc),parent=self)
    def save_sequence(self):
        doc={'format':'moktek-sequencer-v22-integrated','version':1,'steps':16,'bpm':int(self.seq_bpm.get()),'pattern':self.seq_pattern,'sounds':self.seq_sounds}
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.json',filetypes=[('Pattern intégré','*.json')])
        if path:Path(path).write_text(json.dumps(doc,indent=2),encoding='utf-8');self.state.set('Pattern enregistré : '+Path(path).name)
    def load_sequence(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('Pattern intégré','*.json')]);
        if not path:return
        try:
            if Path(path).stat().st_size>64_000:raise ValueError('Fichier trop volumineux')
            doc=json.loads(Path(path).read_text(encoding='utf-8'))
            p=doc.get('pattern')
            if doc.get('format')!='moktek-sequencer-v22-integrated' or doc.get('steps')!=16 or type(p)!=list or len(p)!=6 or any(type(row)!=list or len(row)!=16 or any(type(n)!=bool for n in row) for row in p):raise ValueError('Pattern non compatible')
            bpm=doc.get('bpm')
            if type(bpm)!=int or not 40<=bpm<=300:raise ValueError('BPM invalide')
            sounds=doc.get('sounds',list(DEFAULT_SOUNDS))
            if (not isinstance(sounds,list) or len(sounds)!=6 or
                    any(not isinstance(n,str) or len(n)>100 for n in sounds)):
                raise ValueError('Affectations sonores invalides')
            self.seq_sounds=sounds
            self.seq_bpm.set(bpm);self.seq_pattern=p;self.build_seq_again()
            self.state.set('Pattern chargé : '+Path(path).name)
        except (OSError,ValueError,TypeError) as exc:messagebox.showerror('Pattern',str(exc),parent=self)
