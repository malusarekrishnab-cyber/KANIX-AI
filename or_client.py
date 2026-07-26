import json
import sys
import time
import base64
import logging
from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("groq_client")


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR = _get_base_dir()

import os
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")


def _load_key(name: str) -> str:
    key = os.environ.get(name, "").strip()
    if not key:
        raise ValueError(f"{name} is empty in .env")
    return key


def _load_groq_llm_key() -> str:
    """
    Dedicated key for the Brain (all LLM chat/reasoning traffic).
    NOTE: GROQ_API_KEY is intentionally never read in this file —
    it stays reserved exclusively for Whisper STT elsewhere in the project.
    """
    return _load_key("GROQ_LLM_API_KEY")


# ===== Groq — Brain models (replaces OpenRouter entirely) =====
# NOTE: qwen/qwen3-32b was deprecated by Groq (shutdown 07/17/26) →
# migrated to openai/gpt-oss-120b (Groq's official recommendation).
# NOTE: deepseek-r1-distill-qwen-32b is fully decommissioned on Groq
# (confirmed via live API error, "model_decommissioned") →
# migrated to qwen/qwen3.6-27b, Groq's current live reasoning/coding model.
DEFAULT_MODEL: str = "openai/gpt-oss-120b"            # default assistant
CODING_MODEL: str  = "qwen/qwen3.6-27b"               # coding / debugging / reasoning / complex tasks

TEXT_MODELS: list[str] = [
    DEFAULT_MODEL,
    CODING_MODEL,
]

# Best-effort placeholder pool for vision — neither qwen3-32b nor the
# deepseek-r1-distill model support vision. Swap this if you have a
# preferred Groq vision model; kept here only so vision()/vision_from_file()
# don't break the public API.
VISION_MODELS: list[str] = [
    "llama-4-scout-17b-16e-instruct",
]

# Keywords used to auto-route a prompt to the coding/reasoning model when
# the caller doesn't explicitly pass `model=`.
_CODING_KEYWORDS = (
    "code", "bug", "debug", "error", "exception", "traceback", "stack trace",
    "function", "class ", "python", "javascript", "typescript", "java ",
    "c++", "syntax", "compile", "refactor", "algorithm", "regex",
    "unit test", "stacktrace", "null pointer", "segfault", "script",
    "api", "sql", "query", "reasoning", "step by step", "logic puzzle",
    "prove", "solve this",
)

GROQ_API_URL            = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MAX_TOKENS      = 4096
DEFAULT_TEMPERATURE     = 0.7
REQUEST_TIMEOUT         = 60   # seconds per request
MAX_RETRIES_PER_MODEL   = 2    # attempts before moving to next model
RETRY_DELAY             = 2    # seconds between retries
RATE_LIMIT_COOLDOWN     = 60   # seconds before retrying a rate-limited model

_rate_limited: dict[str, float] = {}


def _detect_coding_task(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in _CODING_KEYWORDS)


class GroqClient:
    """
    Brain client — handles ALL LLM chat/reasoning/vision traffic via Groq.
    Public API is unchanged from the previous OpenRouter-backed client:
        chat(), chat_json(), multi_turn(), vision(), vision_from_file(),
        available_models()
    """

    def __init__(self) -> None:
        self.api_key  = _load_groq_llm_key()
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

    # ---------- rate limit bookkeeping ----------

    def _is_rate_limited(self, model: str) -> bool:
        ts = _rate_limited.get(model)
        if ts is None:
            return False
        if time.time() - ts > RATE_LIMIT_COOLDOWN:
            del _rate_limited[model]
            return False
        return True

    def _mark_rate_limited(self, model: str) -> None:
        _rate_limited[model] = time.time()
        logger.warning(
            f"[Groq] Rate limited: {model} — cooling down for {RATE_LIMIT_COOLDOWN}s"
        )

    # ---------- low level call ----------

    def _call(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        response_format: Optional[dict] = None,
        tools: Optional[list] = None,
    ):
        payload: dict = {
            "model":       model,
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format
        if tools:
            payload["tools"] = tools

        for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
            try:
                resp = requests.post(
                    GROQ_API_URL,
                    headers=self._headers,
                    json=payload,
                    timeout=REQUEST_TIMEOUT,
                )

                if resp.status_code == 429:
                    self._mark_rate_limited(model)
                    return None

                if resp.status_code == 200:
                    data = resp.json()
                    message = data.get("choices", [{}])[0].get("message", {})

                    if message.get("tool_calls"):
                        return {
                            "type": "tool_calls",
                            "calls": message["tool_calls"],
                        }

                    content = message.get("content", "")
                    return {
                        "type": "text",
                        "content": content.strip() if content else "",
                    }

                logger.warning(
                    f"[Groq] {model} → HTTP {resp.status_code} "
                    f"(attempt {attempt}/{MAX_RETRIES_PER_MODEL}) — {resp.text[:200]}"
                )

            except requests.exceptions.Timeout:
                logger.warning(
                    f"[Groq] {model} → Timeout "
                    f"(attempt {attempt}/{MAX_RETRIES_PER_MODEL})"
                )
            except Exception as e:
                logger.error(f"[Groq] {model} → Unexpected error: {e}")

            if attempt < MAX_RETRIES_PER_MODEL:
                time.sleep(RETRY_DELAY)

        return None

    def _call_with_fallback(
        self,
        pool: list[str],
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        response_format: Optional[dict] = None,
        tools: Optional[list] = None,
    ) -> str:
        if model and not self._is_rate_limited(model):
            result = self._call(model, messages, max_tokens, temperature, response_format, tools)
            if result:
                return result["content"] if result["type"] == "text" else result
            logger.info(f"[Groq] Requested model failed, falling back to pool: {model}")

        for m in pool:
            if m == model:
                continue  # already tried above
            if self._is_rate_limited(m):
                continue
            logger.info(f"[Groq] Trying: {m}")
            result = self._call(m, messages, max_tokens, temperature, response_format, tools)
            if result:
                logger.info(f"[Groq] ✓ Success: {m}")
                return result["content"] if result["type"] == "text" else result

        raise RuntimeError(
            "[Groq] All models failed or are rate-limited. "
            "Check GROQ_LLM_API_KEY and your network connection."
        )

    # ---------- public API (unchanged signatures) ----------

    def chat(
        self,
        prompt: str,
        system: str = (
            "You are Kanix (MARK-XXXIX), an AI assistant inspired by JARVIS. "
            "Be concise, helpful, and precise."
        ),
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        tools: Optional[list] = None,
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ]

        chosen_model = model
        if chosen_model is None and _detect_coding_task(prompt):
            chosen_model = CODING_MODEL

        return self._call_with_fallback(
            TEXT_MODELS, messages, chosen_model, max_tokens, temperature, tools=tools
        )

    def chat_json(
        self,
        prompt: str,
        system: str = (
            "Return ONLY valid JSON. "
            "No markdown fences, no extra text, no explanation."
        ),
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict:
        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ]

        chosen_model = model
        if chosen_model is None and _detect_coding_task(prompt):
            chosen_model = CODING_MODEL

        raw = self._call_with_fallback(
            TEXT_MODELS, messages, chosen_model, max_tokens, temperature=0.2
        )

        clean = raw.strip()
        if clean.startswith("```"):
            parts = clean.split("```")
            clean = parts[1] if len(parts) > 1 else clean
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip().rstrip("`").strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error(
                f"[Groq] JSON parse failed: {e}\n"
                f"Raw response (first 300 chars): {raw[:300]}"
            )
            raise ValueError(
                f"Model returned unparseable JSON: {e}\n"
                f"Raw output: {raw[:200]}"
            )

    def vision(
        self,
        prompt: str,
        image_b64: str,
        mime: str = "image/png",
        system: str = "Analyze the image and describe what you see clearly and concisely.",
        model: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{image_b64}"
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            },
        ]
        return self._call_with_fallback(
            VISION_MODELS, messages, model, max_tokens, temperature=0.2
        )

    def vision_from_file(
        self,
        prompt: str,
        image_path: str,
        system: str = "Analyze the image and describe what you see clearly and concisely.",
        model: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> str:
        path = Path(image_path)
        mime_map = {
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif":  "image/gif",
        }
        mime = mime_map.get(path.suffix.lower(), "image/png")

        with open(path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        return self.vision(prompt, image_b64, mime, system, model, max_tokens)

    def multi_turn(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> str:
        chosen_model = model
        if chosen_model is None:
            # inspect the latest user turn to decide default vs coding model
            last_user = next(
                (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
                "",
            )
            if isinstance(last_user, str) and _detect_coding_task(last_user):
                chosen_model = CODING_MODEL

        return self._call_with_fallback(
            TEXT_MODELS, messages, chosen_model, max_tokens, temperature
        )

    def available_models(self) -> dict:
        return {
            "text_models":   TEXT_MODELS,
            "default_model": DEFAULT_MODEL,
            "coding_model":  CODING_MODEL,
            "vision_models": VISION_MODELS,
            "rate_limited":  list(_rate_limited.keys()),
            "total_text":    len(TEXT_MODELS),
            "total_vision":  len(VISION_MODELS),
        }


# ===== Module-level singletons (kept so existing imports don't break) =====
# Previously `client` pointed at OpenRouterClient() and `groq_client` at a
# separate fast-reply GroqClient(). OpenRouter is gone now, so both names
# point at the same Groq-backed brain client.
client      = GroqClient()
groq_client = client


if __name__ == "__main__":
    print("=" * 55)
    print("  KANIX / MARK-XXXIX — Brain Client Self-Test (Groq)")
    print("=" * 55)

    print("\n[TEST 1] Default chat (openai/gpt-oss-120b)...")
    try:
        reply = client.chat("Introduce yourself in one sentence.")
        print(f"  Response : {reply}")
        print(f"  Status   : PASS ✓")
    except Exception as e:
        print(f"  Status   : FAIL ✗ — {e}")

    print("\n[TEST 2] Coding-task auto-routing (qwen/qwen3.6-27b)...")
    try:
        reply = client.chat("Debug this Python function: it throws a TypeError.")
        print(f"  Response : {reply}")
        print(f"  Status   : PASS ✓")
    except Exception as e:
        print(f"  Status   : FAIL ✗ — {e}")

    print("\n[TEST 3] chat_json...")
    try:
        result = client.chat_json("Return a JSON object with keys 'status' and 'ok' set to true/'ready'.")
        print(f"  Response : {result}")
        print(f"  Status   : PASS ✓")
    except Exception as e:
        print(f"  Status   : FAIL ✗ — {e}")

    print("\n" + "=" * 55)
    print("  All tests complete.")
    print("=" * 55)