"""Sayt sessiyalari: foydalanuvchini so'rovdan aniqlash."""
from fastapi import HTTPException, Request

from . import config, db

COOKIE = "ys_session"


def session_token(request: Request) -> str | None:
    # Cookie (oddiy brauzer), X-Session sarlavhasi (Telegram ichida cookie bloklanishi mumkin)
    # yoki ?s= (Telegram ichida fayl yuklab olish havolasi)
    return request.cookies.get(COOKIE) or request.headers.get("x-session") or request.query_params.get("s")


def current_user(request: Request) -> int | None:
    token = session_token(request)
    return db.session_user(token) if token else None


def require_user(request: Request) -> int:
    uid = current_user(request)
    if uid is None:
        raise HTTPException(401, "Avval Telegram orqali kiring")
    return uid


def require_admin(request: Request) -> int:
    uid = require_user(request)
    if uid not in config.ADMIN_IDS:
        raise HTTPException(403, f"Siz admin emassiz. Telegram ID: {uid}. Railway'da ADMIN_IDS ga shu raqamni yozing.")
    return uid
