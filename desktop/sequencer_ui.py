"""Tribe Sequencer window, visually aligned with Android's dark/red interface."""
import json
import tempfile
import winsound
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from sequencer_engine import TRACKS, SOUNDS, DEFAULT_SOUNDS, default_pattern, render, export_wav, librarian_choices
BG='#100f10';PANEL='#211d1a';RED='#ff493e';STEEL='#887766';TEXT='#e9dac2';MUTED='#b9a99b'

class TribeSequencer(tk.Toplevel):
    def __init__(self, parent, data_dir):
        super().__init__(parent)
        self.title('mokteK // TRIBE SEQUENCER • Windows V7')
        self.geometry('1240x690');self.minsize(880,510);self.configure(bg=BG)
        self.data_dir=Path(data_dir);self.preview_path=None
        self.steps=tk.IntVar(value=16);self.bpm=tk.IntVar(value=174)
        self.repeat=tk.IntVar(value=2)
        self.style=tk.StringVar(value='TRIBE')
        self.sounds=[tk.StringVar(value=s) for s in DEFAULT_SOUNDS]
        self.volumes=[tk.DoubleVar(value=.8) for _ in TRACKS]
        self.mutes=[tk.BooleanVar(value=False) for _ in TRACKS]
        self.solos=[tk.BooleanVar(value=False) for _ in TRACKS]
        self.swing=tk.IntVar(value=0)
        self.extra_sounds={}
        self.refresh_librarian_choices()
        self.pattern=default_pattern('TRIBE',16)
        self.status=tk.StringVar(value='Séquenceur local • lecture WAV Windows • aucun transfert matériel')
        self.buttons=[]
        top=tk.Frame(self,bg='#332b25',padx=14,pady=12);top.pack(fill='x')
        tk.Label(top,text='TRIBE SEQUENCER  //  6 TRACKS',bg='#332b25',fg=RED,font=('Segoe UI',19,'bold')).pack(side='left')
        tk.Label(top,text='V7  •  16 / 32 / 64 STEPS',bg='#332b25',fg=MUTED,font=('Segoe UI',10,'bold')).pack(side='right')
        tk.Frame(self,bg=RED,height=3).pack(fill='x')
        controls=tk.Frame(self,bg=PANEL,padx=12,pady=12);controls.pack(fill='x',padx=12,pady=(10,4))
        self.label(controls,'STYLE').pack(side='left')
        ttk.Combobox(controls,textvariable=self.style,values=['TRIBE','JUNGLE','GABBER','BREAKCORE'],width=13,state='readonly').pack(side='left',padx=6)
        self.button(controls,'CHARGER STYLE',self.load_style).pack(side='left',padx=5)
        self.label(controls,'PAS').pack(side='left',padx=(15,0))
        ttk.Combobox(controls,textvariable=self.steps,values=[16,32,64],width=5,state='readonly').pack(side='left',padx=6)
        self.steps.trace_add('write',lambda *_:self.resize_pattern())
        self.label(controls,'BPM').pack(side='left',padx=(15,0))
        tk.Spinbox(controls,from_=40,to=300,textvariable=self.bpm,width=5,bg='#150e0e',fg=TEXT,buttonbackground=PANEL).pack(side='left',padx=6)
        self.label(controls,'SWING %').pack(side='left',padx=(15,0))
        tk.Spinbox(controls,from_=0,to=75,textvariable=self.swing,width=4,bg='#150e0e',fg=TEXT,buttonbackground=PANEL).pack(side='left',padx=6)
        self.label(controls,'BOUCLES').pack(side='left',padx=(15,0))
        tk.Spinbox(controls,from_=1,to=16,textvariable=self.repeat,width=4,bg='#150e0e',fg=TEXT,buttonbackground=PANEL).pack(side='left',padx=6)
        self.button(controls,'EFFACER',self.clear_pattern).pack(side='right',padx=4)
        self.button(controls,'↻ SAMPLES',self.refresh_samples).pack(side='right',padx=4)
        grid_box=tk.Frame(self,bg=PANEL,padx=8,pady=10);grid_box.pack(fill='both',expand=True,padx=12,pady=7)
        tk.Label(grid_box,text='Clic pour activer/désactiver un pas   •   Défilement horizontal pour 32/64 pas',bg=PANEL,fg=MUTED,anchor='w').pack(fill='x',pady=(0,7))
        container=tk.Frame(grid_box,bg=PANEL);container.pack(fill='both',expand=True)
        self.scroll=tk.Canvas(container,bg=PANEL,highlightthickness=0)
        scrollbar=tk.Scrollbar(container,orient='horizontal',command=self.scroll.xview)
        self.scroll.configure(xscrollcommand=scrollbar.set)
        self.scroll.pack(fill='both',expand=True);scrollbar.pack(fill='x')
        self.inner=tk.Frame(self.scroll,bg=PANEL)
        self.scroll_window=self.scroll.create_window((0,0),window=self.inner,anchor='nw')
        self.inner.bind('<Configure>',lambda _:self.scroll.configure(scrollregion=self.scroll.bbox('all')))
        actions=tk.Frame(self,bg='#332b25',padx=10,pady=11);actions.pack(fill='x',padx=12,pady=(0,8))
        for name,cmd in [('▶ ÉCOUTER',self.preview),('■ STOP',self.stop),('EXPORT WAV',self.export),('SAUVER PATTERN',self.save_pattern),('OUVRIR PATTERN',self.open_pattern)]:
            self.button(actions,name,cmd).pack(side='left',expand=True,fill='x',padx=3)
        tk.Label(self,textvariable=self.status,bg=BG,fg=MUTED,anchor='w',padx=16,pady=6).pack(fill='x')
        self.redraw()
        self.protocol('WM_DELETE_WINDOW',self.close)

    def label(self,parent,text):
        return tk.Label(parent,text=text,bg=PANEL,fg=TEXT,font=('Segoe UI',10,'bold'))
    def button(self,parent,text,command):
        return tk.Button(parent,text=text,command=command,bg='#49201e',fg=TEXT,activebackground=RED,activeforeground='white',relief='flat',padx=9,pady=8,cursor='hand2')
    def resize_pattern(self):
        try:count=self.steps.get()
        except tk.TclError:return
        if count not in (16,32,64):return
        for row in self.pattern:row[:]=row[:count]+[False]*max(0,count-len(row))
        self.redraw()
    def load_style(self):
        self.stop();self.pattern=default_pattern(self.style.get(),self.steps.get());self.redraw();self.status.set('Style chargé : '+self.style.get())
    def clear_pattern(self):
        self.stop();self.pattern=[[False]*self.steps.get() for _ in TRACKS];self.redraw()
    def toggle(self,track,step):
        self.pattern[track][step]=not self.pattern[track][step]
        self.buttons[track][step].configure(bg=RED if self.pattern[track][step] else ('#382c29' if (step//4)%2==0 else '#241a1a'))
    def redraw(self):
        if not hasattr(self,'inner'):return
        for widget in self.inner.winfo_children():widget.destroy()
        self.buttons=[]
        tk.Label(self.inner,text='PISTE / SOURCE / MIXER',width=52,bg=PANEL,fg=TEXT,anchor='w').grid(row=0,column=0,sticky='w')
        for step in range(self.steps.get()):
            tk.Label(self.inner,text=str(step+1),width=3,bg=PANEL,fg=RED if step%4==0 else MUTED,font=('Consolas',9)).grid(row=0,column=step+1)
        for ti,name in enumerate(TRACKS):
            section=tk.Frame(self.inner,bg=PANEL)
            section.grid(row=ti+1,column=0,sticky='w',padx=(0,8),pady=5)
            tk.Label(section,text=name,width=7,anchor='w',bg=PANEL,fg=TEXT,font=('Consolas',10,'bold')).pack(side='left')
            ttk.Combobox(section,textvariable=self.sounds[ti],values=list(SOUNDS)+list(self.extra_sounds),width=16,state='readonly').pack(side='left',padx=2)
            tk.Checkbutton(section,text='M',variable=self.mutes[ti],bg=PANEL,fg=RED,selectcolor='#161111',activebackground=PANEL).pack(side='left')
            tk.Checkbutton(section,text='S',variable=self.solos[ti],bg=PANEL,fg='#f0c969',selectcolor='#161111',activebackground=PANEL).pack(side='left')
            tk.Scale(section,variable=self.volumes[ti],from_=0,to=1,resolution=.05,orient='horizontal',length=94,showvalue=False,highlightthickness=0,bg=PANEL,fg=TEXT,troughcolor='#6c302c',activebackground=RED).pack(side='left')
            buttons=[]
            for step in range(self.steps.get()):
                enabled=self.pattern[ti][step]
                base='#382c29' if (step//4)%2==0 else '#241a1a'
                b=tk.Button(self.inner,width=2,height=1,relief='flat',bg=RED if enabled else base,activebackground='#ff9d8e',command=lambda tr=ti,s=step:self.toggle(tr,s))
                b.grid(row=ti+1,column=step+1,padx=1,pady=5,sticky='ns')
                buttons.append(b)
            self.buttons.append(buttons)
        self.scroll.xview_moveto(0)
    def inputs(self):
        try:
            bpm=int(self.bpm.get());reps=int(self.repeat.get());steps=int(self.steps.get())
            if bpm<40 or bpm>300 or reps<1 or reps>16:raise ValueError('BPM 40–300 ; boucles 1–16')
            return bpm,steps,reps
        except (tk.TclError,ValueError) as exc:raise ValueError('Vérifie le BPM et les répétitions') from exc
    def audio(self):
        bpm,steps,reps=self.inputs()
        swing=self.swing.get()
        return render(self.pattern,bpm,steps,[s.get() for s in self.sounds],[v.get() for v in self.volumes],bars=reps,mutes=[v.get() for v in self.mutes],solos=[v.get() for v in self.solos],swing=swing,data_dir=self.data_dir)
    def stop(self):
        winsound.PlaySound(None,0)
        if self.preview_path is not None:
            try:self.preview_path.unlink(missing_ok=True)
            except OSError:pass
            self.preview_path=None
    def preview(self):
        self.stop()
        try:
            pcm=self.audio()
            f=tempfile.NamedTemporaryFile(suffix='.wav',delete=False);f.close()
            self.preview_path=Path(f.name);export_wav(f.name,pcm)
            winsound.PlaySound(str(self.preview_path),winsound.SND_FILENAME|winsound.SND_ASYNC)
            self.status.set(f'Lecture locale : {len(pcm)//2/44100:.1f} secondes • STOP pour arrêter')
        except Exception as exc:messagebox.showerror('Séquenceur',str(exc),parent=self)
    def export(self):
        path=filedialog.asksaveasfilename(parent=self,title='Exporter la séquence',defaultextension='.wav',initialfile='moktek-tribe-sequence.wav',filetypes=[('WAV PCM 16 bits','*.wav')])
        if not path:return
        try:
            export_wav(path,self.audio());self.status.set('WAV exporté : '+Path(path).name)
        except Exception as exc:messagebox.showerror('Export',str(exc),parent=self)
    def save_pattern(self):
        self.data_dir.mkdir(parents=True,exist_ok=True)
        path=filedialog.asksaveasfilename(parent=self,initialdir=str(self.data_dir),defaultextension='.json',initialfile='tribe-pattern.json',filetypes=[('Pattern mokteK','*.json')])
        if not path:return
        payload={'format':'moktek-windows-sequencer-v2','steps':self.steps.get(),'bpm':self.bpm.get(),'loops':self.repeat.get(),'pattern':self.pattern,'sounds':[v.get() for v in self.sounds],'volumes':[v.get() for v in self.volumes],'mutes':[v.get() for v in self.mutes],'solos':[v.get() for v in self.solos],'swing':self.swing.get()}
        try:Path(path).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');self.status.set('Pattern sauvegardé')
        except Exception as exc:messagebox.showerror('Sauvegarde',str(exc),parent=self)
    def open_pattern(self):
        path=filedialog.askopenfilename(parent=self,initialdir=str(self.data_dir),filetypes=[('Pattern mokteK','*.json')])
        if not path:return
        try:
            if Path(path).stat().st_size>200000:raise ValueError('Fichier trop volumineux')
            data=json.loads(Path(path).read_text(encoding='utf-8'))
            steps=data['steps'];pattern=data['pattern'];sounds=data['sounds']
            if data.get('format') not in ('moktek-windows-sequencer-v1','moktek-windows-sequencer-v2') or steps not in (16,32,64) or len(pattern)!=6 or len(sounds)!=6 or any(len(row)!=steps or any(type(v)!=bool for v in row) for row in pattern) or any(s not in SOUNDS and s not in self.extra_sounds for s in sounds):raise ValueError('Format de pattern invalide')
            bpm=int(data['bpm']);loops=int(data['loops'])
            if not 40<=bpm<=300 or not 1<=loops<=16:raise ValueError('Tempo / boucles invalides')
            volumes=data.get('volumes',[.8]*6);mutes=data.get('mutes',[False]*6);solos=data.get('solos',[False]*6);swing=data.get('swing',0)
            if len(volumes)!=6 or any(not isinstance(v,(int,float)) or not 0<=v<=1 for v in volumes) or len(mutes)!=6 or len(solos)!=6 or any(type(v)!=bool for v in mutes+solos) or type(swing)!=int or not 0<=swing<=75:raise ValueError('Paramètres mixer invalides')
            self.stop();self.steps.set(steps);self.pattern=pattern;self.bpm.set(bpm);self.repeat.set(loops);self.swing.set(swing)
            for var,val in zip(self.volumes,volumes):var.set(val)
            for var,val in zip(self.mutes,mutes):var.set(val)
            for var,val in zip(self.solos,solos):var.set(val)
            for var,value in zip(self.sounds,sounds):var.set(value)
            self.redraw();self.status.set('Pattern restauré • '+Path(path).name)
        except Exception as exc:messagebox.showerror('Ouverture',str(exc),parent=self)
    def refresh_librarian_choices(self):
        self.extra_sounds=librarian_choices(self.data_dir)

    def refresh_samples(self):
        self.refresh_librarian_choices()
        self.redraw()
        self.status.set(f'{len(self.extra_sounds)} sample(s) Librarian disponibles • les sources absentes ne seront pas remplacées')

    def close(self):
        self.stop();self.destroy()
