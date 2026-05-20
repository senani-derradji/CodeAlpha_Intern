from database.models import ShortUrl, ClickersInfo
import requests
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

        user_id = await self.user_ops.get_user_by_email(user)

        if original_url:
            if isinstance(original_url, str):
                short_code = self.generate_short_code(original_url)

        if self.db.query(ShortUrl).filter(ShortUrl.short_code == short_code).first():
            short_code = self.generate_short_code(original_url)

        if self.db.query(ShortUrl).filter(ShortUrl.original_url == original_url and ShortUrl.is_active == 1).first():
            return {
                "original_url": self.db.query(ShortUrl).filter(ShortUrl.original_url == original_url).first().original_url,
                "short_url": self.domain + '/url/' + self.db.query(ShortUrl).filter(ShortUrl.original_url == original_url).first().short_code
                }

        short_url = ShortUrl(
            original_url=original_url,
            short_code=short_code,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=Info.URL_EXPIRATION_TIME_IN_SECONDS),
            clicks=0,
            is_active=1,
            user_id=user_id.id,

            )
        self.db.add(short_url)
        self.db.commit()
        self.db.refresh(short_url)

        if short_url:
            return {"original_url": original_url, "short_url": self.domain + '/url/' + short_url.short_code}

        else:
            raise ValueError("Failed to create short URL")



    async def change_clicks(
        self,
        short_url: str,
        ip: str,
        user_agent: str,
        browser: str,
        platform: str
    ):

        short_code = short_url.split('/')[-1]

        data = self.db.query(ShortUrl).filter(
            ShortUrl.short_code == short_code,
            ShortUrl.is_active == 1
        ).first()

        if data is None:
            raise ValueError("URL not found")

        geo = requests.get(
            f"http://ip-api.com/json/{ip}"
        ).json()

        country = geo.get("country")

        city = geo.get("city")

        clicker = ClickersInfo(
            short_url_id=data.id,
            ip=ip,
            user_agent=user_agent,
            browser=browser,
            platform=platform,
            country=country,
            city=city
        )

        self.db.add(clicker)

        data.clicks += 1

        self.db.commit()

        self.db.refresh(data)

        return data.original_url


    async def get_all_urls(self, user):

        user_id = await self.user_ops.get_user_by_email(user)

        if user is None:
            raise ValueError("User not found")

        urls = self.db.query(ShortUrl).filter(
            ShortUrl.user_id == user_id.id,
            ShortUrl.is_active == 1
        ).all()

        return [
            {
                "original_url": url.original_url,
                "short_url": f"{self.domain}/url/{url.short_code}",
                "clicks": url.clicks,
                "expires_at": url.expires_at,

                "clickers": [
                    {
                        "ip": clicker.ip,
                        "browser": clicker.browser,
                        "platform": clicker.platform,
                        "country": clicker.country,
                        "city": clicker.city,
                        "clicked_at": clicker.clicked_at
                    }
                    for clicker in url.clickers
                ]
            }
            for url in urls
        ]


    async def delete_url(self, short_url: str, user):
        short_code = short_url.split('/')[-1]
        data = self.db.query(ShortUrl).filter(ShortUrl.short_code == short_code, ShortUrl.is_active == 1).first()

        user_id = await self.user_ops.get_user_by_email(user)
        print("user_id inisd eurl servcies delete url : ", user_id.email, " - ", user_id.id)
        if user is None:
            raise ValueError("User not found")

        if data is None:
            raise ValueError("URL not found")

        if data.user_id != user_id.id:
            raise ValueError("You are not authorized to delete this URL")
        data.is_active = 0
        self.db.commit()
        self.db.refresh(data)


        return data.original_url