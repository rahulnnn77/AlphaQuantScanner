from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, is_legacy_hash, create_access_token
from app.core.session_store import session_manager
from app.models.entities import User
from app.schemas.schemas import (
    AppLoginRequest,
    AppLoginResponse,
    DhanLoginRequest,
    DhanLoginResponse,
    SessionStatusResponse
)
from app.services.dhan_service import DhanClientService
from app.services.screener_engine import ScreenerEngine
from app.api.deps import get_current_user, require_admin

router = APIRouter()

@router.post("/login", response_model=AppLoginResponse)
def login_user(req: AppLoginRequest, db: Session = Depends(get_db)):
    """
    Standard application login for both Admin and Viewers.
    Transparently upgrades legacy SHA-256 password hashes to bcrypt on login.
    """
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated"
        )
    if is_legacy_hash(user.hashed_password):
        user.hashed_password = get_password_hash(req.password)
        db.commit()
    
    token = create_access_token(subject=user.username, role=user.role)
    return AppLoginResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        username=user.username
    )

@router.post("/dhan-login", response_model=DhanLoginResponse)
def dhan_broker_login(req: DhanLoginRequest, admin_user: User = Depends(require_admin)):
    """
    Admin-only: Exchanges or saves Dhan API credentials securely.
    Supports both direct Access Token / OAuth and PIN + TOTP generation.
    Raw tokens are NEVER returned in response.
    """
    try:
        if req.pin and req.totp:
            res = DhanClientService.login_with_pin_totp(
                client_id=req.api_key.strip(),
                pin=req.pin.strip(),
                totp_secret=req.totp.strip()
            )
        else:
            res = DhanClientService.authenticate_broker(
                client_id=req.api_key,
                api_secret=req.api_secret,
                request_token=req.request_token
            )
        return DhanLoginResponse(
            status="authenticated",
            session_valid=True,
            message="Broker session established and securely cached.",
            client_id=res.get("client_id")
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dhan authentication failed: {str(e)}"
        )

@router.get("/session-status", response_model=SessionStatusResponse)
def check_session_status(current_user: User = Depends(get_current_user)):
    """
    Checks if a persistent Dhan session is cached on the backend,
    verifies live broker connectivity, and checks Indian Market trading hours.
    Requires authenticated user; masks raw client_id for non-admin users.
    """
    # Ensure session is active or auto-renewed/auto-logged in via .env credentials
    is_valid = DhanClientService.ensure_valid_session()
    session_data = session_manager.load_session()
    prof_info = (session_data.get("profile") or session_data.get("profile_info") or {}) if session_data else {}
    raw_info = prof_info.get("raw") or {}
    raw_cid = session_data.get("client_id") if (is_valid and session_data) else None
    display_cid = raw_cid if (current_user.role == "admin") else ("CONNECTED" if raw_cid else None)
    return SessionStatusResponse(
        authenticated=bool(is_valid and session_data and session_data.get("access_token")),
        client_id=display_cid,
        last_updated=session_data.get("updated_at") if session_data else None,
        token_validity=(prof_info.get("token_validity") or prof_info.get("tokenValidity") or raw_info.get("tokenValidity")) if is_valid else None,
        active_segment=(raw_info.get("activeSegment") or ", ".join(prof_info.get("enabled_exchanges", []))) if is_valid else None,
        data_plan=(raw_info.get("dataPlan") or "Active") if is_valid else None,
        market_open=ScreenerEngine.is_market_open()
    )

@router.post("/dhan-logout")
def dhan_broker_logout(admin_user: User = Depends(require_admin)):
    """
    Admin-only: Clears cached broker credentials and notifies on Telegram.
    """
    cid = session_manager.get_client_id()
    session_manager.clear_session()
    DhanClientService.check_and_notify_broker_health(is_valid=False, client_id=cid, profile=None)
    return {"status": "cleared", "message": "Dhan broker session cleared successfully"}
