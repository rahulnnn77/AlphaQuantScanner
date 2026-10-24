import logging
import requests
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.entities import TelegramSettings, User

logger = logging.getLogger("telegram_service")

class TelegramAlertService:
    """
    Handles Telegram Bot notifications:
    - Broadcast alerts to a shared Group / Channel
    - Send private DMs to individual users based on their custom preferences
    - Test connection status using getMe
    """

    @staticmethod
    def get_settings(db: Session) -> TelegramSettings:
        settings = db.query(TelegramSettings).filter(TelegramSettings.id == 1).first()
        if not settings:
            settings = TelegramSettings(id=1, is_enabled=False)
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return settings

    @staticmethod
    def update_settings(db: Session, update_data: Dict[str, Any]) -> TelegramSettings:
        settings = TelegramAlertService.get_settings(db)
        for key, val in update_data.items():
            if hasattr(settings, key):
                setattr(settings, key, val)
        settings.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(settings)
        return settings

    @staticmethod
    def test_bot_connection(bot_token: str) -> Dict[str, Any]:
        """Validates the bot token with Telegram getMe API."""
        if not bot_token:
            return {"status": "error", "message": "Bot token cannot be empty"}
        
        try:
            url = f"https://api.telegram.org/bot{bot_token.strip()}/getMe"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if data.get("ok"):
                bot_user = data.get("result", {})
                return {
                    "status": "success",
                    "bot_name": bot_user.get("first_name", ""),
                    "bot_username": bot_user.get("username", ""),
                    "message": f"Connected successfully to @{bot_user.get('username')}"
                }
            else:
                return {
                    "status": "error",
                    "message": data.get("description", "Failed to connect to Telegram")
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def send_message(bot_token: str, chat_id: str, text: str) -> Dict[str, Any]:
        """Dispatches an HTML/Markdown formatted message to a given chat ID."""
        if not bot_token or not chat_id:
            return {"status": "error", "message": "Bot token and Chat ID are required"}

        try:
            url = f"https://api.telegram.org/bot{bot_token.strip()}/sendMessage"
            payload = {
                "chat_id": str(chat_id).strip(),
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()
            if data.get("ok"):
                return {"status": "success", "message_id": data.get("result", {}).get("message_id")}
            else:
                return {"status": "error", "message": data.get("description", "Telegram API error")}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def broadcast_breakout_alert(db: Session, stock_alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches an HPS Breakout alert:
        - To the main Group/Channel (if enabled)
        - To individual users who opted in for direct DMs
        """
        settings = TelegramAlertService.get_settings(db)
        if not settings.is_enabled or not settings.bot_token or not settings.alert_on_hps_breakout:
            return {"status": "skipped", "reason": "HPS Breakout alerts disabled or bot not configured"}

        # Format alert message cleanly without revealing confidential indicator formulas
        symbol = stock_alert.get("symbol", "")
        name = stock_alert.get("name", symbol)
        universe = "NIFTY F&O" if stock_alert.get("is_fo") else "NIFTY 500"
        timeframe = stock_alert.get("timeframe", "Daily").upper()
        signal = "Bullish Breakout" if stock_alert.get("status") == "BROKEN_ABOVE" else "Bearish Breakdown"
        ltp = stock_alert.get("ltp", 0.0)
        spread = stock_alert.get("spread_pct", 0.0)
        spread_sign = "+" if spread > 0 else ""

        text = (
            f"<b>AlphaQuant Screener Alert</b>\n"
            f"<b>Setup:</b> HPS Breakout Signal\n"
            f"<b>Stock:</b> <code>{symbol}</code> ({name})\n"
            f"<b>Universe:</b> {universe}\n"
            f"<b>Timeframe:</b> {timeframe}\n"
            f"<b>Signal:</b> {signal}\n"
            f"<b>LTP:</b> ₹{ltp:,.2f} ({spread_sign}{spread:.2f}%)\n"
            f"<i>Time: {datetime.now().strftime('%d %b %Y, %H:%M:%S IST')}</i>"
        )

        results = {"channel_sent": False, "direct_sent_count": 0}

        # 1. Send to public/private channel or group
        if settings.default_channel_id:
            res = TelegramAlertService.send_message(settings.bot_token, settings.default_channel_id, text)
            if res.get("status") == "success":
                results["channel_sent"] = True

        # 2. Send to individual opted-in users
        users = db.query(User).filter(
            User.is_active == True,
            User.telegram_chat_id.isnot(None),
            User.telegram_alerts_enabled == True
        ).all()

        for u in users:
            if u.telegram_chat_id:
                TelegramAlertService.send_message(settings.bot_token, u.telegram_chat_id, text)
                results["direct_sent_count"] += 1

        return {"status": "success", "results": results}

    @staticmethod
    def broadcast_mean_reversion_alert(db: Session, stock_alert: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches an HPS Mean Reversion alert:
        - To the main Group/Channel (if enabled)
        - To individual users who opted in for direct DMs
        """
        settings = TelegramAlertService.get_settings(db)
        if not settings.is_enabled or not settings.bot_token or not settings.alert_on_mean_reversion:
            return {"status": "skipped", "reason": "Mean Reversion alerts disabled or bot not configured"}

        symbol = stock_alert.get("symbol", "")
        name = stock_alert.get("name", symbol)
        universe = "NIFTY F&O" if stock_alert.get("is_fo") else "NIFTY 500"
        timeframe = stock_alert.get("timeframe", "Daily").upper()
        level = stock_alert.get("level", "Level-1")
        condition = stock_alert.get("status", "At Support Level")
        ltp = stock_alert.get("ltp", 0.0)
        spread = stock_alert.get("spread_pct", 0.0)
        spread_sign = "+" if spread > 0 else ""

        text = (
            f"<b>AlphaQuant Screener Alert</b>\n"
            f"<b>Setup:</b> HPS Mean Reversion\n"
            f"<b>Stock:</b> <code>{symbol}</code> ({name})\n"
            f"<b>Universe:</b> {universe}\n"
            f"<b>Timeframe:</b> {timeframe}\n"
            f"<b>Reversion Tier:</b> {level} ({condition})\n"
            f"<b>LTP:</b> ₹{ltp:,.2f} ({spread_sign}{spread:.2f}% from level)\n"
            f"<i>Time: {datetime.now().strftime('%d %b %Y, %H:%M:%S IST')}</i>"
        )

        results = {"channel_sent": False, "direct_sent_count": 0}

        # 1. Send to group channel
        if settings.default_channel_id:
            res = TelegramAlertService.send_message(settings.bot_token, settings.default_channel_id, text)
            if res.get("status") == "success":
                results["channel_sent"] = True

        # 2. Send to individual opted-in users
        users = db.query(User).filter(
            User.is_active == True,
            User.telegram_chat_id.isnot(None),
            User.telegram_alerts_enabled == True
        ).all()

        for u in users:
            if u.telegram_chat_id:
                TelegramAlertService.send_message(settings.bot_token, u.telegram_chat_id, text)
                results["direct_sent_count"] += 1

        return {"status": "success", "results": results}
