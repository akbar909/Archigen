from flask import Blueprint, jsonify, request
from utils.db import users_collection
from utils.auth import hash_password, verify_password, generate_token

auth_bp = Blueprint("auth", __name__)

@auth_bp.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required"}), 400

    email = email.lower().strip()
    
    if users_collection().find_one({"email": email}):
        return jsonify({"success": False, "error": "User already exists with this email"}), 409

    hashed_pw = hash_password(password)
    
    user_doc = {
        "email": email,
        "password_hash": hashed_pw
    }
    result = users_collection().insert_one(user_doc)
    
    token = generate_token(result.inserted_id, email)
    return jsonify({"success": True, "token": token}), 201

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

    token = generate_token(user["_id"], email)
    return jsonify({"success": True, "token": token}), 200
