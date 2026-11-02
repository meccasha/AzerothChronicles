"""Password hashing, opaque token generation and credential encryption."""

import base64
import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def new_token(prefix: str = "", nbytes: int = 32) -> str:
    return f"{prefix}{secrets.token_urlsafe(nbytes)}"


def hash_token(token: str) -> str:
    """Tokens are stored only as SHA-256 digests; the raw value is shown once."""
    return hashlib.sha256(token.encode()).hexdigest()


def _fernet() -> Fernet:
    key = get_settings().credentials_encryption_key
    if not key:
        if get_settings().app_env == "production":
            raise RuntimeError("CREDENTIALS_ENCRYPTION_KEY must be set in production")
        # Development fallback: derive a deterministic key so local dev works out of the box.
        key = base64.urlsafe_b64encode(hashlib.sha256(b"azeroth-dev-only-key").digest()).decode()
    return Fernet(key.encode())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:  # pragma: no cover - indicates key rotation problem
        raise RuntimeError("Unable to decrypt stored credential (encryption key changed?)") from exc
