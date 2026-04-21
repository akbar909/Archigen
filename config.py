import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# Flask server config
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# MongoDB config
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://fyp:fyp@cluster0.xr6mbty.mongodb.net/?appName=Cluster0")
MONGO_DB_NAME = os.getenv("name", "yourpassword")

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

