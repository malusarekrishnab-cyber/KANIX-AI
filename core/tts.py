"""
KANIX AI — TTS module (Kokoro, local, mode-independent)

This module is ALWAYS local — it does not check router.py's online/offline
state, because Kokoro runs on-device regardless of internet availability.
"""

import os
import sys

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np
import sounddevice as sd
from kokoro import KPipeline

VOICE = "af_nova"
LANG_CODE = "a"
SAMPLE_RATE = 24000
REPO_ID = "hexgrad/Kokoro-82M"

TARGET_PEAK = 0.95

_pipeline = None


def _get_pipeline() -> KPipeline:
    global _pipeline
    if _pipeline is None:
        try:
            _pipeline = KPipeline(lang_code=LANG_CODE, repo_id=REPO_ID)
        except Exception:
            os.environ["HF_HUB_OFFLINE"] = "0"
            _pipeline = KPipeline(lang_code=LANG_CODE, repo_id=REPO_ID)
            os.environ["HF_HUB_OFFLINE"] = "1"
    return _pipeline


def synthesize(text: str, voice: str = VOICE) -> np.ndarray:
    pipeline = _get_pipeline()
    float_chunks = []
    for _graphemes, _phonemes, audio in pipeline(text, voice=voice):
        float_chunks.append(np.asarray(audio, dtype=np.float32))

    if not float_chunks:
        return np.zeros(0, dtype=np.int16)

    full = np.concatenate(float_chunks)

    peak = float(np.max(np.abs(full))) if full.size else 0.0
    if peak > 1e-6:
        full = full * (TARGET_PEAK / peak)
    full = np.clip(full, -1.0, 1.0)

    return (full * 32767).astype(np.int16)


def stop_speech():
    """Interrupts any current TTS audio playback immediately."""
    try:
        sd.stop()
        print("[TTS] 🛑 Speech interrupted.")
    except Exception as e:
        print(f"[TTS] ⚠️ Error stopping speech: {e}")


def speak(text: str, voice: str = VOICE, blocking: bool = True) -> None:
    audio = synthesize(text, voice=voice)
    if audio.size == 0:
        print("[TTS] Kokoro returned no audio for this text.")
        return
    sd.play(audio, samplerate=SAMPLE_RATE)
    if blocking:
        sd.wait()


if __name__ == "__main__":
    test_text = sys.argv[1] if len(sys.argv) > 1 else (
        "Hello, this is Kanix speaking. Testing Kokoro text to speech."
    )
    print(f"[TTS] Synthesizing with voice='{VOICE}': {test_text!r}")
    speak(test_text)
    print("[TTS] Done. If you heard audio, Kokoro is working correctly.")
