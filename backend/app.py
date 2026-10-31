# pyrefly: ignore [missing-import]
import re
from flask import Flask, jsonify, request
from flask_cors import CORS

from config import ALLOWED_ORIGINS, DEBUG, HOST, PORT
from routes.auth import auth_bp
from routes.chat import chat_bp
from utils.db import get_db
from utils.gemini import GeminiSchemaValidationError
from utils.s3_storage import configure_bucket_cors

CORS_ORIGIN_PATTERNS = [
    re.compile(r"^https?://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?$"),
]
ALL_ALLOWED_ORIGINS = list(ALLOWED_ORIGINS) + CORS_ORIGIN_PATTERNS


def _is_allowed_origin(origin: str) -> bool:
    if not origin:
        return False
    if origin in ALLOWED_ORIGINS:
        return True
    for pattern in CORS_ORIGIN_PATTERNS:
        if pattern.match(origin):
            return True
    return False


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(
        app,
        resources={r"/*": {"origins": ALL_ALLOWED_ORIGINS}},
        supports_credentials=True,
        methods=["GET", "HEAD", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    )

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin and _is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
        elif not origin:
            response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization,X-Requested-With"
        response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,PATCH,DELETE,OPTIONS"
        return response

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/api")

    # Initialize db and S3 bucket CORS
    try:
        get_db()
        print("Database connected successfully!")
    except Exception as e:
        # Keep app running; endpoints will surface errors
        print(f"Failed to connect to database: {e}")
        pass

    try:
        configure_bucket_cors()
    except Exception:
        pass

    @app.get("/health")
    def health_check():
        return jsonify({"status": "ok"}), 200

    @app.get("/")
    def root():
        # Provide a simple landing payload so hitting '/' doesn't 404
        return jsonify({
            "status": "ok",
            "message": "ArchiGen API is running",
            "endpoints": ["/health", "/api/auth/login", "/api/auth/register",
                    "/api/chat", "/api/history",
                    "/api/projects", "/api/projects/<id>", "/api/projects/<id>/generate",
                    "/api/projects/<id>/versions", "/api/versions/<id>"],
        }), 200

    @app.errorhandler(GeminiSchemaValidationError)
    def handle_gemini_schema_validation_error(exc):
        return jsonify({"success": False, "error": str(exc)}), 422

    @app.errorhandler(Exception)
    def handle_generic_exception(exc):
        import traceback
        print(f"[ERROR] Uncaught exception: {exc}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(exc)}), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=DEBUG)
