"""
core/llm_provider.py

Central LLM entry point used by every action/agent file in this repo
(code_helper, file_processor, screen_processor, planner, executor,
error_handler — all of them just do `LLMProvider()` and call
`.chat()` or `.chat_vision()`, so fixing the fallback order here fixes
it everywhere at once).

Confirmed architecture:
  TEXT (brain)  : Gemini key #1 -> Groq key #3 -> Ollama (offline)
  VISION        : Gemini key #2 -> Groq vision -> Ollama vision (offline)

Both chains are "try the next tier on ANY failure" — quota error,
network error, missing key, whatever. We never raise up to the
caller; worst case we return a plain apology string so the rest of
the app doesn't crash.
"""

import os
import base64
import traceback

import requests
import ollama
from dotenv import load_dotenv

load_dotenv()

from core.router import (
    ModelRouter, Route,
    GEMINI_TEXT_MODEL, GROQ_BRAIN_MODEL, GROQ_VISION_MODEL,
    OLLAMA_TEXT_MODEL, OLLAMA_VISION_MODEL,
)
from core.internet import is_online, check_ollama_available

# ---- keys ---------------------------------------------------------------
# Gemini: two separate keys, two separate jobs. Don't mix them up.
GEMINI_API_KEY_1 = os.environ.get("GEMINI_API_KEY_1", "")  # brain
GEMINI_API_KEY_2 = os.environ.get("GEMINI_API_KEY_2", "")  # vision

# Groq: key #3 is the brain fallback. Vision fallback reuses key #2
# (same key used for STT Whisper) unless GROQ_API_KEY_2 isn't set, in
# which case we fall back further to whatever GROQ_API_KEY / 
# GROQ_LLM_API_KEY is present, for backward compatibility with older
# .env files that only had one Groq key.
GROQ_API_KEY_3 = (
    os.environ.get("GROQ_API_KEY_3")
    or os.environ.get("GROQ_LLM_API_KEY")
    or os.environ.get("GROQ_API_KEY")
    or ""
)
GROQ_API_KEY_2 = (
    os.environ.get("GROQ_API_KEY_2")
    or os.environ.get("GROQ_LLM_API_KEY")
    or os.environ.get("GROQ_API_KEY")
    or ""
)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT_SECONDS = 15.0


class LLMProvider:
    def __init__(self):
        self.router = ModelRouter()

    # ------------------------------------------------------------------
    # TEXT: Gemini (key #1) -> Groq (key #3) -> Ollama
    # ------------------------------------------------------------------
    def chat(self, prompt: str, system: str = "", tools: list = None) -> dict:
        online = is_online()

        # TIER 1 — Gemini
        if online and GEMINI_API_KEY_1:
            try:
                return self._chat_gemini(prompt, system, tools)
            except Exception as e:
                print(f"[LLM] Gemini brain failed, falling back to Groq: {str(e)[:150]}")

        # TIER 2 — Groq
        if online and GROQ_API_KEY_3:
            try:
                return self._chat_groq(prompt, system, tools)
            except Exception as e:
                print(f"[LLM] Groq failed, falling back to Ollama: {str(e)[:150]}")

        # TIER 3 — Ollama (also the only path when fully offline)
        if check_ollama_available():
            try:
                return self._chat_ollama(prompt, system, tools)
            except Exception as e:
                print(f"[LLM] Ollama error: {e}")

        return {
            "type": "text",
            "content": "Sorry, I cannot respond right now. Check internet and API keys.",
        }

    def _chat_gemini(self, prompt: str, system: str, tools: list) -> dict:
        from google import genai

        client = genai.Client(api_key=GEMINI_API_KEY_1)
        contents = f"{system}\n\n{prompt}" if system else prompt
        print(f"[LLM] Calling Gemini ({GEMINI_TEXT_MODEL})...")
        resp = client.models.generate_content(model=GEMINI_TEXT_MODEL, contents=contents)
        content = getattr(resp, "text", "") or ""
        print(f"[LLM] Gemini SUCCESS: {content[:80]}...")
        return {"type": "text", "content": content}

    def _chat_groq(self, prompt: str, system: str, tools: list) -> dict:
        route_decision = self.router.route(prompt)
        selected_model = route_decision.model
        print(f"[LLM Router] Mode: {route_decision.name}, Selected Model: {selected_model}")

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY_3}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": selected_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        if tools:
            payload["tools"] = tools

        resp = requests.post(GROQ_CHAT_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Groq error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        msg = data["choices"][0]["message"]
        if msg.get("tool_calls"):
            print("[LLM] Groq: tool_calls generated")
            return {"type": "tool_calls", "calls": msg["tool_calls"]}

        content = msg.get("content", "")
        print(f"[LLM] Groq SUCCESS: {content[:80]}...")
        return {"type": "text", "content": content}

    def _chat_ollama(self, prompt: str, system: str = "", tools: list = None) -> dict:
        messages = []
        if tools:
            tool_names = [t["function"]["name"] for t in tools if "function" in t]
            system = (system or "") + f"\n\nTools: {', '.join(tool_names)}"
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        client = ollama.Client(host="http://localhost:11434", timeout=TIMEOUT_SECONDS)
        print("[Ollama] Sending request...")
        response = client.chat(model=OLLAMA_TEXT_MODEL, messages=messages, tools=tools)
        message = response.get("message", {})

        if message.get("tool_calls"):
            return {"type": "tool_calls", "calls": message["tool_calls"]}

        content = message.get("content", "").strip()
        print(f"[Ollama] SUCCESS: {content[:50]}...")
        return {"type": "text", "content": content}

    # ------------------------------------------------------------------
    # VISION: Gemini (key #2) -> Groq vision -> Ollama vision
    # ------------------------------------------------------------------
    def chat_vision(self, prompt: str, image_path: str, system: str = "") -> str:
        online = is_online()

        if online and GEMINI_API_KEY_2:
            try:
                return self._vision_gemini(prompt, image_path, system)
            except Exception as e:
                print(f"[Vision] Gemini failed, falling back to Groq: {str(e)[:150]}")

        if online and GROQ_API_KEY_2:
            try:
                return self._vision_groq(prompt, image_path, system)
            except Exception as e:
                print(f"[Vision] Groq failed, falling back to Ollama: {str(e)[:150]}")

        if check_ollama_available():
            try:
                return self._vision_ollama(prompt, image_path, system)
            except Exception as e:
                print(f"[Vision] Ollama error: {e}")
                traceback.print_exc()

        return "Sorry, I can't analyze the image right now. Check internet and API keys."

    def _vision_gemini(self, prompt: str, image_path: str, system: str) -> str:
        from google import genai
        from google.genai import types

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        client = genai.Client(api_key=GEMINI_API_KEY_2)
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            f"{system}\n\n{prompt}" if system else prompt,
        ]
        print(f"[Vision] Calling Gemini ({GEMINI_TEXT_MODEL})...")
        resp = client.models.generate_content(model=GEMINI_TEXT_MODEL, contents=contents)
        return getattr(resp, "text", "") or ""

    def _vision_groq(self, prompt: str, image_path: str, system: str) -> str:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY_2}",
            "Content-Type": "application/json",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        })
        payload = {"model": GROQ_VISION_MODEL, "messages": messages, "temperature": 0.5, "max_tokens": 1024}

        print(f"[Vision] Calling Groq ({GROQ_VISION_MODEL})...")
        resp = requests.post(GROQ_CHAT_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Groq vision error {resp.status_code}: {resp.text[:200]}")
        return resp.json()["choices"][0]["message"].get("content", "")

    def _vision_ollama(self, prompt: str, image_path: str, system: str) -> str:
        client = ollama.Client(host="http://localhost:11434", timeout=TIMEOUT_SECONDS)
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        print(f"[Vision] Calling Ollama ({OLLAMA_VISION_MODEL})...")
        response = client.chat(
            model=OLLAMA_VISION_MODEL,
            messages=[{"role": "user", "content": full_prompt, "images": [image_path]}],
        )
        return response.get("message", {}).get("content", "").strip()