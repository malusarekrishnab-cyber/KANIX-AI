"""
KANIX AI — Phase 3: STT module (faster-whisper, local, offline path)

Standalone: mic record -> faster-whisper transcribe -> text return.
Used in offline mode (Gemini Live is online-only, so offline needs its
own discrete record->STT->text step instead of streaming raw audio).

Not yet wired into main.py — connection happens after Phase 4 (TTS),
once the full loop exists: mic -> stt.py -> router (main AI) ->
response -> tts.py (Kokoro) -> speaker.
"""

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

# ---- config -------------------------------------------------------------
SAMPLE_RATE = 16000        # matches SEND_SAMPLE_RATE already used in main.py
CHANNELS = 1
MODEL_SIZE = "small"       # base struggles on Hinglish/Marathi-mixed speech;
                            # medium+ is too slow on CPU. Change this one
                            # line if you need to tune the tradeoff.
SILENCE_THRESHOLD = 500     # RMS-ish cutoff below which we treat audio as silence
SILENCE_DURATION = 1.5      # seconds of silence that ends recording
MAX_DURATION = 15           # hard cap so it never records forever

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


def transcribe(audio: np.ndarray) -> str:
    """Run faster-whisper over an int16 mono numpy array, return text."""
    if audio.size == 0:
        return ""
    model = _get_model()
    audio_float = audio.astype(np.float32) / 32768.0
    segments, _info = model.transcribe(audio_float, language=None)
    return " ".join(seg.text.strip() for seg in segments).strip()


def listen_and_transcribe() -> str:
    """Convenience wrapper: record until silence, then transcribe."""
    audio = record_until_silence()
    return transcribe(audio)


if __name__ == "__main__":
    print("[STT] speak now (recording stops after ~1.5s of silence)...")
    text = listen_and_transcribe()
    print(f"[STT] Transcribed: {text!r}")
