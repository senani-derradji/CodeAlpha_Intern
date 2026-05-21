from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from admin.admin_db import Base


class Admin(Base):
    __tablename__ = "admins"

    id         = Column(Integer, primary_key=True, index=True)
    email      = Column(String, unique=True, nullable=False, index=True)
    name       = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)