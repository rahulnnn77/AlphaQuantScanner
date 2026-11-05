from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, UniqueConstraint
from datetime import datetime
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="viewer", nullable=False) # 'admin' or 'viewer'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    telegram_alerts_enabled = Column(Boolean, default=True)

class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    display_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WatchlistStock(Base):
    __tablename__ = "watchlist_stocks"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "stock_symbol", "exchange", name="uq_watchlist_symbol_exchange"),
    )

    id = Column(Integer, primary_key=True, index=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_symbol = Column(String(40), nullable=False, index=True)
    company_name = Column(String(160), nullable=True)
    exchange = Column(String(15), default="NSE", nullable=False)
    sector = Column(String(100), nullable=True)
    display_order = Column(Integer, default=0, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)

class ScreenerRule(Base):
    __tablename__ = "screener_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    universe = Column(String(50), default="NIFTY50") # NIFTY50, NIFTY500, FO, BANKNIFTY
    is_active = Column(Boolean, default=True)
    
    # Filter conditions stored in JSON
    # e.g., {"min_price": 50, "max_price": 5000, "min_change_pct": 1.5, "rsi_min": 50, "rsi_max": 75, "min_volume_ratio": 1.2, "ma_cross": "EMA20_ABOVE_EMA50"}
    criteria = Column(JSON, nullable=False, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserScreenerAccess(Base):
    __tablename__ = "user_screener_access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    rule_id = Column(Integer, nullable=False)
    can_view = Column(Boolean, default=True)

class TelegramSettings(Base):
    __tablename__ = "telegram_settings"

    id = Column(Integer, primary_key=True, index=True)
    is_enabled = Column(Boolean, default=False)
    bot_token = Column(String(255), nullable=True)
    bot_username = Column(String(100), nullable=True)
    default_channel_id = Column(String(100), nullable=True) # Broadcast channel or group chat ID (e.g. -100xxxxxxx)
    alert_on_hps_breakout = Column(Boolean, default=True)
    alert_on_mean_reversion = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
