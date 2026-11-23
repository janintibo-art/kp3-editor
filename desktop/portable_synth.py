"""Portable Synth Factory preset V15. Preserves editable parameters; engines are not audio-identical.
Never communicates with hardware Korg. Rejects malformed and oversized archives.
"""
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path

FORMAT = 'moktek-portable-synth-v1'
ENTRY = 'metadata/portable-synth.json'
KINDS = ('Kick', 'Bass', 'Zap', 'Lead', 'Noise', 'Sine', 'Acid', 'Snare', 'Hat', 'Tom')
WINDOWS_KINDS = ('Kick','Bass','Zap','Lead','Noise','Sine')

def number(n,lo,hi):
    if type(n) not in (int,float) or not math.isfinite(n) or not lo<=n<=hi:raise ValueError('Paramètre synthèse hors plage')
    return float(n)

def validate(d):
    if not isinstance(d,dict) or d.get('format')!=FORMAT:raise ValueError('Format de preset incompatible')
    if d.get('kind') not in KINDS:raise ValueError('Moteur inconnu')
    if not isinstance(d.get('name'),str) or not 1<=len(d['name'])<=80:raise ValueError('Nom invalide')
    if type(d.get('bpm'))!=int or not 70<=d['bpm']<=240:raise ValueError('Tempo invalide')
    for k,a,b in [('pitch',25,1800),('decay',.02,4),('drive',0,8),('tone',0,1),('volume',0,1)]:number(d.get(k),a,b)
    if d.get('origin') not in ('android','windows'):raise ValueError('Source invalide')
    return d

def from_windows(name,kind,pitch,duration,volume,drive,color,bpm=174):
    return validate({'format':FORMAT,'name':name[:80],'kind':kind,'pitch':float(pitch),'decay':float(duration),
                     'drive':float(drive),'tone':float(color),'volume':float(volume),'bpm':int(bpm),'origin':'windows'})

def to_windows(d):
    d=validate(d)
    fallback={'Acid':'Lead','Snare':'Noise','Hat':'Noise','Tom':'Kick'}
    kind=fallback.get(d['kind'],d['kind'])
    return (kind,max(30,min(1800,d['pitch'])),max(.08,min(4,d['decay'])),d['volume'],
            max(0,min(1,(d['drive']-1)/7 if d['origin']=='android' else d['drive'])),d['tone'])

def to_android(d):
    d=validate(d)
    fallback={'Zap':'Tom','Lead':'Acid','Noise':'Snare','Sine':'Bass'}
    return {'name':d['name'],'kind':fallback.get(d['kind'],d['kind']),
            'bpm':d['bpm'],'pitch':max(25,min(400,d['pitch'])), 'decay':max(.02,min(.5,d['decay'])),
            'drive':max(1,min(8,1+d['drive']*7 if d['origin']=='windows' else d['drive'])), 'tone':d['tone']}

def export_zip(destination,preset):
    d=validate(preset)
    data=json.dumps(d,ensure_ascii=False,sort_keys=True).encode('utf-8')
    manifest={'format':'moktek-exchange','version':1,'origin':d['origin'],'hardwareWrite':False,
              'files':{ENTRY:hashlib.sha256(data).hexdigest()}}
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr(ENTRY,data)
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))

def import_zip(source):
    with zipfile.ZipFile(source) as z:
        infos=z.infolist()
        if len(infos)!=2 or set(z.namelist())!={ENTRY,'manifest.json'}:raise ValueError('Archive de preset non conforme')
        if any(i.is_dir() or i.file_size>32768 or i.compress_size>32768 for i in infos):raise ValueError('ZIP trop volumineux')
        manifest=json.loads(z.read('manifest.json'))
        if manifest.get('format')!='moktek-exchange' or manifest.get('version')!=1 or set(manifest.get('files',{}))!={ENTRY}:raise ValueError('Manifest invalide')
        data=z.read(ENTRY)
        if hashlib.sha256(data).hexdigest()!=manifest['files'][ENTRY]:raise ValueError('Empreinte SHA-256 non conforme')
        return validate(json.loads(data))
