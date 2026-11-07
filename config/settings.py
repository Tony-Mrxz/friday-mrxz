"""
config/settings.py - Central Configuration & Environment Manager for Friday AI
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

# Load .env file if present
if ENV_FILE.exists():
    load_dotenv(ENV_FILE, override=True)

# Directories
DATA_DIR = BASE_DIR / "data"
MEMORY_DIR = BASE_DIR / "memory" / "data"
LOGS_DIR = BASE_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"

for d in [DATA_DIR, MEMORY_DIR, LOGS_DIR, TEMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def get_github_token() -> str:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)
    return os.getenv("GITHUB_TOKEN", "").strip()


def get_groq_key() -> str:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)
    return os.getenv("GROQ_API_KEY", "").strip()


def get_telegram_token() -> str:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def get_authorized_user_ids() -> list:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)
    _raw = os.getenv("AUTHORIZED_USER_IDS", "").strip()
    if not _raw or _raw.lower() in ["all", "*", "none", "disable", "disabled"]:
        return []
    return [int(uid.strip()) for uid in _raw.split(",") if uid.strip().isdigit()]


# Static fallbacks for initial module load
GITHUB_TOKEN = get_github_token()
GROQ_API_KEY = get_groq_key()
TELEGRAM_BOT_TOKEN = get_telegram_token()
AUTHORIZED_USER_IDS = get_authorized_user_ids()

WEBRTC_PORT = int(os.getenv("WEBRTC_PORT", "8000"))
GITHUB_MODEL_NAME = "gpt-4o"
GROQ_MODEL_NAME = "openai/gpt-oss-120b"
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"



def save_env_values(github_token: str = None, groq_key: str = None, tg_token: str = None, user_ids: str = None):
    """Saves API keys dynamically into .env file."""
    env_data = {}
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    env_data[k] = v

    if github_token is not None:
        env_data["GITHUB_TOKEN"] = github_token.strip()
    if groq_key is not None:
        env_data["GROQ_API_KEY"] = groq_key.strip()
    if tg_token is not None:
        env_data["TELEGRAM_BOT_TOKEN"] = tg_token.strip()
    if user_ids is not None:
        env_data["AUTHORIZED_USER_IDS"] = user_ids.strip()

    if "WEBRTC_PORT" not in env_data:
        env_data["WEBRTC_PORT"] = "8000"

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("# Friday AI Environment Configuration\n")
        for k, v in env_data.items():
            f.write(f"{k}={v}\n")

    # Force re-read
    load_dotenv(ENV_FILE, override=True)
