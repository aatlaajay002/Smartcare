"""Central configuration. Values come from environment variables or a .env file in this folder."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent


def _load_env_file():
    env = BASE_DIR / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    FRONTEND_DIR = ROOT_DIR / "Frontend"
    ML_DIR = ROOT_DIR / "ML"
    MODEL_PATH = ML_DIR / "symptom_model.joblib"

    # ---- Database: "mysql" or "sqlite" (sqlite = zero-setup fallback) ----
    DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()
    SQLITE_PATH = os.getenv("SQLITE_PATH", str(BASE_DIR / "healthcare.db"))
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "smart_healthcare")

    # ---- Generative AI (LLM API): anthropic | gemini | openai ----
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower()
    LLM_MODEL = os.getenv("LLM_MODEL", "")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # ---- Admin account (created automatically on first start) ----
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Administrator")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@smartcare.com").lower()
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin@123")

    MAX_REPORT_CHARS = 6000
    MAX_UPLOAD_MB = 5
