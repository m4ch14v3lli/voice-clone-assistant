# backend/tts_adapters.py
import os
from typing import Optional
import base64

# Optional dependency
try:
    import openai
except Exception:
    openai = None

class OpenAIAdapter:
    """
    Adapter that uses OpenAI for transcription, chat, and (optionally) TTS.
    Replace or adapt speak_using_reference() to match the provider's TTS API for voice cloning.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.is_configured = bool(api_key) and openai is not None
        if self.is_configured:
            openai.api_key = api_key

    def transcribe_audio_bytes(self, audio_bytes: bytes, filename="audio.wav") -> str:
        if not self.is_configured:
            raise RuntimeError("OpenAIAdapter not configured")
        # Write temp file
        import tempfile
        tf = tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix if '.' in filename else ".wav")
        tf.write(audio_bytes)
        tf.flush()
        tf.close()

        # Use OpenAI whisper transcriptions (this example uses openai.Audio.transcribe)
        # NOTE: adapt to the exact client method if your openai package version differs.
        with open(tf.name, "rb") as fh:
            resp = openai.Audio.transcribe("gpt-4o-transcribe", fh)
            # Many OpenAI python client implementations return a dict or object with 'text' field
            text = resp["text"] if isinstance(resp, dict) and "text" in resp else getattr(resp, "text", None)
        os.unlink(tf.name)
        return text

    def generate_chat_response(self, user_text: str) -> str:
        if not self.is_configured:
            raise RuntimeError("OpenAIAdapter not configured")
        # Use chat completion
        resp = openai.ChatCompletion.create(
            model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": user_text}],
            max_tokens=400
        )
        # adapt to client response structure
        content = resp["choices"][0]["message"]["content"] if isinstance(resp, dict) else resp.choices[0].message.content
        return content

    def speak_using_reference(self, text: str, reference_audio_path: str, out_format: str = "wav") -> bytes:
        """
        Example placeholder.
        Replace this logic with the real call to create a cloned voice using the provider you choose.
        Approaches:
        - OpenAI Realtime/Audio TTS with reference audio (if available) -> call provider API
        - Local TTS (Coqui/Resemble/Whatever) calling a CLI or SDK
        For the example we will show a *mock* implementation that returns plain TTS (or raises) — replace it.
        """
        if not self.is_configured:
            raise RuntimeError("OpenAIAdapter not configured")

        # *** IMPORTANT ***
        # This is a stub. Many providers require you to upload the reference audio,
        # register a voice profile, then call TTS with the voice_id and text.
        # Implement the provider-specific flow here.
        raise NotImplementedError(
            "speak_using_reference is a placeholder — integrate with your chosen TTS provider here"
        )


class LocalAdapter:
    """
    Local adapter for running local TTS that may support voice cloning.
    Example usages:
    - Call a Coqui/ESPnet/other TTS CLI that accepts a reference audio
    - Or run your own model in Python and return bytes
    """
    def __init__(self):
        pass

    def speak_using_reference(self, text: str, reference_audio_path: str, out_format: str = "wav") -> bytes:
        """
        Replace this with command line calls or SDK calls to your local TTS engine.
        For example: run `coqui-tts --model ... --reference-track reference_audio_path --text "..." --out out.wav`
        Then read out.wav bytes and return.
        """
        raise NotImplementedError("LocalAdapter.speak_using_reference must be implemented for your local TTS")
