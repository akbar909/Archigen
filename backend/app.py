# pyrefly: ignore [missing-import]
from flask import Flask, jsonify, request
from flask_cors import CORS

from config import DEBUG, HOST, PORT
from routes.auth import auth_bp
from routes.chat import chat_bp
from utils.db import get_db
from utils.gemini import GeminiSchemaValidationError
from utils.s3_storage import configure_bucket_cors


def create_app() -> Flask:
	app = Flask(__name__)
	CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True, methods=["GET", "HEAD", "POST", "OPTIONS", "PUT", "PATCH", "DELETE"])

	@app.after_request
	def add_cors_headers(response):
		origin = request.headers.get("Origin")
		response.headers["Access-Control-Allow-Origin"] = origin if origin else "*"
		response.headers["Access-Control-Allow-Credentials"] = "true"
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

