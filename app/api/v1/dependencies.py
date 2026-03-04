from fastapi import Depends, HTTPException

from app.api.v1.routes_users import get_current_user
from app.models.user import User


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Solo administradores")
    return current_user
