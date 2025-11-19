# backend/voice_store.py
import json
import uuid
from pathlib import Path
from typing import Dict

class VoiceStore:
    """
    Simple filesystem-backed voice store.
    Each voice profile = a small JSON file + the uploaded reference audio.
    """
    def __init__(self, storage_dir: Path):
        self.storage_dir = Path(storage_dir)
        self.profiles_dir = self.storage_dir / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def create_voice(self, audio_bytes: bytes, original_filename: str = "sample.wav", name: str | None = None) -> str:
        voice_id = uuid.uuid4().hex[:12]
        filename = f"{voice_id}_{Path(original_filename).name}"
        path = self.profiles_dir / filename
        with open(path, "wb") as f:
            f.write(audio_bytes)

        meta = {
            "id": voice_id,
            "name": name or f"voice-{voice_id}",
            "filename": filename,
            "path": str(path),
        }
        meta_path = self.profiles_dir / f"{voice_id}.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        return voice_id

    def get(self, voice_id: str) -> Dict | None:
        meta_path = self.profiles_dir / f"{voice_id}.json"
        if not meta_path.exists():
            return None
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def list(self):
        res = []
        for p in self.profiles_dir.glob("*.json"):
            with open(p, "r", encoding="utf-8") as f:
                res.append(json.load(f))
        return res
