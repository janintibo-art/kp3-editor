"""Local, defensive desktop panel layout state. Never touches MIDI or project data."""
import json
from pathlib import Path

DEFAULT = {"version": 1, "mode": "equilibre", "geometry": [1350, 820], "sashes": None, "last_tool": "live"}

def normalize_layout(data):
    if not isinstance(data, dict):
        return dict(DEFAULT)
    result = dict(DEFAULT)
    if data.get("mode") in ("equilibre", "live", "studio"):
        result["mode"] = data["mode"]
    if data.get("last_tool") in ("live", "sample", "synth", "seq", "library"):
        result["last_tool"] = data["last_tool"]
    geometry = data.get("geometry")
    if isinstance(geometry, list) and len(geometry)==2 and all(type(n) is int for n in geometry):
        result["geometry"] = [max(1040, min(3000, geometry[0])), max(690, min(1800, geometry[1]))]
    sashes = data.get("sashes")
    if isinstance(sashes, list) and len(sashes) == 2 and all(type(n) in (int,float) for n in sashes):
        a,b=sashes
        if .15 <= a <= .38 and .63 <= b <= .88 and b-a >= .35:
            result["sashes"] = [float(a), float(b)]
    return result

def load_layout(data_dir):
    path=Path(data_dir)/"workspace_v21.json"
    try:
        if path.stat().st_size > 8192: return dict(DEFAULT)
        return normalize_layout(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return dict(DEFAULT)

def save_layout(data_dir, layout):
    folder=Path(data_dir);folder.mkdir(parents=True, exist_ok=True)
    dest=folder/"workspace_v21.json"
    temp=folder/"workspace_v21.json.tmp"
    temp.write_text(json.dumps(normalize_layout(layout), ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(dest)
