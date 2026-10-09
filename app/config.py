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
# Faqat raqamlar olinadi ("123, 456" yoki "123 456"); noto'g'ri yozuv dasturni to'xtatmaydi
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(",", " ").replace(";", " ").split()
             if x.strip().lstrip("-").isdigit()}

# AI matn. AI_PROVIDER: gemini (bepul), claude yoki demo.
# Bo'sh qolsa: GEMINI_API_KEY bo'lsa gemini, ANTHROPIC_API_KEY bo'lsa claude, aks holda demo.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
# Ixtiyoriy bepul zaxira: https://console.groq.com/keys (Gemini limiti tugasa ishlatiladi)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
AI_PROVIDER = os.getenv("AI_PROVIDER", "").lower() or (
    "gemini" if GEMINI_API_KEY or GROQ_API_KEY else "claude" if ANTHROPIC_API_KEY else "demo"
)
DEMO_MODE = AI_PROVIDER == "demo"

# Rasmlar. IMAGE_PROVIDER: pollinations (bepul AI rasm, kalitsiz), pexels (bepul foto, kalit kerak), none.
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "").lower() or ("pexels" if PEXELS_API_KEY else "pollinations")

# Sayt
PORT = int(os.getenv("PORT", "8000"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
# Saytning ochiq manzili (botdagi «Saytda ochish» tugmasi uchun). Railway domenni o'zi beradi.
SITE_URL = (os.getenv("SITE_URL") or (
    f"https://{os.environ['RAILWAY_PUBLIC_DOMAIN']}" if os.getenv("RAILWAY_PUBLIC_DOMAIN") else ""
)).rstrip("/")  # bo'sh bo'lsa ishga tushganda Telegram'dan olinadi

# Narxlar (so'm)
PRICE_PRESENTATION = int(os.getenv("PRICE_PRESENTATION", "2000"))
WELCOME_BONUS = int(os.getenv("WELCOME_BONUS", "2000"))
REFERRAL_BONUS = int(os.getenv("REFERRAL_BONUS", "500"))

# Click orqali avtomatik to'lov (Click merchant kabinetidan olinadi). Bo'sh bo'lsa o'chiq.
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "")
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "")
CLICK_ENABLED = bool(CLICK_SERVICE_ID and CLICK_MERCHANT_ID and CLICK_SECRET_KEY)
TOPUP_AMOUNTS = [2000, 5000, 10000, 20000, 50000]

# Qo'lda to'lov: foydalanuvchi shu kartaga o'tkazib, chekni yuboradi
PAYMENT_CARD = os.getenv("PAYMENT_CARD", "8600 0000 0000 0000")
PAYMENT_CARD_OWNER = os.getenv("PAYMENT_CARD_OWNER", "Ism Familiya")

MIN_SLIDES = 5
MAX_SLIDES = 20

DB_PATH = Path(os.getenv("DB_PATH", ROOT / "data" / "bot.db"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", ROOT / "data" / "output"))
TEMPLATES_DIR = ROOT / "templates"
PREVIEWS_DIR = ROOT / "previews"
