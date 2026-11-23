"""mokteK V14 shared pattern interchange, explicit loss-aware conversions.
Only six tracks and basic grid/tempo/mixer map to Android V18.
No physical Korg commands.
"""
import json, re
from pathlib import Path

FMT='moktek-portable-pattern-v1'
WIN=('moktek-windows-sequencer-v1','moktek-windows-sequencer-v2','moktek-windows-sequencer-v3')

def _validate(obj):
    if not isinstance(obj,dict) or obj.get('format')!=FMT:raise ValueError('Format pattern portable inconnu')
    steps=obj.get('steps');bpm=obj.get('bpm');grid=obj.get('grid');vol=obj.get('volumes')
    if type(steps)!=int or steps not in (16,32,64):raise ValueError('Nombre de pas invalide')
    if type(bpm)!=int or not 70<=bpm<=240:raise ValueError('BPM hors plage Android 70–240')
    if not isinstance(grid,list) or len(grid)!=6 or any(not isinstance(row,list) or len(row)!=steps or any(type(x)!=bool for x in row) for row in grid):raise ValueError('Grille invalide')
    if not isinstance(vol,list) or len(vol)!=6 or any(type(v) not in (float,int) or not 0<=v<=1 for v in vol):raise ValueError('Volumes invalides')
    return obj

def from_windows(payload):
    if not isinstance(payload,dict) or payload.get('format') not in WIN:raise ValueError('Pattern Windows inconnu')
    if payload.get('steps') not in (16,32,64) or len(payload.get('pattern',[]))!=6:raise ValueError('Pattern invalide')
    result={'format':FMT,'steps':payload['steps'],'bpm':payload['bpm'],'grid':payload['pattern'],'volumes':payload.get('volumes',[1]*6),
       'origin':'windows','notice':'Le swing, les sons, les chaînes, la vélocité et les roulements ne sont pas appliqués par le séquenceur Android V18.'}
    return _validate(result)

def from_android_prefs(pref):
    if not isinstance(pref,dict):raise ValueError('Préférences Android invalides')
    def val(key):
        obj=pref.get(key)
        if not isinstance(obj,dict) or 'value' not in obj:raise ValueError('Champ Android manquant: '+key)
        return obj['value']
    bits=val('grid');steps=val('steps');bpm=val('bpm');vol=val('vol')
    if not isinstance(bits,str) or not re.fullmatch('[01]{384}',bits):raise ValueError('Grille Android invalide')
    if not isinstance(vol,str):raise ValueError('Volumes Android invalides')
    values=[float(x) for x in vol.split(',')]
    return _validate({'format':FMT,'steps':steps,'bpm':bpm,'grid':[[bits[lane*64+s]=='1' for s in range(steps)] for lane in range(6)],'volumes':values,'origin':'android'})

def to_windows(portable):
    p=_validate(portable);steps=p['steps']
    from sequencer_engine import DEFAULT_SOUNDS
    return {'format':'moktek-windows-sequencer-v3','steps':steps,'bpm':p['bpm'],'loops':1,'pattern':p['grid'],
      'sounds':list(DEFAULT_SOUNDS),'volumes':p['volumes'],'mutes':[False]*6,'solos':[False]*6,'swing':0,
      'step_settings':[[[100,100,1] for _ in range(steps)] for _ in range(6)],'slots':{},'order':'A','slot':'A'}
