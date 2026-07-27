"""
KANIX AI — STT module: dual path (Groq Whisper online, faster-whisper offline)

Flow: mic record -> (online? Groq Whisper key : local faster-whisper) -> text
Both paths return a plain string, so nothing downstream needs to know which
engine produced it (main.py just calls listen_and_transcribe()).
"""

import io
import os
import wave

import numpy as np
import requests
import sounddevice as sd
from faster_whisper import WhisperModel

from core.internet import is_online

# ---- config -------------------------------------------------------------
SAMPLE_RATE = 16000        # matches SEND_SAMPLE_RATE already used in main.py
CHANNELS = 1
MODEL_SIZE = "small"       # base struggles on Hinglish/Marathi-mixed speech;
                            # medium+ is too slow on CPU. Change this one
                            # line if you need to tune the tradeoff.
SILENCE_THRESHOLD = 500     # RMS-ish cutoff below which we treat audio as silence
SILENCE_DURATION = 1.5      # seconds of silence that ends recording
MAX_DURATION = 15           # hard cap so it never records forever

# Reserved specifically for Whisper STT (never used for the brain/LLM key —
# that's GROQ_LLM_API_KEY, see core/llm_provider.py).
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_STT_MODEL = "whisper-large-v3-turbo"  # check Groq's current model list if this 404s

_model = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        # compute_type="int8" keeps it CPU-friendly
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def record_until_silence() -> np.ndarray:
    """Record from the default mic until the user stops speaking."""
    block_duration = 0.25
    block_size = int(SAMPLE_RATE * block_duration)
    silence_blocks_needed = int(SILENCE_DURATION / block_duration)
    max_blocks = int(MAX_DURATION / block_duration)

    frames = []
    silent_run = 0
    started_speaking = False

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=block_size,
    ) as stream:
        for _ in range(max_blocks):
            block, _ = stream.read(block_size)
            frames.append(block.copy())

            rms = np.sqrt(np.mean(block.astype(np.float32) ** 2))
            if rms > SILENCE_THRESHOLD:
                started_speaking = True
                silent_run = 0
            elif started_speaking:
                silent_run += 1
                if silent_run >= silence_blocks_needed:
                    break

    if not frames:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate(frames).flatten()


def _audio_to_wav_bytes(audio: np.ndarray) -> bytes:
    """Pack an int16 mono numpy array into an in-memory WAV file (no temp file)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


def _transcribe_offline(audio: np.ndarray) -> str:
    """Local faster-whisper path — always available, no internet needed."""
    if audio.size == 0:
        return ""
    model = _get_model()
    audio_float = audio.astype(np.float32) / 32768.0
    segments, _info = model.transcribe(audio_float, language=None)
    return " ".join(seg.text.strip() for seg in segments).strip()


def _transcribe_online_groq(audio: np.ndarray) -> str:
    """Groq Whisper path — used when online and GROQ_API_KEY is set."""
    wav_bytes = _audio_to_wav_bytes(audio)
    files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
    data = {"model": GROQ_STT_MODEL}
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    resp = requests.post(GROQ_STT_URL, headers=headers, data=data, files=files, timeout=30)
    resp.raise_for_status()
    return (resp.json().get("text") or "").strip()


def transcribe(audio: np.ndarray) -> str:
    """
    Public entry point used by both the manual test below and any code
    that already has recorded audio in hand. Picks online/offline path.
    """
    if audio.size == 0:
        return ""

    if GROQ_API_KEY and is_online():
        try:
            return _transcribe_online_groq(audio)
        except Exception as e:
            print(f"[STT] ⚠️ Groq Whisper failed ({e}), falling back to local faster-whisper.")

    return _transcribe_offline(audio)


def listen_and_transcribe() -> str:
    """Convenience wrapper: record until silence, then transcribe (online or offline)."""
    audio = record_until_silence()
    return transcribe(audio)


if __name__ == "__main__":
    print("[STT] speak now (recording stops after ~1.5s of silence)...")
    text = listen_and_transcribe()
    print(f"[STT] Transcribed: {text!r}")