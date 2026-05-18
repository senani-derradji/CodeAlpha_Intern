from starlette.middleware.sessions import SessionMiddleware
from database.conf import Info


def register_session_middleware(app):

    app.add_middleware(
        SessionMiddleware,
        secret_key=Info.SECRET_KEY
    )