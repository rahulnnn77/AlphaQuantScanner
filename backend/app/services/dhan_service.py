import logging
import requests
from typing import Dict, Any, Optional
from dhanhq import DhanLogin, dhanhq
from app.core.session_store import session_manager

logger = logging.getLogger("dhan_service")

class DhanClientService:
    """
    Broker client service integrating dhanhq SDK.
    Handles token consumption, profile checking, and market feeds.
    """
    
    @staticmethod
    def authenticate_broker(client_id: str, api_secret: Optional[str] = None, request_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates or consumes Dhan credentials.
        Supports both:
        1. OAuth exchange: api_key (App ID), api_secret, and request_token (Token ID from OAuth consent)
        2. Direct Access Token: when request_token is already the generated access token
        """
        token_to_use = None
        
        # Mode 1: OAuth flow consumption via DhanLogin
        if api_secret and request_token and len(request_token) < 80:
            try:
                login_helper = DhanLogin(client_id)
                # Consume consent tokenId to get access token
                res = login_helper.consume_token_id(request_token, client_id, api_secret)
                logger.info(f"Consumed token ID successfully: {res}")
                token_to_use = res.get("accessToken") or res.get("data", {}).get("accessToken")
            except Exception as e:
                logger.warning(f"consume_token_id failed: {e}. Checking if token can be validated directly...")
        
        # Mode 2: If request_token is already the direct access token (very common in Dhan API console)
        if not token_to_use and request_token:
            token_to_use = request_token.strip()

        if not token_to_use:
            raise ValueError("No valid token could be determined from the provided credentials.")

        # Test token validity by fetching user profile
        profile = DhanClientService.fetch_broker_profile(client_id, token_to_use)
        actual_client_id = str(profile.get("client_id") or client_id)
        
        # Persist securely on backend disk
        session_manager.save_session(client_id=actual_client_id, access_token=token_to_use, profile_info=profile)
        DhanClientService._reset_alert_state_on_connect(actual_client_id, profile)
        
        return {
            "status": "authenticated",
            "session_valid": True,
            "client_id": actual_client_id,
            "profile": profile
        }

    @staticmethod
    def login_with_pin_totp(client_id: str, pin: str, totp_secret: str) -> Dict[str, Any]:
        """
        Headless automated token generation using Dhan Client ID, PIN, and TOTP Secret (or 6-digit TOTP code).
        Runs fully headless without opening browser.
        """
        import pyotp
        cleaned_totp = totp_secret.replace(" ", "").strip()
        if cleaned_totp.isdigit() and len(cleaned_totp) == 6:
            current_totp = cleaned_totp
        else:
            totp_obj = pyotp.TOTP(cleaned_totp)
            current_totp = totp_obj.now()
        
        login_helper = DhanLogin(client_id)
        res = login_helper.generate_token(pin=pin.strip(), totp=current_totp)
        logger.info(f"Dhan PIN/TOTP generation response: {res}")
        
        token = res.get("accessToken") or res.get("data", {}).get("accessToken") or res.get("token")
        if not token:
            raise ValueError(f"Could not retrieve accessToken from response: {res}")
            
        profile = DhanClientService.fetch_broker_profile(client_id, token)
        actual_client_id = str(profile.get("client_id") or client_id)
        session_manager.save_session(client_id=actual_client_id, access_token=token, profile_info=profile)
        DhanClientService._reset_alert_state_on_connect(actual_client_id, profile)
        
        return {
            "status": "authenticated",
            "session_valid": True,
            "client_id": actual_client_id,
            "profile": profile
        }

    @staticmethod
    def ensure_valid_session():
        """
        Checks if token is valid or expired. If expired or missing,
        and DHAN_PIN & DHAN_TOTP_SECRET are in .env, performs automatic login.
        """
        from app.core.config import settings
        
        token = session_manager.get_token()
        client_id = settings.DHAN_CLIENT_ID or session_manager.get_client_id()
        
        # Test existing token validity
        if token and client_id:
            try:
                prof = DhanClientService.fetch_broker_profile(client_id, token)
                if prof and prof.get("user_name"):
                    DhanClientService.check_and_notify_broker_health(is_valid=True, client_id=client_id, profile=prof)
                    return True
            except Exception:
                logger.warning("Existing token invalid or expired. Attempting renewal or re-login...")
        
        # Attempt renewal if old token exists
        if token and client_id:
            try:
                login_helper = DhanLogin(client_id)
                res = login_helper.renew_token(token)
                new_token = res.get("accessToken") or res.get("data", {}).get("accessToken")
                if new_token:
                    prof = DhanClientService.fetch_broker_profile(client_id, new_token)
                    session_manager.save_session(client_id=client_id, access_token=new_token, profile_info=prof)
                    DhanClientService._reset_alert_state_on_connect(client_id, prof)
                    logger.info("Dhan session renewed successfully.")
                    return True
            except Exception as e:
                logger.warning(f"RenewToken attempt returned: {e}")

        # Attempt auto-login with PIN + TOTP if configured
        if client_id and settings.DHAN_PIN and settings.DHAN_TOTP_SECRET:
            try:
                logger.info(f"Triggering automated headless login for Dhan Client ID: {client_id}...")
                DhanClientService.login_with_pin_totp(
                    client_id=client_id,
                    pin=settings.DHAN_PIN,
                    totp_secret=settings.DHAN_TOTP_SECRET
                )
                logger.info("Automated daily headless login succeeded.")
                return True
            except Exception as err:
                logger.error(f"Automated daily login failed: {err}")
                DhanClientService.check_and_notify_broker_health(is_valid=False, client_id=client_id, profile=None)
                return False

        DhanClientService.check_and_notify_broker_health(is_valid=False, client_id=client_id, profile=None)
        return False

    @staticmethod
    def fetch_broker_profile(client_id: Optional[str] = None, access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves user profile details from Dhan profile endpoint.
        """
        if not client_id or not access_token:
            token = session_manager.get_token()
            cid = session_manager.get_client_id()
            if not token or not cid:
                raise ValueError("Broker not authenticated.")
            client_id = cid
            access_token = token

        try:
            # First attempt with DhanLogin helper
            login_helper = DhanLogin(client_id)
            res = login_helper.user_profile(access_token)
            if res and isinstance(res, dict) and (res.get("status") == "success" or "data" in res or "dhanClientId" in res):
                data = res.get("data", res)
                return {
                    "client_id": data.get("dhanClientId", client_id),
                    "user_name": data.get("userName", "Trading Account"),
                    "active_products": data.get("activeProducts", ["CNC", "INTRADAY", "MARGIN", "MTF"]),
                    "enabled_exchanges": data.get("enabledExchanges", ["NSE", "BSE", "NFO"]),
                    "token_validity": data.get("tokenValidity", "Active"),
                    "raw": data
                }
        except Exception as e:
            logger.warning(f"DhanLogin profile check returned: {e}")

        # Fallback direct HTTP check to https://api.dhan.co/v2/profile
        url = "https://api.dhan.co/v2/profile"
        headers = {
            "access-token": access_token,
            "client-id": client_id
        }
        try:
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json().get("data", resp.json())
                return {
                    "client_id": data.get("dhanClientId", client_id),
                    "user_name": data.get("userName", "Trader Admin"),
                    "active_products": data.get("activeProducts", ["CNC", "INTRADAY", "MARGIN"]),
                    "enabled_exchanges": data.get("enabledExchanges", ["NSE", "BSE", "NFO"]),
                    "token_validity": data.get("tokenValidity", "Active")
                }
            else:
                raise ValueError(f"Dhan profile returned status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"HTTP profile fallback check returned: {e}")
            raise ValueError(f"Broker token invalid or expired: {e}")

    @staticmethod
    def is_session_valid() -> bool:
        token = session_manager.get_token()
        return bool(token and len(token) > 10)

    @staticmethod
    def get_dhan_instance():
        client_id = session_manager.get_client_id()
        token = session_manager.get_token()
        if not client_id or not token:
            return None
        try:
            return dhanhq(client_id, token)
        except Exception:
            return None

    @staticmethod
    def _get_alert_state_path() -> str:
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "dhan_alert_state.json")

    @staticmethod
    def _load_alert_state() -> Dict[str, Any]:
        import os, json
        path = DhanClientService._get_alert_state_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    @staticmethod
    def _save_alert_state(state: Dict[str, Any]):
        import json
        path = DhanClientService._get_alert_state_path()
        try:
            with open(path, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save dhan_alert_state: {e}")

    @staticmethod
    def _reset_alert_state_on_connect(client_id: str, profile: Optional[Dict[str, Any]] = None):
        token_validity = (profile or {}).get("token_validity") or ((profile or {}).get("raw") or {}).get("tokenValidity") or ""
        state = {
            "last_status": "connected",
            "client_id": str(client_id or ""),
            "token_validity": str(token_validity),
            "disconnect_alert_sent": False,
            "expiry_1h_alert_sent_for": ""
        }
        DhanClientService._save_alert_state(state)

    @staticmethod
    def _dispatch_telegram_system_alert(html_msg: str):
        """
        Sends an administrative system alert via Telegram strictly to Rahul's private DM
        with @HPS_AQ_SCREENER_BOT (chat_id: 1367920205) and NEVER to the 'Aq selected' group (-5562647743)
        or other viewer accounts.
        """
        try:
            from app.core.database import SessionLocal
            from app.models.entities import TelegramSettings, User
            db = SessionLocal()
            tg_settings = db.query(TelegramSettings).first()
            if not tg_settings or not tg_settings.bot_token:
                db.close()
                return

            # Send strictly to Rahul's private chat ID (1367920205) on HPS_AQ_SCREENER_BOT
            admin_private_chat_ids = {"1367920205"}
            admin_users = db.query(User).filter(
                User.role == "admin",
                User.telegram_chat_id.isnot(None),
                User.is_active == True
            ).all()
            for u in admin_users:
                cid_str = (u.telegram_chat_id or "").strip()
                # Never send to group/channel IDs (negative IDs)
                if cid_str and not cid_str.startswith("-"):
                    admin_private_chat_ids.add(cid_str)

            bot_token = tg_settings.bot_token.strip()
            db.close()

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            for cid in admin_private_chat_ids:
                try:
                    requests.post(
                        url,
                        json={"chat_id": cid, "text": html_msg, "parse_mode": "HTML", "disable_web_page_preview": True},
                        timeout=8
                    )
                except Exception as e:
                    logger.warning(f"Failed sending Dhan status Telegram alert to {cid}: {e}")
        except Exception as e:
            logger.error(f"Error in _dispatch_telegram_system_alert: {e}")

    @staticmethod
    def check_and_notify_broker_health(is_valid: bool, client_id: Optional[str] = None, profile: Optional[Dict[str, Any]] = None):
        """
        Checks if:
        1) Dhan API connection has become disconnected/expired -> sends a one-time Telegram alert until reconnected.
        2) Dhan API token will expire within 1 hour (<= 60 mins) -> sends a one-time Telegram 1-hour expiry warning.
        """
        try:
            from datetime import datetime
            import pytz
            ist = pytz.timezone("Asia/Kolkata")
            now_ist = datetime.now(ist)
            now_str = now_ist.strftime("%d %b %Y, %I:%M %p IST")

            state = DhanClientService._load_alert_state()
            cid = client_id or state.get("client_id") or "1105208739"

            if not is_valid:
                if not state.get("disconnect_alert_sent"):
                    msg = (
                        "<b>[URGENT] AlphaQuant — Dhan Broker Disconnected</b>\n\n"
                        f"<b>Status:</b> NOT CONNECTED / TOKEN EXPIRED\n"
                        f"<b>Client ID:</b> <code>{cid}</code>\n"
                        f"<b>Time:</b> {now_str}\n\n"
                        "Your DhanHQ API session has disconnected or expired. "
                        "Please open <b>AlphaQuant Admin -> Broker Connect</b> and update your Access Token or PIN + TOTP."
                    )
                    DhanClientService._dispatch_telegram_system_alert(msg)
                    state["last_status"] = "disconnected"
                    state["disconnect_alert_sent"] = True
                    DhanClientService._save_alert_state(state)
                    logger.info("Sent Telegram alert for Dhan Broker disconnection.")
                return

            # Connection is valid: clear disconnect_alert_sent if it was previously set
            state_changed = False
            if state.get("disconnect_alert_sent") or state.get("last_status") != "connected":
                state["last_status"] = "connected"
                state["disconnect_alert_sent"] = False
                state_changed = True

            token_validity = (
                (profile or {}).get("token_validity")
                or ((profile or {}).get("raw") or {}).get("tokenValidity")
                or state.get("token_validity")
                or ""
            ).strip()

            if token_validity and token_validity != "Active":
                state["token_validity"] = token_validity
                # Parse Dhan tokenValidity format, e.g. "30/10/2026 08:26" or "30/10/2026 21:33"
                exp_dt = None
                for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                    try:
                        naive_dt = datetime.strptime(token_validity, fmt)
                        exp_dt = ist.localize(naive_dt)
                        break
                    except Exception:
                        continue

                if exp_dt is not None:
                    mins_remaining = (exp_dt - now_ist).total_seconds() / 60.0
                    # Alert when token is within 60 minutes of expiring (0 < mins_remaining <= 60)
                    if 0 < mins_remaining <= 60 and state.get("expiry_1h_alert_sent_for") != token_validity:
                        mins_int = max(1, int(round(mins_remaining)))
                        msg = (
                            "<b>[WARNING] AlphaQuant — Dhan Token Expiring in 1 Hour</b>\n\n"
                            f"<b>Status:</b> EXPIRING SOON ({mins_int} mins left)\n"
                            f"<b>Client ID:</b> <code>{cid}</code>\n"
                            f"<b>Token Expiry:</b> <code>{token_validity} IST</code>\n"
                            f"<b>Checked At:</b> {now_str}\n\n"
                            "Your DhanHQ API connection will expire in less than 1 hour. "
                            "Please renew or update your token in <b>AlphaQuant Admin -> Broker Connect</b> to avoid any feed interruption."
                        )
                        DhanClientService._dispatch_telegram_system_alert(msg)
                        state["expiry_1h_alert_sent_for"] = token_validity
                        state_changed = True
                        logger.info(f"Sent Telegram 1-hour expiry warning for Dhan token ({token_validity}).")

            if state_changed:
                DhanClientService._save_alert_state(state)
        except Exception as e:
            logger.warning(f"check_and_notify_broker_health error: {e}")
