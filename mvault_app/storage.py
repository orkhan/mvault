"""Object storage (MinIO / S3) for custom icons and file-record attachments."""
import io
import uuid
from functools import lru_cache
import boto3
from botocore.config import Config
from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError

ICON_SIZE = 128
AVATAR_SIZE = 256
ICON_FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}


class StorageError(Exception):
    pass


def is_configured():
    return settings.S3_CONFIGURED


def _require_storage():
    if not is_configured():
        raise StorageError("File storage is not configured on this server.")


class _KeepOpen:
    """Read-only view of a file that ignores close(); boto3 closes the object it uploads."""

    def __init__(self, fileobj):
        self._file = fileobj

    def read(self, size=-1):
        return self._file.read(size)

    def seek(self, *args):
        return self._file.seek(*args)

    def tell(self):
        return self._file.tell()

    def close(self):
        pass


class S3Storage:
    def __init__(self):
        self.client = boto3.client(
            "s3", endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY, aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION, config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                                                  retries={"max_attempts": 3}, connect_timeout=5, read_timeout=60),
        )

    def put(self, bucket, key, fileobj, content_type):
        self.client.upload_fileobj(_KeepOpen(fileobj), bucket, key, ExtraArgs={"ContentType": content_type})

    def open(self, bucket, key):
        """Return (streaming body, content length)."""
        obj = self.client.get_object(Bucket=bucket, Key=key)
        return obj["Body"], obj["ContentLength"]

    def delete(self, bucket, key):
        self.client.delete_object(Bucket=bucket, Key=key)

    def copy(self, bucket, source_key, target_key):
        self.client.copy_object(Bucket=bucket, Key=target_key, CopySource={"Bucket": bucket, "Key": source_key})


@lru_cache(maxsize=1)
def get_storage():
    return S3Storage()


def icon_public_url(key):
    return f"{settings.ICONS_PUBLIC_BASE_URL}/{key}" if settings.ICONS_PUBLIC_BASE_URL else f"/media/icons/{key}"


def avatar_public_url(key):
    return f"{settings.AVATARS_PUBLIC_BASE_URL}/{key}" if settings.AVATARS_PUBLIC_BASE_URL else f"/media/avatars/{key}"


def save_icon(kind, upload):
    """Validate an uploaded image, normalise it to a 128px PNG, store it; return the object key."""
    return _save_image(kind, upload, settings.S3_ICONS_BUCKET, ICON_SIZE, "Icons", settings.MAX_ICON_BYTES)


def save_avatar(upload):
    """Validate an uploaded picture, centre-crop it to a 256px square PNG, store it in the avatars bucket."""
    return _save_image("users", upload, settings.S3_AVATARS_BUCKET, AVATAR_SIZE, "Avatars", settings.MAX_ICON_BYTES, square=True)


def delete_avatar(key):
    try:
        get_storage().delete(settings.S3_AVATARS_BUCKET, key)
    except Exception:  # a leftover public object is not worth failing the request
        pass


def _save_image(kind, upload, bucket, size, label, max_bytes, square=False):
    _require_storage()
    if upload.size > max_bytes:
        raise StorageError(f"{label} must be 2 MB or smaller.")
    try:
        image = Image.open(upload)
        if image.format not in ICON_FORMATS:
            raise StorageError(f"{label} must be PNG, JPEG, WebP, or GIF images.")
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise StorageError("That file is not a valid image.") from exc
    image = image.convert("RGBA")
    if square:
        image = ImageOps.fit(image, (size, size))
    else:
        image.thumbnail((size, size))
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    buffer.seek(0)
    key = f"{kind}/{uuid.uuid4().hex}.png"
    try:
        get_storage().put(bucket, key, buffer, "image/png")
    except Exception as exc:  # boto raises many types; surface one
        raise StorageError("Could not store the image. Try again later.") from exc
    return key


def save_attachment(upload):
    """Store an uploaded file in the private bucket; return its object key."""
    _require_storage()
    key = f"attachments/{uuid.uuid4().hex}"
    try:
        upload.seek(0)
        get_storage().put(settings.S3_ATTACHMENTS_BUCKET, key, upload, upload.content_type or "application/octet-stream")
    except Exception as exc:
        raise StorageError("Could not store the file. Try again later.") from exc
    return key


def copy_attachment(source_key):
    _require_storage()
    key = f"attachments/{uuid.uuid4().hex}"
    try:
        get_storage().copy(settings.S3_ATTACHMENTS_BUCKET, source_key, key)
    except Exception as exc:
        raise StorageError("Could not copy the file. Try again later.") from exc
    return key


def delete_attachment(key):
    get_storage().delete(settings.S3_ATTACHMENTS_BUCKET, key)
