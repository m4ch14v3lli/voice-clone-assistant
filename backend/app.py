from fastapi import FastAPI, UploadFile
from voice_clone import VoiceCloner
import uvicorn

app = FastAPI()
cloner = VoiceCloner()

@app.post("/clone-voice")
async def clone_voice(audio: UploadFile):
    voice_id = cloner.create_voice(await audio.read())
    return {"voice_id": voice_id}

@app.post("/speak")
async def speak(text: str, voice_id: str):
    audio_bytes = cloner.speak(text, voice_id)
    return {
        "audio": audio_bytes.hex()
    }

@app.post("/assistant")
async def assistant(audio: UploadFile, voice_id: str):
    # 1. STT
    text = cloner.transcribe(await audio.read())

    # 2. Generate response
    response = cloner.generate(text)

    # 3. TTS with cloned voice
    audio_bytes = cloner.speak(response, voice_id)

    return {
        "text": response,
        "audio": audio_bytes.hex()
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
