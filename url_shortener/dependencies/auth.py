from fastapi import Depends

from api.auth_guard import AuthGuard


async def get_current_user(
    user=Depends(AuthGuard.require_auth)
):
    return user