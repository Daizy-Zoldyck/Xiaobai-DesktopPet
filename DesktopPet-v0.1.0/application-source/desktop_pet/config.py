import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def runtime_directory():
    override = os.environ.get("DESKTOPPET_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "DesktopPet"
    return ROOT / "runtime"


RUNTIME = runtime_directory()
DEFAULTS = {
    "renderer": "png",
    "image": "assets/pet.png",
    "height": 300,
    "position": None,
    "edge_snap": True,
    "idle_motion": False,
    "refresh_seconds": 300,
    "bucket_id": "codex",
    "codex_executable": "",
    "event_bindings": {},
}


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


class Settings:
    def __init__(self, path: Path = RUNTIME / "config.json"):
        self.path = path
        self.data = dict(DEFAULTS)
        try:
            values = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(values, dict):
                self.data.update(values)
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            logging.warning("Settings could not be loaded; using defaults")
        try:
            self.data["height"] = max(180, min(600, int(self.data["height"])))
            self.data["refresh_seconds"] = max(60, min(3600, int(self.data["refresh_seconds"])))
        except (TypeError, ValueError):
            self.data["height"] = 300
            self.data["refresh_seconds"] = 300
        pos = self.data.get("position")
        if not (isinstance(pos, list) and len(pos) == 2 and all(type(v) is int for v in pos)):
            self.data["position"] = None

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        try:
            atomic_json(self.path, self.data)
        except OSError:
            logging.exception("Could not save settings")
