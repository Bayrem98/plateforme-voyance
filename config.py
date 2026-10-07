import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', '25ebef9b2cecd5a078f4e62d89f19fe3dcf0fb16ba1d9d2d503b1fe70ead909e')

    # Neon fournit une URL en postgresql://, SQLAlchemy attend postgresql+psycopg2://
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
    if _db_url and _db_url.startswith('postgresql://'):
        _db_url = _db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ✅ Bien indenté
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 5,
        "max_overflow": 10,
    }

    # ========== EMAIL (Gmail) ==========
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 465
    MAIL_USE_TLS = False
    MAIL_USE_SSL = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME')

    BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')