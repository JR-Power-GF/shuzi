import bcrypt
import hashlib
import datetime

import jwt

from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(user_id: int, role: str, username: str) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "username": username,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id: int) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
