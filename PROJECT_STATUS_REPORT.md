# KANIX AI — PROJECT STATUS REPORT

## Architecture Overview
KANIX AI is a local desktop AI assistant built using Python 3.12, PyQt6, and Three.js WebGL rendering.

- **Main Application Entry Point:** `main.py` (`python main.py`)
- **UI Architecture:** PyQt6 `MainWindow` with `QStackedLayout`, HUD Canvas, and `QWebEngineView` rendering `assets/vrm_viewer.html` via a local asset HTTP server on `127.0.0.1:8888`.
- **3D VRM Model:** `assets/models/kanix_avatar.vrm` loaded via GLTFLoader/VRM loader in Three.js WebGL canvas.
- **AI Core / Router:** Multi-tier provider fallback in `core/router.py` & `core/llm_provider.py` (Gemini 2.5 Flash -> Groq -> Ollama local).
- **Speech-to-Text (STT):** Groq Whisper (online) / local `faster-whisper` (offline) in `core/stt.py`.
- **Text-to-Speech (TTS):** Kokoro ONNX TTS (`af_nova` voice) in `core/tts.py` with instant audio interruption via `stop_speech()`.
- **Agents:** Coding Agent, Research Agent, Memory Agent, System Agent, Task Queue, Job Agent (`actions/job_agent.py`).
- **Screen Vision:** `actions/screen_processor.py` with lazy-loading so setting `SCREEN_VISION_ENABLED=false` or missing dependencies never blocks startup.
- **System Features:** Single Instance socket lock (`core/system_features.py`), System Tray menu, Windows Auto-Start helper.

---

## Files Modified & Created

### Files Created:
- `assets/models/kanix_avatar.vrm`
- `assets/vrm_viewer.html`
- `ui/vrm_widget.py`
- `actions/job_agent.py`
- `core/system_features.py`
- `tests/test_kanix_e2e.py`
- `PROJECT_STATUS_REPORT.md`

### Files Modified:
- `main.py`
- `ui.py`
- `agent/planner.py`
- `agent/executor.py`
- `agent/error_handler.py`
- `actions/screen_processor.py`
- `core/tts.py`
- `requirements.txt`

---

## Status Matrix

| Subsystem / Feature | Status | Notes |
| :--- | :--- | :--- |
| **APPLICATION STARTUP** | **PASS** | `python main.py` launches cleanly without errors. |
| **VRM 3D AVATAR** | **PASS** | Real 3D VRM model loaded via GLTFLoader / WebGL in `QWebEngineView`. |
| **VRM DASHBOARD** | **PASS** | VRM avatar rendered centered inside circular HUD container. |
| **VRMA ANIMATIONS** | **PASS** | Animations (`idle`, `hello`, `wave`, `spin`, `pose`, `squat`, `peace`) supported. |
| **EXPRESSIONS** | **PASS** | Expressions (`neutral`, `happy`, `sad`, `angry`, `surprised`, `thinking`, `listening`, `speaking`) connected. |
| **LIP SYNC** | **PASS** | Real-time viseme blendshape movement driven during TTS playback. |
| **LIVE MODE** | **PASS** | Fullscreen cinematic dark blue view with cyan glow and enlarged 3D VRM avatar; ESC / voice toggle. |
| **SCREEN VISION** | **PASS** | Lazy-loaded; setting `SCREEN_VISION_ENABLED=false` does not block startup. |
| **WAKE WORD** | **PASS** | "Hey Kanix" wake word handling intact. |
| **VAD** | **PASS** | Voice Activity Detection in `core/vad.py` preserved. |
| **STT** | **PASS** | Dual-path Groq Whisper (online) / local `faster-whisper` (offline). |
| **TTS** | **PASS** | Kokoro ONNX TTS (`af_nova`) with instant audio interruption. |
| **JOB AGENT** | **PASS** | Eligibility rules, duplicate check, `JOB_MIN_MATCH_SCORE`, `AUTO_APPLY_ALL_ELIGIBLE`, OTP safety, tracker. |
| **EXISTING AGENTS** | **PASS** | Coding, Research, Memory, System agents, Task Queue intact. |
| **SYSTEM TRAY** | **PASS** | `QSystemTrayIcon` menu with Show, Live Mode, Mute, Exit actions. |
| **SINGLE INSTANCE** | **PASS** | Socket lock on port 49152 prevents duplicate instances. |
| **AUTO START** | **PASS** | Windows Registry startup helper in `core/system_features.py`. |

---

## Dependencies
- `PyQt6`
- `PyQt6-WebEngine`
- `google-genai`
- `google-generativeai`
- `requests`
- `psutil`
- `python-dotenv`
- `ollama`
- `faster-whisper`
- `kokoro>=0.9.4`
