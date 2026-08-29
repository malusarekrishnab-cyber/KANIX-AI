import threading
import json
import os
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types
from ui import kanixUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
    should_extract_memory, extract_memory
)

from core import stt as stt_module
from core import tts as tts_module
from core.system_features import ensure_single_instance

from actions.file_processor import file_processor
from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater
from actions.job_agent         import job_agent_action


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"

BRAIN_MODEL = "models/gemini-2.5-flash"


def _get_api_key() -> str:
    env_key = os.environ.get("GEMINI_API_KEY_1", "").strip()
    if env_key:
        return env_key
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("gemini_api_key", "")
    except Exception:
        return ""


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are KANIX, created by Krushna malusare. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

_last_memory_input = ""

def _update_memory_async(user_text: str, kanix_text: str) -> None:
    global _last_memory_input

    user_text  = (user_text  or "").strip()
    kanix_text = (kanix_text or "").strip()

    if len(user_text) < 5 or user_text == _last_memory_input:
        return
    _last_memory_input = user_text

    try:
        api_key = _get_api_key()
        if not api_key:
            return
        if not should_extract_memory(user_text, kanix_text, api_key):
            return
        data = extract_memory(user_text, kanix_text, api_key)
        if data:
            update_memory(data)
            print(f"[Memory] ✅ {list(data.keys())}")
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] ⚠️ {e}")


TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "Opens any application on the Windows computer.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {"type": "STRING", "description": "Exact name of application"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Search query"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders safely.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action"},
                "path": {"type": "STRING", "description": "Path"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "shutdown_kanix",
        "description": "Shuts down the assistant completely.",
        "parameters": {"type": "OBJECT", "properties": {}}
    }
]


class kanixLoop:
    def __init__(self, ui: kanixUI):
        self.ui     = ui
        api_key = _get_api_key() or "dummy_key_for_init"
        self.client = genai.Client(
            api_key=api_key,
            http_options={"api_version": "v1beta"}
        )
        self.chat = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
            self.ui.trigger_vrm_expression("speaking")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")
            self.ui.trigger_vrm_expression("listening")

    def speak(self, text: str, blocking: bool = True):
        if not text:
            return
        self.set_speaking(True)
        try:
            tts_module.speak(text, blocking=blocking)
        except Exception as e:
            print(f"[TTS] ⚠️ Kokoro speak failed: {e}")
        finally:
            self.set_speaking(False)

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.ui.trigger_vrm_expression("sad")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _build_system_instruction(self) -> str:
        from datetime import datetime
        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()
        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        return f"[DATE & TIME]\n{time_str}\n\n{mem_str}\n\n{sys_prompt}"

    def _start_chat(self):
        config = types.GenerateContentConfig(
            system_instruction=self._build_system_instruction(),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
        )
        self.chat = self.client.chats.create(model=BRAIN_MODEL, config=config)

    def _handle_user_text(self, user_text: str):
        if not user_text or not user_text.strip():
            return

        tts_module.stop_speech()
        cmd = user_text.lower().strip()

        # Live Mode Commands
        if "live mode" in cmd:
            if "exit" in cmd:
                self.ui._win.exit_live_mode()
                self.speak("Exiting live mode.")
                return
            else:
                self.ui._win.toggle_live_mode()
                self.speak("Entering live mode.")
                return

        # Expanded Voice Trigger Check for VRM Animations & Expressions
        if "hello" in cmd or "wave" in cmd or "say hello" in cmd:
            self.ui.trigger_vrm_animation("wave")
            self.ui.trigger_vrm_expression("happy")
        elif "spin" in cmd:
            self.ui.trigger_vrm_animation("spin")
        elif "dance" in cmd:
            self.ui.trigger_vrm_animation("dance")
            self.ui.trigger_vrm_expression("happy")
        elif "peace" in cmd:
            self.ui.trigger_vrm_animation("peace")
            self.ui.trigger_vrm_expression("happy")
        elif "squat" in cmd:
            self.ui.trigger_vrm_animation("squat")
        elif "pose" in cmd:
            self.ui.trigger_vrm_animation("pose")
        elif "stop animation" in cmd or "look at me" in cmd:
            self.ui.trigger_vrm_animation("idle")

        if "happy" in cmd:
            self.ui.trigger_vrm_expression("happy")
        elif "sad" in cmd:
            self.ui.trigger_vrm_expression("sad")
        elif "angry" in cmd:
            self.ui.trigger_vrm_expression("angry")
        elif "surprised" in cmd:
            self.ui.trigger_vrm_expression("surprised")

        if self.chat is None:
            self._start_chat()

        self.ui.write_log(f"You: {user_text}")
        self.ui.set_state("THINKING")
        self.ui.trigger_vrm_expression("thinking")

        try:
            response = self.chat.send_message(user_text)
            self.ui.trigger_vrm_expression("neutral")
        except Exception as e:
            print(f"[JARVIS] ❌ send_message: {e}")
            traceback.print_exc()
            self.speak_error("brain", e)
            return

        final_text = (getattr(response, "text", "") or "").strip()
        if final_text:
            self.ui.write_log(f"KANIX: {final_text}")
            self.speak(final_text)

    def _on_text_command(self, text: str):
        threading.Thread(target=self._handle_user_text, args=(text,), daemon=True).start()

    def run_turn(self):
        self.ui.set_state("LISTENING")
        self.ui.trigger_vrm_expression("listening")
        text = stt_module.listen_and_transcribe()
        if not text or not text.strip():
            return
        self._handle_user_text(text)

    def run_forever(self):
        if self.chat is None:
            self._start_chat()
        self.ui.set_state("LISTENING")
        self.ui.write_log("SYS: KANIX online (Whisper in / Kokoro out).")
        while True:
            try:
                if not self.ui.muted:
                    self.run_turn()
            except Exception as e:
                print(f"[JARVIS] ⚠️ {e}")
                traceback.print_exc()


def main():
    if not ensure_single_instance():
        print("[KANIX] Exiting because another instance is active.")
        sys.exit(0)

    ui = kanixUI("face.png")

    def runner():
        ui.wait_for_api_key()
        jarvis = kanixLoop(ui)
        try:
            jarvis.run_forever()
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()


if __name__ == "__main__":
    main()
