import hashlib
import secrets
from datetime import timedelta
from uuid import UUID

import jwt

from app.core.config import Settings
from app.core.time import utc_now


class TokenError(Exception):
    pass


def create_access_token(user_id: UUID, settings: Settings) -> str:
    now = utc_now()
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    if not isinstance(token, str):
        raise TokenError
    return token


def decode_access_token(token: str, settings: Settings) -> UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise TokenError
        return UUID(subject)
    except (jwt.PyJWTError, ValueError) as exc:
        raise TokenError from exc


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
