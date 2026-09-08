import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Load all key=value pairs from gem_api.env into environment variables
def _load_env_file(filepath):
    """Reads a simple KEY=VALUE env file and sets them as environment variables."""
    if not os.path.isfile(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and value:
                    os.environ[key] = value


_load_env_file(os.path.join(BASE_DIR, "gem_api.env"))


# Flask server config
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "7860"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# MongoDB config
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://fyp:fyp@cluster0.xr6mbty.mongodb.net/?appName=Cluster0")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", os.getenv("name", "archigen"))

# Auth / JWT
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY_FILE = os.getenv(
	"GEMINI_API_KEY_FILE", os.path.join(BASE_DIR, "gem_api.env")
)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_BASE_URL = os.getenv(
	"GEMINI_API_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/models"
)

# Blender Worker microservice config
BLENDER_SERVICE_URL = os.getenv("BLENDER_SERVICE_URL", "http://localhost:5001")
BLENDER_ENABLED = os.getenv("BLENDER_ENABLED", "true").lower() == "true"
BLENDER_TIMEOUT_SECONDS = int(os.getenv("BLENDER_TIMEOUT_SECONDS", "180"))

# AWS S3 Storage config
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET", "archigen-storage")
AWS_S3_PUBLIC_BASE_URL = os.getenv("AWS_S3_PUBLIC_BASE_URL", "")


