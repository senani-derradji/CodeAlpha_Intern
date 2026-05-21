from fastapi import FastAPI
from contextlib import asynccontextmanager

import os , sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.routers.url_endpoints import UrlShortenerAPI
from api.routers.auth_google import GoogleAuthAPI
from api.database.db import init_db
from api.utils.create_super_users import create_admin_user
from api.admin.admin_endpoints import router as admin_router
from api.admin.admin_db import init_db as init_admin_db
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from fastapi import HTTPException

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


register_cors_middleware(app)
register_session_middleware(app)


router_url_shortener = UrlShortenerAPI()
router_auth_google = GoogleAuthAPI()
# router_admin = AdminAPI()

app.include_router(router_url_shortener.router, prefix="/url")
app.include_router(router_auth_google.router, prefix="/auth")
app.include_router(admin_router, prefix="/admin")


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Serve static frontend files (html, css, js)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def root():
    return FileResponse(FRONTEND_DIR / "index.html")


from fastapi import Request
@app.get("/derradji")
def admin(request: Request):
    client_ip = request.client.host
    print("Client IP:", client_ip)

    allowed_ips = ["105.235.135.122", "127.0.0.1", "::1"]

    if not client_ip.startswith("105.") or client_ip not in allowed_ips:
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(FRONTEND_DIR / "admin.html")

@app.get("/admin.html")
async def admin_page():
    # You must RAISE the exception, not return it
    raise HTTPException(
        status_code=403,
        detail="Access denied to this resource"
    )