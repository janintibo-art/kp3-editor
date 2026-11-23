"""Accessible Windows V9 arranger with simple linear timeline."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from arranger_engine import SECTIONS, make_project, load_project, render_song, validate_timeline
from sequencer_engine import RATE, export_wav
BG='#100f10';PANEL='#211d1a';RED='#ff493e';TEXT='#e9dac2';MUTED='#b9a99b'

class SongArranger(tk.Toplevel):
    def __init__(self,parent,sequencer):
        super().__init__(parent)
        self.source=sequencer
        self.title('mokteK // ARRANGEUR • Windows V9')
        self.geometry('860x615');self.minsize(700,510);self.configure(bg=BG)
        self.blocks=[];self.pattern=tk.StringVar(value='A');self.section=tk.StringVar(value='INTRO');self.repeats=tk.IntVar(value=1)
        self.status=tk.StringVar(value='Mémorise les patterns A–D dans le séquenceur avant de composer. Durée max : 120 s.')
        top=tk.Frame(self,bg='#332b25',padx=16,pady=13);top.pack(fill='x')
        tk.Label(top,text='SONG ARRANGER  //  TIMELINE',font=('Segoe UI',18,'bold'),bg='#332b25',fg=RED).pack(side='left')
        tk.Label(top,text='V9  •  OFFLINE WAV',bg='#332b25',fg=MUTED).pack(side='right')
        tk.Frame(self,bg=RED,height=3).pack(fill='x')
        toolbar=tk.Frame(self,bg=PANEL,padx=10,pady=12);toolbar.pack(fill='x',padx=12,pady=10)
        self.label(toolbar,'SECTION').pack(side='left')
        ttk.Combobox(toolbar,textvariable=self.section,values=SECTIONS,width=11,state='readonly').pack(side='left',padx=5)
        self.label(toolbar,'PATTERN').pack(side='left',padx=(10,0))
        ttk.Combobox(toolbar,textvariable=self.pattern,values=list('ABCD'),width=4,state='readonly').pack(side='left',padx=5)
        self.label(toolbar,'RÉPÉTITIONS').pack(side='left',padx=(10,0))
        tk.Spinbox(toolbar,from_=1,to=16,textvariable=self.repeats,width=4,bg=BG,fg=TEXT,buttonbackground=PANEL).pack(side='left',padx=5)
        self.button(toolbar,'+ AJOUTER',self.add).pack(side='right')
        timeline=tk.Frame(self,bg=PANEL,padx=12,pady=10);timeline.pack(fill='both',expand=True,padx=12)
        self.label(timeline,'ORDRE DU MORCEAU — sélectionne une section pour la déplacer ou la supprimer').pack(anchor='w',pady=(0,8))
        mid=tk.Frame(timeline,bg=PANEL);mid.pack(fill='both',expand=True)
        self.list=tk.Listbox(mid,font=('Consolas',12),bg='#151112',fg=TEXT,selectbackground='#73302b',highlightthickness=0,activestyle='none')
        self.list.pack(side='left',fill='both',expand=True)
        bar=tk.Scrollbar(mid,command=self.list.yview);bar.pack(side='right',fill='y');self.list.config(yscrollcommand=bar.set)
        actions=tk.Frame(self,bg=PANEL,padx=10,pady=8);actions.pack(fill='x',padx=12,pady=(6,0))
        for title,command in [('↑ MONTER',lambda:self.move(-1)),('↓ DESCENDRE',lambda:self.move(1)),('SUPPRIMER',self.delete),('TOUT EFFACER',self.clear)]:
            self.button(actions,title,command).pack(side='left',expand=True,fill='x',padx=4)
        bottom=tk.Frame(self,bg='#332b25',padx=10,pady=12);bottom.pack(fill='x',padx=12,pady=(10,0))
        for title,command in [('▶ ÉCOUTER',self.play),('■ STOP',self.source.stop),('EXPORT WAV',self.export),('SAUVER',self.save),('OUVRIR',self.open)]:
            self.button(bottom,title,command).pack(side='left',expand=True,fill='x',padx=3)
        tk.Label(self,textvariable=self.status,bg=BG,fg=MUTED,anchor='w',padx=16,pady=8,wraplength=800).pack(fill='x')
        self.protocol('WM_DELETE_WINDOW',self.destroy)
    def label(self,where,value):return tk.Label(where,text=value,bg=PANEL,fg=TEXT,font=('Segoe UI',10,'bold'))
    def button(self,where,title,action):return tk.Button(where,text=title,command=action,bg='#49201e',fg=TEXT,activebackground=RED,activeforeground='white',relief='flat',padx=8,pady=9)
    def slots(self):
        slots=dict(self.source.slots)
        slots[self.source.slot.get()]=self.source.snapshot()
        return slots
    def add(self):
        try:
            block={'section':self.section.get(),'pattern':self.pattern.get(),'repeats':int(self.repeats.get())}
            if len(self.blocks)>=64:raise ValueError('64 sections maximum')
            items=self.blocks+[block]
            validate_timeline(items,self.slots(),int(self.source.bpm.get()))
            self.blocks=items;self.refresh()
        except Exception as exc:messagebox.showerror('Arrangeur',str(exc),parent=self)
    def refresh(self):
        self.list.delete(0,'end')
        for i,b in enumerate(self.blocks):self.list.insert('end',f'{i+1:02d}   {b["section"]:<9}  PATTERN {b["pattern"]}   × {b["repeats"]}')
        self.status.set(f'{len(self.blocks)} section(s) • BPM {self.source.bpm.get()} • export mono 44,1 kHz / 16 bits')
    def selected(self):
        sel=self.list.curselection();return sel[0] if sel else None
    def move(self,delta):
        i=self.selected()
        if i is None or not 0<=i+delta<len(self.blocks):return
        self.blocks[i],self.blocks[i+delta]=self.blocks[i+delta],self.blocks[i];self.refresh();self.list.selection_set(i+delta)
    def delete(self):
        i=self.selected()
        if i is not None:self.blocks.pop(i);self.refresh()
    def clear(self):
        if self.blocks and messagebox.askyesno('Arrangeur','Effacer toute la timeline ?',parent=self):self.blocks.clear();self.refresh()
    def project(self):
        return make_project(self.blocks,self.slots(),int(self.source.bpm.get()),[v.get() for v in self.source.sounds],[v.get() for v in self.source.volumes],[v.get() for v in self.source.mutes],[v.get() for v in self.source.solos],self.source.swing.get())
    def audio(self):
        p=self.project()
        return render_song(p['timeline'],p['slots'],p['bpm'],p['sounds'],p['volumes'],p['mutes'],p['solos'],p['swing'],self.source.data_dir)
    def play(self):self.source.play_pcm(self.audio,'Morceau V9')
    def export(self):self.source.export_audio(self.audio,'moktek-morceau-v9.wav')
    def save(self):
        try:p=self.project()
        except Exception as exc:messagebox.showerror('Sauvegarde',str(exc),parent=self);return
        target=filedialog.asksaveasfilename(parent=self,initialdir=str(self.source.data_dir),initialfile='moktek-arrangement.json',defaultextension='.json',filetypes=[('Arrangement mokteK','*.json')])
        if target:
            try:Path(target).write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8');self.status.set('Arrangement sauvegardé : '+Path(target).name)
            except Exception as exc:messagebox.showerror('Sauvegarde',str(exc),parent=self)
    def open(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[('Arrangement mokteK','*.json')])
        if not path:return
        try:
            p=load_project(path)
            # Restore mixer settings and A–D slots; no MIDI messages are sent.
            self.source.stop();self.source.slots=p['slots'];self.source.bpm.set(p['bpm']);self.source.swing.set(p['swing'])
            for var,v in zip(self.source.sounds,p['sounds']):var.set(v)
            for var,v in zip(self.source.volumes,p['volumes']):var.set(v)
            for var,v in zip(self.source.mutes,p['mutes']):var.set(v)
            for var,v in zip(self.source.solos,p['solos']):var.set(v)
            self.blocks=p['timeline'];self.refresh();self.status.set('Arrangement chargé : '+Path(path).name)
        except Exception as exc:messagebox.showerror('Ouverture',str(exc),parent=self)
