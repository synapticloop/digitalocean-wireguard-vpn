from django.conf import settings
from cryptography.fernet import Fernet


def fernet():
    if not settings.WG_ENCRYPTION_KEY:
        raise RuntimeError('WG_ENCRYPTION_KEY is not configured')
    return Fernet(settings.WG_ENCRYPTION_KEY.encode())


def encrypt(value: str) -> bytes:
    return fernet().encrypt(value.encode())


def decrypt(value: bytes) -> str:
    return fernet().decrypt(value).decode()
