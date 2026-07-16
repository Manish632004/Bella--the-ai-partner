"""
BELLA — Voice Loop Engine (v2 — Wake Word Edition)
Handles the full voice agent lifecycle:
  Wake Word Detection → Chime → VAD Capture → Whisper STT → Ollama Streaming → Piper TTS → Loop
"""

import os
import math
import wave
import io
import time
import queue
import threading
import asyncio
import numpy as np
import sounddevice as sd

from bella.core.llm import llm
from bella.core.conversation import conversation_manager
from bella.voice.stt import stt
from bella.voice.tts import tts
from bella.voice.wakeword import WakeWordDetector


class VoiceLoop:
    """Always-listening Voice Agent engine with wake word detection."""

    def __init__(
        self,
        session_id="desktop-session",
        on_state_change=None,
        on_transcript=None,
        on_volume=None,
        on_caption=None,
    ):
        self.session_id = session_id
        self.on_state_change = on_state_change  # Callback (state, detail)
        self.on_transcript = on_transcript      # Callback (role, text)
        self.on_volume = on_volume              # Callback (volume_float)
        self.on_caption = on_caption            # Callback (role, text) — live captions

        self.running = False
        self.loop_thread = None
        self.playback_thread = None

        # Queues
        self.tts_queue = queue.Queue()          # Queues of (audio_bytes, text) to play
        self.stop_playback_event = threading.Event()

        # Voice Activity Detection Settings
        self.sample_rate = 16000
        self.block_size = 1280                 # 80ms frames — matches openwakeword requirement
        self.silence_threshold = 0.02          # RMS energy threshold
        self.silence_duration_limit = 1.2      # Silence duration before ending speech
        self.min_speech_duration = 0.4         # Min duration to count as speech
        self.max_recording_time = 15.0         # Max recording length

        # State flags
        self.is_speaking = False
        self.is_muted = False

        # Wake word detector (lazy-initialized in the loop thread to keep startup fast)
        self._detector = None

    def start(self):
        """Start the voice assistant loop threads."""
        if self.running:
            return
        self.running = True
        self.stop_playback_event.clear()

        # Start Voice Loop thread
        self.loop_thread = threading.Thread(target=self._run_voice_loop, daemon=True)
        self.loop_thread.start()

        # Start Playback thread
        self.playback_thread = threading.Thread(target=self._run_playback_loop, daemon=True)
        self.playback_thread.start()

    def stop(self):
        """Stop all background threads and audio streams."""
        self.running = False
        self.stop_playback_event.set()
        sd.stop()  # Stop any active sounddevice playback/recording

        # Empty queues
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
            except queue.Empty:
                break

        self._update_state("idle")

    def toggle_mute(self):
        """Mute/unmute voice output."""
        self.is_muted = not self.is_muted
        if self.is_muted:
            sd.stop()
            # Clear queue
            while not self.tts_queue.empty():
                try:
                    self.tts_queue.get_nowait()
                except queue.Empty:
                    break
        return self.is_muted

    # ─────────────────────────────────────────────────────────────
    #  Callback helpers
    # ─────────────────────────────────────────────────────────────
    def _update_state(self, state, detail=""):
        if self.on_state_change:
            self.on_state_change(state, detail)

    def _update_transcript(self, role, text):
        if self.on_transcript:
            self.on_transcript(role, text)

    def _update_volume(self, volume):
        if self.on_volume:
            self.on_volume(volume)

    def _update_caption(self, role, text):
        if self.on_caption:
            self.on_caption(role, text)

    # ─────────────────────────────────────────────────────────────
    #  Chime synthesis — plays a short C5→E5 chord with decay
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _make_chime() -> np.ndarray:
        """Synthesize a short two-tone chime (C5 → E5, ~350ms)."""
        sr = 22050
        duration = 0.35
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)

        # C5 (523.25 Hz) and E5 (659.25 Hz) layered
        tone = 0.35 * np.sin(2 * math.pi * 523.25 * t)
        tone += 0.25 * np.sin(2 * math.pi * 659.25 * t)

        # Exponential decay envelope
        envelope = np.exp(-t * 8.0)
        chime = (tone * envelope * 32767).astype(np.int16)
        return chime

    def _play_chime(self):
        """Play the wake-word-trigger chime synchronously."""
        chime = self._make_chime()
        try:
            sd.play(chime, samplerate=22050)
            sd.wait()
        except Exception as e:
            print(f"[VoiceLoop] Chime play error: {e}")

    # ─────────────────────────────────────────────────────────────
    #  Playback loop (TTS sentence queue consumer)
    # ─────────────────────────────────────────────────────────────
    def _run_playback_loop(self):
        """Handles sequential playback of synthesized sentence blocks."""
        while self.running:
            try:
                # Wait for synthesized speech chunks
                item = self.tts_queue.get(timeout=0.5)
                if self.is_muted:
                    self.tts_queue.task_done()
                    continue

                wav_bytes, text = item
                self.is_speaking = True
                self._update_state("speaking", f"Speaking: {text[:60]}…")
                self._update_caption("assistant", text)

                # Play WAV bytes using sounddevice
                try:
                    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
                        params = wav.getparams()
                        frames = wav.readframes(params.nframes)
                        audio_data = np.frombuffer(frames, dtype=np.int16)

                        # Play synchronously
                        sd.play(audio_data, params.framerate)

                        # Wait for sound to end or stop signal
                        while sd.get_stream().active and self.running and not self.is_muted:
                            time.sleep(0.05)

                        if self.is_muted or not self.running:
                            sd.stop()
                except Exception as e:
                    print(f"[VoiceLoop] Error playing speech: {e}")

                self.is_speaking = False
                self.tts_queue.task_done()
            except queue.Empty:
                continue

    # ─────────────────────────────────────────────────────────────
    #  Core voice loop state machine
    # ─────────────────────────────────────────────────────────────
    def _run_voice_loop(self):
        """
        Core voice loop:
          1. Wake Word Detection  (sleeping)
          2. Chime + transition
          3. VAD Capture          (listening)
          4. STT + LLM + TTS     (thinking → speaking)
          5. → back to 1
        """
        # Lazy-init the wake word detector in the loop thread
        self._update_state("sleeping", "Loading wake word model…")
        try:
            self._detector = WakeWordDetector(model_name="hey_jarvis", threshold=0.5)
            print("[VoiceLoop] Wake word detector loaded (ONNX).")
        except Exception as e:
            print(f"[VoiceLoop] Wake word init failed: {e}  — falling back to direct listening.")
            self._detector = None

        conversation = conversation_manager.get_or_create(self.session_id)

        while self.running:
            # ━━━ PHASE 1 — Wake Word Detection ━━━━━━━━━━━━━━━━━━
            if self._detector is not None:
                self._update_state("sleeping", "Waiting for \"Hey Jarvis\"…")
                self._update_volume(0.0)

                woke = self._wait_for_wake_word()
                if not woke:
                    # Loop was stopped
                    break

                # ── Trigger acknowledged — play chime ────────────
                self._play_chime()

            # ━━━ PHASE 2 — Active VAD Capture ━━━━━━━━━━━━━━━━━━
            self._update_state("listening", "Listening for your voice…")

            audio_buffer = []
            speaking = False
            silence_start_time = None
            speech_start_time = None

            # Simple queue to communicate audio chunks from stream callback to loop
            audio_queue = queue.Queue()

            def audio_callback(indata, frames, time_info, status):
                if status:
                    print(status, flush=True)
                audio_queue.put(indata.copy())

            # Start recording input stream
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                blocksize=self.block_size,
                callback=audio_callback,
                dtype="float32"
            )

            with stream:
                while self.running:
                    # Suspend listening while assistant is speaking
                    if self.is_speaking:
                        while not audio_queue.empty():
                            audio_queue.get_nowait()
                        time.sleep(0.1)
                        continue

                    try:
                        chunk = audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    # Calculate RMS volume energy
                    rms = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) > 0 else 0.0
                    self._update_volume(rms)

                    # VAD state machine
                    if not speaking:
                        if rms > self.silence_threshold:
                            speaking = True
                            speech_start_time = time.time()
                            audio_buffer.extend(chunk.flatten())
                            self._update_state("listening", "Hearing speech…")
                        else:
                            # If wake word mode and no speech detected for 8s, go back to sleep
                            if self._detector is not None:
                                if speech_start_time is None:
                                    speech_start_time = time.time()
                                if time.time() - speech_start_time >= 8.0:
                                    break  # timeout — return to wake word
                    else:
                        audio_buffer.extend(chunk.flatten())

                        # Check silence
                        if rms < self.silence_threshold:
                            if silence_start_time is None:
                                silence_start_time = time.time()
                            elif time.time() - silence_start_time >= self.silence_duration_limit:
                                # User stopped speaking!
                                break
                        else:
                            silence_start_time = None

                        # Check maximum recording timeout
                        if time.time() - speech_start_time >= self.max_recording_time:
                            break

            # If loop was stopped, exit
            if not self.running:
                break

            # Calculate actual speech length
            duration = len(audio_buffer) / self.sample_rate
            if duration < self.min_speech_duration or not audio_buffer:
                # Discard too short or empty clicks/noises — return to wake word
                time.sleep(0.2)
                continue

            # ━━━ PHASE 3 — Transcription ━━━━━━━━━━━━━━━━━━━━━━━
            self._update_state("thinking", "Transcribing…")
            self._update_volume(0.0)

            # Convert float32 array back to int16 for WAV compilation
            audio_array = np.array(audio_buffer)
            audio_int16 = np.clip(audio_array, -1.0, 1.0)
            audio_int16 = (audio_int16 * 32767).astype(np.int16)

            # Create standard WAV in memory
            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_int16.tobytes())

            # Save temporary WAV to disk for WhisperModel to parse
            temp_path = "temp_recording.wav"
            try:
                with open(temp_path, "wb") as f:
                    f.write(wav_io.getvalue())

                # Transcribe
                user_text = stt.transcribe(temp_path)
                os.remove(temp_path)
            except Exception as e:
                print(f"[VoiceLoop] Transcription failed: {e}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                continue

            if not user_text.strip():
                # Discard empty transcriptions
                continue

            # Show user transcription
            self._update_transcript("user", user_text)
            self._update_caption("user", user_text)
            self._update_state("thinking", "Thinking…")

            # ━━━ PHASE 4 — LLM Streaming + TTS ━━━━━━━━━━━━━━━━
            messages = conversation.add_user_message(user_text)

            full_response = []
            sentence_buffer = []

            # Simple list of punctuation to split sentences
            delimiters = {".", "?", "!", "\n"}

            def on_token(token):
                full_response.append(token)
                sentence_buffer.append(token)

                # Check if we completed a sentence
                current_block = "".join(sentence_buffer)
                if any(delim in token for delim in delimiters) and len(current_block.strip()) > 10:
                    # Clean and queue the completed sentence for neural TTS
                    sentence_text = current_block.strip()
                    sentence_buffer.clear()

                    # Live-update the BELLA caption with each sentence
                    self._update_caption("assistant", sentence_text)

                    if not self.is_muted:
                        try:
                            # Generate TTS bytes
                            wav_bytes = tts.synthesize(sentence_text)
                            self.tts_queue.put((wav_bytes, sentence_text))
                        except Exception as e:
                            print(f"[VoiceLoop] TTS synthesis error: {e}")

            # Define async runner to stream Ollama tokens
            async def run_stream():
                async for token in llm.chat_stream(messages):
                    on_token(token)

            try:
                # Execute async stream block synchronously in this loop thread
                asyncio.run(run_stream())
            except Exception as e:
                print(f"[VoiceLoop] LLM stream error: {e}")
                continue

            # Synthesize any leftover text in sentence buffer
            leftover_text = "".join(sentence_buffer).strip()
            if leftover_text and not self.is_muted:
                self._update_caption("assistant", leftover_text)
                try:
                    wav_bytes = tts.synthesize(leftover_text)
                    self.tts_queue.put((wav_bytes, leftover_text))
                except Exception as e:
                    print(f"[VoiceLoop] Leftover TTS error: {e}")

            # Add completed assistant response to session history
            complete_response_text = "".join(full_response)
            conversation.add_assistant_message(complete_response_text)
            self._update_transcript("assistant", complete_response_text)

            # Wait for all queued sentence speak playbacks to finish
            while not self.tts_queue.empty() or self.is_speaking:
                if not self.running:
                    break
                time.sleep(0.1)

            # Extra breathing space before going back to wake word
            time.sleep(0.5)

    # ─────────────────────────────────────────────────────────────
    #  Wake word detection sub-loop
    # ─────────────────────────────────────────────────────────────
    def _wait_for_wake_word(self) -> bool:
        """
        Block until the wake word is detected or self.running becomes False.

        Returns True if the wake word was detected, False if the loop was stopped.
        """
        audio_queue: queue.Queue = queue.Queue()

        def audio_callback(indata, frames, time_info, status):
            if status:
                print(status, flush=True)
            audio_queue.put(indata.copy())

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            blocksize=self.block_size,
            callback=audio_callback,
            dtype="float32"
        )

        with stream:
            while self.running:
                try:
                    chunk = audio_queue.get(timeout=0.3)
                except queue.Empty:
                    continue

                # Convert float32 [-1.0, 1.0] → int16 PCM bytes for openwakeword
                int16_data = np.clip(chunk.flatten(), -1.0, 1.0)
                int16_data = (int16_data * 32767).astype(np.int16)
                pcm_bytes = int16_data.tobytes()

                # Feed to wake word detector
                detected = self._detector.predict(pcm_bytes)
                if detected:
                    print("[VoiceLoop] Wake word detected!")
                    return True

        return False
