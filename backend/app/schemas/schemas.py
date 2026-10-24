from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime

# Auth Schemas
class AppLoginRequest(BaseModel):
    username: str
    password: str

class AppLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str

class DhanLoginRequest(BaseModel):
    api_key: str  # Dhan Client ID or App ID
    api_secret: Optional[str] = None
    request_token: Optional[str] = None # Or access token if direct

class DhanLoginResponse(BaseModel):
    status: str
    session_valid: bool
    message: Optional[str] = None
    client_id: Optional[str] = None

class SessionStatusResponse(BaseModel):
    authenticated: bool
    client_id: Optional[str] = None
    last_updated: Optional[str] = None
    market_open: bool = False

# User Management Schemas
class UserCreateRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: str = "viewer"

class UserUpdateRequest(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None
    password: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    telegram_chat_id: Optional[str] = None
    telegram_alerts_enabled: Optional[bool] = True
    
    class Config:
        from_attributes = True

# Screener Schemas
class ScreenerCriteria(BaseModel):
    min_price: Optional[float] = 10.0
    max_price: Optional[float] = 50000.0
    min_change_pct: Optional[float] = None
    max_change_pct: Optional[float] = None
    min_volume_ratio: Optional[float] = None # e.g. 1.5x average volume
    rsi_min: Optional[float] = None
    rsi_max: Optional[float] = None
    moving_average: Optional[str] = None # "ABOVE_SMA20", "ABOVE_EMA50", "GOLDEN_CROSS"
    breakout: Optional[str] = None # "DAY_HIGH", "52W_HIGH", "NONE"

class ScreenerRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    universe: str = "NIFTY50"
    is_active: bool = True
    criteria: ScreenerCriteria

class ScreenerRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    universe: Optional[str] = None
    is_active: Optional[bool] = None
    criteria: Optional[ScreenerCriteria] = None

class ScreenerRuleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    universe: str
    is_active: bool
    criteria: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Scan Result Schemas
class StockScanResult(BaseModel):
    symbol: str
    name: str
    ltp: float
    change_pct: float
    change: float
    volume: int
    high: float
    low: float
    open: float
    prev_close: float
    rsi: Optional[float] = None
    sma20: Optional[float] = None
    ema50: Optional[float] = None
    volume_surge_x: Optional[float] = None
    triggered_criteria: List[str] = []
    matched_rules: List[str] = []
    last_updated: str
