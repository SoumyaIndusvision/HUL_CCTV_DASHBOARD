import os
from pathlib import Path
from dotenv import load_dotenv
from celery.schedules import crontab
# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-6@cen74$wv(km$xjh95r#7v0#*ev)v6afj&lzzhkqtv6vfs2er'

# Secret Key (Do NOT expose this in public repositories)
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')

DEBUG = True

ALLOWED_HOSTS = ['*', 'localhost', '127.0.0.1', 'cctv.indusvision.in', 'www.cctv.indusvision.in', 'cctv.localhost']

# Installed Apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'users',
    'multi_cam_stream',
    'rest_framework',
    'drf_yasg',
    'corsheaders',
]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'HUL_CCTV_PROJ.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'HUL_CCTV_PROJ.wsgi.application'

# Database Configuration (Use .env variables for production settings)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

AUTH_USER_MODEL = 'users.User'

# Redis for Celery (Use .env for Redis connection string)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Celery Beat Schedule (Ping cameras task every 1 hour)
CELERY_BEAT_SCHEDULE = {
    'ping-cameras-and-send-report-every-hour': {
        'task': 'multi_cam_stream.tasks.ping_cameras_and_send_report',  # Path to your task
        'schedule': crontab(minute=0, hour='*'),  # Every 1 hour
    },
}

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "https://cctv.indusvision.in",
    "https://www.cctv.indusvision.in",
]
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = ["accept", "accept-encoding", "authorization", "content-type", "dnt", "origin", "user-agent", "x-csrftoken", "x-requested-with"]

# Email Configuration (Use .env for email settings)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')

# Timezone Configuration
TIME_ZONE = 'Asia/Kolkata'
USE_TZ = True

# Static files configuration
STATIC_URL = '/static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
