"""
BELLA - Wake Word Detection Engine
Uses openwakeword to detect wake words (like "hey jarvis") in 16kHz PCM streams.
"""

import numpy as np
from openwakeword.model import Model


class WakeWordDetector:
    """Detects wake words in real-time streaming audio."""

    def __init__(self, model_name: str = "hey_jarvis", threshold: float = 0.5):
        self.model_name = model_name
        self.threshold = threshold
        # Loads pre-trained wake word model
        self.model = Model(wakeword_models=[model_name], inference_framework="onnx")

    def predict(self, chunk: bytes) -> bool:
        """
        Predict if the wake word is present in the current audio chunk.
        
        Args:
            chunk: Raw 16-bit 16kHz mono PCM bytes.
                   Must be 1280 samples (2560 bytes) for openwakeword.
            
        Returns:
            True if wake word probability exceeds threshold.
        """
        if len(chunk) != 2560:
            # Skip invalid chunk sizes
            return False

        # Convert bytes to int16 numpy array
        audio = np.frombuffer(chunk, dtype=np.int16)
        
        # Feed to model and check prediction
        prediction = self.model.predict(audio)
        
        # The key is the base filename of the tflite model (e.g. "hey_jarvis_v0.1")
        # Let's find any key in prediction dict that starts with self.model_name
        prob = 0.0
        for key, val in prediction.items():
            if key.startswith(self.model_name):
                prob = val
                break

        return prob > self.threshold
