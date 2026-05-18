from database.models import ShortUrl
from datetime import datetime


async def deactivate_expired_urls(db):

    expired_urls = db.query(ShortUrl).filter(
        ShortUrl.expires_at < datetime.utcnow(),
        ShortUrl.is_active == True
    ).all()

    for url in expired_urls:

        url.is_active = False

    db.commit()