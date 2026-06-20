"""Auth: bcrypt password check against config/users.yaml + JWT issue/verify."""
from __future__ import annotations

import time

import bcrypt
import jwt
import yaml

from apps.api.core.config import settings


def load_users() -> dict:
    if not settings.USERS_FILE.exists():
        return {}
    data = yaml.safe_load(settings.USERS_FILE.read_text(encoding="utf-8")) or {}
    return data.get("credentials", {}).get("usernames", {})


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def create_token(username: str, name: str, role: str) -> str:
    payload = {
        "sub": username,
        "name": name,
        "role": role,
        "exp": int(time.time()) + settings.JWT_EXPIRE_HOURS * 3600,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
