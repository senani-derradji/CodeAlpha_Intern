from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import Optional

from security.hash_ import _pwd_ctx           # your existing hasher
from admin.admin_models import Admin
# Regular-app models — read-only, for stats/users/urls pages
from database.models import User, ShortUrl, ClickersInfo


class AdminService:
    def __init__(self, admin_db: Session, app_db: Session):
        """
        admin_db  — session from admin_db.get_db()   (url_shortener_admin.db)
        app_db    — session from database.db.get_db() (your main app db)
        """
        self.admin_db = admin_db
        self.app_db   = app_db

    # ── Auth ──────────────────────────────────────────────────────────────────

    def verify_admin_credentials(self, email: str, password: str) -> Optional[dict]:
        """
        Returns {"email", "name"} on success, None on any failure.
        Only touches the admins table.
        """
        admin: Admin | None = (
            self.admin_db.query(Admin)
            .filter(Admin.email == email, Admin.is_active == True)
            .first()
        )
        if admin is None:
            return None
        if not _pwd_ctx.verify(password, admin.hashed_password):
            return None

        admin.last_login = datetime.utcnow()
        self.admin_db.commit()

        return {"email": admin.email, "name": admin.name or admin.email}

    # ── Overview stats (reads app db) ─────────────────────────────────────────

    def get_overview_stats(self) -> dict:
        db = self.app_db
        total_users  = db.query(func.count(User.id)).scalar()
        total_urls   = db.query(func.count(ShortUrl.id)).scalar()
        active_urls  = db.query(func.count(ShortUrl.id)).filter(ShortUrl.is_active == True).scalar()
        total_clicks = db.query(func.sum(ShortUrl.clicks)).scalar() or 0

        week_ago = datetime.utcnow() - timedelta(days=7)
        new_users_week = (
            db.query(func.count(func.distinct(ShortUrl.user_id)))
            .filter(ShortUrl.created_at >= week_ago).scalar() or 0
        )
        clicks_week = (
            db.query(func.count(ClickersInfo.id))
            .filter(ClickersInfo.clicked_at >= week_ago).scalar() or 0
        )
        soon = datetime.utcnow() + timedelta(hours=24)
        expiring_soon = (
            db.query(func.count(ShortUrl.id))
            .filter(
                ShortUrl.is_active == True,
                ShortUrl.expires_at <= soon,
                ShortUrl.expires_at >= datetime.utcnow(),
            ).scalar()
        )
        return {
            "total_users":    total_users,
            "total_urls":     total_urls,
            "active_urls":    active_urls,
            "inactive_urls":  total_urls - active_urls,
            "total_clicks":   total_clicks,
            "new_users_week": new_users_week,
            "clicks_week":    clicks_week,
            "expiring_soon":  expiring_soon,
        }

    def get_clicks_per_day(self, days: int = 14) -> list[dict]:
        since = datetime.utcnow() - timedelta(days=days)

        # SQLite doesn't support cast(..., Date) reliably — use strftime instead.
        # For other databases (Postgres, MySQL) this also works fine.
        day_expr = func.strftime("%Y-%m-%d", ClickersInfo.clicked_at).label("day")

        rows = (
            self.app_db.query(day_expr, func.count(ClickersInfo.id).label("clicks"))
            .filter(ClickersInfo.clicked_at >= since)
            .group_by(day_expr)
            .order_by(day_expr)
            .all()
        )
        return [{"date": r.day, "clicks": r.clicks} for r in rows]

    def get_top_urls(self, limit: int = 10) -> list[dict]:
        rows = (
            self.app_db.query(ShortUrl)
            .order_by(desc(ShortUrl.clicks))
            .limit(limit).all()
        )
        return [self._serialize_url(u) for u in rows]

    def get_top_countries(self, limit: int = 10) -> list[dict]:
        rows = (
            self.app_db.query(ClickersInfo.country, func.count(ClickersInfo.id).label("clicks"))
            .filter(ClickersInfo.country.isnot(None))
            .group_by(ClickersInfo.country).order_by(desc("clicks")).limit(limit).all()
        )
        return [{"country": r.country, "clicks": r.clicks} for r in rows]

    def get_top_browsers(self, limit: int = 8) -> list[dict]:
        rows = (
            self.app_db.query(ClickersInfo.browser, func.count(ClickersInfo.id).label("count"))
            .filter(ClickersInfo.browser.isnot(None))
            .group_by(ClickersInfo.browser).order_by(desc("count")).limit(limit).all()
        )
        return [{"browser": r.browser, "count": r.count} for r in rows]

    def get_top_platforms(self, limit: int = 8) -> list[dict]:
        rows = (
            self.app_db.query(ClickersInfo.platform, func.count(ClickersInfo.id).label("count"))
            .filter(ClickersInfo.platform.isnot(None))
            .group_by(ClickersInfo.platform).order_by(desc("count")).limit(limit).all()
        )
        return [{"platform": r.platform, "count": r.count} for r in rows]

    # ── Users (reads app db) ──────────────────────────────────────────────────

    def get_all_users(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        role: Optional[str] = None,
    ) -> dict:
        q = self.app_db.query(User)
        if search:
            p = f"%{search}%"
            q = q.filter((User.email.ilike(p)) | (User.name.ilike(p)))
        if role:
            q = q.filter(User.role == role)
        total = q.count()
        users = q.offset((page - 1) * page_size).limit(page_size).all()
        return {
            "total": total, "page": page, "page_size": page_size,
            "users": [self._serialize_user(u) for u in users],
        }

    def get_user_detail(self, user_id: int) -> Optional[dict]:
        user = self.app_db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        urls = (
            self.app_db.query(ShortUrl)
            .filter(ShortUrl.user_id == user_id)
            .order_by(desc(ShortUrl.created_at)).all()
        )
        return {**self._serialize_user(user), "urls": [self._serialize_url(u) for u in urls]}

    def update_user_role(self, user_id: int, new_role: str) -> Optional[dict]:
        if new_role not in {"user", "admin"}:
            raise ValueError("Role must be 'user' or 'admin'")
        user = self.app_db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        user.role = new_role
        self.app_db.commit()
        self.app_db.refresh(user)
        return self._serialize_user(user)

    def delete_user(self, user_id: int) -> bool:
        user = self.app_db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        self.app_db.query(ShortUrl).filter(ShortUrl.user_id == user_id).update({"is_active": False})
        self.app_db.delete(user)
        self.app_db.commit()
        return True

    # ── URLs (reads app db) ───────────────────────────────────────────────────

    def get_all_urls(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        active_only: Optional[bool] = None,
        user_id: Optional[int] = None,
    ) -> dict:
        q = self.app_db.query(ShortUrl)
        if search:
            p = f"%{search}%"
            q = q.filter(
                (ShortUrl.original_url.ilike(p)) | (ShortUrl.short_code.ilike(p))
            )
        if active_only is not None:
            q = q.filter(ShortUrl.is_active == active_only)
        if user_id is not None:
            q = q.filter(ShortUrl.user_id == user_id)
        total = q.count()
        urls  = q.order_by(desc(ShortUrl.created_at)).offset((page-1)*page_size).limit(page_size).all()
        return {
            "total": total, "page": page, "page_size": page_size,
            "urls": [self._serialize_url(u) for u in urls],
        }

    def get_url_detail(self, url_id: int) -> Optional[dict]:
        url = self.app_db.query(ShortUrl).filter(ShortUrl.id == url_id).first()
        if not url:
            return None
        clickers = (
            self.app_db.query(ClickersInfo)
            .filter(ClickersInfo.short_url_id == url_id)
            .order_by(desc(ClickersInfo.clicked_at)).limit(100).all()
        )
        return {**self._serialize_url(url), "clickers": [self._serialize_clicker(c) for c in clickers]}

    def toggle_url_active(self, url_id: int) -> Optional[dict]:
        url = self.app_db.query(ShortUrl).filter(ShortUrl.id == url_id).first()
        if not url:
            return None
        url.is_active = not url.is_active
        self.app_db.commit()
        self.app_db.refresh(url)
        return self._serialize_url(url)

    def admin_delete_url(self, url_id: int) -> bool:
        url = self.app_db.query(ShortUrl).filter(ShortUrl.id == url_id).first()
        if not url:
            return False
        self.app_db.delete(url)
        self.app_db.commit()
        return True

    # ── Serializers ───────────────────────────────────────────────────────────

    @staticmethod
    def _serialize_user(u: User) -> dict:
        return {
            "id":        u.id,
            "email":     u.email,
            "name":      u.name,
            "picture":   u.picture,
            "role":      u.role,
            "url_count": len(u.short_urls) if u.short_urls is not None else 0,
        }

    @staticmethod
    def _serialize_url(u: ShortUrl) -> dict:
        return {
            "id":           u.id,
            "original_url": u.original_url,
            "short_code":   u.short_code,
            "clicks":       u.clicks,
            "is_active":    u.is_active,
            "created_at":   u.created_at.isoformat() if u.created_at else None,
            "expires_at":   u.expires_at.isoformat() if u.expires_at else None,
            "user_id":      u.user_id,
        }

    @staticmethod
    def _serialize_clicker(c: ClickersInfo) -> dict:
        return {
            "id":         c.id,
            "ip":         c.ip,
            "browser":    c.browser,
            "platform":   c.platform,
            "country":    c.country,
            "city":       c.city,
            "clicked_at": c.clicked_at.isoformat() if c.clicked_at else None,
        }