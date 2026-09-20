import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "watercare.db"

# Load .env file
load_dotenv(BASE_DIR / ".env")

# Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

def has_gemini_key() -> bool:
    return bool(GEMINI_API_KEY and len(GEMINI_API_KEY) > 10)
