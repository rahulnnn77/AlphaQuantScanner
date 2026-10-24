from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.models.entities import User
from app.services.dhan_service import DhanClientService
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/")
def get_user_broker_profile(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Fetches the broker account profile details.
    Client IDs and broker branding are sanitized and masked for security.
    """
    try:
        profile = DhanClientService.fetch_broker_profile()
        sanitized_profile = {
            "user_name": current_user.username.capitalize() if current_user.username else "Trader",
            "active_products": profile.get("active_products", ["CNC", "INTRADAY", "MARGIN", "MTF"]),
            "enabled_exchanges": profile.get("enabled_exchanges", ["NSE", "BSE", "NFO"]),
            "token_validity": "Active"
        }
        return {
            "status": "success",
            "app_user": current_user.username,
            "app_role": current_user.role,
            "dhan_profile": sanitized_profile
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to fetch profile: {str(e)}"
        )
