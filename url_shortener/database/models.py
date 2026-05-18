from sqlalchemy import Column, Integer, String, DATETIME, ForeignKey
from sqlalchemy.orm import relationship
from database.db import Base
from datetime import datetime, timedelta



class ShortUrl(Base):
    __tablename__ = "short_urls"

    id = Column(Integer, primary_key=True, index=True)
    original_url = Column(String(2048), nullable=False, index=True)
    short_code = Column(String, unique=True, index=True, nullable=False)
    clicks = Column(Integer, default=0)
    created_at = Column(DATETIME, default=datetime.utcnow())
    expires_at = Column(DATETIME, default=datetime.utcnow() + timedelta(days=30) )
    is_active = Column(Integer, default=1)
