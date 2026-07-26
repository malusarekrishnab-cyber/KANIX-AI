"""
KANIX AI — Phase 4: TTS module (Kokoro, local, mode-independent)

This module is ALWAYS local — it does not check router.py's online/offline
state, because Kokoro runs on-device regardless of internet availability.
That "mode shouldn't matter" assumption from the build prompt is verified
by the __main__ test block below (run it once with wifi on, once with
wifi off — output must sound identical).

Output format matches main.py's existing playback stream exactly, so this
can later be dropped into _play_audio() with zero resampling:
    - sample rate : 24000 Hz   (== RECEIVE_SAMPLE_RATE in main.py)
    - channels    : 1 (mono)   (== CHANNELS in main.py)
    - dtype       : int16      (== sd.RawOutputStream dtype in main.py)

Not yet wired into main.py — that happens after the full loop
(mic -> stt.py -> router -> AI response -> tts.py -> speaker) is built,
per the plan.
"""

import sys
import numpy as np
import sounddevice as sd
from kokoro import KPipeline

# ---- config -----------------------------------------------------------
VOICE = "af_nova"        # fixed per build prompt
LANG_CODE = "a"          # 'a' = American English (af_nova is an 'a' voice)
SAMPLE_RATE = 24000       # Kokoro's native output rate; matches main.py

# KPipeline is somewhat heavy to init (loads model weights), so we build
# it once and reuse it across calls instead of per-utterance.
_pipeline = None


def _get_pipeline() -> KPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = KPipeline(lang_code=LANG_CODE)
    return _pipeline


def synthesize(text: str, voice: str = VOICE) -> np.ndarray:
    """
    Run Kokoro over `text` and return a single concatenated int16 mono
    numpy array at SAMPLE_RATE. Does not play anything — pure synthesis,
    so main.py can later push the array straight into its existing
    audio_in_queue instead of calling sd.play directly.
    """
    pipeline = _get_pipeline()
    chunks = []
    for _graphemes, _phonemes, audio in pipeline(text, voice=voice):
        # Kokoro yields float32 audio in [-1, 1]; convert to int16 to match
        # main.py's RawOutputStream(dtype="int16") playback format.
        chunk = np.asarray(audio, dtype=np.float32)
        chunk = np.clip(chunk, -1.0, 1.0)
        chunks.append((chunk * 32767).astype(np.int16))

    if not chunks:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate(chunks)


def speak(text: str, voice: str = VOICE, blocking: bool = True) -> None:
    """
    Synthesize `text` and play it out loud on the default output device.
    Standalone helper for testing this module before it's wired into
    main.py's playback queue.
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
