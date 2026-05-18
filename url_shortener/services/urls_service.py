from database.models import ShortUrl
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database.conf import Info
from utils.generate_short_code import generate


class UrlOperations:
    def __init__(self, db: Session):
        self.db = db
        self.generate_short_code = generate
        self.domain = Info.DOMAIN

    def create_short_url(self, original_url: str):
        if original_url:
            if isinstance(original_url, str):
                short_code = self.generate_short_code(original_url)

        if self.db.query(ShortUrl).filter(ShortUrl.short_code == short_code).first():
            short_code = self.generate_short_code(original_url)

        if self.db.query(ShortUrl).filter(ShortUrl.original_url == original_url).first():
            return self.domain + self.db.query(ShortUrl).filter(ShortUrl.original_url == original_url).first().short_code

        short_url = ShortUrl(
            original_url=original_url,
            short_code=short_code,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
            clicks=0,
            is_active=1,
            )
        self.db.add(short_url)
        self.db.commit()
        self.db.refresh(short_url)

        if short_url:
            return f"{self.domain}/{short_url.short_code}"

        else:
            raise ValueError("Failed to create short URL")


    def change_url_status(self, short_url: str):
        short_code = short_url.split('/')[-1]
        data = self.db.query(ShortUrl).filter(ShortUrl.short_code == short_code).first()

        if data:
            data.is_active = 0
            self.db.commit()
            self.db.refresh(data)
            return True if data else False
        return None

    def change_clicks(self, short_url: str):

        short_code = short_url.split('/')[-1]
        data = self.db.query(ShortUrl).filter(ShortUrl.short_code == short_code, ShortUrl.is_active == 1).first()
        print(short_code)
        print(data)
        if data is not None:
            data.clicks += 1
            self.db.commit()
            self.db.refresh(data)
            print(data.original_url)
        return data.original_url

