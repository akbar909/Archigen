from functools import wraps
from typing import Callable, TypeVar

from bson import ObjectId
from flask import Request, jsonify, request

from utils.auth import decode_token
import jwt

F = TypeVar("F", bound=Callable)


def require_auth(fn: F) -> F:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"error": "Authorization token missing"}), 401

        token = parts[1]
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
            email = payload.get("email")
            if not user_id or not email:
                raise ValueError("Invalid token payload")
            request.user = {"_id": ObjectId(user_id), "email": email}
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401

        return fn(*args, **kwargs)

    return wrapper  # type: ignore
