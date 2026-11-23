"""Safe local transfer to the first empty A-D Sample Librarian slot.
Uses the existing librarian index and never communicates with Korg hardware.
"""
import json
import uuid
import wave
from pathlib import Path
from synth_factory import save_wav
from sequencer_engine import librarian_choices

MAX_BYTES=80*1024*1024

def store_pcm(data_dir, pcm, rate, name):
    if not pcm or len(pcm)%2 or len(pcm)>MAX_BYTES:
        raise ValueError('Audio PCM 16 bits invalide ou trop volumineux')
    if not isinstance(rate,int) or not 8000<=rate<=192000:
        raise ValueError('Fréquence audio non compatible')
    root=Path(data_dir)/'sample_librarian'
    audio=root/'audio'
    index=root/'library.json'
    audio.mkdir(parents=True,exist_ok=True)
    if index.exists():
        if index.stat().st_size>200_000:raise ValueError('Index Librarian trop volumineux')
        doc=json.loads(index.read_text(encoding='utf-8'))
        if doc.get('format')!='moktek-sample-library-v1' or not isinstance(doc.get('slots'),dict):
            raise ValueError('Index Librarian incompatible : aucune écriture effectuée')
    else:doc={'format':'moktek-sample-library-v1','slots':{}}
    slots=doc['slots']
    key=next((f'{bank}{i}' for bank in 'ABCD' for i in range(8) if f'{bank}{i}' not in slots),None)
    if key is None:raise ValueError('32 emplacements occupés : libère un emplacement dans le Librarian')
    filename=uuid.uuid4().hex+'.wav'
    dest=audio/filename
    tmp=index.with_name('library-'+uuid.uuid4().hex+'.tmp')
    try:
        save_wav(dest,pcm,rate)
        with wave.open(str(dest),'rb') as wav:
            if wav.getnchannels()!=1 or wav.getsampwidth()!=2:raise ValueError('Export WAV invalide')
        slots[key]={'file':filename,'name':str(name).strip()[:80] or 'Sample', 'bpm':'', 'mode':'One Shot'}
        tmp.write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
        tmp.replace(index)
    except Exception:
        dest.unlink(missing_ok=True);tmp.unlink(missing_ok=True);raise
    return f'LIB {key[0]}{int(key[1])+1}'

def available_sounds(data_dir):
    from synth_factory import PRESETS
    return list(PRESETS)+sorted(librarian_choices(data_dir))
