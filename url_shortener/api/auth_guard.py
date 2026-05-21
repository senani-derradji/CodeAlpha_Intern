import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException
from config.settings import Info


class AuthGuard:

    @staticmethod
    async def require_auth(request: Request):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")

        token = auth_header[7:]

        try:
            payload = jwt.decode(token, Info.SECRET_KEY, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    @staticmethod
    def create_access_token(data: dict, expires_minutes: int = 60) -> str:
        payload = data.copy()
        payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        return jwt.encode(payload, Info.SECRET_KEY, algorithm="HS256")