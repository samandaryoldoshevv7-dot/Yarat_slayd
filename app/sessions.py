"""Sayt sessiyalari: foydalanuvchini so'rovdan aniqlash."""
import hashlib
import hmac
import time

from fastapi import HTTPException, Request

from . import config, db

COOKIE = "ys_session"
FILE_TOKEN_TTL = 2 * 3600  # fayl havolasi 2 soat amal qiladi


def session_token(request: Request) -> str | None:
    # Cookie (oddiy brauzer) yoki X-Session sarlavhasi (Telegram ichida cookie bloklanishi mumkin).
    # Uzoq muddatli sessiya URL'da yuborilmaydi — fayl havolalari uchun file_token() bor.
    return request.cookies.get(COOKIE) or request.headers.get("x-session")


def current_user(request: Request) -> int | None:
    token = session_token(request)
    return db.session_user(token) if token else None


def require_user(request: Request) -> int:
    uid = current_user(request)
    if uid is None:
        raise HTTPException(401, "Avval Telegram orqali kiring")
    return uid


def _sign(payload: str) -> str:
    key = db.get_secret("file_token").encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()[:32]


def file_token(uid: int, now: float | None = None) -> str:
    """Faqat fayllarni o'qish (yuklab olish, ko'rinish, rasm, PDF) uchun qisqa muddatli imzolangan token.

    Telegram ichida fayl tashqi oynada ochiladi va u yerga cookie ham, sarlavha ham bormaydi — shuning uchun
    havolaga shu token qo'shiladi. U sessiya emas: tahrirlash, to'lov yoki boshqa amallarga yaramaydi.
    """
    exp = int((now or time.time()) + FILE_TOKEN_TTL)
    payload = f"{uid}.{exp}"
    return f"{payload}.{_sign(payload)}"


def _check_file_token(token: str) -> int | None:
    try:
        uid, exp, sig = token.split(".")
        if int(exp) < time.time():
            return None
        if not hmac.compare_digest(sig, _sign(f"{uid}.{exp}")):
            return None
        return int(uid)
    except (ValueError, TypeError):
        return None


def require_file_user(request: Request) -> int:
    """Fayl o'qish endpointlari uchun: sessiya yoki qisqa muddatli ?t= token."""
    uid = current_user(request)
    if uid is None and (t := request.query_params.get("t")):
        uid = _check_file_token(t)
    if uid is None:
        raise HTTPException(401, "Avval Telegram orqali kiring")
    return uid


def require_admin(request: Request) -> int:
    uid = require_user(request)
    if uid not in config.ADMIN_IDS:
        raise HTTPException(403, f"Siz admin emassiz. Telegram ID: {uid}. Railway'da ADMIN_IDS ga shu raqamni yozing.")
    return uid
