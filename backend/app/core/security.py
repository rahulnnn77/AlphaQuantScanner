from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional
import jwt
import hashlib
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    salt = settings.SECRET_KEY[:16]
    hashed = hashlib.sha256(f"{salt}{plain_password}".encode()).hexdigest()
    return hashed == hashed_password

def get_password_hash(password: str) -> str:
    salt = settings.SECRET_KEY[:16]
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def create_access_token(subject: Union[str, Any], role: str, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject), "role": role}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return decoded
    except Exception:
        return None
