import datetime as dt
import os
from typing import Any, Dict

import bcrypt
import jwt
from bson import ObjectId

from config import JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET


def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def verify_password(password: str, password_hash: bytes) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash)
    except Exception:
        return False


def generate_token(user_id: ObjectId, email: str, name: str = "") -> str:
    exp = dt.datetime.utcnow() + dt.timedelta(hours=JWT_EXPIRE_HOURS)
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "name": name,
        "exp": exp,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
