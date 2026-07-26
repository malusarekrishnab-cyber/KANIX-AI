import hashlib
import json
import os
import time
from pathlib import Path
import secrets

try:
    import face_recognition
    import cv2
    FACE_AUTH_AVAILABLE = True
except ImportError:
    FACE_AUTH_AVAILABLE = False

AUTH_FILE = Path(__file__).resolve().parent.parent / "config" / "auth_db.json"

class AuthManager:
    def __init__(self):
        self.session_active = False
        self.last_activity = 0
        self.failed_attempts = 0
        self.max_attempts = 5
        self.lockout_time = 0
        self.session_timeout = 300 # 5 minutes
        
        self._ensure_auth_db()
        
    def _ensure_auth_db(self):
        os.makedirs(AUTH_FILE.parent, exist_ok=True)
        if not AUTH_FILE.exists():
            salt = secrets.token_hex(16)
            default_db = {
                "users": {
                    "admin": {
                        "salt": salt,
                        "password_hash": self._hash_password("admin123", salt),
                        "face_encoding": None,
                        "voice_pattern": None
                    }
                }
            }
            with open(AUTH_FILE, "w") as f:
                json.dump(default_db, f, indent=4)
                
    def _hash_password(self, password: str, salt: str) -> str:
        return hashlib.sha256((password + salt).encode()).hexdigest()
        
    def _load_db(self) -> dict:
        try:
            with open(AUTH_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"users": {}}

    def is_locked_out(self) -> bool:
        if time.time() < self.lockout_time:
            return True
        return False

    def login_password(self, username: str, password: str) -> bool:
        if self.is_locked_out():
            return False
            
        db = self._load_db()
        users = db.get("users", {})
        
        if username in users:
            stored_hash = users[username].get("password_hash")
            salt = users[username].get("salt", "")
            if stored_hash == self._hash_password(password, salt):
                self._login_success()
                return True
                
        self._login_failed()
        return False

    def _login_success(self):
        self.session_active = True
        self.failed_attempts = 0
        self.last_activity = time.time()

    def _login_failed(self):
        self.failed_attempts += 1
        if self.failed_attempts >= self.max_attempts:
            self.lockout_time = time.time() + 300 # 5 min lockout

    def check_session(self) -> bool:
        if not self.session_active:
            return False
        if time.time() - self.last_activity > self.session_timeout:
            self.session_active = False
            return False
        self.last_activity = time.time() # Update activity
        return True
