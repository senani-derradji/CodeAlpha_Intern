from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from api.url_endpoints import UrlShortenerAPI
from api.auth_google import GoogleAuthAPI
from database.db import init_db
from starlette.middleware.sessions import SessionMiddleware
from utils.create_super_users import create_admin_user


from middleware.session_middleware import (
    register_session_middleware
)

from middleware.cors_middleware import (
    register_cors_middleware
)



@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    create_admin_user(
        email="admin@admin.admin",
        picture="admin_picture.jpg",
        name="Admin",
    )
    yield


app = FastAPI(lifespan=lifespan)

register_session_middleware(app)
register_cors_middleware(app)


router_url_shortener = UrlShortenerAPI()
router_auth_google = GoogleAuthAPI()


app.include_router(router_url_shortener.router, prefix="")
app.include_router(router_auth_google.router, prefix="")