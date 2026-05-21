# api/auth_google.py

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from config.settings import Info
from services.users_service import UserOperations
import httpx
import jwt
import time


class GoogleAuthAPI:

    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

    def __init__(self):
        self.router = APIRouter()
        self.client_id = Info.GOOGLE_CLIENT_ID
        self.client_secret = Info.GOOGLE_CLIENT_SECRET
        self.redirect_uri = Info.GOOGLE_REDIRECT_URI
        self.user_ops = UserOperations()

        self.router.add_api_route("/google", self.login_google, methods=["GET"])
        self.router.add_api_route("/google/callback", self.auth_google_callback, methods=["GET"])
        self.router.add_api_route("/me", self.auth_me, methods=["GET"])
        self.router.add_api_route("/logout", self.logout, methods=["GET"])

    async def login_google(self, request: Request):
        import secrets
        from urllib.parse import urlencode

        state = secrets.token_urlsafe(32)

        state_token = jwt.encode(
            {"state": state, "exp": time.time() + 300},
            Info.SECRET_KEY,
            algorithm="HS256"
        )

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state_token,
            "access_type": "offline",
            "prompt": "consent",
        }
        url = self.GOOGLE_AUTH_URL + "?" + urlencode(params)
        return RedirectResponse(url=url)

    async def auth_google_callback(self, request: Request):
        from urllib.parse import urlencode

        code = request.query_params.get("code")
        state_token = request.query_params.get("state")

        # Verify state by decoding the signed JWT — no session needed
        try:
            jwt.decode(state_token, Info.SECRET_KEY, algorithms=["HS256"])
        except jwt.InvalidTokenError:
            return {"error": "State mismatch"}

        async with httpx.AsyncClient() as client:

            token_response = await client.post(
                self.GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_data = token_response.json()

            if "access_token" not in token_data:
                return {"error": "Failed to obtain access token", "details": token_data}

            userinfo_response = await client.get(
                self.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
            )
            user = userinfo_response.json()

        user_data = {
            "email": user["email"],
            "name": user["name"],
            "picture": user.get("picture", ""),
        }

        await self.user_ops.create_user(**user_data)

        payload = {
            **user_data,
            "exp": time.time() + (7 * 24 * 60 * 60)
        }
        token = jwt.encode(payload, Info.SECRET_KEY, algorithm="HS256")

        params = urlencode({
            "loggedin": "1",
            "token": token,
        })
        FRONTEND_URL = Info.DOMAIN
        return RedirectResponse(url=f"{FRONTEND_URL}?{params}")

    async def auth_me(self, request: Request):
        print()
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, Info.SECRET_KEY, algorithms=["HS256"])
            return {
                "email": payload["email"],
                "name": payload["name"],
                "picture": payload.get("picture", "")
            }
        except jwt.InvalidTokenError:
            return None

    async def logout(self, request: Request):
        request.session.clear()
        return {"message": "Logged out successfully"}