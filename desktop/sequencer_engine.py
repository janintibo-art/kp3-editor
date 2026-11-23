"""Offline 6-track, 16/32/64-step PCM16 beat renderer. No hardware MIDI transfers."""
from array import array
from pathlib import Path
import sys
import wave
import math
import json
from synth_factory import generate, RATE, PRESETS

TRACKS = ('KICK', 'SNARE', 'HAT', 'BASS', 'LEAD', 'PERC')
SOUNDS = ('TRIBE KICK','INDUSTRIAL HIT','SPACE ZAP','SUB BASS','RAVE LEAD','ACID BASS','GABBER KICK')
DEFAULT_SOUNDS = ('TRIBE KICK','INDUSTRIAL HIT','SPACE ZAP','SUB BASS','RAVE LEAD','SPACE ZAP')
MAX_EXPORT_SECONDS = 120

def default_pattern(style='TRIBE', steps=16):
    if steps not in (16,32,64): raise ValueError('Longueur incorrecte')
    grid = [[False]*steps for _ in TRACKS]
    for s in range(steps):
        k=s%16
        if style == 'GABBER':
            grid[0][s]=k%4==0
            grid[1][s]=k in (4,12)
            grid[2][s]=k%2==0
            grid[3][s]=k in (0,6,8,14)
            grid[4][s]=k in (3,11)
            grid[5][s]=k in (7,15)
        elif style == 'BREAKCORE':
            grid[0][s]=k in (0,3,7,10,14)
            grid[1][s]=k in (4,6,11,12,15)
            grid[2][s]=k in (0,2,3,5,8,9,11,13,15)
            grid[3][s]=k in (0,7,10)
            grid[4][s]=k in (2,9)
            grid[5][s]=k in (5,13,14)
        elif style == 'JUNGLE':
            grid[0][s]=k in (0,7,10)
            grid[1][s]=k in (4,12,15)
            grid[2][s]=k%2==0 or k in (7,15)
            grid[3][s]=k in (0,3,10)
            grid[4][s]=k in (6,14)
            grid[5][s]=k in (3,11)
        else:
            grid[0][s]=k%4==0
            grid[1][s]=k in (4,12)
            grid[2][s]=k%2==0
            grid[3][s]=k in (0,8)
            grid[4][s]=k in (6,14)
            grid[5][s]=k in (3,11)
    return grid

def librarian_choices(data_dir):
    """Read existing Sample Librarian entries, without modifying its index."""
    root=Path(data_dir) / 'sample_librarian'
    index=root/'library.json'
    if not index.is_file():return {}
    try:
        if index.stat().st_size>200_000:return {}
        doc=json.loads(index.read_text(encoding='utf-8'))
        if doc.get('format')!='moktek-sample-library-v1' or not isinstance(doc.get('slots'),dict):return {}
        choices={}
        for key,item in doc['slots'].items():
            if not (isinstance(key,str) and len(key)==2 and key[0] in 'ABCD' and key[1] in '01234567' and isinstance(item,dict)):
                continue
            filename=item.get('file','')
            if not isinstance(filename,str) or not filename.lower().endswith('.wav') or Path(filename).name!=filename:continue
            p=root/'audio'/filename
            if p.is_file():choices[f'LIB {key[0]}{int(key[1])+1}']=p
        return choices
    except (OSError,ValueError,TypeError,KeyError):return {}

def read_sample(path):
    """Load a short mono/stereo PCM16 sample and resample to synthesis rate."""
    path=Path(path)
    if path.stat().st_size>80*1024*1024:raise ValueError('Sample supérieur à 80 Mo')
    with wave.open(str(path),'rb') as f:
        if f.getcomptype()!='NONE' or f.getsampwidth()!=2 or f.getnchannels() not in (1,2):
            raise ValueError('Sample WAV PCM 16 bits mono/stéréo requis')
        rate=f.getframerate()
        if not 8000<=rate<=192000:raise ValueError('Fréquence WAV incorrecte')
        # Limit each sample to 4 seconds to keep memory and rendering bounded.
        raw=f.readframes(min(f.getnframes(),rate*4))
        channels=f.getnchannels()
    samples=array('h');samples.frombytes(raw)
    if sys.byteorder!='little':samples.byteswap()
    length=len(samples)//channels
    if not length:return array('h')
    if rate==RATE and channels==1:return samples
    out=array('h')
    n=min(int(length*RATE/rate),RATE*4)
    for k in range(n):
        pos=k*rate/RATE;lo=min(int(pos),length-1);hi=min(lo+1,length-1);a=pos-lo
        v0=sum(samples[lo*channels+c] for c in range(channels))/channels
        v1=sum(samples[hi*channels+c] for c in range(channels))/channels
        out.append(int(v0+(v1-v0)*a))
    return out

def render(pattern,bpm,steps,sounds,volumes,bars=1,mutes=None,solos=None,swing=0,data_dir=None):
    """Render 6 tracks to PCM16 mono WAV with bounded swing and track controls."""
    if steps not in (16,32,64) or not 40<=bpm<=300 or not 1<=bars<=16:raise ValueError('Tempo, longueur ou répétitions invalides')
    if len(pattern)!=6 or any(len(t)!=steps for t in pattern):raise ValueError('Pattern invalide')
    if len(sounds)!=6 or len(volumes)!=6:raise ValueError('Pistes invalides')
    if not 0<=swing<=75:raise ValueError('Swing invalide')
    mutes=list(mutes) if mutes is not None else [False]*6
    solos=list(solos) if solos is not None else [False]*6
    if len(mutes)!=6 or len(solos)!=6:raise ValueError('États des pistes invalides')
    choices=librarian_choices(data_dir) if data_dir is not None else {}
    step_frames=RATE*60/(bpm*4)
    total=int(round(steps*step_frames*bars))
    if total/RATE>MAX_EXPORT_SECONDS:raise ValueError('Export limité à 120 secondes')
    mix=array('f',[0.])*total
    cache={};any_solo=any(solos)
    for ti in range(6):
        if mutes[ti] or (any_solo and not solos[ti]):continue
        name=sounds[ti];vol=float(volumes[ti])
        if not 0<=vol<=1:raise ValueError('Volume invalide')
        if vol<=0:continue
        if name not in cache:
            if name in PRESETS:
                sample=array('h');sample.frombytes(generate(*PRESETS[name]))
                if sys.byteorder!='little':sample.byteswap()
            elif name in choices:
                sample=read_sample(choices[name])
            else:raise ValueError(f'Sample introuvable : {name}. Vérifie le Librarian.')
            cache[name]=sample
        sample=cache[name]
        for rep in range(bars):
            for si,enabled in enumerate(pattern[ti]):
                if not enabled:continue
                # Delays odd 16th notes; the following even step remains fixed.
                swing_offset=step_frames*(swing/100.0) if si%2 else 0
                start=round((rep*steps+si)*step_frames+swing_offset)
                if start>=total:continue
                for j in range(min(len(sample),total-start)):
                    mix[start+j]+=sample[j]*vol*.52
    result=array('h',(max(-32768,min(32767,round(v))) for v in mix))
    if sys.byteorder!='little':result.byteswap()
    return result.tobytes()

def export_wav(filename, pcm):
    with wave.open(str(filename),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(RATE);out.writeframes(pcm)
