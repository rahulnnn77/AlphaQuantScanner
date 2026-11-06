import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, is_legacy_hash, create_access_token
from app.core.session_store import session_manager
from app.models.entities import User, AccessRequest, AuditLog
from app.schemas.schemas import (
    AppLoginRequest,
    AppLoginResponse,
    DhanLoginRequest,
    DhanLoginResponse,
    SessionStatusResponse,
    UserRegisterRequest,
    UserRegisterResponse
)
from app.services.dhan_service import DhanClientService
from app.services.screener_engine import ScreenerEngine
from app.api.deps import get_current_user, require_admin

router = APIRouter()

@router.post("/register", response_model=UserRegisterResponse)
def register_user(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    Public registration endpoint.
    Creates account with status='PENDING' and logs an AccessRequest for administrator review.
    """
    email_clean = req.email.strip().lower()
    phone_clean = re.sub(r'[^0-9+]', '', req.phone_number.strip())
    
    # Generate canonical username from email prefix or full name
    candidate_username = email_clean.split('@')[0]
    # Check if user already exists with this email or username
    existing_email = db.query(User).filter(User.email == email_clean).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account is already associated with this email address."
        )

    # Ensure unique username
    base_username = re.sub(r'[^a-zA-Z0-9_]', '', candidate_username) or "trader"
    final_username = base_username
    counter = 1
    while db.query(User).filter(User.username == final_username).first():
        final_username = f"{base_username}{counter}"
        counter += 1

    # Create new User with status='PENDING'
    new_user = User(
        username=final_username,
        email=email_clean,
        full_name=req.full_name.strip(),
        phone_number=phone_clean,
        organization=req.organization.strip() if req.organization else None,
        hashed_password=get_password_hash(req.password),
        role="viewer",
        status="PENDING",
        is_active=True,
        email_verified=True,
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create AccessRequest record
    access_req = AccessRequest(
        user_id=new_user.id,
        full_name=new_user.full_name,
        email=new_user.email,
        phone_number=new_user.phone_number,
        organization=new_user.organization,
        status="PENDING",
        created_at=datetime.utcnow()
    )
    db.add(access_req)
    db.commit()

    return UserRegisterResponse(
        status="success",
        message="Your AlphaQuant account has been created successfully. Your access request is currently under review. You will receive access once approved by the administrator.",
        username=new_user.username,
        email=new_user.email,
        account_status="PENDING"
    )

@router.post("/login", response_model=AppLoginResponse)
def login_user(req: AppLoginRequest, db: Session = Depends(get_db)):
    """
    Standard application login for both Admin and Viewers.
    Strictly verifies account approval status: APPROVED, PENDING, REJECTED, SUSPENDED.
    Supports login via username or email.
    """
    login_ident = req.username.strip()
    user = db.query(User).filter(
        (User.username == login_ident) | (User.email == login_ident.lower())
    ).first()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password"
        )

    # 1. Check Account Approval Status
    account_status = getattr(user, "status", "APPROVED") or "APPROVED"
    if account_status == "PENDING":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your AlphaQuant account is currently under review. You will be able to access the terminal once an administrator approves your access request."
        )
    elif account_status == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account access request has been reviewed and declined. Please contact support or the administrator for inquiries."
        )
    elif account_status == "SUSPENDED" or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been temporarily suspended by the platform administrator. Access to market research tools is revoked."
        )

    if is_legacy_hash(user.hashed_password):
        user.hashed_password = get_password_hash(req.password)
        db.commit()

    user.last_login = datetime.utcnow()
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
