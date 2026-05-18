from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database.db import get_db
from schemas.url_validator import UrlCreate
from services.urls_service import UrlOperations


class UrlShortenerAPI:

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

    def create_short_url(
        self,
        url: UrlCreate,
        db: Session = Depends(get_db)
    ):

        url_ops = UrlOperations(db)

        result = url_ops.create_short_url(url.original_url)

        if result:
            return {"short_url": result}

        raise HTTPException(
            status_code=400,
            detail="Failed to create short URL"
        )

    def redirect_to_original(
        self,
        short_code: str,
        db: Session = Depends(get_db)
    ):

        url_ops = UrlOperations(db)

        domain = url_ops.domain

        full_short_url = f"{domain}/{short_code}"

        result = url_ops.change_clicks(full_short_url)

        if result:
            return RedirectResponse(result)

        raise HTTPException(
            status_code=404,
            detail="URL not found"
        )
