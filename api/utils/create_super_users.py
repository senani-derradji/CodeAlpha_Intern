from sqlalchemy.orm import Session
from admin.admin_models import Admin
from admin.admin_db import get_db, init_db
from security.hash_ import _pwd_ctx
from config.settings import Info


def create_admin_user():
    init_db()

    db: Session = next(get_db())

    email    = Info.ADMIN_EMAIL
    name     = Info.ADMIN_EMAIL.split("@")[0]
    password = Info.ADMIN_PASSWORD

    try:
        if db.query(Admin).filter(Admin.email == email).first():
            print(f"Admin '{email}' already exists — skipping.")
            return

        admin = Admin(
            email=email,
            name=name,
            hashed_password=_pwd_ctx.hash(password),
            is_active=True,
            last_login=None,
        )
        db.add(admin)
        db.commit()
        print(f"Admin '{email}' created successfully.")

    except Exception as e:
        db.rollback()
        print(f"Failed to create admin: {e}")
        raise

    finally:
        db.close()