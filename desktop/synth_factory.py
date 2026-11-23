"""Synth Factory: local procedural mono PCM16 synthesis; no hardware transfer."""
import math
import random
import struct
import tempfile
import wave
import winsound
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from portable_synth import from_windows, to_windows, export_zip, import_zip

BG, PANEL, STEEL, RED, TEXT, MUTED = '#100f10', '#211d1a', '#887766', '#ff493e', '#e9dac2', '#b9a99b'
RATE = 44100
PRESETS = {
    'TRIBE KICK': ('Kick', 55, 0.65, 0.73, 0.20, 0.40),
    'GABBER KICK': ('Kick', 48, 0.80, 0.90, 0.88, 0.72),
    'SUB BASS': ('Bass', 48, 1.30, 0.82, 0.05, 0.02),
    'ACID BASS': ('Bass', 110, 0.80, 0.62, 0.45, 0.46),
    'SPACE ZAP': ('Zap', 620, 0.37, 0.86, 0.40, 0.85),
    'RAVE LEAD': ('Lead', 220, 0.80, 0.72, 0.52, 0.18),
    'INDUSTRIAL HIT': ('Noise', 140, 0.25, 0.90, 0.75, 0.66),
}
TYPES = ('Kick', 'Bass', 'Zap', 'Lead', 'Noise', 'Sine')

def generate(kind='Kick', frequency=55, duration=0.65, volume=0.75, drive=0.2, color=0.4, rate=RATE):
    """Deterministic, bounded mono PCM16 buffer; no scipy/numpy required."""
    if kind not in TYPES: raise ValueError('Type inconnu')
    frequency = max(30., min(1800., float(frequency)))
    duration = max(.08, min(4., float(duration)))
    volume = max(0., min(1., float(volume)))
    drive = max(0., min(1., float(drive)))
    color = max(0., min(1., float(color)))
    total = int(duration * rate)
    phase = 0.
    rng = random.Random(42)
    filtered = 0.
    packed = bytearray(total * 2)
    for i in range(total):
        t = i / rate
        progress = i / total
        if kind == 'Kick':
            freq = frequency * (1 + (5 + 6 * color) * math.exp(-t * (18 + 45 * color)))
            env = (1 - math.exp(-t * 850)) * math.exp(-progress * (5 - 2 * color))
            phase += 2 * math.pi * freq / rate
            value = math.sin(phase) * env
            value += rng.uniform(-1,1) * math.exp(-t * 150) * color * .22
        elif kind == 'Bass':
            phase += 2 * math.pi * frequency / rate
            saw = ((phase / math.pi) % 2) - 1
            env = (1 - math.exp(-t*180)) * (1-progress)**.8
            value = ((1-color)*math.sin(phase) + color*saw) * env
        elif kind == 'Zap':
            freq = frequency * (0.08 + (1 + 5 * color) * math.exp(-t * (15+20*color)))
            phase += 2*math.pi*freq/rate
            value = math.sin(phase) * math.exp(-progress*8)
        elif kind == 'Lead':
            phase += 2*math.pi*frequency/rate
            saw = ((phase/math.pi) % 2)-1
            env = min(1., t*90) * min(1., (1-progress)*10)
            value = (math.sin(phase)*(1-color) + saw*color) * env
        elif kind == 'Noise':
            noise = rng.uniform(-1,1)
            filtered += (noise - filtered) * (0.025 + color * .7)
            value = filtered * math.exp(-progress * (3+color*12))
        else:
            phase += 2*math.pi*frequency/rate
            value = math.sin(phase) * min(1., t*100) * (1-progress)
        gain = 1 + drive*15
        value = math.tanh(value * gain) / math.tanh(gain)
        sample = max(-32768, min(32767, int(value * volume * 32767)))
        struct.pack_into('<h', packed, i*2, sample)
    return bytes(packed)

def save_wav(path, pcm, rate=RATE):
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(pcm)

class SynthFactory(tk.Toplevel):
    def __init__(self, owner, data_dir, btn, panel, text):
        super().__init__(owner)
        self.title('mokteK // SYNTH FACTORY • Windows V15')
        self.geometry('1040x760')
        self.minsize(780,610)
        self.configure(bg=BG)
        self.btn, self.panel, self.text = btn, panel, text
        self.kind = tk.StringVar(value='Kick')
        self.preset = tk.StringVar(value='TRIBE KICK')
        self.frequency = tk.DoubleVar(value=55)
        self.duration = tk.DoubleVar(value=.65)
        self.volume = tk.DoubleVar(value=.73)
        self.drive = tk.DoubleVar(value=.20)
        self.color = tk.DoubleVar(value=.40)
        self.message = tk.StringVar(value='Synthèse locale • PCM 16 bits / 44,1 kHz • aucun transfert matériel')
        self.pcm = b''
        self.preview_file = None
        head = tk.Frame(self,bg='#332b25',padx=18,pady=13)
        head.pack(fill='x')
        tk.Label(head,text='SYNTH FACTORY  //  SOUND DESIGN',bg='#332b25',fg=RED,font=('Segoe UI',20,'bold')).pack(side='left')
        tk.Label(head,text='WINDOWS V5',bg='#332b25',fg=MUTED,font=('Segoe UI',10)).pack(side='right')
        tk.Frame(self,bg=RED,height=3).pack(fill='x')
        body = tk.Frame(self,bg=BG,padx=12,pady=9)
        body.pack(fill='both',expand=True)
        presets = self.panel(body, 'MOTEUR ET PRESETS')
        presets.pack(fill='x',pady=(0,7))
        row=tk.Frame(presets,bg=PANEL); row.pack(fill='x')
        tk.Label(row,text='Preset',bg=PANEL,fg=TEXT).pack(side='left')
        ttk.Combobox(row,textvariable=self.preset,values=list(PRESETS),state='readonly',width=23).pack(side='left',padx=8)
        self.btn(row,'CHARGER',self.load_preset).pack(side='left')
        tk.Label(row,text='Moteur',bg=PANEL,fg=TEXT).pack(side='left',padx=(22,5))
        ttk.Combobox(row,textvariable=self.kind,values=TYPES,state='readonly',width=14).pack(side='left')
        settings=self.panel(body,'PARAMÈTRES DE SYNTHÈSE')
        settings.pack(fill='x',pady=(0,7))
        for label,var,low,high,step in [('Fréquence / hauteur (Hz)',self.frequency,30,1800,1),('Durée (secondes)',self.duration,.08,4,.01),('Volume',self.volume,0,1,.01),('Distorsion / Drive',self.drive,0,1,.01),('Couleur / modulation',self.color,0,1,.01)]:
            line=tk.Frame(settings,bg=PANEL);line.pack(fill='x',pady=3)
            tk.Label(line,text=label,bg=PANEL,fg=TEXT,width=27,anchor='w').pack(side='left')
            tk.Scale(line,from_=low,to=high,resolution=step,orient='horizontal',variable=var,bg=PANEL,fg=RED,troughcolor='#381315',highlightthickness=0,activebackground=RED,length=460).pack(side='left',fill='x',expand=True)
        graph=self.panel(body,'FORME D’ONDE • APERÇU DU SIGNAL')
        graph.pack(fill='both',expand=True,pady=(0,7))
        self.canvas=tk.Canvas(graph,bg='#160c0e',highlightthickness=1,highlightbackground=RED,height=135)
        self.canvas.pack(fill='both',expand=True)
        self.canvas.bind('<Configure>',lambda _:self.draw_wave())
        actions=self.panel(body,'PRODUCTION AUDIO')
        actions.pack(fill='x')
        commands=tk.Frame(actions,bg=PANEL);commands.pack(fill='x')
        for label,callback in [('GÉNÉRER',self.render),('▶ ÉCOUTER',self.preview),('■ STOP',self.stop),('EXPORT WAV',self.export)]:
            self.btn(commands,label,callback).pack(side='left',expand=True,fill='x',padx=4)
        exchange=tk.Frame(self,bg=PANEL,padx=12,pady=6)
        exchange.pack(fill='x')
        self.btn(exchange,'⇄ EXPORTER PRESET POUR ANDROID (ZIP)',self.export_portable).pack(side='left',expand=True,fill='x',padx=3)
        self.btn(exchange,'⇄ IMPORTER PRESET ANDROID (ZIP)',self.import_portable).pack(side='left',expand=True,fill='x',padx=3)
        tk.Label(self,textvariable=self.message,bg=BG,fg=MUTED,anchor='w',padx=12,pady=9).pack(fill='x')
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.load_preset()

    def load_preset(self):
        self.stop()
        kind,freq,dur,vol,drv,col=PRESETS[self.preset.get()]
        self.kind.set(kind);self.frequency.set(freq);self.duration.set(dur)
        self.volume.set(vol);self.drive.set(drv);self.color.set(col)
        self.render()

    def render(self):
        try:
            self.stop()
            self.pcm=generate(self.kind.get(),self.frequency.get(),self.duration.get(),self.volume.get(),self.drive.get(),self.color.get())
            self.message.set(f'Généré : {len(self.pcm)//2 / RATE:.2f} s | mono | 44100 Hz | 16 bits')
            self.draw_wave()
        except Exception as exc:
            messagebox.showerror('Synth Factory',str(exc),parent=self)

    def draw_wave(self):
        if not hasattr(self,'canvas'):return
        c=self.canvas;c.delete('all')
        w=max(c.winfo_width(),1);h=max(c.winfo_height(),1)
        c.create_line(0,h//2,w,h//2,fill='#704044')
        for i in range(1,8): c.create_line(i*w/8,0,i*w/8,h,fill='#372126')
        if not self.pcm:return
        samples=memoryview(self.pcm).cast('h')
        stride=max(1,len(samples)//max(1,w))
        pts=[]
        for px in range(w):
            start=px*stride
            if start>=len(samples):break
            # Show peaks: short transient attacks remain visible
            segment=samples[start:min(start+stride,len(samples))]
            peak=max((abs(v) for v in segment),default=0)/32768
            pts.extend((px,h/2-peak*h*.43,px,h/2+peak*h*.43))
        for i in range(0,len(pts),4):c.create_line(*pts[i:i+4],fill=RED)

    def preview(self):
        if not self.pcm:self.render()
        self.stop()
        try:
            import os
            f=tempfile.NamedTemporaryFile(suffix='.wav',delete=False);f.close()
            self.preview_file=Path(f.name)
            save_wav(self.preview_file,self.pcm)
            winsound.PlaySound(str(self.preview_file),winsound.SND_FILENAME | winsound.SND_ASYNC)
            self.message.set('Lecture en cours • STOP pour interrompre')
        except Exception as exc:messagebox.showerror('Préécoute',str(exc),parent=self)

    def stop(self):
        winsound.PlaySound(None,0)
        if self.preview_file is not None:
            try:self.preview_file.unlink(missing_ok=True)
            except OSError:pass
            self.preview_file=None

    def export_portable(self):
        dest=filedialog.asksaveasfilename(parent=self,defaultextension='.zip',initialfile='moktek_synth_preset_v15.zip',filetypes=[('Preset ZIP','*.zip')])
        if not dest:return
        try:
            preset=from_windows(self.preset.get() or 'Preset Windows',self.kind.get(),self.frequency.get(),self.duration.get(),self.volume.get(),self.drive.get(),self.color.get())
            export_zip(dest,preset)
            self.message.set('Preset exporté en ZIP avec SHA-256. Les moteurs Android peuvent sonner différemment.')
        except Exception as exc:messagebox.showerror('Export impossible',str(exc),parent=self)

    def import_portable(self):
        source=filedialog.askopenfilename(parent=self,filetypes=[('Preset ZIP','*.zip')])
        if not source:return
        try:
            preset=import_zip(source)
            kind,frequency,duration,volume,drive,color=to_windows(preset)
            if not messagebox.askyesno('Conversion du preset',f"Preset : {preset['name']}\nSource : {preset['origin']}\nMoteur : {preset['kind']} → {kind}\nLes moteurs de synthèse ne sont pas identiques. Charger ces réglages ?",parent=self):return
            self.stop()
            self.kind.set(kind);self.frequency.set(frequency);self.duration.set(duration)
            self.volume.set(volume);self.drive.set(drive);self.color.set(color)
            PRESETS[preset['name']]=(kind,frequency,duration,volume,drive,color)
            self.preset.set(preset['name'])
            self.render()
            self.message.set('Preset V15 chargé (conversion des paramètres, audio non identique).')
        except Exception as exc:messagebox.showerror('Import impossible',str(exc),parent=self)

    def export(self):
        if not self.pcm:self.render()
        dest=filedialog.asksaveasfilename(parent=self,title='Exporter le sample',defaultextension='.wav',initialfile=self.preset.get().lower().replace(' ','_')+'.wav',filetypes=[('Audio WAV','*.wav')])
        if not dest:return
        try:
            save_wav(dest,self.pcm)
            self.message.set(f'WAV exporté : {Path(dest).name} • importable dans Sample Librarian')
        except Exception as exc:messagebox.showerror('Export WAV',str(exc),parent=self)

    def close(self):
        self.stop()
        self.destroy()
