from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
print(BASE_DIR)
ENV_PATH = os.path.join(BASE_DIR, '.env')
print(ENV_PATH)

load_dotenv(dotenv_path=ENV_PATH)


class Info:
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")
    DOMAIN = os.getenv("DOMAIN", "http://127.0.0.1:8000")

    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = os.getenv("REDIS_PORT", 6379)
    REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default")
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "password")

    URL_EXPIRATION_TIME_IN_SECONDS = os.getenv("URL_EXPIRATION_TIME_IN_SECONDS", 604800)
    if isinstance(URL_EXPIRATION_TIME_IN_SECONDS, str):
        URL_EXPIRATION_TIME_IN_SECONDS = int(URL_EXPIRATION_TIME_IN_SECONDS)

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

    SECRET_KEY = os.getenv("SECRET_KEY")

    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")



