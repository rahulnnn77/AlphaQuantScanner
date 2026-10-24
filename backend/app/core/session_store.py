import json
import os
import base64
from datetime import datetime
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
import hashlib
from app.core.config import settings

class SessionManager:
    """
    Secure local persistence for Dhan session tokens.
    Uses AES/Fernet encryption derived from backend SECRET_KEY.
    Raw tokens are NEVER exposed to the frontend.
    """
    def __init__(self):
        self.file_path = settings.SESSION_STORAGE_PATH
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        # Derive 32-byte urlsafe base64 key from settings
        key_hash = hashlib.sha256((settings.ENCRYPTION_KEY or settings.SECRET_KEY).encode()).digest()
        self.fernet_key = base64.urlsafe_b64encode(key_hash)
        self.cipher = Fernet(self.fernet_key)

    def save_session(self, client_id: str, access_token: str, profile_info: Optional[Dict[str, Any]] = None) -> bool:
        try:
            data = {
                "client_id": client_id,
                "access_token": access_token,
                "updated_at": datetime.utcnow().isoformat(),
                "profile": profile_info or {}
            }
            json_str = json.dumps(data)
            encrypted = self.cipher.encrypt(json_str.encode()).decode()
            
            with open(self.file_path, "w") as f:
                json.dump({"payload": encrypted, "client_id": client_id, "active": True}, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving session: {e}")
            return False

    def load_session(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            return None
        try:
            with open(self.file_path, "r") as f:
                container = json.load(f)
            encrypted = container.get("payload")
            if not encrypted:
                return None
            decrypted = self.cipher.decrypt(encrypted.encode()).decode()
            data = json.loads(decrypted)
            return data
        except Exception as e:
            print(f"Error reading session: {e}")
            return None

    def get_token(self) -> Optional[str]:
        session = self.load_session()
        if session:
            return session.get("access_token")
        return None

    def get_client_id(self) -> Optional[str]:
        session = self.load_session()
        if session:
            return session.get("client_id")
        return None

    def clear_session(self):
        if os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
            except Exception:
                pass

session_manager = SessionManager()
