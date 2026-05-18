# api/url_endpoints.py

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request
)

from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from database.db import get_db
from schemas.url_schema import UrlCreate
from services.urls_service import UrlOperations
from services.redis_service import RedisClient
from tasks.cleanup_task import deactivate_expired_urls


from api.auth_guard import AuthGuard



class UrlShortenerAPI:

    redis = RedisClient()

    def __init__(self):

        self.router = APIRouter()

        self.router.add_api_route(
            "/shortener",
            self.create_short_url,
            methods=["POST"]
        )

        self.router.add_api_route(
            "/{short_code}",
            self.redirect_to_original,
            methods=["GET"]
        )

        self.router.add_api_route(
            "/{short_code}",
            self.delete_url,
            methods=["DELETE"]
        )

    async def create_short_url(
        self,
        url: UrlCreate,
        request: Request,
        background_tasks: BackgroundTasks,
        user=Depends(AuthGuard.require_auth),
        db: Session = Depends(get_db)
    ):
        print(request.session.get("user"))
        print(request.session)

        background_tasks.add_task(
            deactivate_expired_urls,
            db
        )

        url_ops = UrlOperations(db)
        print(f"USER BEFORE RESULT : {user}")

        result = await url_ops.create_short_url(
            original_url=url.original_url,
            user=user.get("email")
        )

        if result:

            short_code = (
                result.get("short_url")
                .split("/")[-1]
            )

            original_url = result.get(
                "original_url"
            )

            self.redis.add_short_url(
                short_url=short_code,
                original_url=original_url,
            )

            return {
                "short_url": result.get(
                    "short_url"
                ),
                "user": user
            }

        raise HTTPException(
            status_code=400,
            detail="Failed to create short URL"
        )

    async def redirect_to_original(
        self,
        short_code: str,
        request: Request,
        db: Session = Depends(get_db),
    ):

        cached_url = self.redis.check_short_url(
            short_code
        )

        if cached_url:

            self.redis.increment_clicks(
                short_code
            )

            return RedirectResponse(
                cached_url
            )

        url_ops = UrlOperations(db)

        # await url_ops.check_expiration_date(
        #     short_code
        # )



        domain = url_ops.domain

        full_short_url = (
            f"{domain}/{short_code}"
        )

        result = url_ops.change_clicks(
            full_short_url
        )

        if result:

            self.redis.add_short_url(
                short_url=short_code,
                original_url=result,
            )

            self.redis.increment_clicks(
                short_code
            )

            return RedirectResponse(
                result
            )

        raise HTTPException(
            status_code=404,
            detail="URL not found"
        )

    async def delete_url(
        self,
        short_code: str,
        request: Request,
        user=Depends(AuthGuard.require_auth),
        db: Session = Depends(get_db)
    ):

        url_ops = UrlOperations(db)

        result = url_ops.delete_url(
            short_code
        )

        if result:

            self.redis.delete_short_url(
                short_code
            )

            return {
                "message":
                "URL deleted successfully"
            }

        raise HTTPException(
            status_code=404,
            detail="URL not found"
        )