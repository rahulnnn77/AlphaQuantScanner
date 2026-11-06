from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.entities import User, AccessRequest, AuditLog
from app.schemas.schemas import (
    UserCreateRequest,
    UserUpdateRequest,
    UserResponse,
    AccessRequestResponse,
    AccessDecisionRequest
)
from app.api.deps import require_admin, get_current_user

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin-only: Retrieve all users."""
    return db.query(User).order_by(User.id.desc()).all()

@router.post("/", response_model=UserResponse)
def create_user(req: UserCreateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin-only: Create new viewer or admin user."""
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    new_user = User(
        username=req.username,
        email=req.email,
        hashed_password=get_password_hash(req.password),
        role=req.role if req.role in ["admin", "viewer"] else "viewer",
        status="APPROVED",
        is_active=True,
        email_verified=True,
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Log audit entry
    audit = AuditLog(
        admin_username=admin.username,
        action="CREATE_USER",
        target_user_id=new_user.id,
        target_username=new_user.username,
        details=f"Admin created user with role {new_user.role}",
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    db.commit()

    return new_user

@router.patch("/{user_id}", response_model=UserResponse)
def update_user(user_id: int, req: UserUpdateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin-only: Update user status, role, or reset password."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if req.is_active is not None:
        user.is_active = req.is_active
    if req.role is not None and req.role in ["admin", "viewer"]:
        user.role = req.role
    if req.password:
        user.hashed_password = get_password_hash(req.password)
        
    db.commit()
    db.refresh(user)
    return user

@router.delete("/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin-only: Delete user."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own admin account")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Also delete associated access requests
    db.query(AccessRequest).filter(AccessRequest.user_id == user_id).delete()
    db.delete(user)
    db.commit()

    # Log audit entry
    audit = AuditLog(
        admin_username=admin.username,
        action="DELETE_USER",
        target_user_id=user_id,
        target_username=user.username,
        details="Admin permanently deleted user account",
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    db.commit()

    return {"status": "deleted", "user_id": user_id}

# =========================================================================
# ACCESS REQUEST & APPROVAL WORKFLOW ENDPOINTS
# =========================================================================

@router.get("/access-requests", response_model=List[AccessRequestResponse])
def get_access_requests(
    status_filter: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin-only: List all access requests, optionally filtered by status ('PENDING', 'APPROVED', 'REJECTED', 'SUSPENDED').
    """
    query = db.query(AccessRequest)
    if status_filter:
        query = query.filter(AccessRequest.status == status_filter.upper())
    return query.order_by(AccessRequest.id.desc()).all()

@router.get("/access-requests/summary")
def get_access_requests_summary(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin-only: Summary counts of pending, approved, and rejected access requests.
    Used for notification badges and real-time dashboard counters.
    """
    pending = db.query(AccessRequest).filter(AccessRequest.status == "PENDING").count()
    approved = db.query(AccessRequest).filter(AccessRequest.status == "APPROVED").count()
    rejected = db.query(AccessRequest).filter(AccessRequest.status == "REJECTED").count()
    suspended = db.query(User).filter(User.status == "SUSPENDED").count()
    
    # Get latest 5 pending requests for quick notification preview
    recent_pending = db.query(AccessRequest).filter(AccessRequest.status == "PENDING").order_by(AccessRequest.id.desc()).limit(5).all()
    recent_pending_data = [
        {
            "id": r.id,
            "full_name": r.full_name,
            "email": r.email,
            "created_at": r.created_at.strftime("%d %b %Y, %I:%M %p") if r.created_at else ""
        } for r in recent_pending
    ]

    return {
        "pending_count": pending,
        "approved_count": approved,
        "rejected_count": rejected,
        "suspended_count": suspended,
        "recent_pending": recent_pending_data
    }

@router.post("/access-requests/{request_id}/approve")
def approve_access_request(
    request_id: int,
    decision: Optional[AccessDecisionRequest] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin-only: Approve a pending access request.
    Transitions User.status from 'PENDING' to 'APPROVED', enabling terminal login.
    """
    req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Access request not found")

    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Associated user account not found")

    # Update request
    req.status = "APPROVED"
    req.decision_by = admin.username
    req.decision_at = datetime.utcnow()
    req.decision_notes = decision.notes if decision else None

    # Update User account status
    user.status = "APPROVED"
    user.is_active = True
    db.commit()

    # Log audit entry
    audit = AuditLog(
        admin_username=admin.username,
        action="APPROVE_USER",
        target_user_id=user.id,
        target_username=user.username,
        details=f"Approved access for {user.full_name or user.username} ({user.email})",
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Access granted to {user.full_name or user.username}.",
        "user_id": user.id,
        "account_status": user.status
    }

@router.post("/access-requests/{request_id}/reject")
def reject_access_request(
    request_id: int,
    decision: Optional[AccessDecisionRequest] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin-only: Reject a pending access request.
    Transitions User.status to 'REJECTED' preventing login.
    """
    req = db.query(AccessRequest).filter(AccessRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Access request not found")

    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Associated user account not found")

    # Update request
    req.status = "REJECTED"
    req.decision_by = admin.username
    req.decision_at = datetime.utcnow()
    req.decision_notes = decision.notes if decision else None

    # Update User account status
    user.status = "REJECTED"
    user.is_active = False
    db.commit()

    # Log audit entry
    audit = AuditLog(
        admin_username=admin.username,
        action="REJECT_USER",
        target_user_id=user.id,
        target_username=user.username,
        details=f"Rejected access request for {user.full_name or user.username} ({user.email})",
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    db.commit()

    return {
        "status": "success",
        "message": f"Access request for {user.full_name or user.username} has been rejected.",
        "user_id": user.id,
        "account_status": user.status
    }

@router.post("/{user_id}/suspend")
def suspend_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin-only: Immediately suspend an active account.
    """
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot suspend your own admin account")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = "SUSPENDED"
    user.is_active = False
    
    # Also mark any access requests as SUSPENDED
    db.query(AccessRequest).filter(AccessRequest.user_id == user_id).update({"status": "SUSPENDED"})
    db.commit()

    # Log audit entry
    audit = AuditLog(
        admin_username=admin.username,
        action="SUSPEND_USER",
        target_user_id=user.id,
        target_username=user.username,
        details=f"Suspended account access for {user.username}",
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "message": f"User {user.username} has been suspended.", "account_status": "SUSPENDED"}

@router.post("/{user_id}/reinstate")
def reinstate_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin-only: Reinstate a suspended or rejected account back to APPROVED.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.status = "APPROVED"
    user.is_active = True
    
    db.query(AccessRequest).filter(AccessRequest.user_id == user_id).update({"status": "APPROVED"})
    db.commit()

    # Log audit entry
    audit = AuditLog(
        admin_username=admin.username,
        action="REINSTATE_USER",
        target_user_id=user.id,
        target_username=user.username,
        details=f"Reinstated approved terminal access for {user.username}",
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "message": f"User {user.username} has been reinstated.", "account_status": "APPROVED"}

@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 50,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Admin-only: Retrieve administrative audit history.
    """
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "admin_username": l.admin_username,
            "action": l.action,
            "target_user_id": l.target_user_id,
            "target_username": l.target_username,
            "details": l.details,
            "timestamp": l.timestamp.strftime("%d %b %Y, %I:%M:%S %p") if l.timestamp else ""
        } for l in logs
    ]
