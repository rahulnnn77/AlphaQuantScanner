from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
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
from app.api.deps import require_admin

router = APIRouter()

@router.post("/login", response_model=AppLoginResponse)
def login_user(req: AppLoginRequest, db: Session = Depends(get_db)):
    """
    Standard application login for both Admin and Viewers.
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
    Raw tokens are NEVER returned in response.
    """
    try:
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
def check_session_status():
    """
    Checks if a persistent Dhan session is cached on the backend
    and checks live Indian Market trading hours.
    """
    # Ensure session is active or auto-renewed/auto-logged in via .env credentials
    DhanClientService.ensure_valid_session()
    
    session_data = session_manager.load_session()
    is_authed = bool(session_data and session_data.get("access_token"))
    return SessionStatusResponse(
        authenticated=is_authed,
        client_id=session_data.get("client_id") if session_data else None,
        last_updated=session_data.get("updated_at") if session_data else None,
        market_open=ScreenerEngine.is_market_open()
    )

@router.post("/dhan-logout")
def dhan_broker_logout(admin_user: User = Depends(require_admin)):
    """
    Admin-only: Clears cached broker credentials.
    """
    session_manager.clear_session()
    return {"status": "cleared", "message": "Dhan broker session cleared successfully"}
