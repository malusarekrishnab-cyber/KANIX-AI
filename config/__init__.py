import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

REQUIRED_KEYS = [
    "GROQ_API_KEY",
    "TAVILY_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_SECRET_KEY"
]

def check_keys():
    for key in REQUIRED_KEYS:
        if not os.environ.get(key):
            raise ValueError(f"Missing required environment variable: {key}. Please add it to the .env file.")

# Enforce key check at import
check_keys()

def get_config() -> dict:
    return dict(os.environ)

def get_os() -> str:
    """Returns: 'windows' | 'mac' | 'linux'"""
    return os.environ.get("OS_SYSTEM", "windows").lower()

def is_windows() -> bool: return get_os() == "windows"
def is_mac()     -> bool: return get_os() == "mac"
def is_linux()   -> bool: return get_os() == "linux"