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
- `actions/file_controller.py`
- `actions/code_helper.py`
- `core/tts.py`
- `requirements.txt`

---

## Status Matrix

| Subsystem / Feature | Status | Notes |
| :--- | :--- | :--- |
| **APPLICATION STARTUP** | **PASS** | `python main.py` launches cleanly without errors. |
| **VRM 3D AVATAR** | **PASS** | Real 3D VRM model loaded via GLTFLoader / WebGL in `QWebEngineView`. |
| **VRM DASHBOARD** | **PASS** | VRM avatar rendered centered inside circular HUD container. |
| **VRMA ANIMATIONS** | **PASS** | Animations (`idle`, `hello`, `wave`, `spin`, `dance`, `pose`, `squat`, `peace`) supported. |
| **EXPRESSIONS** | **PASS** | Expressions (`neutral`, `happy`, `sad`, `angry`, `surprised`, `thinking`, `listening`, `speaking`) connected. |
| **LIP SYNC** | **PASS** | Real-time viseme blendshape movement driven during TTS playback. |
| **LIVE MODE 2.0** | **PASS** | Fullscreen cinematic view with animated background particles, cyan glow, and enlarged 3D VRM avatar. |
| **SCREEN VISION** | **PASS** | Lazy-loaded; setting `SCREEN_VISION_ENABLED=false` does not block startup. |
| **WAKE WORD** | **PASS** | "Hey Kanix" wake word handling intact. |
| **VAD** | **PASS** | Voice Activity Detection in `core/vad.py` preserved. |
| **STT** | **PASS** | Dual-path Groq Whisper (online) / local `faster-whisper` (offline). |
| **TTS** | **PASS** | Kokoro ONNX TTS (`af_nova`) with instant audio interruption. |
| **FILE CONTROL CENTER**| **PASS** | Permission levels (SAFE, CONFIRM, DANGEROUS), path safety, backups, and syntax validation. |
| **JOB AGENT** | **PASS** | Eligibility rules, duplicate check, `JOB_MIN_MATCH_SCORE`, `AUTO_APPLY_ALL_ELIGIBLE`, OTP safety, tracker. |
| **EXISTING AGENTS** | **PASS** | Coding, Research, Memory, System agents, Task Queue intact. |
| **SYSTEM TRAY** | **PASS** | `QSystemTrayIcon` menu with Show, Live Mode, Mute, Exit actions. |
| **SINGLE INSTANCE** | **PASS** | Socket lock on port 49152 prevents duplicate instances. |
| **AUTO START** | **PASS** | Windows Registry startup helper in `core/system_features.py`. |

---

## FEATURE EXPANSION (PHASE 2)

### 1. 3D VRM Mouse Look-At & Breathing
- **Implementation:** Added cursor tracking interpolation, procedural breathing scaling, and automatic blinking to `assets/vrm_viewer.html`.
- **Files Changed:** `assets/vrm_viewer.html`
- **Runtime Connection:** Connected to mouse move events in WebGL canvas.
- **Test Performed:** Verified in Playwright video/screenshot recording.
- **Result:** **PASS**

### 2. Expanded Voice & Behavior Avatar Controls
- **Implementation:** Added voice commands ("dance", "say hello", "stop animation", "look at me") and conversational state bindings.
- **Files Changed:** `main.py`, `ui.py`
- **Runtime Connection:** Integrated into `kanixLoop._handle_user_text()`.
- **Test Performed:** Verified via command invocation tests.
- **Result:** **PASS**

### 3. Live Mode 2.0
- **Implementation:** Added 120-point particle background system, camera zoom transition, andLive Mode status badge.
- **Files Changed:** `assets/vrm_viewer.html`, `ui.py`
- **Runtime Connection:** Triggered via ESC key or "live mode" voice command.
- **Test Performed:** Verified via Playwright screenshot recording (`/home/jules/verification/screenshots/vrm_live_mode.png`).
- **Result:** **PASS**

### 4. File Control Center with Permission Levels & Path Safety
- **Implementation:** Added permission levels (SAFE, CONFIRM, DANGEROUS), `ALLOWED_ROOTS` traversal safety, `.bak` backup creation, and `py_compile` post-edit syntax checks.
- **Files Changed:** `actions/file_controller.py`
- **Runtime Connection:** Used by `file_controller` tool declarations and agent execution.
- **Test Performed:** Tested create, edit, backup, and delete operations.
- **Result:** **PASS**

### 5. Coding Agent & Smart Error Recovery
- **Implementation:** Enhanced `actions/code_helper.py`, `agent/executor.py`, and `agent/error_handler.py` with targeted edits, exception capturing, and provider fallback logging.
- **Files Changed:** `actions/code_helper.py`, `agent/executor.py`, `agent/error_handler.py`
- **Runtime Connection:** Used for code generation, execution, and error recovery.
- **Test Performed:** Verified unit compilation and plan step execution.
- **Result:** **PASS**

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
