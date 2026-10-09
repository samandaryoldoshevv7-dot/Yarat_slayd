"""Barcha sozlamalar .env faylidan o'qiladi."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}

# AI matn: Claude. Kalit bo'lmasa DEMO rejim (sinov uchun soxta matn).
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1" or not ANTHROPIC_API_KEY

# Rasmlar: Pexels (bepul). Kalit bo'lmasa slaydlar rasmsiz chiqadi.
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# Narxlar (so'm)
PRICE_PRESENTATION = int(os.getenv("PRICE_PRESENTATION", "2000"))
WELCOME_BONUS = int(os.getenv("WELCOME_BONUS", "2000"))
REFERRAL_BONUS = int(os.getenv("REFERRAL_BONUS", "500"))

# Qo'lda to'lov: foydalanuvchi shu kartaga o'tkazib, chekni yuboradi
PAYMENT_CARD = os.getenv("PAYMENT_CARD", "8600 0000 0000 0000")
PAYMENT_CARD_OWNER = os.getenv("PAYMENT_CARD_OWNER", "Ism Familiya")

MIN_SLIDES = 5
MAX_SLIDES = 20

DB_PATH = Path(os.getenv("DB_PATH", ROOT / "data" / "bot.db"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT / "data" / "output"))
TEMPLATES_DIR = ROOT / "templates"
PREVIEWS_DIR = ROOT / "previews"
