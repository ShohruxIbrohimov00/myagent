"""
Markaziy konfiguratsiya. Barcha sozlamalar .env faylidan o'qiladi.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    """Majburiy sozlama. Bo'sh bo'lsa xato beradi (xatoni erta ushlash uchun)."""
    val = os.getenv(name, "").strip()
    if not val:
        raise RuntimeError(f"'.env' faylida {name} to'ldirilmagan!")
    return val


def _list(name: str) -> list[str]:
    """Vergul bilan ajratilgan ro'yxatni o'qiydi."""
    raw = os.getenv(name, "")
    return [x.strip() for x in raw.split(",") if x.strip()]


# --- Telegram bot (admin boshqaruvi) ---
BOT_TOKEN = _require("BOT_TOKEN")
ADMIN_ID = int(_require("ADMIN_ID"))
TARGET_CHANNEL = _require("TARGET_CHANNEL")

# --- Telethon (manba o'qish) ---
API_ID = int(_require("API_ID"))
API_HASH = _require("API_HASH")
SOURCE_CHANNELS = _list("SOURCE_CHANNELS")

# --- Gemini ---
GEMINI_API_KEYS = _list("GEMINI_API_KEYS")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash").strip()

# --- Boshqa ---
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "120"))

# Fayllar joylashuvi
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "shohrux.db")
SESSION_PATH = os.path.join(BASE_DIR, "shohrux_session")
MEDIA_DIR = os.path.join(BASE_DIR, "media")

os.makedirs(MEDIA_DIR, exist_ok=True)


def validate() -> None:
    """Ishga tushishdan oldin sozlamalarni tekshirish."""
    if not GEMINI_API_KEYS:
        raise RuntimeError("Kamida bitta GEMINI_API_KEYS kerak!")
    if not SOURCE_CHANNELS:
        raise RuntimeError("Kamida bitta SOURCE_CHANNELS kerak!")
