import os
from groq import Groq
import json

def get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in environment.")
    return Groq(api_key=api_key)

class GroqLLM:
    def __init__(self):
        self.client = get_groq_client()
        self.model = "llama-3.3-70b-versatile"
        
    def chat(self, prompt: str, system: str = "", tools: list = None) -> dict:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                temperature=0.7,
                max_tokens=4096
            )
            
            choice = response.choices[0]
            
            if choice.message.tool_calls:
                # Return tool calls for main.py to handle
                return {
                    "type": "tool_calls",
                    "calls": choice.message.tool_calls
                }
                
            return {
                "type": "text",
                "content": choice.message.content or ""
            }
        except Exception as e:
            print(f"[Groq Error] {e}")
            return {"type": "text", "content": ""}
