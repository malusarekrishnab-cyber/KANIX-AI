"""
KANIX AI — TTS module (Kokoro, local, mode-independent)

This module is ALWAYS local — it does not check router.py's online/offline
state, because Kokoro runs on-device regardless of internet availability.

Two things fixed here vs the first version:
  1. Speed  — huggingface_hub was doing a HEAD request to huggingface.co on
     EVERY speak() call to check for model updates, even though the model
     is already cached locally. That round-trip is what caused the delay.
     We set HF_HUB_OFFLINE once the model is confirmed cached, so it loads
     straight from disk with zero network calls.
  2. Volume — Kokoro's raw output amplitude is quiet by default. We now
     normalize each utterance to a target peak before converting to int16,
     instead of blindly multiplying by 32767.
"""

import os
import sys

# Must be set BEFORE importing kokoro / huggingface_hub, so the very first
# lookup in this process skips the network check. If the model has never
# been downloaded before, unset this (or delete the HF cache) and run once
# online first — after that this stays fast and fully offline.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np
import sounddevice as sd
from kokoro import KPipeline

# ---- config -----------------------------------------------------------
VOICE = "af_nova"        # fixed per build prompt
LANG_CODE = "a"          # 'a' = American English (af_nova is an 'a' voice)
SAMPLE_RATE = 24000       # Kokoro's native output rate; matches main.py
REPO_ID = "hexgrad/Kokoro-82M"

TARGET_PEAK = 0.95        # normalize each utterance so its loudest sample
                           # hits ~95% of full scale (fixes "voice is too quiet")

_pipeline = None


def _get_pipeline() -> KPipeline:
    global _pipeline
    if _pipeline is None:
        try:
            _pipeline = KPipeline(lang_code=LANG_CODE, repo_id=REPO_ID)
        except Exception:
            # First-ever run: nothing cached yet, HF_HUB_OFFLINE=1 would
            # block the initial download. Retry once with it off.
            os.environ["HF_HUB_OFFLINE"] = "0"
            _pipeline = KPipeline(lang_code=LANG_CODE, repo_id=REPO_ID)
            os.environ["HF_HUB_OFFLINE"] = "1"
    return _pipeline


def synthesize(text: str, voice: str = VOICE) -> np.ndarray:
    """
    Run Kokoro over `text` and return a single concatenated int16 mono
    numpy array at SAMPLE_RATE, normalized to TARGET_PEAK.
    """
    pipeline = _get_pipeline()
    float_chunks = []
    for _graphemes, _phonemes, audio in pipeline(text, voice=voice):
        float_chunks.append(np.asarray(audio, dtype=np.float32))

    if not float_chunks:
        return np.zeros(0, dtype=np.int16)

    full = np.concatenate(float_chunks)

    # Normalize: scale so the loudest sample hits TARGET_PEAK, instead of
    # assuming the raw output already uses the full [-1, 1] range.
    peak = float(np.max(np.abs(full))) if full.size else 0.0
    if peak > 1e-6:
        full = full * (TARGET_PEAK / peak)
    full = np.clip(full, -1.0, 1.0)

    return (full * 32767).astype(np.int16)


def speak(text: str, voice: str = VOICE, blocking: bool = True) -> None:
    """
    Synthesize `text` and play it out loud on the default output device.
    """
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