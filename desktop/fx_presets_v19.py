"""Presets locaux pour le bus FX mono; aucune commande MIDI."""
from mixer_fx_v18 import validate_fx
PRESETS = {
    'NEUTRE': {'gain': 1.0,'drive':0.0,'echo':0.0,'cutoff':20000},
    'TRIBE DRIVE': {'gain':1.05,'drive':0.28,'echo':0.0,'cutoff':13000},
    'DUB ECHO': {'gain':0.9,'drive':0.0,'echo':0.6,'cutoff':10000},
    'DARK FILTER': {'gain':1.1,'drive':0.2,'echo':0.15,'cutoff':1900},
    'BREAK GLITCH': {'gain':0.95,'drive':0.38,'echo':0.27,'cutoff':6500},
}
def preset(name):
    return validate_fx(PRESETS[name])
