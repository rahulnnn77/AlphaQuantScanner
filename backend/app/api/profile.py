from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.models.entities import User
from app.services.dhan_service import DhanClientService
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/")
def get_user_broker_profile(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Fetches the broker account profile details from Dhan:
    - User Name
    - User ID / Client ID
    - Active Products (badges: CNC, INTRADAY, MARGIN, MTF)
    - Enabled Exchanges (badges: NSE, BSE, NFO)
    """
    try:
        profile = DhanClientService.fetch_broker_profile()
        return {
            "status": "success",
            "app_user": current_user.username,
            "app_role": current_user.role,
            "dhan_profile": profile
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to fetch Dhan profile: {str(e)}"
        )
