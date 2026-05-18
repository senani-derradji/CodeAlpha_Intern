# api/auth_google.py

from fastapi import APIRouter, Request
from authlib.integrations.starlette_client import OAuth

from config.settings import Info
from services.users_service import UserOperations




class GoogleAuthAPI:

    def __init__(self):

        self.router = APIRouter()

        self.client_id = Info.GOOGLE_CLIENT_ID
        self.client_secret = Info.GOOGLE_CLIENT_SECRET
        self.redirect_uri = Info.GOOGLE_REDIRECT_URI

        self.user_ops = UserOperations()

        self.oauth = OAuth()

        self.oauth.register(
            name="google",

            client_id=self.client_id,

            client_secret=self.client_secret,

            server_metadata_url=(
                "https://accounts.google.com/"
                ".well-known/openid-configuration"
            ),

            client_kwargs={
                "scope": "openid email profile"
            }
        )

        self.router.add_api_route(
            "/auth/google",
            self.login_google,
            methods=["GET"]
        )

        self.router.add_api_route(
            "/auth/google/callback",
            self.auth_google_callback,
            methods=["GET"]
        )

        self.router.add_api_route(
            "/logout",
            self.logout,
            methods=["GET"]
        )

    async def login_google(
        self,
        request: Request
    ):

        return await self.oauth.google.authorize_redirect(
            request,
            self.redirect_uri
        )

    async def auth_google_callback(
        self,
        request: Request
    ):

        token = await self.oauth.google.authorize_access_token(
            request
        )

        user = token["userinfo"]

        request.session["user"] = {
            "email": user["email"],
            "name": user["name"],
            "picture": user["picture"]
        }

        await self.user_ops.create_user(
            email=user["email"],
            name=user["name"],
            picture=user["picture"],
        )

        return {
            "message": "Login successful",
            "user": request.session["user"],
            "user_data": user
        }

    async def logout(
        self,
        request: Request
    ):

        request.session.clear()

        return {
            "message": "Logged out successfully"
        }