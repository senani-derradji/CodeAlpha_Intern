from database.models import ShortUrl
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from config.settings import Info
from utils.generate_short_code import generate
from services.users_service import UserOperations


class UrlOperations:
    def __init__(self, db: Session):
        self.db = db
        self.generate_short_code = generate
        self.domain = Info.DOMAIN
        self.user_ops = UserOperations()

    async def create_short_url(self, original_url: str, user: str):

        if user is None or await self.user_ops.get_user_by_email(user) is None:
            raise ValueError("User not found")

        user = await self.user_ops.get_user_by_email(user)

        if original_url:
            if isinstance(original_url, str):
                short_code = self.generate_short_code(original_url)

        if self.db.query(ShortUrl).filter(ShortUrl.short_code == short_code).first():
            short_code = self.generate_short_code(original_url)

        if self.db.query(ShortUrl).filter(ShortUrl.original_url == original_url).first():
            return self.domain + '/' + self.db.query(ShortUrl).filter(ShortUrl.original_url == original_url).first().short_code

        short_url = ShortUrl(
            original_url=original_url,
            short_code=short_code,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=Info.URL_EXPIRATION_TIME_IN_SECONDS),
            clicks=0,
            is_active=1,
            user_id=user.id,

            )
        self.db.add(short_url)
        self.db.commit()
        self.db.refresh(short_url)

        if short_url:
            return {"original_url": original_url, "short_url": self.domain + '/' + short_url.short_code}

        else:
            raise ValueError("Failed to create short URL")


    async def change_clicks(self, short_url: str):

        short_code = short_url.split('/')[-1]
        data = self.db.query(ShortUrl).filter(ShortUrl.short_code == short_code, ShortUrl.is_active == 1).first()

        if data is not None:
            data.clicks += 1
            self.db.commit()
            self.db.refresh(data)
        else:
            raise ValueError("URL not found")

        return data.original_url


    async def delete_url(self, short_url: str, user: str):
        short_code = short_url.split('/')[-1]
        data = self.db.query(ShortUrl).filter(ShortUrl.short_code == short_code, ShortUrl.is_active == 1).first()
        user = await self.user_ops.get_user_by_email(user)
        if data is not None:
            if data.user_id != user.id:
                raise ValueError("You are not authorized to delete this URL")
            data.is_active = 0
            self.db.commit()
            self.db.refresh(data)


        return data.original_url
