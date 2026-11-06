from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey, UniqueConstraint
from datetime import datetime
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    full_name = Column(String(120), nullable=True)
    phone_number = Column(String(30), nullable=True)
    organization = Column(String(150), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="viewer", nullable=False) # 'admin' or 'viewer'
    status = Column(String(20), default="APPROVED", nullable=False) # 'APPROVED', 'PENDING', 'REJECTED', 'SUSPENDED'
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    telegram_alerts_enabled = Column(Boolean, default=True)

class AccessRequest(Base):
    __tablename__ = "access_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(100), nullable=False)
    phone_number = Column(String(30), nullable=False)
    organization = Column(String(150), nullable=True)
    status = Column(String(20), default="PENDING", nullable=False) # 'PENDING', 'APPROVED', 'REJECTED', 'SUSPENDED'
    decision_by = Column(String(50), nullable=True) # Admin username
    decision_at = Column(DateTime, nullable=True)
    decision_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_username = Column(String(50), nullable=False, index=True)
    action = Column(String(50), nullable=False) # 'APPROVE_USER', 'REJECT_USER', 'SUSPEND_USER', 'REINSTATE_USER'
    target_user_id = Column(Integer, nullable=True)
    target_username = Column(String(50), nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

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
    default_channel_id = Column(String(100), nullable=True)
    alert_on_hps_breakout = Column(Boolean, default=True)
    alert_on_mean_reversion = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
