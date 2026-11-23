"""Offline master bus FX: independent of MIDI/Korg, bounded & deterministic."""
from array import array
import math
import sys

RATE = 44100

def apply_fx(pcm, gain=1., drive=0., echo=0., cutoff=20000, wet=0.35):
    """Return PCM16 mono with master gain, tanh saturation, one-pole lowpass and feedback-free echo.

    Echo tail fits in the original duration; this does not write to physical devices.
    """
    params = (gain, drive, echo, cutoff, wet)
    if not all(isinstance(v,(int,float)) and math.isfinite(v) for v in params):
        raise ValueError("Réglages FX invalides")
    if not (.0 <= gain <= 2 and 0 <= drive <= 1 and 0 <= echo <= 1 and 100 <= cutoff <= 20000 and 0 <= wet <= 1):
        raise ValueError("Réglages FX hors limites")
    if len(pcm) % 2: raise ValueError("PCM16 incomplet")
    samples = array('h'); samples.frombytes(pcm)
    if sys.byteorder != 'little': samples.byteswap()
    if not samples: return b''
    dry = [v/32768.0 for v in samples]
    alpha = 1-math.exp(-2*math.pi*cutoff/RATE)
    delay = int(.22*RATE)
    previous = 0.
    result = array('h')
    for i,value in enumerate(dry):
        v = value*gain
        if drive:
            amount = 1+drive*11
            v = math.tanh(v*amount)/math.tanh(amount)
        previous += alpha*(v-previous)
        v = previous
        if echo and i>=delay:
            v += echo*wet*dry[i-delay]*gain
        result.append(round(max(-1.,min(32767/32768, v))*32768))
    if sys.byteorder != 'little': result.byteswap()
    return result.tobytes()


def validate_fx(doc):
    if not isinstance(doc,dict): raise ValueError('FX : document invalide')
    defaults={'gain':1.0,'drive':0.0,'echo':0.0,'cutoff':20000,'wet':0.35}
    data={key:doc.get(key,default) for key,default in defaults.items()}
    apply_fx(b'',**data)
    return data
