import os
from datetime import timedelta


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY    = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')

    PAYFAST_MERCHANT_ID  = os.environ.get('PAYFAST_MERCHANT_ID', '10000100')
    PAYFAST_MERCHANT_KEY = os.environ.get('PAYFAST_MERCHANT_KEY', '46f0cd694581a')
    PAYFAST_PASSPHRASE   = os.environ.get('PAYFAST_PASSPHRASE', '')
    PAYFAST_SANDBOX      = os.environ.get('PAYFAST_SANDBOX', 'true').lower() == 'true'

    APP_URL        = os.environ.get('APP_URL', 'http://localhost:5000')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

    MAIL_SERVER   = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT     = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS  = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)


class DevelopmentConfig(Config):
    DEBUG      = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-not-for-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///memory_lane.db'


class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY', '')

    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    _raw_db = os.environ.get('DATABASE_URL', '')
    SQLALCHEMY_DATABASE_URI = (
        _raw_db.replace('postgres://', 'postgresql://', 1)
        if _raw_db else ''
    )


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
