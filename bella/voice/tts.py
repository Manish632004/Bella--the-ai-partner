"""
BELLA - Text to Speech (TTS) Engine
Uses Piper to synthesize neural text-to-speech to WAV format.
Downloads voice model files on demand.
"""

import wave
import io
import os
import httpx
from pathlib import Path
from piper import PiperVoice
from bella.core.config import config


class TextToSpeech:
    """Lazy-loaded Piper neural TTS synthesizer."""

    def __init__(self, model_name: str = "en_US-lessac-medium"):
        self.model_name = model_name
        self.models_dir = config.PROJECT_ROOT / "models" / "piper"
        self.model_path = self.models_dir / f"{model_name}.onnx"
        self.config_path = self.models_dir / f"{model_name}.onnx.json"
        self._voice = None

    def ensure_model(self):
        """Ensure the Piper voice model and config are downloaded locally."""
        if self.model_path.exists() and self.config_path.exists():
            return

        self.models_dir.mkdir(parents=True, exist_ok=True)
        base_url = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium"

        print(f"[BELLA TTS] Downloading Piper voice model to {self.model_path}...")
        with httpx.Client(timeout=180.0) as client:
            # Download model
            resp = client.get(f"{base_url}/{self.model_name}.onnx", follow_redirects=True)
            resp.raise_for_status()
            self.model_path.write_bytes(resp.content)

            # Download config
            resp = client.get(f"{base_url}/{self.model_name}.onnx.json", follow_redirects=True)
            resp.raise_for_status()
            self.config_path.write_bytes(resp.content)
        print("[BELLA TTS] Voice model download complete.")

    @property
    def voice(self) -> PiperVoice:
        """Get or lazily load the Piper voice instance."""
        if self._voice is None:
            self.ensure_model()
            self._voice = PiperVoice.load(
                model_path=str(self.model_path),
                config_path=str(self.config_path)
            )
        return self._voice

    def synthesize(self, text: str) -> bytes:
        """
        Synthesize text into WAV audio bytes.
        
        Args:
            text: Text to synthesize.
            
        Returns:
            Bytes representing the complete WAV file.
        """
        voice = self.voice
        wav_buffer = io.BytesIO()

        with wave.open(wav_buffer, "wb") as wav_file:
            # Piper lessac-medium outputs mono (1 channel), 16-bit PCM (2 bytes/sample), at 22050Hz
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)

            for chunk in voice.synthesize(text):
                wav_file.writeframes(chunk.audio_int16_bytes)

        return wav_buffer.getvalue()


# Singleton instance
tts = TextToSpeech()
