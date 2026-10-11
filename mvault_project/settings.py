import os
import sys
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env.local", override=True)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = sorted({"localhost", "127.0.0.1", *[h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]})
CSRF_TRUSTED_ORIGINS = [u.strip() for u in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if u.strip()]

INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles", "mvault_app",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware", "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    "mvault_app.middleware.PreferredLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "mvault_app.middleware.PasswordChangeRequiredMiddleware",
]
ROOT_URLCONF = "mvault_project.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "mvault_app.context_processors.sidebar", "mvault_app.context_processors.app_meta"]}}]
WSGI_APPLICATION = "mvault_project.wsgi.application"
DATABASES = {"default": {
    "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.postgresql"),
    "NAME": os.environ.get("DB_NAME", "mvault"), "USER": os.environ.get("DB_USER", "mvault"),
    "PASSWORD": os.environ.get("DB_PASSWORD", ""), "HOST": os.environ.get("DB_HOST", "postgresql"),
    "PORT": os.environ.get("DB_PORT", "5432"), "CONN_MAX_AGE": 60,
}}

# Field-level encryption of vault values (see mvault_app/crypto.py). Required outside DEBUG/tests.
ENCRYPTION_KEY = os.environ.get("MVAULT_ENCRYPTION_KEY", "")
ENCRYPTION_SALT = os.environ.get("MVAULT_ENCRYPTION_SALT", "")
if not (ENCRYPTION_KEY and ENCRYPTION_SALT):
    if DEBUG or "test" in sys.argv:
        ENCRYPTION_KEY, ENCRYPTION_SALT = "insecure-local-key", "insecure-local-salt"
    elif "collectstatic" not in sys.argv:
        raise ImproperlyConfigured("Set MVAULT_ENCRYPTION_KEY and MVAULT_ENCRYPTION_SALT.")

# S3-compatible object storage (MinIO): public icons bucket, private attachments bucket.
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "http://minio:9000")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
S3_ICONS_BUCKET = os.environ.get("S3_ICONS_BUCKET", "mvault-icons")
S3_AVATARS_BUCKET = os.environ.get("S3_AVATARS_BUCKET", "mvault-avatars")
S3_ATTACHMENTS_BUCKET = os.environ.get("S3_ATTACHMENTS_BUCKET", "mvault-attachments")
# Optional public base URLs for the icons/avatars buckets. Empty (default): the app serves them at /media/.
ICONS_PUBLIC_BASE_URL = os.environ.get("ICONS_PUBLIC_BASE_URL", "").rstrip("/")
AVATARS_PUBLIC_BASE_URL = os.environ.get("AVATARS_PUBLIC_BASE_URL", "").rstrip("/")
MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024
MAX_ICON_BYTES = 2 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
APP_VERSION = "0.3.0"

AUTH_USER_MODEL = "mvault_app.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher", "django.contrib.auth.hashers.PBKDF2PasswordHasher"]
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("ru", "Русский")]
TIME_ZONE = os.environ.get("TZ") or os.environ.get("MVAULT_TIME_ZONE") or "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true"
    CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
