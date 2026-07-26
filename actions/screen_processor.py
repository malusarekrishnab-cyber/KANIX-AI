import io
import os
import sys
import time
import cv2
import mss
import mss.tools
import numpy as np
from pathlib import Path

try:
    import PIL.Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

from paddleocr import PaddleOCR
from core.llm_provider import LLMProvider

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
IMG_MAX_W = 1024
IMG_MAX_H = 1024
JPEG_Q = 80

# Initialize PaddleOCR globally to save loading time
_ocr_engine = None
def get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
    return _ocr_engine

def _to_jpeg_path(img_bytes: bytes, filename="temp_screen.jpg") -> str:
    path = str(BASE_DIR / filename)
    if not _PIL_OK:
        with open(path, "wb") as f:
            f.write(img_bytes)
        return path
        
    img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img.thumbnail([IMG_MAX_W, IMG_MAX_H], PIL.Image.BILINEAR)
    img.save(path, format="JPEG", quality=JPEG_Q, optimize=False)
    return path

def _capture_screenshot() -> bytes:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        png_bytes = mss.tools.to_png(shot.rgb, shot.size)
    return png_bytes

def _capture_camera() -> bytes:
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError("Camera could not be opened at index 0")
    for _ in range(10):
        cap.read()
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise RuntimeError("Could not capture camera frame.")
        
    if _PIL_OK:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(rgb)
        img.thumbnail([IMG_MAX_W, IMG_MAX_H], PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_Q, optimize=False)
        return buf.getvalue()
        
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_Q])
    return buf.tobytes()

def screen_process(
    parameters: dict,
    response: str | None = None,
    player=None,
    session_memory=None,
) -> str:
    """
    Captures the screen or camera, analyzes it, and returns text.
    Modes:
    - default: Uses Qwen2.5-VL to answer a question about the image.
    - read: Uses PaddleOCR to extract text.
    """
    user_text = (parameters or {}).get("text", "Describe what is on the screen briefly.")
    angle = (parameters or {}).get("angle", "screen").lower().strip()
    mode = (parameters or {}).get("mode", "default").lower().strip()
    
    print(f"[ScreenProcess] angle={angle!r} text={user_text!r} mode={mode!r}")

    try:
        if angle == "camera":
            image_bytes = _capture_camera()
            print("[ScreenProcess] 📷 Camera captured")
        else:
            image_bytes = _capture_screenshot()
            print("[ScreenProcess] 🖥️ Screen captured")
    except Exception as e:
        import traceback; traceback.print_exc()
        err = f"[ScreenProcess] ❌ Capture error: {e}"
        print(err)
        return err

    # Save to temp file for Ollama / OCR
    temp_path = _to_jpeg_path(image_bytes)

    if mode == "read":
        # Use PaddleOCR
        try:
            ocr = get_ocr()
            result = ocr.ocr(temp_path, cls=True)
            text_lines = []
            if result and result[0]:
                for line in result[0]:
                    text_lines.append(line[1][0])
            out = " ".join(text_lines)
            return out if out else "No text found on screen."
        except Exception as e:
            return f"OCR Error: {e}"
    else:
        # Use Qwen2.5-VL via LLMProvider
        llm = LLMProvider()
        system_prompt = "You are an AI assistant. Analyze the image and respond concisely."
        ans = llm.chat_vision(prompt=user_text, image_path=temp_path, system=system_prompt)
        return ans

if __name__ == "__main__":
    print("[TEST] screen_processor.py")
    res = screen_process({"angle": "screen", "text": "What do you see?"})
    print("Vision Output:", res)
