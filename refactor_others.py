import os
import re
from pathlib import Path

BASE = Path(r"c:\Users\malus\ALL VS CODE PROJECT\KANIX -AI\Mark-XXXIX-OR")

files_to_fix = [
    BASE / "actions" / "code_helper.py",
    BASE / "actions" / "desktop.py",
    BASE / "actions" / "dev_agent.py",
    BASE / "actions" / "flight_finder.py",
    BASE / "actions" / "web_search.py",
    BASE / "actions" / "youtube_video.py",
    BASE / "agent" / "error_handler.py",
    BASE / "agent" / "executor.py",
    BASE / "agent" / "planner.py",
]

for file_path in files_to_fix:
    if not file_path.exists():
        continue
    content = file_path.read_text(encoding="utf-8")
    
    # Imports
    content = re.sub(r'import google\.generativeai as genai\n+', 'from core.llm_provider import LLMProvider\n', content)
    
    # Remove _get_api_key
    content = re.sub(r'def _get_api_key.*?\n\s+return json\.load.*?gemini_api_key.*?\n', '', content, flags=re.DOTALL)
    
    # _get_gemini / _gemini_client
    content = re.sub(r'def _get_gemini\(.*?\):.*?return genai\.GenerativeModel\(model\)\n', '', content, flags=re.DOTALL)
    
    # Replaces
    content = content.replace("model = _get_gemini()", "model = LLMProvider()")
    content = content.replace("model  = _get_gemini()", "model = LLMProvider()")
    content = content.replace("model = _gemini_client()", "model = LLMProvider()")
    
    content = content.replace("response = model.generate_content(prompt)", "response = model.chat(prompt)")
    content = content.replace("response.text", "response.get('content', '')")
    
    # For actions/desktop.py
    content = content.replace("_ask_gemini_for_desktop_action", "_ask_llm_for_desktop_action")
    content = content.replace("Asking Gemini:", "Asking LLM:")
    
    # For actions/web_search.py
    content = content.replace("GEMINI_API_KEY", "GROQ_API_KEY") # though groq is not for text, we will just remove it
    content = content.replace("def _gemini_search", "def _llm_search")
    content = content.replace("_gemini_search(", "_llm_search(")
    content = content.replace("genai.configure(api_key=_get_api_key())", "")
    content = content.replace('model = genai.GenerativeModel(\n        model="gemini-2.5-flash",\n        system_instruction=SYS\n    )', 'model = LLMProvider()')
    content = content.replace("response = model.generate_content(prompt)\n    text = response.text.strip()", "text = model.chat(prompt, system=SYS).get('content', '').strip()")
    content = content.replace("Gemini compare failed", "LLM compare failed")
    content = content.replace("Gemini returned an empty response", "LLM returned an empty response")
    
    # youtube_video.py
    content = content.replace("_summarize_with_gemini", "_summarize_with_llm")
    
    # flight_finder.py
    content = content.replace("_parse_flights_with_gemini", "_parse_flights_with_llm")
    
    # agent/
    content = re.sub(r'model = genai\.GenerativeModel\(.*?model_name="gemini.*?\"\)', 'model = LLMProvider()', content, flags=re.DOTALL)
    
    file_path.write_text(content, encoding="utf-8")

print("Refactored all other files.")
