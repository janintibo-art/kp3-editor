"""mokteK V9 offline song arranger, reusing V8 sound and mixer engine."""
import json
from pathlib import Path
from sequencer_engine import render, RATE, MAX_EXPORT_SECONDS, validate_step_settings
from mixer_fx_v18 import apply_fx, validate_fx

SECTIONS=('INTRO','COUPLET','BREAK','DROP','OUTRO','LIBRE')
MAX_BLOCKS=64

def validate_timeline(blocks, slots, bpm):
    if not isinstance(blocks,list) or not 1<=len(blocks)<=MAX_BLOCKS:
        raise ValueError('Arrangeur : 1 à 64 sections nécessaires')
    if type(bpm)!=int or not 40<=bpm<=300:raise ValueError('BPM hors limites')
    if not isinstance(slots,dict):raise ValueError('Patterns absents')
    frames=0
    for block in blocks:
        if not isinstance(block,dict):raise ValueError('Section incorrecte')
        key=block.get('pattern'); repeats=block.get('repeats'); section=block.get('section')
        if key not in 'ABCD' or key not in slots:raise ValueError(f'Pattern {key} non mémorisé')
        if type(repeats)!=int or not 1<=repeats<=16:raise ValueError('Répétitions : 1 à 16')
        if section not in SECTIONS:raise ValueError('Section inconnue')
        p=slots[key]
        if not isinstance(p,dict) or p.get('steps') not in (16,32,64):raise ValueError('Pattern invalide')
        steps=p['steps']; grid=p.get('pattern')
        if not isinstance(grid,list) or len(grid)!=6 or any(not isinstance(row,list) or len(row)!=steps or any(type(x)!=bool for x in row) for row in grid):raise ValueError('Grille de pattern invalide')
        validate_step_settings(p.get('step_settings'),steps)
        frames+=repeats*round(steps*RATE*60/(bpm*4))
    if frames/RATE>MAX_EXPORT_SECONDS:raise ValueError('Durée maximale : 120 secondes')
    return frames

def render_song(blocks,slots,bpm,sounds,volumes,mutes,solos,swing,data_dir=None,fx_enabled=False,master_fx=None):
    validate_timeline(blocks,slots,bpm)
    result=bytearray(); idx=0
    for block in blocks:
        p=slots[block['pattern']]
        for _ in range(block['repeats']):
            result.extend(render(p['pattern'],bpm,p['steps'],sounds,volumes,bars=1,mutes=mutes,solos=solos,swing=swing,data_dir=data_dir,step_settings=p.get('step_settings'),seed=42+idx))
            idx+=1
    return apply_fx(bytes(result),**validate_fx(master_fx or {})) if fx_enabled else bytes(result)

def make_project(blocks,slots,bpm,sounds,volumes,mutes,solos,swing,fx_enabled=False,master_fx=None):
    validate_timeline(blocks,slots,bpm)
    return {'format':'moktek-arranger-v1','bpm':bpm,'timeline':blocks,'slots':slots,'sounds':sounds,'volumes':volumes,'mutes':mutes,'solos':solos,'swing':swing,'fx_enabled':bool(fx_enabled),'master_fx':validate_fx(master_fx or {})}

def load_project(path):
    source=Path(path)
    if source.stat().st_size>500000:raise ValueError('Projet trop volumineux')
    doc=json.loads(source.read_text(encoding='utf-8'))
    if doc.get('format')!='moktek-arranger-v1':raise ValueError('Format non reconnu')
    validate_timeline(doc['timeline'],doc['slots'],doc['bpm'])
    if len(doc['sounds'])!=6 or not all(isinstance(x,str) for x in doc['sounds']):raise ValueError('Sources invalides')
    if len(doc['volumes'])!=6 or any(type(v) not in (float,int) or not 0<=v<=1 for v in doc['volumes']):raise ValueError('Volumes invalides')
    if len(doc['mutes'])!=6 or len(doc['solos'])!=6 or any(type(v)!=bool for v in doc['mutes']+doc['solos']):raise ValueError('Mute / Solo invalides')
    if type(doc['swing'])!=int or not 0<=doc['swing']<=75:raise ValueError('Swing invalide')
    if type(doc.get('fx_enabled',False)) is not bool:raise ValueError('Activation FX incorrecte')
    doc['master_fx']=validate_fx(doc.get('master_fx',{}))
    doc['fx_enabled']=doc.get('fx_enabled',False)
    return doc
