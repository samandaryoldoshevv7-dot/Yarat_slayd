"""Sayt (FastAPI). Bot bilan bitta ma'lumotlar bazasi va bitta balansdan foydalanadi.

Kirish: sayt token yaratadi -> foydalanuvchi t.me/<bot>?start=weblogin_<token> ni ochadi ->
bot tokenni tasdiqlaydi -> sayt buni ko'rib, sessiya cookie beradi.
"""
import asyncio
import logging
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai, config, db, notify, service, templates

log = logging.getLogger("web")
app = FastAPI(title="YaratSlayd", docs_url=None, redoc_url=None)
WEB_DIR = config.ROOT / "web"
COOKIE = "ys_session"

# Fon vazifalari: job_id -> holat (server qayta ishga tushsa yo'qoladi, fayllar esa DB'da qoladi)
jobs: dict[str, dict] = {}
_tasks: set[asyncio.Task] = set()  # create_task natijasi GC tomonidan yo'qolmasligi uchun

# Ro'yxatdan o'tmaganlar uchun reja limiti (bepul AI limitini himoya qiladi)
_plan_hits: dict[str, deque] = defaultdict(deque)
PLAN_LIMIT_PER_HOUR = 15


def _rate_ok(key: str) -> bool:
    now = time.time()
    q = _plan_hits[key]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= PLAN_LIMIT_PER_HOUR:
        return False
    q.append(now)
    return True


def current_user(request: Request) -> int | None:
    token = request.cookies.get(COOKIE)
    return db.session_user(token) if token else None


def require_user(request: Request) -> int:
    uid = current_user(request)
    if uid is None:
        raise HTTPException(401, "Avval Telegram orqali kiring")
    return uid


class PlanIn(BaseModel):
    topic: str = Field(min_length=3, max_length=300)
    lang: str = Field(pattern="^(uz|ru|en)$")
    slides: int = Field(ge=config.MIN_SLIDES, le=config.MAX_SLIDES)


class Outline(BaseModel):
    title: str = Field(max_length=300)
    subtitle: str = Field(default="", max_length=300)
    slides: list[str] = Field(min_length=1, max_length=config.MAX_SLIDES)


class GenerateIn(PlanIn):
    template: str = Field(pattern=r"^\d{2}$")
    outline: Outline


# ---------------- API ----------------

@app.get("/api/config")
def get_config():
    return {
        "price": config.PRICE_PRESENTATION,
        "welcome_bonus": config.WELCOME_BONUS,
        "bot": config.BOT_USERNAME,
        "demo": config.DEMO_MODE,
        "min_slides": config.MIN_SLIDES,
        "max_slides": config.MAX_SLIDES,
        "categories": templates.CATEGORIES,
        "templates": [
            {"id": t.id, "preview": f"/previews/{t.id}.jpg", "category": t.category}
            for t in templates.all_templates()
        ],
    }


@app.get("/api/me")
def me(request: Request):
    uid = current_user(request)
    user = db.get_user(uid) if uid else None
    if not user:
        return {"logged_in": False}
    return {"logged_in": True, "name": user["full_name"], "balance": user["balance"]}


@app.post("/api/login/start")
def login_start():
    if not config.BOT_USERNAME:
        raise HTTPException(503, "Bot ulanmagan (BOT_TOKEN yo'q)")
    token = secrets.token_urlsafe(18)
    db.create_login(token)
    return {"token": token, "url": f"https://t.me/{config.BOT_USERNAME}?start=weblogin_{token}"}


@app.get("/api/login/check")
def login_check(token: str, request: Request, response: Response):
    uid = db.take_login(token)
    if uid is None:
        return {"ok": False}
    session = secrets.token_urlsafe(32)
    db.create_session(session, uid)
    response.set_cookie(
        COOKIE, session, max_age=30 * 24 * 3600, httponly=True, samesite="lax",
        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
    )
    return {"ok": True}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    if token := request.cookies.get(COOKIE):
        db.delete_session(token)
    response.delete_cookie(COOKIE)
    return {"ok": True}


@app.post("/api/plan")
async def plan(body: PlanIn, request: Request):
    key = str(current_user(request) or request.headers.get("x-forwarded-for", request.client.host).split(",")[0])
    if not _rate_ok(key):
        raise HTTPException(429, "Juda ko'p so'rov. Bir soatdan so'ng urinib ko'ring.")
    try:
        return await ai.make_outline(body.topic.strip(), body.lang, body.slides)
    except ai.AIError as e:
        raise HTTPException(502, str(e))


@app.post("/api/generate")
async def generate(body: GenerateIn, request: Request):
    uid = require_user(request)
    if any(j["user_id"] == uid and j["status"] == "working" for j in jobs.values()):
        raise HTTPException(409, "Oldingi taqdimot hali tayyorlanmoqda")
    if not templates.get(body.template):
        raise HTTPException(400, "Bunday dizayn yo'q")
    price = config.PRICE_PRESENTATION
    if not db.charge(uid, price):
        raise HTTPException(402, "Balansda mablag' yetarli emas")

    outline = body.outline.model_dump()
    order_id = db.create_order(uid, body.topic.strip(), body.lang, body.slides, body.template, price)
    job_id = secrets.token_urlsafe(12)
    jobs[job_id] = {"user_id": uid, "status": "working", "step": "Boshlandi...", "order_id": order_id}

    async def progress(text: str):
        jobs[job_id]["step"] = text

    async def run():
        try:
            path = await service.generate(order_id, body.topic.strip(), body.lang, outline, body.template, progress)
            db.finish_order(order_id, "done", str(path))
            jobs[job_id].update(status="done", step="Tayyor!", title=outline["title"])
            # Sayt va bot bitta: fayl Telegram'ga ham yuboriladi
            await notify.send_file(uid, path, f"✅ {outline['title']}\n(saytda tayyorlandi)")
        except Exception as e:
            log.exception("Sayt generatsiya xatosi (order %s)", order_id)
            db.finish_order(order_id, "failed")
            db.add_balance(uid, price)
            reason = str(e) if isinstance(e, ai.AIError) else "texnik xatolik"
            jobs[job_id].update(status="failed", step=f"Kechirasiz, {reason}. Pul balansga qaytarildi.")

    task = asyncio.create_task(run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"job": job_id}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str, request: Request):
    uid = require_user(request)
    job = jobs.get(job_id)
    if not job or job["user_id"] != uid:
        raise HTTPException(404, "Topilmadi")
    out = {k: job.get(k) for k in ("status", "step", "order_id", "title")}
    if job["status"] == "done":
        out["download"] = f"/api/download/{job['order_id']}"
    return out


@app.get("/api/orders")
def orders(request: Request):
    uid = require_user(request)
    return [
        {"id": o["id"], "topic": o["topic"], "slides": o["slides"], "created_at": o["created_at"],
         "download": f"/api/download/{o['id']}"}
        for o in db.user_orders(uid, 30)
    ]


@app.get("/api/download/{order_id}")
def download(order_id: int, request: Request):
    uid = require_user(request)
    order = db.get_order(order_id)
    if not order or order["user_id"] != uid or order["status"] != "done" or not order["file_path"]:
        raise HTTPException(404, "Fayl topilmadi")
    path = Path(order["file_path"])
    if not path.exists():
        raise HTTPException(404, "Fayl serverdan o'chirilgan")
    return FileResponse(path, filename=f"{service.safe_filename(order['topic'])}.pptx")


# ---------------- Sahifalar ----------------

app.mount("/previews", StaticFiles(directory=config.PREVIEWS_DIR), name="previews")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/favicon.ico")
def favicon():
    return FileResponse(WEB_DIR / "static" / "favicon.png")


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")
