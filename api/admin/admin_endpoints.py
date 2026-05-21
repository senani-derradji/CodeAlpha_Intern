from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, EmailStr

from admin.admin_db import get_db as get_admin_db       # admin SQLite
from database.db import get_db as get_app_db            # main app db
from admin.admin_service import AdminService
from api.routers.auth_guard import AuthGuard


# ── Auth dependency ───────────────────────────────────────────────────────────
async def require_admin(payload=Depends(AuthGuard.require_auth)):
    """JWT must carry role='admin' — issued only by POST /admin/."""
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


# ── Helper: build service with both sessions ─────────────────────────────────
def get_svc(
    admin_db: Session = Depends(get_admin_db),
    app_db:   Session = Depends(get_app_db),
) -> AdminService:
    return AdminService(admin_db=admin_db, app_db=app_db)


# ── Request body ──────────────────────────────────────────────────────────────
class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str

router = APIRouter()


# POST /admin/  ── public, no auth required
@router.post("/", summary="Admin login")
async def admin_login(
    body: AdminLoginRequest,
    svc: AdminService = Depends(get_svc),
):
    result = svc.verify_admin_credentials(body.email, body.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    token = AuthGuard.create_access_token({
        "email": result["email"],
        "name":  result["name"],
        "role":  "admin",
    })
    return {"access_token": token, "token_type": "bearer"}


# ── Stats ─────────────────────────────────────────────────────────────────────
@router.get("/stats", summary="Dashboard KPIs")
async def get_stats(
    _=Depends(require_admin),
    svc: AdminService = Depends(get_svc),
):
    return svc.get_overview_stats()


@router.get("/stats/clicks-per-day", summary="Daily click chart")
async def get_clicks_per_day(
    days: int = Query(default=14, ge=1, le=90),
    _=Depends(require_admin),
    svc: AdminService = Depends(get_svc),
):
    return svc.get_clicks_per_day(days=days)


@router.get("/stats/geo", summary="Country / browser / platform breakdown")
async def get_geo_stats(
    _=Depends(require_admin),
    svc: AdminService = Depends(get_svc),
):
    return {
        "countries": svc.get_top_countries(),
        "browsers":  svc.get_top_browsers(),
        "platforms": svc.get_top_platforms(),
    }


@router.get("/stats/top-urls", summary="Top URLs by clicks")
async def get_top_urls(
    limit: int = Query(default=10, ge=1, le=50),
    _=Depends(require_admin),
    svc: AdminService = Depends(get_svc),
):
    return svc.get_top_urls(limit=limit)


# ── Users ─────────────────────────────────────────────────────────────────────
@router.get("/users", summary="Paginated user list")
async def get_users(
    page:      int           = Query(default=1, ge=1),
    page_size: int           = Query(default=20, ge=1, le=100),
    search:    Optional[str] = Query(default=None),
    role:      Optional[str] = Query(default=None),
    _=Depends(require_admin),
    svc: AdminService = Depends(get_svc),
):
    return svc.get_all_users(page=page, page_size=page_size, search=search, role=role)


@router.get("/users/{user_id}", summary="Single user + their URLs")
async def get_user_detail(
    user_id: int,
    _=Depends(require_admin),
    svc: AdminService = Depends(get_svc),
):
    result = svc.get_user_detail(user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@router.patch("/users/{user_id}/role", summary="Promote / demote user")
async def update_user_role(
    user_id: int,
    request: Request,
    _=Depends(require_admin),
    svc: AdminService = Depends(get_svc),
):
    body = await request.json()
    new_role = body.get("role")
    if not new_role:
        raise HTTPException(status_code=422, detail="Field 'role' is required")
    try:
        result = svc.update_user_role(user_id, new_role)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if result is None:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@router.delete("/users/{user_id}", summary="Hard-delete user")
async def delete_user(
    user_id: int,
    _=Depends(require_admin),
    svc: AdminService = Depends(get_svc),
):
    if not svc.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}


# ── URLs ──────────────────────────────────────────────────────────────────────
@router.get("/urls", summary="Paginated URL list")
async def get_urls(
    page:       int            = Query(default=1, ge=1),
    page_size:  int            = Query(default=20, ge=1, le=100),
    search:     Optional[str]  = Query(default=None),
    active_only: Optional[bool]= Query(default=None),
    user_id:    Optional[int]  = Query(default=None),
    _=Depends(require_admin),
    svc: AdminService = Depends(get_svc),
):
    return svc.get_all_urls(
        page=page, page_size=page_size,
        search=search, active_only=active_only, user_id=user_id,
    )


@router.get("/urls/{url_id}", summary="Single URL + click log")
async def get_url_detail(
    url_id: int,
    _=Depends(require_admin),
    svc: AdminService = Depends(get_svc),
):
    result = svc.get_url_detail(url_id)
    if result is None:
        raise HTTPException(status_code=404, detail="URL not found")
    return result


@router.patch("/urls/{url_id}/toggle", summary="Activate / deactivate URL")
async def toggle_url(
    url_id: int,
    _=Depends(require_admin),
    svc: AdminService = Depends(get_svc),
):
    result = svc.toggle_url_active(url_id)
    if result is None:
        raise HTTPException(status_code=404, detail="URL not found")
    return result


@router.delete("/urls/{url_id}", summary="Hard-delete URL")
async def delete_url(
    url_id: int,
    _=Depends(require_admin),
    svc: AdminService = Depends(get_svc),
):
    if not svc.admin_delete_url(url_id):
        raise HTTPException(status_code=404, detail="URL not found")
    return {"message": "URL deleted"}