import os
import sys
import time
import pytest
import jwt
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

# ── make the repo root importable ────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── set env vars BEFORE any app module is imported ───────────────────────────
os.environ["DATABASE_URL"]       = "sqlite:///:memory:"
os.environ["DATABASE_URL_ADMIN"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"]         = "test-secret"
os.environ["REDIS_HOST"]         = "localhost"
os.environ["REDIS_PORT"]         = "6379"
os.environ["REDIS_USERNAME"]     = "default"
os.environ["REDIS_PASSWORD"]     = ""
os.environ["DOMAIN"]             = "http://testserver"
os.environ["ADMIN_EMAIL"]        = "admin@test.com"
os.environ["ADMIN_PASSWORD"]     = "adminpass"

# ─────────────────────────────────────────────────────────────────────────────
# Stub third-party packages that may not be installed in the test environment,
# and fix bare-import paths used inside the app (e.g. `from config.settings
# import Info` instead of `from api.config.settings import Info`).
# All of this must happen BEFORE any api.* module is imported.
# ─────────────────────────────────────────────────────────────────────────────
import types
import importlib

if "redis" not in sys.modules:
    _redis_stub = types.ModuleType("redis")
    _redis_stub.Redis = MagicMock
    sys.modules["redis"] = _redis_stub

# 2. Stub `dotenv` (used by config/settings.py via `from dotenv import load_dotenv`)
if "dotenv" not in sys.modules:
    _dotenv_stub = types.ModuleType("dotenv")
    _dotenv_stub.load_dotenv = lambda *a, **kw: None
    sys.modules["dotenv"] = _dotenv_stub

# 3. Stub `requests` (used by urls_service.py for geo-IP lookups)
if "requests" not in sys.modules:
    _requests_stub = types.ModuleType("requests")
    _requests_stub.get = MagicMock(return_value=MagicMock(json=MagicMock(return_value={})))
    sys.modules["requests"] = _requests_stub

# 4. The app uses bare imports like `from config.settings import Info` when
#    run as a package. Mirror every internal bare-name into sys.modules so
#    those imports resolve to the same objects as `api.config.*` etc.

def _alias(bare: str, full: str):
    """Register sys.modules[bare] = sys.modules[full] (importing full first)."""
    if bare not in sys.modules:
        try:
            mod = importlib.import_module(full)
            sys.modules[bare] = mod
        except Exception:
            pass  # will surface as a real import error later if truly needed

# Bootstrap api package and its sub-packages first
import api
import api.config
import api.database
import api.services
import api.utils
import api.security
import api.schemas
import api.routers
import api.tasks
import api.middleware
import api.admin

# Register bare top-level package aliases
for _pkg in ["config", "database", "services", "utils",
             "security", "schemas", "routers", "tasks", "middleware", "admin"]:
    _alias(_pkg, f"api.{_pkg}")

# Register bare submodule aliases
for _sub in [
    "config.settings",
    "database.db", "database.models", "database.base",
    "services.redis_service", "services.urls_service", "services.users_service",
    "utils.generate_short_code", "utils.create_super_users",
    "security.hash_",
    "schemas.url_schema",
    "routers.auth_guard", "routers.auth_google", "routers.url_endpoints",
    "tasks.cleanup_task",
    "admin.admin_service", "admin.admin_db", "admin.admin_endpoints",
    "admin.admin_models", "admin.base",
]:
    _alias(_sub, f"api.{_sub}")

# ─────────────────────────────────────────────────────────────────────────────
# Patch RedisClient.__init__ so importing url_endpoints doesn't try to
# open a socket at module load time (redis.Redis() is called at class body level)
# ─────────────────────────────────────────────────────────────────────────────
_redis_patcher = patch(
    "api.services.redis_service.redis.Redis",
    return_value=MagicMock()
)
_redis_patcher.start()

# Patch UserOperations.__init__ (calls get_db() / next(...)) at import time
_user_ops_patcher = patch(
    "api.services.users_service.UserOperations.__init__",
    return_value=None
)
_user_ops_patcher.start()

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers.url_endpoints import UrlShortenerAPI
from api.routers.auth_guard    import AuthGuard
from api.routers.auth_google   import GoogleAuthAPI
from api.database.db           import get_db
from api.schemas.url_schema    import UrlCreate
from api.services.redis_service import RedisClient


SECRET = "test-secret"


def _make_token(payload: dict) -> str:
    return jwt.encode(payload, SECRET, algorithm="HS256")


def _valid_token(email: str = "user@test.com") -> str:
    return _make_token({"email": email, "name": "Test User", "exp": time.time() + 3600})


def _admin_token() -> str:
    return _make_token({
        "email": "admin@test.com", "name": "Admin",
        "role": "admin", "exp": time.time() + 3600
    })


def _auth(email: str = "user@test.com") -> dict:
    return {"Authorization": f"Bearer {_valid_token(email)}"}


def _admin_auth() -> dict:
    return {"Authorization": f"Bearer {_admin_token()}"}


# ─────────────────────────────────────────────────────────────────────────────
# Shared app + client fixture
# ─────────────────────────────────────────────────────────────────────────────

def _make_client() -> tuple:
    """
    Build a minimal FastAPI app with UrlShortenerAPI mounted at its prefix,
    override get_db with a MagicMock, and stub all redis methods on the
    class-level redis instance.
    """
    app = FastAPI()
    url_api = UrlShortenerAPI()
    app.include_router(url_api.router, prefix="/url")

    mock_db = MagicMock()

    def override_get_db():
        try:
            yield mock_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Stub every redis method used by the endpoints
    url_api.redis.check_short_url  = MagicMock(return_value=None)
    url_api.redis.add_short_url    = AsyncMock()
    url_api.redis.increment_clicks = AsyncMock()
    url_api.redis.delete_short_url = MagicMock()

    client = TestClient(app, raise_server_exceptions=False)
    return client, url_api, mock_db


# ═════════════════════════════════════════════════════════════════════════════
# 1.  POST /url/create
# ═════════════════════════════════════════════════════════════════════════════

class TestCreateShortUrl:

    def test_requires_authentication(self):
        client, _, _ = _make_client()
        resp = client.post("/url/create", json={"original_url": "https://example.com"})
        assert resp.status_code == 401

    def test_success_returns_short_url(self):
        client, url_api, _ = _make_client()
        expected = {
            "short_url": "http://testserver/url/abc123",
            "original_url": "https://example.com"
        }
        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.create_short_url = AsyncMock(return_value=expected)
            resp = client.post(
                "/url/create",
                json={"original_url": "https://example.com"},
                headers=_auth(),
            )
        assert resp.status_code == 200
        assert resp.json()["short_url"] == "http://testserver/url/abc123"

    def test_success_calls_redis_add(self):
        client, url_api, _ = _make_client()
        expected = {
            "short_url": "http://testserver/url/abc123",
            "original_url": "https://example.com"
        }
        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.create_short_url = AsyncMock(return_value=expected)
            client.post(
                "/url/create",
                json={"original_url": "https://example.com"},
                headers=_auth(),
            )
        url_api.redis.add_short_url.assert_called_once_with(
            short_url="abc123",
            original_url="https://example.com",
        )

    def test_returns_400_when_service_returns_none(self):
        client, _, _ = _make_client()
        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.create_short_url = AsyncMock(return_value=None)
            resp = client.post(
                "/url/create",
                json={"original_url": "https://example.com"},
                headers=_auth(),
            )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Failed to create short URL"

    def test_url_schema_prepends_http_prefix(self):
        """UrlCreate.validate_url prefixes bare domains with http://"""
        url = UrlCreate(original_url="example.com")
        assert url.original_url.startswith("http://")

    def test_url_schema_rejects_oversized_url(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            UrlCreate(original_url="https://" + "a" * 2050 + ".com")

    def test_passes_user_email_to_service(self):
        client, _, _ = _make_client()
        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.create_short_url = AsyncMock(return_value={
                "short_url": "http://testserver/url/x1",
                "original_url": "https://example.com"
            })
            client.post(
                "/url/create",
                json={"original_url": "https://example.com"},
                headers=_auth("owner@test.com"),
            )
            MockOps.return_value.create_short_url.assert_awaited_once_with(
                original_url="https://example.com",
                user="owner@test.com",
            )


# ═════════════════════════════════════════════════════════════════════════════
# 2.  GET /url/{short_code}  (redirect)
# ═════════════════════════════════════════════════════════════════════════════

class TestRedirectToOriginal:

    def test_redirects_from_redis_cache(self):
        client, url_api, _ = _make_client()
        url_api.redis.check_short_url.return_value = "https://cached.com"

        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.change_clicks = AsyncMock(return_value="https://cached.com")
            resp = client.get("/url/abc123", follow_redirects=False)

        assert resp.status_code == 307
        assert resp.headers["location"] == "https://cached.com"

    def test_cache_hit_calls_increment_clicks(self):
        client, url_api, _ = _make_client()
        url_api.redis.check_short_url.return_value = "https://cached.com"

        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.change_clicks = AsyncMock(return_value="https://cached.com")
            client.get("/url/abc123", follow_redirects=False)

        url_api.redis.increment_clicks.assert_called_once()

    def test_redirects_from_db_when_cache_miss(self):
        client, url_api, _ = _make_client()
        url_api.redis.check_short_url.return_value = None

        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            instance = MockOps.return_value
            instance.domain = "http://testserver"
            instance.change_clicks = AsyncMock(return_value="https://db-url.com")
            resp = client.get("/url/abc123", follow_redirects=False)

        assert resp.status_code == 307
        assert resp.headers["location"] == "https://db-url.com"

    def test_404_when_url_not_found_in_db(self):
        client, url_api, _ = _make_client()
        url_api.redis.check_short_url.return_value = None

        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            instance = MockOps.return_value
            instance.domain = "http://testserver"
            instance.change_clicks = AsyncMock(return_value=None)
            resp = client.get("/url/abc123")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "URL not found"

    def test_favicon_returns_404(self):
        client, _, _ = _make_client()
        resp = client.get("/url/favicon.ico")
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 3.  GET /url/get/all
# ═════════════════════════════════════════════════════════════════════════════

class TestGetAllUrls:

    def test_requires_authentication(self):
        client, _, _ = _make_client()
        resp = client.get("/url/get/all")
        assert resp.status_code == 401

    def test_returns_urls_list(self):
        client, _, _ = _make_client()
        urls = [
            {"original_url": "https://a.com", "short_url": "http://testserver/url/aaa", "clicks": 0}
        ]
        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.get_all_urls = AsyncMock(return_value=urls)
            resp = client.get("/url/get/all", headers=_auth())

        assert resp.status_code == 200
        assert resp.json()["urls"] == urls

    def test_returns_empty_list_when_none(self):
        client, _, _ = _make_client()
        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.get_all_urls = AsyncMock(return_value=None)
            resp = client.get("/url/get/all", headers=_auth())

        assert resp.status_code == 200
        assert resp.json() == {"urls": []}

    def test_passes_user_email_to_service(self):
        client, _, _ = _make_client()
        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.get_all_urls = AsyncMock(return_value=[])
            client.get("/url/get/all", headers=_auth("me@test.com"))
            MockOps.return_value.get_all_urls.assert_awaited_once_with("me@test.com")


# ═════════════════════════════════════════════════════════════════════════════
# 4.  DELETE /url/delete/{short_code}
# ═════════════════════════════════════════════════════════════════════════════

class TestDeleteUrl:

    def test_requires_authentication(self):
        client, _, _ = _make_client()
        resp = client.delete("/url/delete/abc123")
        assert resp.status_code == 401

    def test_success_returns_message(self):
        client, _, _ = _make_client()
        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.delete_url = AsyncMock(return_value="https://example.com")
            resp = client.delete("/url/delete/abc123", headers=_auth())

        assert resp.status_code == 200
        assert resp.json() == {"message": "URL deleted successfully"}

    def test_success_calls_redis_delete(self):
        client, url_api, _ = _make_client()
        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.delete_url = AsyncMock(return_value="https://example.com")
            client.delete("/url/delete/abc123", headers=_auth())

        url_api.redis.delete_short_url.assert_called_once_with("abc123")

    def test_404_when_not_found(self):
        client, _, _ = _make_client()
        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.delete_url = AsyncMock(return_value=None)
            resp = client.delete("/url/delete/abc123", headers=_auth())

        assert resp.status_code == 404
        assert resp.json()["detail"] == "URL not found"

    def test_passes_short_code_and_email_to_service(self):
        client, _, _ = _make_client()
        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.delete_url = AsyncMock(return_value="https://example.com")
            client.delete("/url/delete/mycode", headers=_auth("deleter@test.com"))
            MockOps.return_value.delete_url.assert_awaited_once_with(
                "mycode", "deleter@test.com"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 5.  AuthGuard
# ═════════════════════════════════════════════════════════════════════════════

class TestAuthGuard:

    def test_missing_authorization_header_raises_401(self):
        client, _, _ = _make_client()
        resp = client.get("/url/get/all")
        assert resp.status_code == 401
        assert "Authentication required" in resp.json()["detail"]

    def test_non_bearer_scheme_raises_401(self):
        client, _, _ = _make_client()
        token = _valid_token()
        resp = client.get("/url/get/all", headers={"Authorization": f"Basic {token}"})
        assert resp.status_code == 401

    def test_invalid_token_raises_401(self):
        client, _, _ = _make_client()
        resp = client.get(
            "/url/get/all",
            headers={"Authorization": "Bearer this.is.not.valid"}
        )
        assert resp.status_code == 401
        assert "Invalid token" in resp.json()["detail"]

    def test_expired_token_raises_401(self):
        client, _, _ = _make_client()
        expired = _make_token({"email": "x@x.com", "exp": time.time() - 1})
        resp = client.get(
            "/url/get/all",
            headers={"Authorization": f"Bearer {expired}"}
        )
        assert resp.status_code == 401
        assert "Token expired" in resp.json()["detail"]

    def test_valid_token_passes_and_returns_payload(self):
        client, _, _ = _make_client()
        with patch("api.routers.url_endpoints.UrlOperations") as MockOps:
            MockOps.return_value.get_all_urls = AsyncMock(return_value=[])
            resp = client.get("/url/get/all", headers=_auth())
        assert resp.status_code == 200

    def test_create_access_token_is_decodable(self):
        token = AuthGuard.create_access_token({"email": "u@test.com"}, expires_minutes=10)
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["email"] == "u@test.com"
        assert "exp" in payload

    def test_create_access_token_respects_expiry(self):
        token = AuthGuard.create_access_token({"email": "u@test.com"}, expires_minutes=60)
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        # exp should be ~60 minutes from now (allow ±5 s drift)
        assert abs(payload["exp"] - (time.time() + 3600)) < 5


# ═════════════════════════════════════════════════════════════════════════════
# 6.  GoogleAuthAPI — /auth/me
# ═════════════════════════════════════════════════════════════════════════════

class TestAuthMe:

    def _make_auth_app(self):
        app = FastAPI()
        with patch("api.routers.auth_google.UserOperations"):
            auth_api = GoogleAuthAPI()
        app.include_router(auth_api.router, prefix="/auth")
        return TestClient(app, raise_server_exceptions=False)

    def test_me_returns_user_info_for_valid_token(self):
        client = self._make_auth_app()
        token = _make_token({
            "email": "me@test.com",
            "name": "Me",
            "picture": "https://pic.url",
            "exp": time.time() + 3600
        })
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@test.com"
        assert data["name"] == "Me"
        assert data["picture"] == "https://pic.url"

    def test_me_returns_null_without_bearer(self):
        client = self._make_auth_app()
        resp = client.get("/auth/me")
        # Original code returns None (FastAPI serialises as null / 200)
        assert resp.status_code == 200
        assert resp.json() is None

    def test_me_returns_null_for_invalid_token(self):
        client = self._make_auth_app()
        resp = client.get("/auth/me", headers={"Authorization": "Bearer bad.token"})
        assert resp.status_code == 200
        assert resp.json() is None

    def test_me_returns_null_for_expired_token(self):
        client = self._make_auth_app()
        expired = _make_token({"email": "x@x.com", "exp": time.time() - 1})
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
        assert resp.status_code == 200
        assert resp.json() is None


# ═════════════════════════════════════════════════════════════════════════════
# 7.  AdminService unit tests
# ═════════════════════════════════════════════════════════════════════════════

class TestAdminService:

    def _svc(self, admin_db=None, app_db=None):
        from api.admin.admin_service import AdminService
        return AdminService(
            admin_db=admin_db or MagicMock(),
            app_db=app_db or MagicMock(),
        )

    def test_verify_credentials_returns_none_for_unknown_email(self):
        svc = self._svc()
        svc.admin_db.query.return_value.filter.return_value.first.return_value = None
        assert svc.verify_admin_credentials("nobody@test.com", "pass") is None

    def test_verify_credentials_returns_none_for_wrong_password(self):
        from api.security.hash_ import _pwd_ctx
        admin_mock = MagicMock()
        admin_mock.is_active = True
        admin_mock.hashed_password = _pwd_ctx.hash("correct")

        svc = self._svc()
        svc.admin_db.query.return_value.filter.return_value.first.return_value = admin_mock
        assert svc.verify_admin_credentials("admin@test.com", "wrong") is None

    def test_verify_credentials_returns_dict_for_correct_password(self):
        from api.security.hash_ import _pwd_ctx
        admin_mock = MagicMock()
        admin_mock.email = "admin@test.com"
        admin_mock.name  = "Admin"
        admin_mock.is_active = True
        admin_mock.hashed_password = _pwd_ctx.hash("correct")

        svc = self._svc()
        svc.admin_db.query.return_value.filter.return_value.first.return_value = admin_mock
        result = svc.verify_admin_credentials("admin@test.com", "correct")
        assert result == {"email": "admin@test.com", "name": "Admin"}

    def test_get_overview_stats_returns_expected_keys(self):
        svc = self._svc()
        # Each db.query(...).scalar() call returns a sensible value
        svc.app_db.query.return_value.scalar.return_value = 5
        svc.app_db.query.return_value.filter.return_value.scalar.return_value = 3
        svc.app_db.query.return_value.filter.return_value.filter.return_value.scalar.return_value = 1

        stats = svc.get_overview_stats()
        expected_keys = {
            "total_users", "total_urls", "active_urls",
            "inactive_urls", "total_clicks", "new_users_week",
            "clicks_week", "expiring_soon"
        }
        assert expected_keys.issubset(stats.keys())


# ═════════════════════════════════════════════════════════════════════════════
# 8.  AdminEndpoints — POST /admin/, GET /admin/stats, role guard
# ═════════════════════════════════════════════════════════════════════════════

class TestAdminEndpoints:

    def _make_admin_app(self):
        from api.admin.admin_endpoints import router as admin_router
        from api.admin.admin_db import get_db as get_admin_db
        app = FastAPI()
        app.include_router(admin_router, prefix="/admin")

        mock_admin_db = MagicMock()
        mock_app_db   = MagicMock()
        app.dependency_overrides[get_db]       = lambda: mock_app_db
        app.dependency_overrides[get_admin_db] = lambda: mock_admin_db

        client = TestClient(app, raise_server_exceptions=False)
        return client, mock_admin_db, mock_app_db

    def test_login_returns_401_for_invalid_credentials(self):
        client, _, _ = self._make_admin_app()
        with patch("api.admin.admin_service.AdminService.verify_admin_credentials",
                   return_value=None):
            resp = client.post(
                "/admin/",
                json={"email": "admin@test.com", "password": "wrong"}
            )
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    def test_login_returns_token_for_valid_credentials(self):
        client, _, _ = self._make_admin_app()
        with patch("api.admin.admin_service.AdminService.verify_admin_credentials",
                   return_value={"email": "admin@test.com", "name": "Admin"}):
            resp = client.post(
                "/admin/",
                json={"email": "admin@test.com", "password": "correct"}
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_token_contains_admin_role(self):
        client, _, _ = self._make_admin_app()
        with patch("api.admin.admin_service.AdminService.verify_admin_credentials",
                   return_value={"email": "admin@test.com", "name": "Admin"}):
            resp = client.post(
                "/admin/",
                json={"email": "admin@test.com", "password": "correct"}
            )
        token = resp.json()["access_token"]
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload.get("role") == "admin"

    def test_stats_requires_admin_role(self):
        client, _, _ = self._make_admin_app()
        # Regular user token (no role field)
        resp = client.get("/admin/stats", headers=_auth())
        assert resp.status_code == 403

    def test_stats_accessible_with_admin_token(self):
        client, _, _ = self._make_admin_app()
        with patch("api.admin.admin_service.AdminService.get_overview_stats",
                   return_value={"total_users": 1, "total_urls": 1, "active_urls": 1,
                                 "inactive_urls": 0, "total_clicks": 0,
                                 "new_users_week": 0, "clicks_week": 0, "expiring_soon": 0}):
            resp = client.get("/admin/stats", headers=_admin_auth())
        assert resp.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# 9.  RedisClient — unit (no real Redis)
# ═════════════════════════════════════════════════════════════════════════════

class TestRedisClient:
    """
    RedisClient wraps a redis.Redis instance. We mock that instance
    and verify the client calls the right Redis commands.
    """

    def _client(self):
        rc = RedisClient.__new__(RedisClient)
        rc.expiration_seconds = 604800
        rc.redis_client = MagicMock()
        return rc

    def test_add_short_url_calls_set_twice(self):
        rc = self._client()
        rc.add_short_url("abc", "https://example.com")
        assert rc.redis_client.set.call_count == 2

    def test_add_short_url_stores_correct_key(self):
        rc = self._client()
        rc.add_short_url("abc", "https://example.com")
        first_call_args = rc.redis_client.set.call_args_list[0]
        assert first_call_args[0][0] == "abc"
        assert first_call_args[0][1] == "https://example.com"

    def test_add_short_url_creates_clicks_key(self):
        rc = self._client()
        rc.add_short_url("abc", "https://example.com")
        second_call_args = rc.redis_client.set.call_args_list[1]
        assert second_call_args[0][0] == "clicks:abc"
        assert second_call_args[0][1] == 0

    def test_check_short_url_calls_get(self):
        rc = self._client()
        rc.redis_client.get.return_value = "https://example.com"
        result = rc.check_short_url("abc")
        rc.redis_client.get.assert_called_once_with("abc")
        assert result == "https://example.com"

    def test_check_short_url_returns_none_when_missing(self):
        rc = self._client()
        rc.redis_client.get.return_value = None
        assert rc.check_short_url("notexist") is None

    def test_delete_short_url_deletes_both_keys(self):
        rc = self._client()
        rc.delete_short_url("abc")
        deleted = [c[0][0] for c in rc.redis_client.delete.call_args_list]
        assert "abc" in deleted
        assert "clicks:abc" in deleted

    def test_increment_clicks_calls_incr(self):
        rc = self._client()
        rc.increment_clicks("abc")
        rc.redis_client.incr.assert_called_once_with("clicks:abc")

    def test_get_clicks_returns_int(self):
        rc = self._client()
        rc.redis_client.get.return_value = "42"
        assert rc.get_clicks("abc") == 42

    def test_get_clicks_returns_zero_for_missing(self):
        rc = self._client()
        rc.redis_client.get.return_value = None
        assert rc.get_clicks("abc") == 0

    def test_ping_calls_redis_ping(self):
        rc = self._client()
        rc.redis_client.ping.return_value = True
        assert rc.ping() is True


# ═════════════════════════════════════════════════════════════════════════════
# 10. UrlCreate schema
# ═════════════════════════════════════════════════════════════════════════════

class TestUrlSchema:

    def test_https_url_unchanged(self):
        assert UrlCreate(original_url="https://example.com").original_url == "https://example.com"

    def test_http_url_unchanged(self):
        assert UrlCreate(original_url="http://example.com").original_url == "http://example.com"

    def test_bare_domain_gets_http_prefix(self):
        assert UrlCreate(original_url="example.com").original_url == "http://example.com"

    def test_url_exactly_2048_chars_allowed(self):
        url = "https://" + "a" * (2048 - len("https://"))
        assert len(UrlCreate(original_url=url).original_url) == 2048

    def test_url_over_2048_chars_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            UrlCreate(original_url="https://" + "a" * 2048 + ".com")