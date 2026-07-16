import pytest
import numpy as np
import io
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import WebSocketDisconnect

from bella.app import app
from bella.voice.stt import SpeechToText
from bella.voice.tts import TextToSpeech
from bella.voice.wakeword import WakeWordDetector


def test_stt_transcribe_mock():
    # Mock WhisperModel
    with patch("bella.voice.stt.WhisperModel") as mock_whisper_class:
        mock_model = MagicMock()
        mock_segment = MagicMock()
        mock_segment.text = "Hello world"
        mock_model.transcribe.return_value = ([mock_segment], None)
        mock_whisper_class.return_value = mock_model

        stt_engine = SpeechToText()
        text = stt_engine.transcribe("dummy_path.wav")
        assert text == "Hello world"
        mock_model.transcribe.assert_called_once_with("dummy_path.wav", beam_size=5)


def test_tts_synthesize_mock():
    # Mock PiperVoice
    with patch("bella.voice.tts.PiperVoice") as mock_piper_class:
        mock_voice = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.audio_int16_bytes = b"\x00\x00\x01\x00"
        mock_voice.synthesize.return_value = [mock_chunk]
        mock_piper_class.load.return_value = mock_voice

        # Mock ensure_model to do nothing
        with patch.object(TextToSpeech, "ensure_model", return_value=None):
            tts_engine = TextToSpeech()
            # Force trigger load
            _ = tts_engine.voice
            
            wav_bytes = tts_engine.synthesize("Hello")
            assert isinstance(wav_bytes, bytes)
            assert len(wav_bytes) > 44  # WAV header is 44 bytes minimum


def test_wakeword_detector():
    with patch("bella.voice.wakeword.Model") as mock_model_class:
        mock_model = MagicMock()
        mock_model.predict.return_value = {"hey_jarvis_v0.1": 0.8}
        mock_model_class.return_value = mock_model

        detector = WakeWordDetector(threshold=0.5)
        # 1280 samples * 2 bytes = 2560 bytes
        dummy_chunk = b"\x00" * 2560
        assert detector.predict(dummy_chunk) is True

        # Test when prediction is below threshold
        mock_model.predict.return_value = {"hey_jarvis_v0.1": 0.2}
        assert detector.predict(dummy_chunk) is False

        # Test invalid chunk size
        assert detector.predict(b"\x00" * 100) is False


def test_api_transcribe():
    client = TestClient(app)
    # Mock stt transcribe method
    with patch("bella.api.voice.stt.transcribe", return_value="Test transcription text") as mock_transcribe:
        file_content = b"fake audio data"
        # We pass a simple file to upload
        file = {"file": ("recording.webm", file_content, "audio/webm")}
        response = client.post("/api/voice/transcribe", files=file)
        
        assert response.status_code == 200
        assert response.json() == {"text": "Test transcription text"}


def test_api_synthesize():
    client = TestClient(app)
    # Mock tts synthesize method
    with patch("bella.api.voice.tts.synthesize", return_value=b"fake wav bytes") as mock_synthesize:
        response = client.post("/api/voice/synthesize", json={"text": "Synthesize this"})
        
        assert response.status_code == 200
        assert response.content == b"fake wav bytes"
        assert response.headers["content-type"] == "audio/wav"


def test_api_wakeword_websocket():
    client = TestClient(app)
    
    # Mock WakeWordDetector
    with patch("bella.api.voice.WakeWordDetector") as mock_detector_class:
        mock_detector = MagicMock()
        mock_detector.predict.side_effect = [False, True]
        mock_detector_class.return_value = mock_detector

        with client.websocket_connect("/api/voice/wakeword") as websocket:
            # Send first chunk (detector returns False)
            websocket.send_bytes(b"\x00" * 2560)
            
            # Send second chunk (detector returns True)
            websocket.send_bytes(b"\x00" * 2560)
            
            # Expect event JSON response from WebSocket
            resp = websocket.receive_json()
            assert resp == {"event": "wakeword_detected"}
