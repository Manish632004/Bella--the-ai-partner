"""
BELLA - Voice API Routes
Endpoints for speech transcription, TTS synthesis, and WebSocket wake word streaming.
"""

import os
import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, WebSocket, WebSocketDisconnect, Response
from pydantic import BaseModel, Field

from bella.voice.stt import stt
from bella.voice.tts import tts
from bella.voice.wakeword import WakeWordDetector

router = APIRouter(prefix="/api/voice", tags=["voice"])


class SynthesizeRequest(BaseModel):
    """Text to synthesize into voice."""
    text: str = Field(..., min_length=1, max_length=2000)


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Upload an audio file (WebM, WAV, OGG, etc.) and get transcription text.
    """
    suffix = Path(file.filename).suffix or ".webm"
    # Ensure temporary directory exists under PROJECT_ROOT/scratch
    temp_dir = Path(tempfile.gettempdir())
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=temp_dir) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # Transcribe using Whisper
        text = stt.transcribe(tmp_path)
        return {"text": text}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/synthesize")
async def synthesize_speech(req: SynthesizeRequest):
    """
    Synthesize text into WAV audio bytes using Piper TTS.
    """
    try:
        wav_bytes = tts.synthesize(req.text)
        return Response(
            content=wav_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav"
            }
        )
    except Exception as e:
        return Response(
            content=f"Error: {e}".encode(),
            status_code=500,
            media_type="text/plain"
        )


@router.websocket("/wakeword")
async def websocket_wakeword(websocket: WebSocket):
    """
    WebSocket endpoint for streaming 16kHz PCM audio to detect wake words.
    Expects binary frames containing raw 16-bit 16kHz mono PCM.
    """
    await websocket.accept()
    detector = WakeWordDetector()
    buffer = bytearray()
    
    try:
        while True:
            # Receive binary frame
            data = await websocket.receive_bytes()
            buffer.extend(data)
            
            # Group into 1280 sample chunks (2560 bytes)
            while len(buffer) >= 2560:
                chunk = bytes(buffer[:2560])
                del buffer[:2560]
                
                # Check for wake word
                if detector.predict(chunk):
                    # Trigger client wake event
                    await websocket.send_json({"event": "wakeword_detected"})
                    # Clear buffer to prevent double triggers
                    buffer.clear()
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # Print or log error silently without crashing socket handler
        print(f"[BELLA Voice] Wake word WebSocket disconnected/error: {e}")
