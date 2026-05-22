# DERRADJI — URL Shortener

> A full-stack URL shortener built with FastAPI, Redis, SQLite, and Google OAuth.
> Live at **[codealpha-intern-url-shortener.onrender.com](https://codealpha-intern-url-shortener.onrender.com/)**

---

## Table of contents

1. [Overview](#overview)
2. [Features](#features)
3. [Tech stack](#tech-stack)
4. [Project structure](#project-structure)
5. [Architecture diagram](#architecture-diagram)
6. [Request flow — client to server and back](#request-flow)
7. [Database schema](#database-schema)
8. [API reference](#api-reference)
9. [Authentication system](#authentication-system)
10. [Redis caching layer](#redis-caching-layer)
11. [Admin panel](#admin-panel)
12. [CI/CD pipeline](#cicd-pipeline)
13. [Environment variables](#environment-variables)
14. [Running locally](#running-locally)
15. [Docker](#docker)
16. [Deployment on Render](#deployment-on-render)

---

## Overview

DERRADJI Link is a URL shortener that lets authenticated users shorten long URLs into short 6-character codes, track how many times each link was clicked, see geo and browser analytics per link, and manage everything through a clean single-page frontend. An admin panel at `/derradji` gives the site owner full visibility over all users, all URLs, and click analytics.

---

## Features

- **Google OAuth 2.0** — sign in with Google, no passwords for end users
- **Short code generation** — 6-character alphanumeric codes (62⁶ = ~56 billion combinations)
- **Redis cache** — redirect lookups served from memory, no DB hit on hot links
- **Click analytics** — IP, browser, platform, country, city tracked per click via ip-api.com
- **URL expiry** — links expire after 7 days by default; expired links are soft-deleted in the background
- **Admin dashboard** — KPIs, daily click chart, top URLs, geo breakdown, user management, role promotion
- **JWT-based auth** — stateless tokens, 7-day expiry for users, 60-minute expiry for admin
- **Single-file frontend** — `index.html` and `admin.html` served directly by FastAPI, no separate frontend server
- **Docker-ready** — one `Dockerfile`, runs with `uvicorn` on port 8000
- **GitHub Actions CI/CD** — automated tests + Docker Hub push on every merge to `main`

---

## Tech stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI 0.130+ |
| ASGI server | Uvicorn (standard) |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (two files: app + admin) |
| Cache | Redis (Upstash or any Redis instance) |
| Auth | Google OAuth 2.0 + PyJWT (HS256) |
| Password hashing | bcrypt |
| HTTP client | httpx (async), requests (sync geo lookup) |
| Validation | Pydantic v2 |
| Testing | pytest + pytest-asyncio |
| Container | Docker (python:3.11-slim) |
| CI/CD | GitHub Actions |
| Hosting | Render |

---

## Project structure

```
CodeAlpha_Intern/
├── .github/
│   └── workflows/
│       └── ci-cd.yml          # GitHub Actions pipeline
├── api/
│   ├── main.py                # App entry point, router registration, lifespan
│   ├── config/
│   │   └── settings.py        # Env var loader (Info class)
│   ├── database/
│   │   ├── base.py            # SQLAlchemy declarative base
│   │   ├── db.py              # Engine, session factory, init_db()
│   │   └── models.py          # ShortUrl, User, ClickersInfo models
│   ├── schemas/
│   │   └── url_schema.py      # Pydantic UrlCreate validator
│   ├── routers/
│   │   ├── url_endpoints.py   # /url/* routes (create, redirect, list, delete)
│   │   ├── auth_google.py     # /auth/* routes (login, callback, me, logout)
│   │   └── auth_guard.py      # JWT middleware (require_auth, create_access_token)
│   ├── services/
│   │   ├── urls_service.py    # URL CRUD + click tracking logic
│   │   ├── users_service.py   # User create / lookup
│   │   └── redis_service.py   # Redis set/get/delete/incr wrapper
│   ├── admin/
│   │   ├── admin_db.py        # Separate admin SQLite engine + session
│   │   ├── admin_models.py    # Admin model (bcrypt password)
│   │   ├── admin_service.py   # Stats, user mgmt, URL mgmt queries
│   │   ├── admin_endpoints.py # /admin/* routes (login, stats, users, urls)
│   │   └── base.py            # Admin declarative base
│   ├── middleware/
│   │   ├── cors_middleware.py # CORS (allow_origins=["*"])
│   │   └── session_middleware.py # Starlette session (for OAuth state)
│   ├── dependencies/
│   │   └── auth.py            # get_current_user FastAPI dependency
│   ├── security/
│   │   └── hash_.py           # bcrypt helpers
│   ├── tasks/
│   │   └── cleanup_task.py    # Background task: soft-delete expired URLs
│   ├── utils/
│   │   ├── generate_short_code.py  # Random 6-char alphanumeric code
│   │   └── create_super_users.py   # Seeds admin user on startup
│   ├── frontend/
│   │   ├── index.html         # User-facing SPA
│   │   └── admin.html         # Admin dashboard SPA
│   └── tests.py               # pytest test suite
├── Dockerfile
├── requirements.txt
└── .gitignore
```

---

## Architecture diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Render (cloud)                             │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                  FastAPI  (Uvicorn / port 8000)              │  │
│   │                                                              │  │
│   │  Middleware stack                                            │  │
│   │  ┌──────────────┐  ┌──────────────────┐                     │  │
│   │  │ CORS         │  │ Session (Starlette│                     │  │
│   │  │ (allow: *)   │  │ secret key)       │                     │  │
│   │  └──────────────┘  └──────────────────┘                     │  │
│   │                                                              │  │
│   │  Routers                                                     │  │
│   │  ┌────────────────┐ ┌─────────────────┐ ┌────────────────┐  │  │
│   │  │ /url/*         │ │ /auth/*         │ │ /admin/*       │  │  │
│   │  │ url_endpoints  │ │ auth_google     │ │ admin_endpoints│  │  │
│   │  └───────┬────────┘ └────────┬────────┘ └───────┬────────┘  │  │
│   │          │                   │                   │           │  │
│   │  Services│                   │                   │           │  │
│   │  ┌───────┴────────┐          │          ┌────────┴────────┐  │  │
│   │  │ UrlOperations  │          │          │ AdminService    │  │  │
│   │  │ UserOperations │          │          │                 │  │  │
│   │  │ RedisClient    │          │          │                 │  │  │
│   │  └───────┬────────┘          │          └────────┬────────┘  │  │
│   │          │                   │                   │           │  │
│   └──────────┼───────────────────┼───────────────────┼───────────┘  │
│              │                   │                   │              │
│   ┌──────────▼──────┐  ┌─────────▼──────┐  ┌────────▼────────┐    │
│   │  SQLite (app)   │  │ Google OAuth   │  │ SQLite (admin)  │    │
│   │  users          │  │ accounts.google│  │ admins          │    │
│   │  short_urls     │  │ .com           │  │                 │    │
│   │  clickers_info  │  └────────────────┘  └─────────────────┘    │
│   └─────────────────┘                                              │
│                                                                     │
│   ┌─────────────────────────────────────────┐                      │
│   │  Redis (Upstash / external)             │                      │
│   │  key: <short_code>    → original_url    │                      │
│   │  key: clicks:<code>   → click counter   │                      │
│   └─────────────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Request flow

### 1. User visits the site

```
Browser  ──GET /──►  FastAPI  ──►  FileResponse(index.html)
```

FastAPI serves `index.html` directly from `api/frontend/`. No Nginx, no CDN.

---

### 2. Google OAuth login

```
Browser
  │
  ├──GET /auth/google──────────────────────────────────────────────────►  FastAPI
  │                                                                         │
  │                             builds state JWT (signed, 5 min TTL)       │
  │◄── 302 redirect to accounts.google.com/o/oauth2/v2/auth ───────────────┘
  │
  ├──[user approves]──► Google redirects to /auth/google/callback?code=…&state=…
  │
  ├──GET /auth/google/callback──────────────────────────────────────────►  FastAPI
  │                                                                         │
  │                  1. decode & verify state JWT                           │
  │                  2. POST to oauth2.googleapis.com/token → access_token  │
  │                  3. GET googleapis.com/oauth2/v3/userinfo → email/name  │
  │                  4. upsert User row in SQLite                            │
  │                  5. mint app JWT {email, name, picture, exp: +7 days}   │
  │◄── 302 redirect to /?loggedin=1&token=<JWT> ────────────────────────────┘
  │
  └── frontend stores token in localStorage, attaches as Bearer on every request
```

---

### 3. Shorten a URL

```
Browser  ──POST /url/create──────────────────────────────────────────►  FastAPI
          Authorization: Bearer <JWT>
          Body: { "original_url": "https://..." }
                                                                         │
                          1. AuthGuard.require_auth → decode JWT         │
                          2. background task: deactivate_expired_urls    │
                          3. UrlOperations.create_short_url              │
                             a. validate user exists in DB               │
                             b. if original_url already exists → return  │
                                existing short_url (dedup)               │
                             c. generate_short_code(url) → 6 random chars│
                             d. check short_code not already taken        │
                             e. INSERT into short_urls                    │
                          4. RedisClient.add_short_url                   │
                             SET short_code → original_url  EX 604800    │
                             SET clicks:<code> → 0           EX 604800   │
                                                                         │
◄── { "short_url": "https://domain/url/<code>", "user": {...} } ─────────┘
```

---

### 4. Redirect (the core feature)

```
Visitor  ──GET /url/<short_code>──────────────────────────────────────►  FastAPI
                                                                         │
                          1. redis.check_short_url(short_code)           │
                                                                         │
                 ┌── HIT (cached) ──────────────────────────────────────►│
                 │                 2a. redis.increment_clicks(short_code) │
                 │                 3a. db.change_clicks(                  │
                 │                       ip, user_agent, browser,         │
                 │                       platform)                        │
                 │                       → calls ip-api.com for geo       │
                 │                       → INSERT ClickersInfo row        │
                 │                       → UPDATE short_urls.clicks += 1  │
                 │◄── 302 RedirectResponse(url=cached_url) ───────────────┘
                 │
                 └── MISS (not cached) ────────────────────────────────►│
                                   2b. db.change_clicks(short_url)       │
                                       → same tracking as above          │
                                   3b. redis.add_short_url(              │
                                         short_code, original_url)       │
                                   4b. redis.increment_clicks            │
                                   ◄── 302 RedirectResponse ─────────────┘

Visitor  ◄──302 Location: https://original-long-url.com────────────────
```

---

### 5. List & delete user URLs

```
GET  /url/get/all
  → AuthGuard check
  → UrlOperations.get_all_urls(email)
  → returns [ { original_url, short_url, clicks, expires_at, clickers: [...] } ]

DELETE /url/delete/<short_code>
  → AuthGuard check
  → UrlOperations.delete_url(short_code, email)
  → ownership check: data.user_id == user.id
  → soft-delete: is_active = 0
  → RedisClient.delete_short_url(short_code)
```

---

### 6. Admin flow

```
Browser  ──POST /admin/──────────────────────────────────────────────►  FastAPI
          Body: { email, password }
                                                                         │
                  AdminService.verify_admin_credentials                  │
                  → query Admin table (admin SQLite)                     │
                  → bcrypt.checkpw(password, hashed_password)           │
                  → create_access_token({ role: "admin" }, exp=60min)   │
                                                                         │
◄── { access_token, token_type: "bearer" } ──────────────────────────────┘

All subsequent admin calls:
  Authorization: Bearer <admin-JWT>
  require_admin dependency → payload["role"] == "admin" or 403
```

---

## Database schema

### `short_urls`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | auto-increment |
| original_url | VARCHAR(2048) | the full URL |
| short_code | VARCHAR UNIQUE | 6-char alphanumeric |
| clicks | INTEGER | total click count |
| created_at | DATETIME | UTC |
| expires_at | DATETIME | UTC, default +7 days |
| is_active | BOOLEAN | soft-delete flag |
| user_id | INTEGER FK | → users.id |

### `users`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| email | VARCHAR UNIQUE | from Google |
| name | VARCHAR | from Google |
| picture | VARCHAR | Google profile pic URL |
| role | VARCHAR | `"user"` or `"admin"` |

### `clickers_info`
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| short_url_id | INTEGER FK | → short_urls.id |
| ip | VARCHAR | visitor IP |
| user_agent | VARCHAR(2048) | raw UA string |
| browser | VARCHAR | from `sec-ch-ua` header |
| platform | VARCHAR | from `sec-ch-ua-platform` |
| country | VARCHAR | from ip-api.com |
| city | VARCHAR | from ip-api.com |
| clicked_at | DATETIME | UTC |

### `admins` (separate SQLite file)
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| email | VARCHAR UNIQUE | |
| name | VARCHAR | |
| hashed_password | VARCHAR | bcrypt |
| is_active | BOOLEAN | |
| created_at | DATETIME | |
| last_login | DATETIME | |

---

## API reference

### Auth endpoints (`/auth`)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/auth/google` | — | Redirect to Google OAuth consent screen |
| GET | `/auth/google/callback` | — | OAuth callback, returns JWT via redirect |
| GET | `/auth/me` | Bearer JWT | Returns current user info |
| GET | `/auth/logout` | — | Clears session |

### URL endpoints (`/url`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/url/create` | Bearer JWT | Create a short URL |
| GET | `/url/{short_code}` | — | Redirect to original URL |
| GET | `/url/get/all` | Bearer JWT | List all URLs for current user |
| DELETE | `/url/delete/{short_code}` | Bearer JWT | Soft-delete a URL |

### Admin endpoints (`/admin`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/admin/` | — | Admin login, returns JWT |
| GET | `/admin/stats` | Admin JWT | Dashboard KPIs |
| GET | `/admin/stats/clicks-per-day` | Admin JWT | Daily click chart (1–90 days) |
| GET | `/admin/stats/geo` | Admin JWT | Country / browser / platform breakdown |
| GET | `/admin/stats/top-urls` | Admin JWT | Top URLs by clicks (limit 1–50) |
| GET | `/admin/users` | Admin JWT | Paginated user list (search, role filter) |
| GET | `/admin/users/{id}` | Admin JWT | User detail + their URLs |
| PATCH | `/admin/users/{id}/role` | Admin JWT | Promote / demote user |
| DELETE | `/admin/users/{id}` | Admin JWT | Hard-delete user |
| GET | `/admin/urls` | Admin JWT | Paginated URL list (search, active filter) |
| GET | `/admin/urls/{id}` | Admin JWT | URL detail + full click log |
| PATCH | `/admin/urls/{id}/toggle` | Admin JWT | Activate / deactivate URL |
| DELETE | `/admin/urls/{id}` | Admin JWT | Hard-delete URL |

### Frontend pages

| Path | Description |
|---|---|
| `/` | User-facing SPA (`index.html`) |
| `/derradji` | Admin dashboard (`admin.html`) — IP-based access commented out |
| `/admin.html` | Returns 403 (direct path is blocked) |

---

## Authentication system

The app uses a **stateless JWT approach** — no server-side sessions are needed for the main auth flow.

**User auth:**
1. Google OAuth issues an authorization code.
2. The server exchanges the code for an access token, fetches the user's profile from Google, and mints its own JWT: `{ email, name, picture, exp: now + 7 days }` signed with `SECRET_KEY` (HS256).
3. The JWT is passed back to the frontend via a redirect query parameter and stored in `localStorage`.
4. Every protected API call includes `Authorization: Bearer <token>`.
5. `AuthGuard.require_auth` decodes and validates the token on every request.

**Admin auth:**
1. Admin logs in with email + bcrypt password via `POST /admin/`.
2. Server mints a separate JWT with `role: "admin"` and a 60-minute expiry.
3. All admin routes check `payload["role"] == "admin"`.

**State CSRF protection in OAuth:**
A signed JWT (5-minute TTL) is used as the OAuth `state` parameter instead of a session cookie. This avoids the need for server-side session storage while still preventing CSRF on the callback.

---

## Redis caching layer

Redis is used as a look-aside cache for the redirect hot path:

```
Key: <short_code>           Value: <original_url>     TTL: 604800s (7 days)
Key: clicks:<short_code>    Value: <integer count>     TTL: 604800s (7 days)
```

On **redirect**: `GET short_code` → hit → serve from cache, write click to DB async. Miss → read from DB, then warm the cache.

On **create**: immediately `SET short_code → original_url` so the first redirect is always a cache hit.

On **delete**: `DEL short_code` and `DEL clicks:<short_code>` are called immediately so stale data is never served.

This means for high-traffic links, SQLite is never hit on the redirect itself — only for the click analytics write, which happens asynchronously.

---

## Admin panel

The admin panel lives at `/derradji` (obscured path, not `/admin` which returns 403). It is a single-page app served by FastAPI.

Capabilities:
- Dashboard KPIs: total URLs, total users, total clicks, active links
- Click chart: bar chart of clicks over the last N days (1–90)
- Geo stats: top countries, browsers, platforms from `clickers_info`
- Top URLs: most-clicked links across the platform
- User management: list, search, view detail, change role, delete
- URL management: list, search, filter by active/inactive, toggle, delete

The admin account is seeded at startup from `ADMIN_EMAIL` and `ADMIN_PASSWORD` env vars by `create_admin_user()` in `utils/create_super_users.py`.

---

## CI/CD pipeline

The pipeline in `.github/workflows/ci-cd.yml` has **two jobs**:

```
push / PR to main
        │
        ▼
┌───────────────────┐
│   Job 1: test     │   runs-on: ubuntu-latest
│                   │
│  1. checkout      │
│  2. python 3.11   │   pip cache enabled
│  3. pip install   │
│  4. pytest        │   env: SQLite in-memory, real Redis secrets
│     tests.py -v   │
└────────┬──────────┘
         │ needs: test
         │ only on: push to main (not PRs)
         ▼
┌────────────────────────┐
│   Job 2: build         │   runs-on: ubuntu-latest
│                        │
│  1. checkout           │
│  2. docker/login@v3    │   DOCKER_USERNAME / DOCKER_PASSWORD secrets
│  3. build-push@v5      │   context: .
│     tags:              │   → docker.io/<user>/url-shortener:latest
│       :latest          │   → docker.io/<user>/url-shortener:<sha>
│       :<git-sha>       │
└────────────────────────┘
```

The deploy job (SSH into server, `docker pull`, `docker run`) exists in the file but is **commented out** — deployment is handled by Render's native Docker image sync, which watches Docker Hub directly.

**Secrets required in GitHub:**

| Secret | Used in |
|---|---|
| `SECRET_KEY` | test env |
| `REDIS_HOST` | test env |
| `REDIS_PORT` | test env |
| `REDIS_USERNAME` | test env |
| `REDIS_PASSWORD` | test env |
| `ADMIN_EMAIL` | test env |
| `ADMIN_PASSWORD` | test env |
| `GOOGLE_CLIENT_ID` | test env |
| `GOOGLE_CLIENT_SECRET` | test env |
| `DOCKER_USERNAME` | build job |
| `DOCKER_PASSWORD` | build job |

---

## Environment variables

Create `api/.env` (or set these in Render / GitHub Secrets):

```env
# Database
DATABASE_URL=sqlite:///./sql_app.db
DATABASE_URL_ADMIN=sqlite:///./admin.db

# App
SECRET_KEY=your-secret-key-here
DOMAIN=https://codealpha-intern-url-shortener.onrender.com

# Redis (Upstash or self-hosted)
REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_USERNAME=default
REDIS_PASSWORD=your-redis-password

# Google OAuth
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=https://codealpha-intern-url-shortener.onrender.com/auth/google/callback

# Admin seed user
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=strong-password-here

# Optional
URL_EXPIRATION_TIME_IN_SECONDS=604800   # 7 days (default)
```

---

## Running locally

```bash
# 1. Clone
git clone https://github.com/senani-derradji/CodeAlpha_Intern_Url_Shortener.git
cd CodeAlpha_Intern_Url_Shortener

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up .env
cp api/.env.example api/.env   # then fill in your values

# 4. Run
uvicorn api.main:app --reload --port 8000

# 5. Open
# http://localhost:8000        → user frontend
# http://localhost:8000/derradji  → admin panel
```

**Running tests:**
```bash
cd api
DATABASE_URL="sqlite:///:memory:" \
DATABASE_URL_ADMIN="sqlite:///:memory:" \
DOMAIN="http://localhost:8000" \
pytest tests.py -v --tb=short
```

---

## Docker

```bash
# Build
docker build -t url-shortener .

# Run
docker run -d \
  --name url-shortener \
  -p 8000:8000 \
  -e DATABASE_URL="sqlite:///./sql_app.db" \
  -e SECRET_KEY="your-secret" \
  -e REDIS_HOST="your-redis-host" \
  -e REDIS_PORT="6379" \
  -e REDIS_USERNAME="default" \
  -e REDIS_PASSWORD="your-redis-password" \
  -e DOMAIN="http://localhost:8000" \
  -e ADMIN_EMAIL="admin@example.com" \
  -e ADMIN_PASSWORD="password" \
  -e GOOGLE_CLIENT_ID="..." \
  -e GOOGLE_CLIENT_SECRET="..." \
  -e GOOGLE_REDIRECT_URI="http://localhost:8000/auth/google/callback" \
  url-shortener
```

The `Dockerfile` uses `python:3.11-slim`, installs dependencies, copies the project, exposes port 8000, and starts with:
```
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## Deployment on Render

The app is deployed at **[codealpha-intern-url-shortener.onrender.com](https://codealpha-intern-url-shortener.onrender.com/)**.

Render is configured to pull the Docker image from Docker Hub (`url-shortener:latest`) which is pushed automatically by the GitHub Actions build job on every merge to `main`. All environment variables listed above are set in the Render dashboard under the service's Environment tab.

Redis is provided by **Upstash** (external managed Redis), configured via the `REDIS_*` environment variables.

---

## Notes

- The `short_code` generation uses `random.choice` on a 62-character alphabet, seeded fresh per call. It is not cryptographically unpredictable — if you need that, swap in `secrets.choice`.
- The geo lookup calls `ip-api.com` synchronously inside an `async` route using the `requests` library. For high traffic this will block the event loop; a future improvement would be to use `httpx.AsyncClient` for this call or move it into the background task alongside `deactivate_expired_urls`.
- The CORS middleware is set to `allow_origins=["*"]` which is fine for a personal project but should be tightened to the specific domain in production.
- The admin route is at `/derradji` — an obscured path that acts as light security through obscurity. The commented-out IP allowlist in `main.py` is the proper way to lock it down.