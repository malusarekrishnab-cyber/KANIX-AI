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
                "query": {"type": "STRING", "description": "Search query"},
                "mode": {"type": "STRING", "description": "search or compare"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver": {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "Message text"},
                "platform": {"type": "STRING", "description": "Platform"}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date": {"type": "STRING", "description": "Date YYYY-MM-DD"},
                "time": {"type": "STRING", "description": "Time HH:MM"},
                "message": {"type": "STRING", "description": "Reminder text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": "Controls YouTube.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending"},
                "query": {"type": "STRING", "description": "Query"}
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": "Captures and analyzes the screen or webcam image.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' or 'camera'"},
                "text": {"type": "STRING", "description": "Question"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": "Controls computer settings.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action"},
                "description": {"type": "STRING", "description": "Description"},
                "value": {"type": "STRING", "description": "Value"}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": "Controls web browser.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action"},
                "url": {"type": "STRING", "description": "URL"},
                "query": {"type": "STRING", "description": "Query"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders.",
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
        "name": "desktop_control",
        "description": "Controls the desktop.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, or runs code.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action"},
                "description": {"type": "STRING", "description": "Description"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete projects.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description": {"type": "STRING", "description": "Description"}
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": "Executes complex multi-step tasks.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal": {"type": "STRING", "description": "Goal"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": "Game updater for Steam and Epic.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "Action"}
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin": {"type": "STRING", "description": "Origin"},
                "destination": {"type": "STRING", "description": "Destination"},
                "date": {"type": "STRING", "description": "Date"}
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "job_agent",
        "description": "Searches and applies to jobs adhering strictly to safety and eligibility rules.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "search | apply | list_applications"},
                "query": {"type": "STRING", "description": "Job title or query"},
                "otp_code": {"type": "STRING", "description": "OTP authorization code"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_processor",
        "description": "Processes uploaded or dropped files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "file_path": {"type": "STRING", "description": "File path"},
                "action": {"type": "STRING", "description": "Action"}
            },
            "required": []
        }
    },
    {
        "name": "shutdown_kanix",
        "description": "Shuts down the assistant completely.",
        "parameters": {"type": "OBJECT", "properties": {}}
    },
    {
        "name": "save_memory",
        "description": "Save personal facts to memory.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "STRING", "description": "Category"},
                "key": {"type": "STRING", "description": "Key"},
                "value": {"type": "STRING", "description": "Value"}
            },
            "required": ["category", "key", "value"]
        }
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

    def _execute_tool(self, name: str, args: dict) -> dict:
        print(f"[JARVIS] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return {"result": "ok", "silent": True}

        result = "Done."
        try:
            if name == "open_app":
                result = open_app(parameters=args, response=None, player=self.ui) or f"Opened {args.get('app_name')}."

            elif name == "weather_report":
                result = weather_action(parameters=args, player=self.ui) or "Weather delivered."

            elif name == "browser_control":
                result = browser_control(parameters=args, player=self.ui) or "Done."

            elif name == "file_controller":
                result = file_controller(parameters=args, player=self.ui) or "Done."

            elif name == "send_message":
                result = send_message(parameters=args, response=None, player=self.ui, session_memory=None) \
                    or f"Message sent to {args.get('receiver')}."

            elif name == "reminder":
                result = reminder(parameters=args, response=None, player=self.ui) or "Reminder set."

            elif name == "youtube_video":
                result = youtube_video(parameters=args, response=None, player=self.ui) or "Done."

            elif name == "file_processor":
                if not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                result = file_processor(parameters=args, player=self.ui, speak=self.speak) or "Done."

            elif name == "screen_process":
                threading.Thread(
                    target=screen_process,
                    kwargs={"parameters": args, "response": None,
                            "player": self.ui, "session_memory": None},
                    daemon=True
                ).start()
                result = "Vision module activated."

            elif name == "computer_settings":
                result = computer_settings(parameters=args, response=None, player=self.ui) or "Done."

            elif name == "desktop_control":
                result = desktop_control(parameters=args, player=self.ui) or "Done."

            elif name == "code_helper":
                result = code_helper(parameters=args, player=self.ui, speak=self.speak) or "Done."

            elif name == "dev_agent":
                result = dev_agent(parameters=args, player=self.ui, speak=self.speak) or "Done."

            elif name == "job_agent":
                result = job_agent_action(parameters=args) or "Done."

            elif name == "agent_task":
                from agent.task_queue import get_queue, TaskPriority
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                result   = f"Task started (ID: {task_id})."

            elif name == "web_search":
                result = web_search_action(parameters=args, player=self.ui) or "Done."

            elif name == "computer_control":
                result = computer_control(parameters=args, player=self.ui) or "Done."

            elif name == "game_updater":
                result = game_updater(parameters=args, player=self.ui, speak=self.speak) or "Done."

            elif name == "flight_finder":
                result = flight_finder(parameters=args, player=self.ui) or "Done."

            elif name == "shutdown_kanix":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir.")

                def _shutdown():
                    import time
                    time.sleep(1)
                    os._exit(0)

                threading.Thread(target=_shutdown, daemon=True).start()

            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[JARVIS] 📤 {name} → {str(result)[:80]}")
        return {"result": result}

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

        # Voice Trigger Check for VRM Animations & Expressions
        if "hello" in cmd or "wave" in cmd:
            self.ui.trigger_vrm_animation("wave")
            self.ui.trigger_vrm_expression("happy")
        elif "spin" in cmd:
            self.ui.trigger_vrm_animation("spin")
        elif "peace" in cmd:
            self.ui.trigger_vrm_animation("peace")
            self.ui.trigger_vrm_expression("happy")
        elif "squat" in cmd:
            self.ui.trigger_vrm_animation("squat")
        elif "pose" in cmd:
            self.ui.trigger_vrm_animation("pose")

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
