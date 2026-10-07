import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-moi-en-prod-super-secret')
    
    # ⚠️ Neon fournit une URL en postgresql://, mais SQLAlchemy attend postgresql+psycopg2://
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
    if _db_url and _db_url.startswith('postgresql://'):
        _db_url = _db_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ========== EMAIL (Gmail) ==========
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_USERNAME')

    # URL de base pour les liens dans les emails
    BASE_URL = os.environ.get('BASE_URL', 'http://127.0.0.1:5000')