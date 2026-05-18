from fastapi import Request, HTTPException


class AuthGuard:

    @staticmethod
    async def require_auth(request: Request):

        user = request.session.get("user")

        if not user:

            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )

        return user