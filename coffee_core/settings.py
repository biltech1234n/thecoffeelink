import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-change-me-for-production'
# Change these lines:
DEBUG = 'RENDER' not in os.environ # False on Render, True on your PC
ALLOWED_HOSTS = ['*'] # Allows Render to access your site

# INSTALLED_APPS: Order matters! 'daphne' must be before 'django.contrib.staticfiles'
INSTALLED_APPS = [
    'daphne', # For Chat/WebSockets
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Custom Apps
    'accounts',
    'market',
    'chat',
    'core',
    # Add these two:
    'cloudinary_storage',
    'cloudinary',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'coffee_core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Global templates folder
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.user_notifications',
            ],
        },
    },
]

# Database Connection (PostgreSQL)
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': 'coffee_db',
#         'USER': 'postgres',        # Default user
#         'PASSWORD': 'Bilal1234', # <--- PUT YOUR POSTGRES PASSWORD HERE
#         'HOST': 'localhost',
#         'PORT': '5432',
#     }
# }
# Database (Auto-switches between Neon on Render and Local on PC)
DATABASES = {
    'default': dj_database_url.config(
        # Your local fallback (keep using your local postgres info here for development)
        default='postgresql://postgres:yourpassword@localhost:5432/coffee_db',
        conn_max_age=600,
        ssl_require=True 
    )
}


# User Model
AUTH_USER_MODEL = 'accounts.User'

# Channel Layer (For Chat - Using In-Memory for Dev, use Redis for Prod)
ASGI_APPLICATION = 'coffee_core.asgi.application'
# Chat (Redis) Configuration
if 'REDIS_URL' in os.environ:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [os.environ.get('REDIS_URL')],
            },
        },
    }
else:
    # Local fallback
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }

# Static & Media
STATIC_URL = 'static/'

# ADD THIS PART!
# This tells Django to look in the 'static' folder in your root directory
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redirects
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

ADMIN_SIGNUP_PASSCODE = "COFFEE_MASTER_2025"

# settings.py

# 1. Configuration for CloudinaryField (The one causing the error)
CLOUDINARY = {
    'cloud_name': 'dhfyolanv',
    'api_key': '399471574245624',
    'api_secret': 'kFY9tTVdDfUTLT9-oux8SMFuNGQ',
}

# 2. Configuration for Django File Storage (For general storage)
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': 'dhfyolanv',
    'API_KEY': '399471574245624',
    'API_SECRET': 'kFY9tTVdDfUTLT9-oux8SMFuNGQ',
}

# 3. Set the media storage
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'