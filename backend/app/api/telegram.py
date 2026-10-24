from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel
from app.core.database import get_db
from app.models.entities import User, TelegramSettings
from app.api.deps import get_current_user
from app.services.telegram_service import TelegramAlertService

router = APIRouter()

class TelegramConfigPayload(BaseModel):
    is_enabled: Optional[bool] = None
    bot_token: Optional[str] = None
    bot_username: Optional[str] = None
    default_channel_id: Optional[str] = None
    alert_on_hps_breakout: Optional[bool] = None
    alert_on_mean_reversion: Optional[bool] = None

class UserTelegramPayload(BaseModel):
    telegram_chat_id: Optional[str] = None
    telegram_alerts_enabled: Optional[bool] = None

class TestMessagePayload(BaseModel):
    chat_id: Optional[str] = None
    message: Optional[str] = None

@router.get("/config")
def get_telegram_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Admin endpoint to fetch Telegram bot and broadcast configuration."""
    settings = TelegramAlertService.get_settings(db)
    
    # Mask bot token for non-admins or security
    masked_token = ""
    if settings.bot_token:
        if len(settings.bot_token) > 12:
            masked_token = settings.bot_token[:6] + "..." + settings.bot_token[-4:]
        else:
            masked_token = "***"

    return {
        "status": "success",
        "is_enabled": settings.is_enabled,
        "bot_username": settings.bot_username or "",
        "bot_token_set": bool(settings.bot_token),
        "bot_token_masked": masked_token,
        "default_channel_id": settings.default_channel_id or "",
        "alert_on_hps_breakout": settings.alert_on_hps_breakout,
        "alert_on_mean_reversion": settings.alert_on_mean_reversion,
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None
    }

@router.put("/config")
def update_telegram_config(
    payload: TelegramConfigPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Admin endpoint to update Telegram bot configuration."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can modify Telegram bot configuration")

    update_dict = {}
    if payload.is_enabled is not None:
        update_dict["is_enabled"] = payload.is_enabled
    if payload.bot_token is not None and payload.bot_token.strip() != "":
        # Test bot token validity
        test_res = TelegramAlertService.test_bot_connection(payload.bot_token.strip())
        if test_res.get("status") != "success":
            raise HTTPException(status_code=400, detail=f"Invalid Bot Token: {test_res.get('message')}")
        update_dict["bot_token"] = payload.bot_token.strip()
        update_dict["bot_username"] = test_res.get("bot_username", "")
    if payload.default_channel_id is not None:
        update_dict["default_channel_id"] = payload.default_channel_id.strip()
    if payload.alert_on_hps_breakout is not None:
        update_dict["alert_on_hps_breakout"] = payload.alert_on_hps_breakout
    if payload.alert_on_mean_reversion is not None:
        update_dict["alert_on_mean_reversion"] = payload.alert_on_mean_reversion

    settings = TelegramAlertService.update_settings(db, update_dict)
    return {
        "status": "success",
        "message": "Telegram configuration saved successfully",
        "bot_username": settings.bot_username
    }

@router.post("/test-connection")
def test_telegram_connection(
    payload: Dict[str, str] = Body(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Validates any given Bot Token."""
    token = payload.get("bot_token", "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Bot token is required")
    return TelegramAlertService.test_bot_connection(token)

@router.post("/send-test")
def send_test_message(
    payload: TestMessagePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Sends a test broadcast or DM to verify chat ID."""
    settings = TelegramAlertService.get_settings(db)
    if not settings.bot_token:
        raise HTTPException(status_code=400, detail="Bot token is not configured yet")

    chat_id = payload.chat_id or settings.default_channel_id
    if not chat_id:
        raise HTTPException(status_code=400, detail="No Target Chat ID or Channel ID provided")

    sample_msg = (
        "<b>AlphaQuant Screener - Test Alert</b>\n\n"
        "This is a test notification confirming that Telegram alerts are properly linked and operational.\n"
        f"<b>Target:</b> <code>{chat_id}</code>\n"
        "<b>Status:</b> Live & Connected"
    )
    res = TelegramAlertService.send_message(settings.bot_token, chat_id, sample_msg)
    if res.get("status") != "success":
        raise HTTPException(status_code=400, detail=res.get("message", "Failed to dispatch message"))
    return {"status": "success", "message": "Test alert dispatched successfully"}

@router.get("/user-pref")
def get_user_telegram_preferences(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Fetches logged-in user's personal Telegram preferences."""
    return {
        "status": "success",
        "telegram_chat_id": current_user.telegram_chat_id or "",
        "telegram_alerts_enabled": bool(current_user.telegram_alerts_enabled)
    }

@router.put("/user-pref")
def update_user_telegram_preferences(
    payload: UserTelegramPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Updates logged-in user's personal Telegram Chat ID & alert toggles."""
    if payload.telegram_chat_id is not None:
        current_user.telegram_chat_id = payload.telegram_chat_id.strip() or None
    if payload.telegram_alerts_enabled is not None:
        current_user.telegram_alerts_enabled = payload.telegram_alerts_enabled

    db.commit()
    db.refresh(current_user)
    return {
        "status": "success",
        "message": "User Telegram preferences updated",
        "telegram_chat_id": current_user.telegram_chat_id,
        "telegram_alerts_enabled": current_user.telegram_alerts_enabled
    }
