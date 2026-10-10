"""Sayt (FastAPI). Bot bilan bitta ma'lumotlar bazasi va bitta balansdan foydalanadi.

Kirish: sayt token yaratadi -> foydalanuvchi t.me/<bot>?start=weblogin_<token> ni ochadi ->
bot tokenni tasdiqlaydi -> sayt buni ko'rib, sessiya cookie beradi.
"""
import asyncio
import io
import logging
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import admin, ai, click, config, db, images, notify, service, templates, tg_auth
from .sessions import COOKIE, current_user, require_user, session_token

log = logging.getLogger("web")
app = FastAPI(title="YaratSlayd", docs_url=None, redoc_url=None)
app.include_router(click.router)
app.include_router(admin.router)
WEB_DIR = config.ROOT / "web"

# Fon vazifalari: job_id -> holat (server qayta ishga tushsa yo'qoladi, fayllar esa DB'da qoladi)
jobs: dict[str, dict] = {}
_tasks: set[asyncio.Task] = set()  # create_task natijasi GC tomonidan yo'qolmasligi uchun

MAX_UPLOAD = 8 * 1024 * 1024
# Windows/Mac'da odatda o'rnatilgan shriftlar ("" — shablonning o'z shrifti)
FONTS = ["", "Calibri", "Arial", "Segoe UI", "Verdana", "Tahoma", "Trebuchet MS", "Century Gothic",
         "Georgia", "Cambria", "Times New Roman", "Bahnschrift", "Candara", "Corbel"]

# Ro'yxatdan o'tmaganlar uchun reja limiti (bepul AI limitini himoya qiladi)
_plan_hits: dict[str, deque] = defaultdict(deque)
PLAN_LIMIT_PER_HOUR = 15


@app.middleware("http")
async def same_origin_only(request: Request, call_next):
    """Boshqa saytdan yuborilgan POST so'rovlarni rad etadi (cookie SameSite=None bo'lgani uchun)."""
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        if origin and urlparse(origin).netloc != host:
            return JSONResponse({"detail": "Ruxsat yo'q"}, status_code=403)
    return await call_next(request)


def _rate_ok(key: str) -> bool:
    now = time.time()
    q = _plan_hits[key]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= PLAN_LIMIT_PER_HOUR:
        return False
    q.append(now)
    return True


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
    charts: bool = False


# ---------------- API ----------------

@app.get("/api/config")
def get_config():
    return {
        "price": config.PRICE_PRESENTATION,
        "welcome_bonus": config.WELCOME_BONUS,
        "click": config.CLICK_ENABLED,
        "topup_amounts": config.TOPUP_AMOUNTS,
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


def _start_session(uid: int, request: Request, response: Response) -> str:
    session = secrets.token_urlsafe(32)
    db.create_session(session, uid)
    https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    # Telegram Desktop/Web Mini App'ni iframe ichida ochadi — u yerda cookie faqat SameSite=None bilan ishlaydi
    response.set_cookie(
        COOKIE, session, max_age=30 * 24 * 3600, httponly=True,
        samesite="none" if https else "lax", secure=https,
    )
    return session


@app.get("/api/login/check")
def login_check(token: str, request: Request, response: Response):
    uid = db.take_login(token)
    if uid is None:
        return {"ok": False}
    return {"ok": True, "session": _start_session(uid, request, response)}


class TelegramLoginIn(BaseModel):
    init_data: str = Field(max_length=4096)


@app.post("/api/login/telegram")
def login_telegram(body: TelegramLoginIn, request: Request, response: Response):
    """Bot menyusidagi Mini App: Telegram imzolagan initData orqali avtomatik kirish."""
    user = tg_auth.validate_init_data(body.init_data, config.BOT_TOKEN)
    if user is None:
        raise HTTPException(401, "Telegram ma'lumotlari tasdiqlanmadi. Mini App'ni botdan qayta oching.")
    name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x) or "Foydalanuvchi"
    db.register_user(user["id"], user.get("username"), name, None)
    return {"ok": True, "session": _start_session(user["id"], request, response)}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    if token := session_token(request):
        db.delete_session(token)
    response.delete_cookie(COOKIE)
    return {"ok": True}


class TopupIn(BaseModel):
    amount: int


@app.post("/api/click/invoice")
def click_invoice(body: TopupIn, request: Request):
    uid = require_user(request)
    if not config.CLICK_ENABLED:
        raise HTTPException(503, "Click orqali to'lov hali ulanmagan. Balansni Telegram botda to'ldiring.")
    if body.amount not in config.TOPUP_AMOUNTS:
        raise HTTPException(400, "Noto'g'ri summa")
    return {"url": click.create_payment(uid, body.amount)}


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
            path = await service.generate(order_id, body.topic.strip(), body.lang, outline, body.template, progress,
                                          charts=body.charts)
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
         "download": f"/api/download/{o['id']}",
         "editable": (service.project_dir(o["id"]) / "project.json").exists()}
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


# ---------------- Tayyor taqdimotni tahrirlash ----------------

def _own_project(order_id: int, uid: int) -> dict:
    order = db.get_order(order_id)
    if not order or order["user_id"] != uid or order["status"] != "done":
        raise HTTPException(404, "Taqdimot topilmadi")
    project = service.load_project(order_id)
    if project is None:
        raise HTTPException(409, "Bu taqdimot eski usulda yaratilgan, uni tahrirlab bo'lmaydi. Yangisini yarating.")
    return project


@app.get("/api/orders/{order_id}/project")
def get_project(order_id: int, request: Request):
    uid = require_user(request)
    project = _own_project(order_id, uid)
    imgs = service.load_images(order_id, len(project["content"]["slides"]))
    return {**project, "images": [img is not None for img in imgs], "fonts_list": FONTS}


@app.get("/api/orders/{order_id}/image/{index}")
def get_image(order_id: int, index: int, request: Request):
    uid = require_user(request)
    _own_project(order_id, uid)
    path = service.project_dir(order_id) / f"img_{index}.jpg"
    if not path.exists():
        raise HTTPException(404, "Rasm yo'q")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


def _normalize_image(data: bytes) -> bytes:
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as im:
            im = im.convert("RGB")
            im.thumbnail((1600, 1600))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=88)
            return buf.getvalue()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(400, "Bu fayl rasm emas. JPG yoki PNG yuklang.")


@app.post("/api/orders/{order_id}/image/{index}")
async def upload_image(order_id: int, index: int, request: Request, file: UploadFile = File(...)):
    uid = require_user(request)
    project = _own_project(order_id, uid)
    if not 0 <= index < len(project["content"]["slides"]):
        raise HTTPException(400, "Noto'g'ri slayd")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(400, "Rasm juda katta (8 MB gacha)")
    service.save_image(order_id, index, _normalize_image(data))
    return {"ok": True}


class ImageQuery(BaseModel):
    query: str = Field(min_length=2, max_length=120)


@app.post("/api/orders/{order_id}/image/{index}/ai")
async def ai_image(order_id: int, index: int, body: ImageQuery, request: Request):
    uid = require_user(request)
    project = _own_project(order_id, uid)
    if not 0 <= index < len(project["content"]["slides"]):
        raise HTTPException(400, "Noto'g'ri slayd")
    got = (await images.fetch_images([body.query]))[0]
    if not got:
        raise HTTPException(502, "Rasm topilmadi yoki xizmat javob bermadi. Boshqa so'z bilan urinib ko'ring.")
    service.save_image(order_id, index, _normalize_image(got))
    return {"ok": True}


@app.delete("/api/orders/{order_id}/image/{index}")
def delete_image(order_id: int, index: int, request: Request):
    uid = require_user(request)
    _own_project(order_id, uid)
    service.save_image(order_id, index, None)
    return {"ok": True}


class ChartIn(BaseModel):
    type: str = Field(pattern="^(column|bar|pie|line)$")
    title: str = Field(default="", max_length=80)
    unit: str = Field(default="", max_length=20)
    labels: list[str] = Field(min_length=2, max_length=8)
    values: list[float] = Field(min_length=2, max_length=8)


class SlideIn(BaseModel):
    title: str = Field(max_length=200)
    bullets: list[str] = Field(max_length=10)
    chart: ChartIn | None = None


class SaveIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    subtitle: str = Field(default="", max_length=300)
    closing: str = Field(default="", max_length=400)
    slides: list[SlideIn]
    template: str = Field(pattern=r"^\d{2}$")
    fonts: dict[str, str] = {}


@app.post("/api/orders/{order_id}/save")
async def save_project(order_id: int, body: SaveIn, request: Request):
    """Tahrirlangan matn/diagramma/shrift/dizayn bilan faylni qayta yig'adi (bepul)."""
    uid = require_user(request)
    project = _own_project(order_id, uid)
    old = project["content"]["slides"]
    if len(body.slides) != len(old):
        raise HTTPException(400, "Slaydlar soni mos emas, sahifani yangilang")
    if not templates.get(body.template):
        raise HTTPException(400, "Bunday dizayn yo'q")
    fonts = {k: v for k, v in body.fonts.items() if k in ("title", "body") and v in FONTS}
    for src, dst in zip(body.slides, old):
        dst["title"] = src.title.strip() or dst["title"]
        dst["bullets"] = [b.strip() for b in src.bullets if b.strip()][:8]
        chart = None
        if src.chart:
            chart = ai.clean_chart(src.chart.model_dump())
            if chart is None:
                raise HTTPException(400, f"«{dst['title']}» slaydidagi diagramma to'liq emas: nom va raqamlarni kiriting")
        dst["chart"] = chart
    project["outline"].update(title=body.title.strip(), subtitle=body.subtitle.strip(),
                              slides=[s["title"] for s in old])
    project["content"]["closing"] = body.closing.strip()
    project["template"] = body.template
    project["fonts"] = fonts
    path = await service.rebuild(order_id, project)
    db.finish_order(order_id, "done", str(path))
    await notify.send_file(uid, path, f"✏️ {project['outline']['title']}\n(saytda tahrirlandi)")
    return {"ok": True, "download": f"/api/download/{order_id}", "version": project["version"]}


# ---------------- Sahifalar ----------------

app.mount("/previews", StaticFiles(directory=config.PREVIEWS_DIR), name="previews")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/favicon.ico")
def favicon():
    return FileResponse(WEB_DIR / "static" / "favicon.png")


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")
