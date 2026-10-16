"""mVault settings. All configuration comes from environment variables (see docs/configuration.md).

Secrets may be supplied as NAME or as NAME_FILE (path to a file containing the value, e.g. a Docker secret).
"""
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env.local", override=True)  # developer convenience; absent in containers


def env(name, default=""):
    path = os.environ.get(f"{name}_FILE")
    if path:
        return Path(path).read_text(encoding="utf-8").strip()
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = env(name, "")
    return default if value == "" else value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name):
    return [item.strip() for item in env(name, "").split(",") if item.strip()]


TESTING = "test" in sys.argv
DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG or TESTING:
        SECRET_KEY = "insecure-development-secret-key"
    else:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY (openssl rand -hex 48).")

# --- Public address -----------------------------------------------------------------------------
# MVAULT_BASE_URL (for example https://vault.example.com) drives allowed hosts, CSRF origins, secure
# cookies and HSTS. DJANGO_ALLOWED_HOSTS / DJANGO_CSRF_TRUSTED_ORIGINS add extras.
BASE_URL = env("MVAULT_BASE_URL").rstrip("/")
_base = urlsplit(BASE_URL) if BASE_URL else None
HTTPS_BASE = bool(_base and _base.scheme == "https")
ALLOWED_HOSTS = sorted({"localhost", "127.0.0.1", *env_list("DJANGO_ALLOWED_HOSTS"), *([_base.hostname] if _base and _base.hostname else [])})
CSRF_TRUSTED_ORIGINS = sorted({*env_list("DJANGO_CSRF_TRUSTED_ORIGINS"), *([f"{_base.scheme}://{_base.netloc}"] if _base else [])})

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
    "mvault_app.middleware.ContentSecurityPolicyMiddleware",
]
ROOT_URLCONF = "mvault_project.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages", "mvault_app.context_processors.sidebar", "mvault_app.context_processors.app_meta"]}}]
WSGI_APPLICATION = "mvault_project.wsgi.application"

# --- Database: DATABASE_URL (postgres://user:pass@host:port/name) or DB_* variables -----------------
_db_url = env("DATABASE_URL")
if _db_url:
    _u = urlsplit(_db_url)
    if _u.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must be a postgres:// or postgresql:// URL.")
    _db = {"NAME": unquote(_u.path.lstrip("/")), "USER": unquote(_u.username or ""), "PASSWORD": unquote(_u.password or ""),
           "HOST": _u.hostname or "localhost", "PORT": str(_u.port or 5432)}
else:
    _db = {"NAME": env("DB_NAME", "mvault"), "USER": env("DB_USER", "mvault"), "PASSWORD": env("DB_PASSWORD"),
           "HOST": env("DB_HOST", "localhost"), "PORT": env("DB_PORT", "5432")}
DATABASES = {"default": {"ENGINE": env("DB_ENGINE", "django.db.backends.postgresql"), "CONN_MAX_AGE": 60, **_db}}

# --- Field-level encryption of vault values (mvault_app/crypto.py) ------------------------------
ENCRYPTION_KEY = env("MVAULT_ENCRYPTION_KEY")
ENCRYPTION_SALT = env("MVAULT_ENCRYPTION_SALT")
if not (ENCRYPTION_KEY and ENCRYPTION_SALT):
    if DEBUG or TESTING:
        ENCRYPTION_KEY, ENCRYPTION_SALT = "insecure-local-key", "insecure-local-salt"
    elif "collectstatic" not in sys.argv:
        raise ImproperlyConfigured("Set MVAULT_ENCRYPTION_KEY and MVAULT_ENCRYPTION_SALT (openssl rand -hex 32 each).")

# --- S3-compatible object storage (optional): icons, avatars, file attachments -------------------
S3_ENDPOINT_URL = env("S3_ENDPOINT_URL")
S3_ACCESS_KEY = env("S3_ACCESS_KEY")
S3_SECRET_KEY = env("S3_SECRET_KEY")
if TESTING and not S3_ENDPOINT_URL:
    S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY = "http://storage.invalid:9000", "test", "test"
S3_REGION = env("S3_REGION", "us-east-1")
S3_ICONS_BUCKET = env("S3_ICONS_BUCKET", "mvault-icons")
S3_AVATARS_BUCKET = env("S3_AVATARS_BUCKET", "mvault-avatars")
S3_ATTACHMENTS_BUCKET = env("S3_ATTACHMENTS_BUCKET", "mvault-attachments")
S3_ADDRESSING_STYLE = env("S3_ADDRESSING_STYLE", "path")  # "path" (MinIO, R2, B2) or "virtual" (AWS S3)
S3_CONFIGURED = bool(S3_ENDPOINT_URL and S3_ACCESS_KEY and S3_SECRET_KEY)
# Optional public base URLs for the icons/avatars buckets. Empty (default): the app serves them at /media/.
ICONS_PUBLIC_BASE_URL = env("ICONS_PUBLIC_BASE_URL").rstrip("/")
AVATARS_PUBLIC_BASE_URL = env("AVATARS_PUBLIC_BASE_URL").rstrip("/")
MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024
MAX_ICON_BYTES = 2 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
APP_VERSION = "0.6.0"

# --- Accounts ---------------------------------------------------------------------------------------
ADMIN_EMAIL = (env("MVAULT_ADMIN_EMAIL") or "admin@mvault.local").strip().lower()
ADMIN_PASSWORD = env("MVAULT_ADMIN_PASSWORD")  # only used to create the first administrator
LOGIN_MAX_ATTEMPTS = int(env("MVAULT_LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_ATTEMPT_WINDOW_SECONDS = int(env("MVAULT_LOGIN_WINDOW_SECONDS", "900"))
TRUST_PROXY_HEADERS = env_bool("MVAULT_TRUST_PROXY", True)  # use the proxy-appended X-Forwarded-For entry for throttling
AUTH_USER_MODEL = "mvault_app.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher", "django.contrib.auth.hashers.PBKDF2PasswordHasher"]
LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"), ("ru", "Русский"), ("az", "Azərbaycanca"), ("tr", "Türkçe"),
    ("es", "Español"), ("be", "Беларуская"), ("uk", "Українська"),
]
TIME_ZONE = env("MVAULT_TIME_ZONE") or env("TZ") or "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

# --- Transport and cookie security ------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Secure cookies need HTTPS; default on when MVAULT_BASE_URL is https, off for plain-HTTP LAN installs.
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", HTTPS_BASE)
    CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
    SECURE_HSTS_SECONDS = int(env("MVAULT_HSTS_SECONDS", "31536000" if HTTPS_BASE else "0"))
