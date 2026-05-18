from database.models import User
from sqlalchemy.orm import Session
from database.db import get_db


class UserOperations:
    def __init__(self):
        self.db : Session = next(get_db())


    async def create_user(self, email: str, name: str, picture: str):
        if self.db.query(User).filter(User.email == email).first():
            return None
        user = User(email=email, name=name, picture=picture)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return user.name

    async def get_user_by_email(self, email: str):
        if email is None:
            return None
        user = self.db.query(User).filter(User.email == email).first()
        if user is None:
            return None
        return user