import os
import requests
from dotenv import load_dotenv

load_dotenv()
GROQ_API_KEY = os.environ.get("GROQ_LLM_API_KEY", "")

def is_online() -> bool:
    urls_to_try = [
        "https://www.google.com",
        "https://api.groq.com",
        "https://1.1.1.1"
    ]
    for url in urls_to_try:
        try:
            requests.get(url, timeout=3)
            return True
        except (requests.ConnectionError, requests.Timeout):
            continue
    return False

def check_groq_available() -> bool:
    if not GROQ_API_KEY:
        return False
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        resp = requests.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=3)
        return resp.status_code == 200
    except:
        return False

def check_ollama_available() -> bool:
    try:
        resp = requests.get("http://localhost:11434/api/version", timeout=2)
        return resp.status_code == 200
    except:
        return False