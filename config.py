import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-moi-en-prod-super-secret')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False