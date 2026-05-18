from sqlalchemy.orm import Session
from database.models import User
from database.db import get_db

def create_admin_user(email: str, name: str, picture: str, db: Session = next(get_db())):
    if db.query(User).filter(User.email == email).first():
        return

    user = User(email=email, name=name, picture=picture, role="admin")
    db.add(user)
    db.commit()
    db.refresh(user)

    return user