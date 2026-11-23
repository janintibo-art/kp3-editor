"""V16 interchange project: verified ZIP with portable assets, no device I/O.

V16 is a compatible extension of moktek-exchange v1 so V13/V14 readers can
retain unfamiliar JSON payloads without mutating hardware or overwriting work.
"""
from pathlib import Path
import hashlib, io, json, zipfile
from project_exchange import _archive, _verify, _wav, export_exchange
from portable_project import _validate
from portable_synth import validate as validate_synth, import_zip as import_synth_zip

PROJECT_PATH='metadata/project-v16.json'
SYNTH_PATH='metadata/portable-synth.json'
PATTERN_PATH='metadata/portable-pattern.json'
MAX_PROJECT=192*1024*1024

def _bytes(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False).encode('utf-8')

def inspect_project(source):
    entries=_archive(source)
    _verify(entries)
    if PROJECT_PATH not in entries:raise ValueError('Projet V16 absent (archive V13/V14/V15 possible, utiliser Échanges classiques)')
    project=json.loads(entries[PROJECT_PATH]);
    if not isinstance(project,dict) or project.get('format')!='moktek-common-project-v1':raise ValueError('Projet V16 inconnu')
    if project.get('origin') not in ('windows','android') or type(project.get('title')) is not str or not 1<=len(project['title'])<=80:raise ValueError('Métadonnées de projet invalides')
    if project.get('hardwareWrite') is not False:raise ValueError('Un projet ne peut pas envoyer de commandes Korg')
    if PATTERN_PATH in entries:_validate(json.loads(entries[PATTERN_PATH]))
    if SYNTH_PATH in entries:validate_synth(json.loads(entries[SYNTH_PATH]))
    count=0
    for name,data in entries.items():
        if name.startswith('audio/'):
            if name not in [f'audio/{b}{i}.wav' for b in 'ABCD' for i in range(8)]:raise ValueError('Slot audio invalide')
            _wav(data);count+=1
    return {'title':project['title'],'origin':project['origin'],'samples':count,
      'pattern':PATTERN_PATH in entries,'synth':SYNTH_PATH in entries,
      'session':'metadata/windows-session.json' in entries,
      'notice':'Le son des moteurs de synthèse peut différer. Aucune écriture Korg.'}

def export_project(data_dir,destination,title,session=None,pattern=None,synth=None):
    if not isinstance(title,str) or not 1<=len(title.strip())<=80:raise ValueError('Nom de projet requis (80 caractères max)')
    # Reuse vetted V13 library export; originals never changed.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmp:
        staging=Path(tmp)/'exchange.zip'
        export_exchange(data_dir,staging,session=session,pattern=pattern)
        records=_archive(staging);_verify(records)
    if synth:
        preset=import_synth_zip(synth) if str(synth).lower().endswith('.zip') else json.loads(Path(synth).read_text(encoding='utf-8'))
        records[SYNTH_PATH]=_bytes(validate_synth(preset))
    records[PROJECT_PATH]=_bytes({'format':'moktek-common-project-v1','version':1,
       'title':title.strip(),'origin':'windows','hardwareWrite':False,
       'notice':'Échange local, non compatible avec les fichiers All Data Korg. Les réglages non reconnus sont conservés.'})
    # Remove old manifest and replace its hash inventory.
    records.pop('manifest.json',None)
    if sum(len(value) for value in records.values())>MAX_PROJECT:raise ValueError('Projet supérieur à 192 Mo')
    manifest={'format':'moktek-exchange','version':1,'origin':'windows','hardwareWrite':False,
       'files':{key:hashlib.sha256(value).hexdigest() for key,value in records.items()}}
    target=Path(destination);target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for key,value in records.items():z.writestr(key,value)
        z.writestr('manifest.json',_bytes(manifest))
    return inspect_project(target)
