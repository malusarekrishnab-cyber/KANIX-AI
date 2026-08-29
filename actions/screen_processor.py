import io
import os
import sys
import time
from pathlib import Path

def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
IMG_MAX_W = 1024
IMG_MAX_H = 1024
JPEG_Q = 80

_ocr_engine = None

def get_ocr():
    """Lazy loads PaddleOCR only when explicitly invoked."""
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from paddleocr import PaddleOCR
            _ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        except Exception as e:
            print(f"[ScreenProcessor] ⚠️ PaddleOCR import/initialization failed: {e}")
            return None
    return _ocr_engine

def _to_jpeg_path(img_bytes: bytes, filename="temp_screen.jpg") -> str:
    path = str(BASE_DIR / filename)
    try:
        import PIL.Image
        img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img.thumbnail([IMG_MAX_W, IMG_MAX_H], PIL.Image.BILINEAR)
        img.save(path, format="JPEG", quality=JPEG_Q, optimize=False)
        return path
    except Exception:
        with open(path, "wb") as f:
            f.write(img_bytes)
        return path

def _capture_screenshot() -> bytes:
    import mss
    import mss.tools
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        png_bytes = mss.tools.to_png(shot.rgb, shot.size)
    return png_bytes

def _capture_camera() -> bytes:
    import cv2
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY)
    if not cap.isOpened():
        raise RuntimeError("Camera could not be opened at index 0")
    for _ in range(5):
        cap.read()
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise RuntimeError("Could not capture camera frame.")
        
    try:
        import PIL.Image
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(rgb)
        img.thumbnail([IMG_MAX_W, IMG_MAX_H], PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_Q, optimize=False)
        return buf.getvalue()
    except Exception:
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
    Lazy loads vision dependencies and respects SCREEN_VISION_ENABLED.
    """
    if os.environ.get("SCREEN_VISION_ENABLED", "true").lower() == "false":
        return "Screen Vision is currently disabled."

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
        err = f"[ScreenProcess] ❌ Capture error: {e}"
        print(err)
        return err

    temp_path = _to_jpeg_path(image_bytes)

    if mode == "read":
        try:
            ocr = get_ocr()
            if ocr is None:
                return "OCR is unavailable on this system."
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
        try:
            from core.llm_provider import LLMProvider
            llm = LLMProvider()
            system_prompt = "You are an AI assistant. Analyze the image and respond concisely."
            ans = llm.chat_vision(prompt=user_text, image_path=temp_path, system=system_prompt)
            return ans
        except Exception as e:
            return f"Vision Error: {e}"

if __name__ == "__main__":
    print("[TEST] screen_processor.py")
    res = screen_process({"angle": "screen", "text": "What do you see?"})
    print("Vision Output:", res)
