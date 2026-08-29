import json
import re
import sys
import threading
import subprocess
import tempfile
import os
from pathlib import Path
from typing import Callable

from agent.planner       import create_plan, replan
from agent.error_handler import analyze_error, generate_fix, ErrorDecision


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


def _run_generated_code(description: str, speak: Callable | None = None) -> str:
    from core.llm_provider import LLMProvider
    if speak:
        speak("Writing custom code for this task, sir.")

    home      = Path.home()
    desktop   = home / "Desktop"
    downloads = home / "Downloads"
    documents = home / "Documents"

    if not desktop.exists():
        try:
            import winreg
            key     = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
            desktop = Path(winreg.QueryValueEx(key, "Desktop")[0])
        except Exception:
            pass

    try:
        model = LLMProvider()
        prompt = f"Write a standalone Python script to accomplish: {description}\nReturn ONLY executable Python code."
        res = model.chat(prompt)
        code = res.get("content", "").strip()
        code = re.sub(r"```(?:python)?", "", code).strip().rstrip("`").strip()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        print(f"[Executor] 🐍 Running generated code: {tmp_path}")

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True, text=True,
            timeout=120, cwd=str(Path.home())
        )

        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        output = result.stdout.strip()
        error  = result.stderr.strip()

        if result.returncode == 0 and output:
            return output
        elif result.returncode == 0:
            return "Task completed successfully."
        elif error:
            raise RuntimeError(f"Code error: {error[:400]}")
        return "Completed."

    except subprocess.TimeoutExpired:
        raise RuntimeError("Generated code timed out after 120 seconds.")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Generated code failed: {e}")


def _translate_to_goal_language(text: str, goal: str) -> str:
    return text


def _inject_context(params: dict, tool: str, step_results: dict, goal: str = "") -> dict:
    if not step_results:
        return params

    params = dict(params)

    if tool == "file_controller" and params.get("action") in ("write", "create_file"):
        content = params.get("content", "")
        if not content or len(content) < 50:
            all_results = [
                v for v in step_results.values()
                if v and len(v) > 100 and v not in ("Done.", "Completed.")
            ]
            if all_results:
                combined = "\n\n---\n\n".join(all_results)
                translated = _translate_to_goal_language(combined, goal)
                params["content"] = translated
                print(f"[Executor] 💉 Injected + translated content")

    return params


class AgentExecutor:
    def __init__(self):
        pass

    def _execute_tool(self, tool: str, params: dict, speak: Callable | None = None) -> str:
        print(f"[Executor] Executing tool: {tool} args={params}")
        if tool == "web_search":
            from actions.web_search import web_search
            return web_search(parameters=params) or "Search completed."
        elif tool == "file_controller":
            from actions.file_controller import file_controller
            return file_controller(parameters=params) or "File action completed."
        elif tool == "open_app":
            from actions.open_app import open_app
            return open_app(parameters=params) or f"Opened {params.get('app_name')}."
        elif tool == "code_helper":
            from actions.code_helper import code_helper
            return code_helper(parameters=params, speak=speak) or "Code helper finished."
        elif tool == "computer_control":
            from actions.computer_control import computer_control
            return computer_control(parameters=params) or "Computer action completed."
        elif tool == "generated_code":
            return _run_generated_code(params.get("description", ""), speak=speak)
        else:
            return f"Tool '{tool}' executed with params {params}."

    def execute(
        self,
        goal: str,
        speak: Callable | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> str:
        print(f"[Executor] Starting execution for goal: {goal}")
        plan = create_plan(goal)
        steps = plan.get("steps", [])
        step_results = {}
        completed_steps = []

        for step in steps:
            if cancel_flag and cancel_flag.is_set():
                return "Task cancelled by user."

            step_id = step.get("step")
            tool = step.get("tool", "web_search")
            desc = step.get("description", "")
            params = _inject_context(step.get("parameters", {}), tool, step_results, goal)

            print(f"[Executor] Step {step_id}: [{tool}] {desc}")
            if speak:
                speak(f"Step {step_id}: {desc}")

            try:
                res = self._execute_tool(tool, params, speak=speak)
                step_results[step_id] = res
                completed_steps.append(step)
            except Exception as e:
                err_msg = str(e)
                print(f"[Executor] Step {step_id} failed: {err_msg}")
                decision_info = analyze_error(step, err_msg)
                decision = decision_info.get("decision", ErrorDecision.REPLAN)
                if decision == ErrorDecision.SKIP:
                    continue
                elif decision == ErrorDecision.ABORT:
                    raise RuntimeError(f"Task aborted at step {step_id}: {err_msg}")
                else:
                    fixed_step = generate_fix(step, err_msg, decision_info.get("fix_suggestion", ""))
                    res = self._execute_tool(
                        fixed_step.get("tool", "web_search"),
                        fixed_step.get("parameters", {}),
                        speak=speak,
                    )
                    step_results[step_id] = res
                    completed_steps.append(step)

        summary = f"Completed goal: {goal}"
        if speak:
            speak(summary)
        return summary
