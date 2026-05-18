from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean
)

from sqlalchemy.orm import relationship
from database.db import Base
from datetime import datetime, timedelta


def default_expiration():
    return datetime.utcnow() + timedelta(seconds=604800)


class ShortUrl(Base):
    __tablename__ = "short_urls"

    id = Column(Integer, primary_key=True, index=True)

    original_url = Column(String(2048), nullable=False, index=True)

    short_code = Column(String, unique=True, index=True, nullable=False)

    clicks = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    expires_at = Column(DateTime, default=default_expiration)

    is_active = Column(Boolean, default=True)

    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="short_urls")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String, unique=True, index=True, nullable=False)

    name = Column(String, nullable=False, index=True)

    picture = Column(String, nullable=True)

    role = Column(String, nullable=False, default="user")

    short_urls = relationship("ShortUrl", back_populates="user")