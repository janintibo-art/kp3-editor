"""mokteK V13: validated, non-destructive cross-platform archive exchange.
No Korg hardware writes. Android native backups are accepted as import sources.
"""
from __future__ import annotations
import hashlib, io, json, re, shutil, uuid, wave, zipfile
from pathlib import Path
from portable_project import from_windows, from_android_prefs, to_windows, _validate

MAX_TOTAL=192*1024*1024
MAX_FILE=48*1024*1024
MAX_ENTRIES=256
FORMAT='moktek-exchange'

def _json(data):
    return json.loads(data.decode('utf-8'))

def _wav(data):
    if len(data)>MAX_FILE: raise ValueError('WAV trop volumineux')
    with wave.open(io.BytesIO(data),'rb') as w:
        if (w.getcomptype()!='NONE' or w.getsampwidth()!=2 or w.getnchannels() not in (1,2)
            or w.getframerate() not in range(8000,192001) or w.getnframes()<1):
            raise ValueError('WAV PCM 16 bits requis')

def _name(path):
    if not isinstance(path,str) or not path or '\\' in path or '\x00' in path or path.startswith('/'):
        raise ValueError('Nom non sûr')
    parts=path.split('/')
    if any(x in ('','.','..') for x in parts): raise ValueError('Chemin interdit')
    return path

def _archive(path):
    records={}; total=0
    with zipfile.ZipFile(path) as z:
        if len(z.infolist())>MAX_ENTRIES: raise ValueError('Archive trop grande')
        for info in z.infolist():
            name=_name(info.filename)
            if info.is_dir() or name in records or info.file_size>MAX_FILE:raise ValueError('Entrée ZIP non valide')
            total+=info.file_size
            if total>MAX_TOTAL:raise ValueError('Archive supérieure à 192 Mo')
            with z.open(info) as stream:
                data=stream.read(MAX_FILE+1)
            if len(data)!=info.file_size:raise ValueError('Longueur ZIP invalide')
            records[name]=data
    return records

def _verify(records):
    if 'manifest.json' not in records:raise ValueError('Manifest manquant')
    manifest=_json(records['manifest.json'])
    fmt=manifest.get('format')
    if fmt==FORMAT and manifest.get('version')==1:
        hashes=manifest.get('files',{})
        if set(hashes)!=(set(records)-{'manifest.json'}):raise ValueError('Fichiers non conformes')
    elif fmt=='moktek-backup' and manifest.get('version') in (1,2):
        hashes=manifest.get('files',{})
        if set(hashes)!=(set(records)-{'manifest.json'}):raise ValueError('Sauvegarde incomplète')
        required=['native_sessions','banks_v11']+( ['patterns_v9','synth_presets'] if manifest['version']==2 else [])
        for pref in required:
            if 'prefs/'+pref+'.json' not in records:raise ValueError('Sauvegarde Android incomplète')
        for name in records:
            if name=='manifest.json':continue
            if not (name in ['prefs/'+p+'.json' for p in ('native_sessions','banks_v11','patterns_v9','synth_presets')] or
                (name.startswith('banks/') and re.fullmatch(r'[A-Za-z0-9._-]+\.wav',name[6:])) or
                name.startswith('reference/')):raise ValueError('Entrée Android non autorisée')
    else:raise ValueError('Format inconnu')
    for name,hash_value in hashes.items():
        if not isinstance(hash_value,str) or hashlib.sha256(records[name]).hexdigest()!=hash_value:
            raise ValueError('Intégrité SHA-256 invalide : '+name)
    return fmt

def export_exchange(data_dir,destination,session=None,pattern=None):
    root=Path(data_dir); lib=root/'sample_librarian'; index=lib/'library.json'
    records={}; inventory={}; total=0
    if index.is_file():
        data=json.loads(index.read_text(encoding='utf-8'))
        if data.get('format')!='moktek-sample-library-v1' or not isinstance(data.get('slots'),dict):raise ValueError('Bibliothèque incompatible')
        for slot,meta in data['slots'].items():
            if not re.fullmatch(r'[ABCD][0-7]',slot) or not isinstance(meta,dict):continue
            name=meta.get('file','')
            if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_-]+\.wav',name):continue
            path=lib/'audio'/name
            if not path.is_file():raise ValueError('WAV manquant : '+name)
            sample=path.read_bytes();_wav(sample)
            dest=f'audio/{slot}.wav';records[dest]=sample
            inventory[slot]={'file':dest,'name':str(meta.get('name','Sample'))[:80], 'bpm':str(meta.get('bpm',''))[:12],'mode':str(meta.get('mode','One Shot'))}
    records['metadata/library.json']=json.dumps({'slots':inventory},ensure_ascii=False).encode()
    if session:
        raw=Path(session).read_bytes()
        if len(raw)>200000 or _json(raw).get('format')!='moktek-windows-session-v1':raise ValueError('Session non reconnue')
        records['metadata/windows-session.json']=raw
    if pattern:
        raw=Path(pattern).read_bytes()
        if len(raw)>200000 or _json(raw).get('format') not in ('moktek-windows-sequencer-v1','moktek-windows-sequencer-v2','moktek-windows-sequencer-v3'):
            raise ValueError('Pattern Windows non reconnu')
        records['metadata/windows-pattern.json']=raw
        records['metadata/portable-pattern.json']=json.dumps(from_windows(_json(raw)),ensure_ascii=False).encode('utf-8')
    total=sum(map(len,records.values()))
    if total>MAX_TOTAL:raise ValueError('Archive supérieure à 192 Mo')
    manifest={'format':FORMAT,'version':1,'origin':'windows','hardwareWrite':False,
              'files':{name:hashlib.sha256(payload).hexdigest() for name,payload in records.items()}}
    dest=Path(destination);dest.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for name,payload in records.items():z.writestr(name,payload)
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    return len(inventory)

def import_exchange(data_dir,source):
    records=_archive(source);fmt=_verify(records)
    lib=Path(data_dir)/'sample_librarian'; audio=lib/'audio'; audio.mkdir(parents=True,exist_ok=True)
    index=lib/'library.json'; existing={'format':'moktek-sample-library-v1','slots':{}}
    if index.is_file():
        existing=json.loads(index.read_text(encoding='utf-8'))
        if existing.get('format')!='moktek-sample-library-v1' or not isinstance(existing.get('slots'),dict):
            raise ValueError('Index existant inconnu : import annulé')
    slots=existing['slots']; free=[f'{bank}{i}' for bank in 'ABCD' for i in range(8) if f'{bank}{i}' not in slots]
    if fmt==FORMAT:
        meta=_json(records.get('metadata/library.json',b'{}')).get('slots',{})
        candidates=[(name,records[name],meta.get(name.removeprefix('audio/').removesuffix('.wav'),{}))
            for name in sorted(records) if re.fullmatch(r'audio/[ABCD][0-7]\.wav',name)]
    else:
        candidates=[(name,records[name],{'name':Path(name).stem}) for name in sorted(records)
            if name.startswith('banks/') and name.lower().endswith('.wav')]
    for _,raw,_ in candidates:_wav(raw)
    if len(candidates)>len(free):raise ValueError(f'Pas assez de places libres : {len(free)} disponibles, {len(candidates)} samples')
    created=[];new_slots={}
    try:
        for (_,raw,meta),slot in zip(candidates,free):
            filename=uuid.uuid4().hex+'.wav';dest=audio/filename
            with dest.open('xb') as w:w.write(raw)
            created.append(dest)
            new_slots[slot]={'file':filename,'name':str(meta.get('name','Sample'))[:80],
                             'bpm':str(meta.get('bpm',''))[:12],
                             'mode':meta.get('mode','One Shot') if meta.get('mode') in ('One Shot','Loop') else 'One Shot'}
        # Preserve opaque Android settings / Windows patterns; never reinterpret them.
        inbox=Path(data_dir)/'exchange_inbox';inbox.mkdir(parents=True,exist_ok=True)
        opaque=[name for name in records if name.startswith('metadata/') or name.startswith('prefs/')]
        copied=[]
        for name in opaque:
            if name=='metadata/library.json':continue
            if not re.fullmatch(r'(metadata|prefs)/[A-Za-z0-9._-]+\.json',name):continue
            dest=inbox/(uuid.uuid4().hex+'-'+Path(name).name)
            dest.write_bytes(records[name]);copied.append(dest)
        # Convert compatible pattern without overwriting any user work.
        portable=None
        if 'metadata/portable-pattern.json' in records:
            portable=_validate(_json(records['metadata/portable-pattern.json']))
        elif 'prefs/patterns_v9.json' in records:
            # Native Android backup : extract its saved 6-track grid.
            try:portable=from_android_prefs(_json(records['prefs/patterns_v9.json']))
            except (ValueError,TypeError,KeyError):portable=None
        if portable is not None:
            converted=json.dumps(to_windows(portable),ensure_ascii=False,indent=2).encode('utf-8')
            dest=inbox/(uuid.uuid4().hex+'-portable-pattern-windows.json')
            dest.write_bytes(converted);copied.append(dest)
        slots.update(new_slots)
        temp=index.with_name('library.json.tmp')
        try:
            temp.write_text(json.dumps(existing,ensure_ascii=False,indent=2),encoding='utf-8')
            temp.replace(index)
        except Exception:
            for path in copied:path.unlink(missing_ok=True)
            raise
    except Exception:
        for path in created:path.unlink(missing_ok=True)
        raise
    return {'format':fmt,'samples':len(candidates),'preserved':len(copied)}
