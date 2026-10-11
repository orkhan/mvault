import json
from django.db import models
from .crypto import decrypt_text, encrypt_text, is_encrypted


class EncryptedJSONField(models.TextField):
    """JSON value stored as AES-GCM ciphertext in a text column.

    Reads tolerate legacy plaintext JSON so rows can be migrated in place; every write
    is encrypted.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("default", dict)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return None
        return json.loads(decrypt_text(value) if is_encrypted(value) else value)

    def to_python(self, value):
        if isinstance(value, str):
            try:
                return json.loads(decrypt_text(value) if is_encrypted(value) else value)
            except ValueError:
                return value
        return value

    def get_prep_value(self, value):
        if value is None:
            return None
        return encrypt_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
