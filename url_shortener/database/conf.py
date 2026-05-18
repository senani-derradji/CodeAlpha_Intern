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
