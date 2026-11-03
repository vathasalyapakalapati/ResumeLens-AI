"""Password hashing and token helpers. No database or HTTP code lives here."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import get_settings

_hasher = PasswordHasher()
_ALGORITHM = "HS256"

# Verified against when the email is unknown, so a login attempt takes the same time
# whether or not the account exists (no user enumeration by timing).
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=get_settings().access_token_minutes),
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=_ALGORITHM)


def read_access_token(token: str) -> uuid.UUID | None:
    """The user id inside a valid, unexpired access token, else None."""
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def new_refresh_token() -> str:
    """An opaque random token. Only its hash is stored."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    # The token is 384 random bits, so a fast hash is enough (no need for Argon2 here).
    return hashlib.sha256(token.encode()).hexdigest()
