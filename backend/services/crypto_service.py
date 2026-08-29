import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from backend.config import settings

_PREFIX = "fernet:"


def _derive_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(_derive_key(settings.SECRET_KEY))


def is_encrypted(value: str) -> bool:
    return isinstance(value, str) and value.startswith(_PREFIX)


def encrypt_secret(plain: str) -> str:
    if plain is None:
        plain = ""
    if is_encrypted(plain) or plain == "":
        return plain
    return _PREFIX + _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    if value is None:
        return ""
    if not is_encrypted(value):
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX):].encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""
