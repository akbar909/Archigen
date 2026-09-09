import datetime as dt
from flask import Blueprint, jsonify, request
from utils.db import users_collection
from utils.auth import hash_password, verify_password, generate_token

auth_bp = Blueprint("auth", __name__)

@auth_bp.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")
    name = (data.get("name") or "").strip()

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    email = email.lower().strip()
    
    if users_collection().find_one({"email": email}):
        return jsonify({"success": False, "error": "User already exists with this email"}), 409

    hashed_pw = hash_password(password)
    now = dt.datetime.utcnow()
    
    user_doc = {
        "name": name,
        "email": email,
        "password_hash": hashed_pw,
        "created_at": now
    }
    result = users_collection().insert_one(user_doc)
    
    token = generate_token(result.inserted_id, email, name=name)
    return jsonify({
        "success": True,
        "token": token,
        "user": {
            "id": str(result.inserted_id),
            "email": email,
            "name": name
        }
    }), 201

@auth_bp.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    email = email.lower().strip()
    
    user = users_collection().find_one({"email": email})
    if not user:
        return jsonify({"success": False, "error": "Invalid credentials"}), 401

    if not verify_password(password, user["password_hash"]):
        return jsonify({"success": False, "error": "Invalid credentials"}), 401

    name = user.get("name", "")
    token = generate_token(user["_id"], email, name=name)
    return jsonify({
        "success": True,
        "token": token,
        "user": {
            "id": str(user["_id"]),
            "email": email,
            "name": name
        }
    }), 200
