"""
tools/voice_input.py - Silent Background Wake Word ("Friday") Engine (Alexa/Siri style)
"""

import os
import sys
import time
import wave
import tempfile
import threading
import re
from pathlib import Path

from core.logger import logger

# Global daemon state & singleton Whisper model
_voice_thread = None
_stop_event = threading.Event()
_is_active = False
_whisper_model = None
_whisper_lock = threading.Lock()

WAKE_WORD = "friday"
DEFAULT_WHISPER_MODEL = "base.en"
ENERGY_THRESHOLD = 250  # RMS threshold below which audio is considered silence


def _get_whisper_model():
    """Lazy-loads the local faster-whisper INT8 model."""
    global _whisper_model
    if _whisper_model is None:
        with _whisper_lock:
            if _whisper_model is None:
                try:
                    from faster_whisper import WhisperModel
                    logger.info(f"Loading local Whisper model '{DEFAULT_WHISPER_MODEL}' (cpu, int8)...")
                    _whisper_model = WhisperModel(
                        DEFAULT_WHISPER_MODEL,
                        device="cpu",
                        compute_type="int8"
                    )
                    logger.info("Local Whisper model loaded successfully.")
                except Exception as e:
                    logger.error(f"Failed to load faster-whisper model: {e}")
                    raise
    return _whisper_model


def is_voice_active() -> bool:
    """Returns whether the background voice daemon is running."""
    global _is_active
    return _is_active and _voice_thread is not None and _voice_thread.is_alive()


NOISE_HALLUCINATIONS = {
    ".", "...", ",", "?", "!", "[blank_audio]", "(music)", "thank you.",
    "subtitles by", "amara.org", "thanks for watching", "you", "the", "bye", "uh", "um"
}


def is_valid_transcript(text: str) -> bool:
    """Returns True ONLY if transcript is genuine user speech and not noise/punctuation artifacts."""
    if not text:
        return False
    clean = text.strip().lower()
    clean_no_punc = re.sub(r"[^\w\s]", "", clean).strip()
    if not clean_no_punc or len(clean_no_punc) < 2:
        return False
    if clean in NOISE_HALLUCINATIONS or clean_no_punc in NOISE_HALLUCINATIONS:
        return False
    return True


def check_is_speech(audio_data) -> bool:
    """Bulletproof speech detector that works regardless of whether driver outputs int16 or float32."""
    import numpy as np
    abs_data = np.abs(audio_data.astype(np.float32))
    max_amp = np.max(abs_data) if len(abs_data) > 0 else 0
    rms = np.sqrt(np.mean(abs_data ** 2)) if len(abs_data) > 0 else 0
    if max_amp <= 1.5:
        return rms > 0.005 or max_amp > 0.03
    else:
        return rms > 150 or max_amp > 500


def get_active_microphone_device():
    """
    Scans input devices and selects the active physical microphone index,
    filtering out dead virtual software audio cables like SteelSeries Sonar or Voicemod.
    """
    import sounddevice as sd
    import numpy as np

    VIRTUAL_KEYWORDS = ["sonar", "voicemod", "droidcam", "iriun", "virtual", "mapper", "stereo mix", "stream", "midi"]
    
    try:
        devices = sd.query_devices()
        candidates = []
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                name = dev.get("name", "").lower()
                if not any(v in name for v in VIRTUAL_KEYWORDS):
                    candidates.append(idx)

        # Test physical candidates for live audio signal
        best_device = None
        max_signal = -1.0

        for idx in candidates[:6]:
            try:
                rec = sd.rec(int(0.15 * 16000), samplerate=16000, channels=1, dtype='float32', device=idx)
                sd.wait()
                amp = float(np.max(np.abs(rec)))
                if amp > max_signal:
                    max_signal = amp
                    best_device = idx
            except Exception:
                continue

        if best_device is not None:
            return best_device
        if candidates:
            return candidates[0]
    except Exception as e:
        logger.debug(f"Error selecting microphone device: {e}")
    return None


def record_speech_audio(duration: float = 3.5, sample_rate: int = 16000) -> str:
    """
    Silently records audio from active physical microphone using sounddevice.
    Returns path to WAV file if speech detected (via adaptive check_is_speech), or None if silence.
    """
    import sounddevice as sd
    import numpy as np

    try:
        device_idx = get_active_microphone_device()
        recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16', device=device_idx)
        sd.wait()

        # Silence check using adaptive speech detector
        if not check_is_speech(recording.flatten()):
            return None

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            wav_path = tmp_file.name
            with wave.open(wav_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit PCM
                wf.setframerate(sample_rate)
                wf.writeframes(recording.tobytes())
            return wav_path
    except Exception as e:
        logger.debug(f"Audio recording error: {e}")
        return None




def listen_once(timeout: float = 3.5) -> str:
    """
    Records speech audio silently and transcribes instantly via Groq Whisper.
    Returns clean transcript string or empty string.
    """
    temp_wav_path = None
    try:
        temp_wav_path = record_speech_audio(duration=timeout)
        if not temp_wav_path:
            return ""

        # 1. Fast Groq Whisper API (sub-second STT)
        from llm.router import LLMRouter
        router = LLMRouter()
        raw_transcript = router.transcribe_audio(temp_wav_path)
        if raw_transcript and is_valid_transcript(raw_transcript):
            logger.debug(f"Speech Transcribed (Groq Whisper): '{raw_transcript}'")
            return raw_transcript.strip()

        # If silence or invalid transcript, return "" instantly without blocking
        return ""

    except Exception as e:
        logger.debug(f"Error during voice transcription: {e}")
    finally:
        if temp_wav_path and os.path.exists(temp_wav_path):
            try:
                os.unlink(temp_wav_path)
            except Exception:
                pass
    return ""



def _voice_daemon_loop(callback=None):
    """
    Background worker loop: works silently like Alexa/Siri.
    Only triggers callback when wake word 'Friday' is explicitly spoken.
    """
    global _is_active
    logger.info("🎙️ Silent Voice Daemon started. Listening for wake word 'Friday'...")

    while not _stop_event.is_set():
        try:
            transcript = listen_once(timeout=3.5)
            if not transcript or _stop_event.is_set():
                continue

            lower_txt = transcript.lower()

            # Strict Alexa/Siri Wake Word Check: Must contain 'friday'
            if WAKE_WORD in lower_txt:
                # Extract command after wake word if user said "Friday open Spotify"
                match = re.search(r"\bfriday\b\s*(.*)", lower_txt, re.IGNORECASE)
                command = match.group(1).strip() if match else ""

                print(f"\n[bold cyan]🎙️ Wake word detected ('Friday')![/bold cyan]")

                if not command or not is_valid_transcript(command):
                    # User only said "Friday", listen for immediate command
                    print("[bold yellow]🗣️ Friday is listening for your command...[/bold yellow]")
                    command = listen_once(timeout=5.0)

                if command and is_valid_transcript(command):
                    print(f"[bold yellow]🗣️ Heard Command:[/bold yellow] {command}")
                    if callback and callable(callback):
                        try:
                            callback(command)
                        except Exception as cb_err:
                            logger.error(f"Error executing voice callback: {cb_err}")

        except Exception as err:
            logger.error(f"Error in voice daemon loop: {err}")
            time.sleep(1)

    _is_active = False
    logger.info("Voice daemon thread terminated cleanly.")


def start_voice_daemon(callback=None) -> bool:
    """
    Starts background thread silently listening for wake word "Friday".
    Returns True if started successfully, False otherwise.
    """
    global _voice_thread, _stop_event, _is_active

    if is_voice_active():
        logger.info("Voice daemon is already active.")
        return True

    _stop_event.clear()
    _is_active = True

    _voice_thread = threading.Thread(
        target=_voice_daemon_loop,
        kwargs={"callback": callback},
        daemon=True,
        name="FridayVoiceDaemon"
    )
    _voice_thread.start()
    return True


def stop_voice_daemon() -> bool:
    """Stops the background voice daemon thread."""
    global _stop_event, _is_active
    _stop_event.set()
    _is_active = False
    logger.info("Voice daemon stop requested.")
    return True

