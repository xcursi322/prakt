"""
Налаштування Django для проєкту sportshop.

Згенеровано командою 'django-admin startproject' з використанням Django 6.0.1.

Детальніше про цей файл:
https://docs.djangoproject.com/en/6.0/topics/settings/

Повний список налаштувань і їхніх значень:
https://docs.djangoproject.com/en/6.0/ref/settings/
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

try:
    import dj_database_url  # pyright: ignore[reportMissingImports]
except ImportError:
    dj_database_url = None

# Формуємо шляхи всередині проєкту так: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Налаштування для швидкого старту розробки — не підходять для продакшену
# Див. https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# ПОПЕРЕДЖЕННЯ БЕЗПЕКИ: тримайте секретний ключ продакшену в таємниці!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-only-key')

# ПОПЕРЕДЖЕННЯ БЕЗПЕКИ: не вмикайте debug у продакшені!
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', '.onrender.com,localhost,127.0.0.1').split(',')
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', 'https://*.onrender.com').split(',')
    if origin.strip()
]


# Визначення застосунків

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'shop',
    'widget_tweaks',
]

CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME', '').strip()
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY', '').strip()
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET', '').strip()

USE_CLOUDINARY = all([
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
])

if USE_CLOUDINARY:
    INSTALLED_APPS += [
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

ROOT_URLCONF = 'sportshop.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'shop.context_processors.cart_count',
            ],
        },
    },
]

WSGI_APPLICATION = 'sportshop.wsgi.application'


# База даних
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

if os.getenv('DATABASE_URL'):
    if dj_database_url is None:
        raise ImproperlyConfigured('dj-database-url must be installed when DATABASE_URL is set.')
    DATABASES['default'] = dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True,
    )


# Перевірка паролів
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Інтернаціоналізація
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Статичні файли (CSS, JavaScript, зображення)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Медіафайли
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT', str(BASE_DIR / 'media')))

if USE_CLOUDINARY:
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
        'API_KEY': CLOUDINARY_API_KEY,
        'API_SECRET': CLOUDINARY_API_SECRET,
        'SECURE': True,
    }

    STORAGES = {
        'default': {
            'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
else:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
