import os
import requests
import json
import ollama
import traceback
from dotenv import load_dotenv

load_dotenv()
from core.router import ModelRouter, Route
from core.internet import is_online, check_ollama_available

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.environ.get("GROQ_LLM_API_KEY", "")

OLLAMA_TEXT_MODEL = "qwen3:8b"
TIMEOUT_SECONDS = 15.0

class LLMProvider:
    def __init__(self):
        self.router = ModelRouter()
        self.current_mode = "groq"
    
    def chat(self, prompt: str, system: str = "", tools: list = None) -> dict:
        """Main chat - Groq first, Ollama fallback"""
        # Determine routing model
        route_decision = self.router.route(prompt)
        selected_model = route_decision.model
        print(f"[LLM Router] Mode: {route_decision.name}, Selected Model: {selected_model}")

        # TRY GROQ FIRST if online and key exists
        if GROQ_API_KEY and is_online():
            try:
                print(f"[LLM] Calling Groq API DIRECTLY with model {selected_model}...")
                
                headers = {
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                
                payload = {
                    "model": selected_model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 4096
                }
                
                if tools:
                    payload["tools"] = tools
                
                resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
                
                if resp.status_code == 200:
                    data = resp.json()
                    msg = data["choices"][0]["message"]
                    
                    if msg.get("tool_calls"):
                        print(f"[LLM] Groq: tool_calls generated")
                        return {"type": "tool_calls", "calls": msg["tool_calls"]}
                    
                    content = msg.get("content", "")
                    print(f"[LLM] Groq SUCCESS: {content[:80]}...")
                    return {"type": "text", "content": content}
                else:
                    error_text = resp.text[:200]
                    print(f"[LLM] Groq error {resp.status_code}: {error_text}")
                    
            except Exception as e:
                print(f"[LLM] Groq exception: {str(e)[:150]}")
        
        # FALLBACK TO OLLAMA
        print(f"[LLM] Groq failed or offline. Trying Ollama fallback...")
        if check_ollama_available():
            try:
                return self._chat_ollama(prompt, system, tools)
            except Exception as e:
                print(f"[LLM] Ollama error: {e}")
        
        return {"type": "text", "content": "Sorry, I cannot respond right now. Check internet and API keys."}
    
    def _chat_ollama(self, prompt: str, system: str = "", tools: list = None) -> dict:
        messages = []
        if tools:
            tool_names = [t["function"]["name"] for t in tools if "function" in t]
            system += f"\n\nTools: {', '.join(tool_names)}"
        
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        try:
            client = ollama.Client(host="http://localhost:11434", timeout=TIMEOUT_SECONDS)
            print(f"[Ollama] Sending request...")
            response = client.chat(model=OLLAMA_TEXT_MODEL, messages=messages, tools=tools)
            message = response.get("message", {})
            
            if message.get("tool_calls"):
                return {"type": "tool_calls", "calls": message["tool_calls"]}
            
            content = message.get("content", "").strip()
            print(f"[Ollama] SUCCESS: {content[:50]}...")
            return {"type": "text", "content": content}
            
        except Exception as e:
            print(f"[Ollama] Failed: {e}")
            raise