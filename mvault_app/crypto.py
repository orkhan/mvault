"""Application-level encryption for vault values stored in PostgreSQL.

A 256-bit AES-GCM key is derived with scrypt from two deployment secrets: the master
key (MVAULT_ENCRYPTION_KEY) and the salt (MVAULT_ENCRYPTION_SALT). Every value gets a
fresh random nonce. Ciphertext is stored as ``enc:v1:<base64(nonce + ciphertext+tag)>``.
Losing either secret makes the stored values unrecoverable.
"""
import base64
import hashlib
import os
from functools import lru_cache
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

PREFIX = "enc:v1:"
_CONTEXT = b"mvault-field-v1"


class DecryptionError(Exception):
    pass


@lru_cache(maxsize=4)
def _derive_key(master, salt):
    if not master or not salt:
        raise ImproperlyConfigured("MVAULT_ENCRYPTION_KEY and MVAULT_ENCRYPTION_SALT must be set.")
    return hashlib.scrypt(master.encode(), salt=salt.encode(), n=2 ** 15, r=8, p=1, dklen=32, maxmem=128 * 1024 * 1024)


def derive_key(master, salt):
    return _derive_key(master, salt)


def _aead(key=None):
    return AESGCM(key or _derive_key(settings.ENCRYPTION_KEY, settings.ENCRYPTION_SALT))


def is_encrypted(value):
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt_text(plaintext, key=None):
    nonce = os.urandom(12)
    sealed = _aead(key).encrypt(nonce, plaintext.encode("utf-8"), _CONTEXT)
    return PREFIX + base64.b64encode(nonce + sealed).decode("ascii")


def decrypt_text(token, key=None):
    try:
        raw = base64.b64decode(token[len(PREFIX):], validate=True)
        return _aead(key).decrypt(raw[:12], raw[12:], _CONTEXT).decode("utf-8")
    except (InvalidTag, ValueError) as exc:
        raise DecryptionError("Stored value could not be decrypted; check the encryption key and salt.") from exc
