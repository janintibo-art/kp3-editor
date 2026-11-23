"""Analyse locale et non destructive des WAV PCM 16 bits.
Aucune détection de type ou de BPM n'est présentée comme certaine.
"""
import array
import math
import sys
import wave
from pathlib import Path

MAX_BYTES = 80 * 1024 * 1024
MAX_ENVELOPE_SECONDS = 45
ENVELOPE_HZ = 100


def analyze_wav(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('WAV supérieur à 80 Mo : analyse refusée')
    with wave.open(str(path), 'rb') as audio:
        if audio.getcomptype() != 'NONE' or audio.getsampwidth() != 2:
            raise ValueError('Analyse disponible pour WAV PCM 16 bits non compressé')
        channels, rate, frames = audio.getnchannels(), audio.getframerate(), audio.getnframes()
        if channels not in (1, 2) or rate <= 0 or frames <= 0:
            raise ValueError('Format WAV non pris en charge')
        duration = frames / rate
        window = max(1, round(rate / ENVELOPE_HZ))
        peak = 0
        square_sum = 0
        sample_count = 0
        envelope = []
        read_frames = 0
        # Streaming : ne jamais charger un fichier complet en RAM.
        while True:
            raw = audio.readframes(min(window, max(0, frames - read_frames)))
            if not raw:
                break
            count = len(raw) // (2 * channels)
            read_frames += count
            values = array.array('h')
            values.frombytes(raw)
            if sys.byteorder != 'little':
                values.byteswap()
            if not values:
                continue
            local_max = max(abs(v) for v in values)
            peak = max(peak, local_max)
            square_sum += sum(v * v for v in values)
            sample_count += len(values)
            if read_frames <= rate * MAX_ENVELOPE_SECONDS:
                envelope.append(math.sqrt(sum(v * v for v in values) / len(values)) / 32768.0)
        rms = math.sqrt(square_sum / sample_count) / 32768.0 if sample_count else 0
        peak_normalized = min(1.0, peak / 32768.0)
        bpm, confidence = estimate_bpm(envelope, rate / window)
        return {
            'name': path.name, 'duration_seconds': round(duration, 3),
            'sample_rate_hz': rate, 'channels': channels, 'bit_depth': 16,
            'peak_dbfs': round(20 * math.log10(max(peak_normalized, 1e-12)), 1),
            'rms_dbfs': round(20 * math.log10(max(rms, 1e-12)), 1),
            'bpm_estimate': bpm, 'bpm_confidence': confidence,
            'bpm_note': 'Estimation rythmique indicative, à confirmer à l’oreille',
        }


def estimate_bpm(envelope, sample_hz):
    """Autocorrélation de transitoires, conservative : None si incertain."""
    if len(envelope) < 4 * sample_hz or max(envelope, default=0) < 0.015:
        return None, 'insuffisante'
    # Positive spectral-flux proxy (energy onset). Remove weak transients.
    flux = [0.0] + [max(0.0, envelope[i] - envelope[i - 1]) for i in range(1, len(envelope))]
    average = sum(flux) / len(flux)
    flux = [max(0.0, x - average * 1.5) for x in flux]
    energy = sum(x * x for x in flux)
    if energy < 1e-5:
        return None, 'insuffisante'
    best = (0.0, 0)
    runners = []
    for bpm in range(70, 221):
        lag = round(sample_hz * 60 / bpm)
        if lag <= 0 or lag >= len(flux):
            continue
        cross = sum(a * b for a, b in zip(flux[lag:], flux[:-lag]))
        norm = math.sqrt(sum(v * v for v in flux[lag:]) * sum(v * v for v in flux[:-lag]))
        score = cross / norm if norm else 0.0
        runners.append((score, bpm))
        if score > best[0]:
            best = score, bpm
    # Avoid presenting an arbitrary BPM for unstructured material.
    if best[0] < 0.28:
        return None, 'insuffisante'
    return int(best[1]), 'indicative'
