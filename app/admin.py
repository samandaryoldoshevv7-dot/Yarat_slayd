"""Admin panel API (/admin sahifasi uchun). Faqat ADMIN_IDS dagi foydalanuvchilar."""
import io
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from . import ai, config, db, notify
from .sessions import require_admin

log = logging.getLogger("admin")
router = APIRouter()


def _som(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " so'm"


@router.get("/admin")
def admin_page():
    return FileResponse(config.ROOT / "web" / "admin.html")


@router.get("/api/admin/overview")
def overview(request: Request):
    require_admin(request)
    return {
        "stats": db.admin_stats(),
        "setup": {
            "ai_provider": config.AI_PROVIDER,
            "gemini_key": bool(config.GEMINI_API_KEY),
            "gemini_model": config.GEMINI_MODEL,
            "groq_key": bool(config.GROQ_API_KEY),
            "images": config.IMAGE_PROVIDER,
            "bot": bool(notify.bot),
            "bot_username": config.BOT_USERNAME,
            "site_url": config.SITE_URL,
            "click": config.CLICK_ENABLED,
            "admins": sorted(config.ADMIN_IDS),
            "price": config.PRICE_PRESENTATION,
            "db_path": str(config.DB_PATH),
            "volume": os.path.ismount(config.DB_PATH.parent),  # Railway Volume — alohida disk
        },
        "last_ai_error": dict(ai.last_error),
    }


@router.post("/api/admin/ai-check")
async def ai_check(request: Request):
    require_admin(request)
    return await ai.health_check()


@router.get("/api/admin/payments")
def payments(request: Request):
    require_admin(request)
    return [
        {"id": p["id"], "user_id": p["user_id"], "name": p["full_name"], "username": p["username"],
         "created_at": p["created_at"]}
        for p in db.pending_payments()
    ]


@router.get("/api/admin/receipt/{payment_id}")
async def receipt(payment_id: int, request: Request):
    require_admin(request)
    p = db.get_payment(payment_id)
    if not p or not p["photo_file_id"] or notify.bot is None:
        raise HTTPException(404, "Chek topilmadi")
    buf = io.BytesIO()
    try:
        await notify.bot.download(p["photo_file_id"], destination=buf)
    except Exception:
        log.exception("Chekni yuklab bo'lmadi")
        raise HTTPException(404, "Chekni Telegram'dan yuklab bo'lmadi")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")


class Decision(BaseModel):
    amount: int  # 0 — rad etish


@router.post("/api/admin/payments/{payment_id}")
async def decide(payment_id: int, body: Decision, request: Request):
    require_admin(request)
    if body.amount < 0 or body.amount > 10_000_000:
        raise HTTPException(400, "Noto'g'ri summa")
    row = db.resolve_payment(payment_id, body.amount, "approved" if body.amount else "rejected")
    if row is None:
        raise HTTPException(409, "Bu to'lov allaqachon ko'rib chiqilgan")
    if body.amount:
        await notify.send_message(row["user_id"], f"✅ Balansingiz {_som(body.amount)} ga to'ldirildi.\n"
                                                  f"Joriy balans: {_som(db.balance(row['user_id']))}")
    else:
        await notify.send_message(row["user_id"], "❌ To'lov tasdiqlanmadi. Savollar bo'lsa adminga yozing.")
    return {"ok": True}


@router.get("/api/admin/users")
def users(request: Request, q: str = ""):
    require_admin(request)
    return [
        {"id": u["id"], "name": u["full_name"], "username": u["username"], "balance": u["balance"],
         "created_at": u["created_at"]}
        for u in db.list_users(q.strip())
    ]


class BalanceChange(BaseModel):
    delta: int


@router.post("/api/admin/users/{user_id}/balance")
async def change_balance(user_id: int, body: BalanceChange, request: Request):
    require_admin(request)
    if not db.get_user(user_id):
        raise HTTPException(404, "Foydalanuvchi topilmadi")
    if body.delta == 0 or abs(body.delta) > 10_000_000:
        raise HTTPException(400, "Noto'g'ri summa")
    new = db.add_balance(user_id, body.delta)
    await notify.send_message(user_id, f"💰 Balansingiz o'zgardi: {body.delta:+} so'm. Joriy: {_som(new)}")
    return {"balance": new}


@router.get("/api/admin/orders")
def orders(request: Request):
    require_admin(request)
    return [
        {"id": o["id"], "user_id": o["user_id"], "name": o["full_name"], "topic": o["topic"], "slides": o["slides"],
         "template": o["template"], "status": o["status"], "price": o["price"], "created_at": o["created_at"]}
        for o in db.recent_orders()
    ]
