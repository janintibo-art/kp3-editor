"""Offline 6-track, 16/32/64-step PCM16 beat renderer. No hardware MIDI transfers."""
from array import array
from pathlib import Path
import sys
import wave
import math
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

def render(pattern, bpm, steps, sounds, volumes, bars=1):
    """Produces one playable PCM16 mono buffer. 4 steps per beat, bar=16 steps."""
    if steps not in (16,32,64) or not 40<=bpm<=300 or not 1<=bars<=16: raise ValueError('Tempo, longueur ou répétitions invalides')
    if len(pattern)!=6 or any(len(t)!=steps for t in pattern): raise ValueError('Pattern invalide')
    if len(sounds)!=6 or len(volumes)!=6:raise ValueError('Pistes invalides')
    # bars = loop repetitions, not musical measures
    step_frames=RATE * 60.0 / (bpm*4)
    duration=steps*step_frames/RATE*bars
    if duration>MAX_EXPORT_SECONDS: raise ValueError('Export limité à 120 secondes')
    total=int(round(steps*step_frames*bars))
    mix=array('f',[0.0])*total
    cache={}
    for ti in range(6):
        name=sounds[ti]
        if name not in PRESETS: raise ValueError('Preset inconnu')
        volume=float(volumes[ti]);
        if not 0<=volume<=1:raise ValueError('Volume invalide')
        if volume==0:continue
        if name not in cache:
            pcm=generate(*PRESETS[name])
            sample=array('h');sample.frombytes(pcm)
            if sys.byteorder!='little':sample.byteswap()
            cache[name]=sample
        sample=cache[name]
        for rep in range(bars):
            for si in range(steps):
                if not pattern[ti][si]:continue
                start=round((rep*steps+si)*step_frames)
                end=min(len(sample),total-start)
                # bounded to loop duration; safe at last step
                for j in range(end):mix[start+j]+=sample[j]*volume*.52
    result=array('h',(max(-32768,min(32767,round(v))) for v in mix))
    if sys.byteorder!='little':result.byteswap()
    return result.tobytes()

def export_wav(filename, pcm):
    with wave.open(str(filename),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(RATE);out.writeframes(pcm)
