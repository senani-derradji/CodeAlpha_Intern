from fastapi import FastAPI
from contextlib import asynccontextmanager
from api.url_endpoints import UrlShortenerAPI
from api.auth_google import GoogleAuthAPI
from database.db import init_db
from utils.create_super_users import create_admin_user
from admin.admin_endpoints import router as admin_router
from admin.admin_db import init_db as init_admin_db

# from api.admin_endpoints import AdminAPI

from middleware.session_middleware import (
    register_session_middleware
)

from middleware.cors_middleware import (
    register_cors_middleware
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    create_admin_user()
    yield

app = FastAPI(lifespan=lifespan)

register_cors_middleware(app)      # ← CORS
register_session_middleware(app)   # ← Session


router_url_shortener = UrlShortenerAPI()
router_auth_google = GoogleAuthAPI()
# router_admin = AdminAPI()

app.include_router(router_url_shortener.router, prefix="/url")
app.include_router(router_auth_google.router, prefix="/auth")
app.include_router(admin_router, prefix="/admin")