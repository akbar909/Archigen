from flask import Flask, jsonify
from flask_cors import CORS

from config import DEBUG, HOST, PORT
from routes.auth import auth_bp
from routes.chat import chat_bp
from utils.db import get_db


def create_app() -> Flask:
	app = Flask(__name__)
	CORS(app, supports_credentials=True)

	# Register blueprints
	app.register_blueprint(auth_bp, url_prefix="/api")
	app.register_blueprint(chat_bp, url_prefix="/api")

	# Initialize db early to fail fast if connection is bad
	try:
		get_db()
		print("Database connected successfully!")
	except Exception as e:
		# Keep app running; endpoints will surface errors
		print(f"Failed to connect to database: {e}")
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
			"endpoints": ["/health", "/api/auth/login", "/api/auth/register", "/api/chat", "/api/history"],
		}), 200

	return app


app = create_app()


if __name__ == "__main__":
	app.run(host=HOST, port=PORT, debug=DEBUG)

