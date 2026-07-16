"""
BELLA - Speech to Text (STT) Engine
Uses faster-whisper to transcribe audio files on CPU.
"""

from pathlib import Path
from faster_whisper import WhisperModel


class SpeechToText:
    """Lazy-loaded Whisper engine for speech-to-text transcription."""

    def __init__(self, model_size: str = "tiny", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    @property
    def model(self) -> WhisperModel:
        """Lazily initialize the Whisper model on first access."""
        if self._model is None:
            # Loads the model from Hugging Face hub / local cache
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
        return self._model

    def transcribe(self, file_path: str | Path) -> str:
        """
        Transcribe an audio file to text.
        
        Args:
            file_path: Path to the audio file (wav, webm, mp3, etc.).
            
        Returns:
            The combined transcribed text.
        """
        segments, info = self.model.transcribe(str(file_path), beam_size=5)
        text = "".join(segment.text for segment in segments)
        return text.strip()


# Singleton instance
stt = SpeechToText()
