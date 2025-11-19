# backend/app.py
import os
import base64
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .voice_store import VoiceStore
from .tts_adapters import OpenAIAdapter, LocalAdapter
from dotenv import load_dotenv

load_dotenv()

STORAGE_DIR = Path(os.getenv("VOICE_STORAGE_DIR", "voice_storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Voice Clone Assistant Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only; tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

voice_store = VoiceStore(STORAGE_DIR)

# Choose adapters here. We initialize both; choose per-request via `provider` param.
openai_adapter = OpenAIAdapter(api_key=os.getenv("OPENAI_API_KEY"))
local_adapter = LocalAdapter()  # requires you to implement / configure

class CreateVoiceResponse(BaseModel):
    voice_id: str
    name: str
    filename: str
    download_url: str

@app.post("/voices", response_model=CreateVoiceResponse)
async def create_voice(file: UploadFile = File(...), name: str = Form(None)):
    """
    Upload a reference audio sample for a character / voice.
    Returns a voice_id and metadata. Save the voice_id and use it for TTS calls.
    """
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Upload must be an audio file")

    contents = await file.read()
    voice_id = voice_store.create_voice(contents, original_filename=file.filename, name=name)
    download_url = f"/voices/{voice_id}/download"
    return CreateVoiceResponse(voice_id=voice_id, name=voice_store.get(voice_id)["name"],
                              filename=voice_store.get(voice_id)["filename"],
                              download_url=download_url)

@app.get("/voices/{voice_id}")
async def get_voice_metadata(voice_id: str):
    v = voice_store.get(voice_id)
    if not v:
        raise HTTPException(status_code=404, detail="voice not found")
    return v

@app.get("/voices/{voice_id}/download")
async def download_voice_file(voice_id: str):
    v = voice_store.get(voice_id)
    if not v:
        raise HTTPException(status_code=404, detail="voice not found")
    return FileResponse(v["path"], media_type="application/octet-stream", filename=v["filename"])

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...), provider: str = Form("openai")):
    """
    Transcribe an uploaded audio file. Uses provider specified (currently supports 'openai').
    """
    contents = await file.read()
    if provider == "openai":
        if not openai_adapter.is_configured:
            raise HTTPException(status_code=500, detail="OpenAI adapter not configured (set OPENAI_API_KEY)")
        text = openai_adapter.transcribe_audio_bytes(contents, filename=file.filename)
        return {"text": text}
    else:
        raise HTTPException(status_code=400, detail="Unknown provider")

class SpeakRequest(BaseModel):
    text: str
    voice_id: str
    provider: str | None = "openai"   # which TTS provider to use
    format: str | None = "wav"        # wav or mp3

@app.post("/speak")
async def speak(req: SpeakRequest):
    """
    Synthesize text using the voice referred by voice_id.
    Returns base64-encoded WAV bytes (so you can easily play it client-side).
    """
    v = voice_store.get(req.voice_id)
    if not v:
        raise HTTPException(status_code=404, detail="voice not found")

    if req.provider == "openai":
        if not openai_adapter.is_configured:
            raise HTTPException(status_code=500, detail="OpenAI adapter not configured (set OPENAI_API_KEY)")
        audio_bytes = openai_adapter.speak_using_reference(text=req.text, reference_audio_path=v["path"], out_format=req.format)
    elif req.provider == "local":
        audio_bytes = local_adapter.speak_using_reference(text=req.text, reference_audio_path=v["path"], out_format=req.format)
    else:
        raise HTTPException(status_code=400, detail="Unknown provider")

    payload_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    return {"audio_base64": payload_b64, "format": req.format}

class AssistantRequest(BaseModel):
    audio_file_b64: str   # base64-encoded audio bytes recorded by user
    voice_id: str
    provider: str | None = "openai"

@app.post("/assistant")
async def assistant(req: AssistantRequest):
    """
    Full flow: user posts recorded audio (base64). We:
    1) transcribe user input
    2) send to LLM for response (OpenAI chat)
    3) synthesize response with the specified voice
    """
    # decode incoming audio
    audio_bytes = base64.b64decode(req.audio_file_b64)

    # 1) STT
    if not openai_adapter.is_configured:
        raise HTTPException(status_code=500, detail="OpenAI adapter not configured")
    user_text = openai_adapter.transcribe_audio_bytes(audio_bytes, filename="user.wav")

    # 2) Generate reply (simple chat)
    ai_reply = openai_adapter.generate_chat_response(user_text)

    # 3) TTS
    v = voice_store.get(req.voice_id)
    if not v:
        raise HTTPException(status_code=404, detail="voice not found")
    audio_reply = openai_adapter.speak_using_reference(text=ai_reply, reference_audio_path=v["path"], out_format="wav")

    audio_b64 = base64.b64encode(audio_reply).decode("utf-8")
    return {"transcription": user_text, "response_text": ai_reply, "audio_base64": audio_b64, "format": "wav"}
