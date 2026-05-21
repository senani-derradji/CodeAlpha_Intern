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
import requests


class UrlShortenerAPI:

    redis = RedisClient()


    def __init__(self):

        self.router = APIRouter()

        self.router.add_api_route(
            "/create",
            self.create_short_url,
            methods=["POST"]
        )

        self.router.add_api_route(
            "/{short_code}",
            self.redirect_to_original,
            methods=["GET"]
        )

        self.router.add_api_route(
            "/get/all",
            self.get_all_urls,
            methods=["GET"]
        )

        self.router.add_api_route(
            "/delete/{short_code}",
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

        background_tasks.add_task(
            deactivate_expired_urls,
            db
        )

        url_ops = UrlOperations(db)

        result = await url_ops.create_short_url(
            original_url=url.original_url,
            user=user.get("email")
        )

        if result:

            short_code = result["short_url"].split("/")[-1]
            print(short_code)

            original_url = result["original_url"]
            print(original_url)

            self.redis.add_short_url(
                short_url=short_code,
                original_url=original_url,
            )

            return {
                "short_url": result.get("short_url"),
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
        self.url_ops = UrlOperations(db)
        ip = request.client.host
        user_agent = request.headers.get("user-agent")

        browser = request.headers.get("sec-ch-ua")
        platform = request.headers.get("sec-ch-ua-platform")

        if short_code == "favicon.ico":
            raise HTTPException(status_code=404)

        cached_url = self.redis.check_short_url(
            short_code
        )

        if cached_url:

            self.redis.increment_clicks(
                short_url=short_code,
                # ip=ip,
                # user_agent=user_agent,
                # browser=browser,
                # platform=platform
            )
            await self.url_ops.change_clicks(
                short_url=short_code,
                ip=ip,
                user_agent=user_agent,
                browser=browser,
                platform=platform
            )


            return RedirectResponse(
                url=cached_url
            )

        url_ops = UrlOperations(db)

        domain = url_ops.domain

        full_short_url = (
            f"{domain}/url/{short_code}"
        )

        result = await url_ops.change_clicks(
            full_short_url
        )

        if result:

            await self.redis.add_short_url(
                short_url=short_code,
                original_url=result,
            )

            await self.redis.increment_clicks(
                short_code
            )

            return RedirectResponse(
                url=result
            )

        raise HTTPException(
            status_code=404,
            detail="URL not found"
        )

    async def get_all_urls(
        self,
        request: Request,
        user=Depends(AuthGuard.require_auth),
        db: Session = Depends(get_db)
    ):
    
        url_ops = UrlOperations(db)

        result = await url_ops.get_all_urls(
            user.get("email")
        )

        return {
            "urls": result or []
        }

    async def delete_url(
        self,
        short_code: str,
        request: Request,
        user=Depends(AuthGuard.require_auth),
        db: Session = Depends(get_db)
    ):

        url_ops = UrlOperations(db)
        print("user inisde delete endpoint get email : ",user.get("email"))

        result = await url_ops.delete_url(
            short_code,
            user.get("email")
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