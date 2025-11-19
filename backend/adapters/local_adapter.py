# backend/adapters/local_adapter.py
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional

VOICE_STORE_DIR = Path("backend/storage/voices")  # update to your repo's voice folder
TTS_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"  # change if you prefer another model

VOICE_STORE_DIR.mkdir(parents=True, exist_ok=True)


class LocalAdapter:
    """
    Local adapter that uses Coqui TTS CLI (python package `TTS`) to synthesize
    speech using a reference audio (speaker_wav / reference).
    """

    def __init__(self, voice_dir: Path = VOICE_STORE_DIR, model_name: str = TTS_MODEL_NAME):
        self.voice_dir = Path(voice_dir)
        self.model_name = model_name

    def _normalize_reference(self, src_path: Path) -> Path:
        """
        Ensure reference is WAV, mono, 22050Hz (or 16000 if you pick),
        writes a normalized copy and returns its path.
        """
        src = Path(src_path)
        if not src.exists():
            raise FileNotFoundError(f"Reference audio not found: {src}")

        normalized = self.voice_dir / f"{src.stem}_normalized_{uuid.uuid4().hex}.wav"
        # Use ffmpeg to resample/convert to WAV 22050 mono
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "22050",
            "-f",
            "wav",
            str(normalized),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return normalized

    def create_voice(self, reference_audio_path: str, name: Optional[str] = None) -> dict:
        """
        Save the reference sample in voice store and return metadata.
        This is a minimal local 'voice creation' that stores the sample and returns a voice_id.
        """
        src = Path(reference_audio_path)
        if not src.exists():
            raise FileNotFoundError("Reference audio file not found")

        voice_id = uuid.uuid4().hex
        filename = f"{voice_id}_{src.name}"
        dst = self.voice_dir / filename
        shutil.copy2(src, dst)

        meta = {
            "voice_id": voice_id,
            "name": name or f"local-{voice_id[:8]}",
            "filename": filename,
            "path": str(dst),
        }
        # Persist however your repo expects (file, DB). Example: write a json, or call VoiceStore.
        # For demo, we write a small meta json file alongside the wav:
        import json
        with open(self.voice_dir / f"{voice_id}.json", "w") as f:
            json.dump(meta, f)
        return meta

    def _load_voice_meta(self, voice_id: str) -> dict:
        meta_path = self.voice_dir / f"{voice_id}.json"
        if not meta_path.exists():
            raise FileNotFoundError("Voice metadata not found")
        import json
        with open(meta_path, "r") as f:
            return json.load(f)

    def speak_using_reference(self, voice_id: str, text: str, out_format: str = "wav") -> bytes:
        """
        Synthesize speech for `text` using the stored reference for `voice_id`.
        Returns raw audio bytes (WAV by default).
        """
        meta = self._load_voice_meta(voice_id)
        ref_path = Path(meta["path"])
        # normalize reference to expected sample rate & channels
        normalized_ref = self._normalize_reference(ref_path)

        # produce temp output file
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / f"out.{out_format}"
            # Build CLI command for coqui TTS
            # Note: CLI option names vary by coqui TTS version: `--speaker_wav` or `--speaker_wav_path`.
            # The widely supported option is `--speaker_wav` (used in many examples).
            cmd = [
                "tts",
                "--text",
                text,
                "--model_name",
                self.model_name,
                "--out_path",
                str(out_path),
                "--speaker_wav",
                str(normalized_ref),
            ]

            # If the selected model requires language or speaker index, add args here.
            # Example:
            # cmd += ["--language", "en"]

            proc = subprocess.run(cmd, capture_output=True)
            if proc.returncode != 0 or not out_path.exists():
                raise RuntimeError(
                    f"Coqui TTS failed (rc={proc.returncode}). stdout: {proc.stdout.decode()}\nstderr: {proc.stderr.decode()}"
                )

            # Read bytes and return
            audio_bytes = out_path.read_bytes()

        # cleanup normalized ref
        try:
            normalized_ref.unlink()
        except Exception:
            pass

        return audio_bytes
