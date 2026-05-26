from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-only-change-me')
DEBUG = os.environ.get('DJANGO_DEBUG', 'false').lower() == 'true'
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,10.44.0.1').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'accounts', 'peers', 'commits', 'usage', 'integrations',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.WireGuardOnlyMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'wg_admin_project.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'wg_admin_project.wsgi.application'

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.environ.get('WG_SQLITE_PATH', str(BASE_DIR / 'db.sqlite3')), 'OPTIONS': {'timeout': 20}}}
AUTH_USER_MODEL = 'accounts.User'
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = os.environ.get('DJANGO_STATIC_ROOT', str(BASE_DIR / 'staticfiles'))
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
X_FRAME_OPTIONS = 'DENY'

WG_INTERFACE = os.environ.get('WG_INTERFACE', 'wg0')
WG_SUBNET = os.environ.get('WG_SUBNET', '10.44.0.0/24')
WG_SERVER_IP = os.environ.get('WG_SERVER_IP', '10.44.0.1')
WG_LISTEN_PORT = int(os.environ.get('WG_LISTEN_PORT', '51820'))
WG_PUBLIC_ENDPOINT = os.environ.get('WG_PUBLIC_ENDPOINT', '')
WG_PUBLIC_INTERFACE = os.environ.get('WG_PUBLIC_INTERFACE', 'eth0')
WG_CONFIG_PATH = os.environ.get('WG_CONFIG_PATH', '/etc/wireguard/wg0.conf')
WG_CANDIDATE_PATH = os.environ.get('WG_CANDIDATE_PATH', '/run/wg-admin/wg0.candidate.conf')
WG_APP_DATA_DIR = os.environ.get('WG_APP_DATA_DIR', '/var/lib/wg-admin')
WG_ENCRYPTION_KEY = os.environ.get('WG_ENCRYPTION_KEY', '')
