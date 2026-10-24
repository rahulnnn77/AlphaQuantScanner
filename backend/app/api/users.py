from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.entities import User
from app.schemas.schemas import UserCreateRequest, UserUpdateRequest, UserResponse
from app.api.deps import require_admin, get_current_user

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Admin-only: Retrieve all users."""
    return db.query(User).all()

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
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
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
    db.delete(user)
    db.commit()
    return {"status": "deleted", "user_id": user_id}
