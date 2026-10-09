"""YaratSlayd Telegram bot. Ishga tushirish: python bot.py"""
import asyncio
import logging
import random

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InputMediaPhoto,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import ai, config, db, service, templates

log = logging.getLogger("bot")
router = Router()

BTN_CREATE = "📊 Taqdimot yaratish"
BTN_BALANCE = "💰 Balans"
BTN_FILES = "📁 Mening ishlarim"
BTN_INVITE = "👥 Do'st taklif qilish"
BTN_HELP = "❓ Yordam"

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_CREATE)],
        [KeyboardButton(text=BTN_BALANCE), KeyboardButton(text=BTN_FILES)],
        [KeyboardButton(text=BTN_INVITE), KeyboardButton(text=BTN_HELP)],
    ],
    resize_keyboard=True,
)

LANG_NAMES = {"uz": "🇺🇿 O'zbek", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}
SLIDE_OPTIONS = [5, 7, 10, 12, 15, 20]
TOPUP_AMOUNTS = [2000, 5000, 10000, 20000, 50000]


class Create(StatesGroup):
    topic = State()
    lang = State()
    slides = State()
    template = State()
    plan = State()
    working = State()


class Topup(StatesGroup):
    receipt = State()


def som(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"


# ---------------- Asosiy menyu ----------------

@router.message(CommandStart())
async def start(msg: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    ref = None
    if command.args and command.args.startswith("ref"):
        try:
            ref = int(command.args[3:])
        except ValueError:
            pass
    is_new = db.register_user(msg.from_user.id, msg.from_user.username, msg.from_user.full_name, ref)
    text = (
        f"Assalomu alaykum, <b>{msg.from_user.first_name}</b>! 👋\n\n"
        "Men mavzu bo'yicha <b>tayyor taqdimot (PowerPoint)</b> yasab beraman:\n"
        "mavzuni yozasiz → reja tuziladi → dizaynni tanlaysiz → 1–2 daqiqada .pptx fayl.\n\n"
        f"💵 Narxi: <b>{som(config.PRICE_PRESENTATION)}</b> — reja bepul."
    )
    if is_new and config.WELCOME_BONUS:
        text += f"\n🎁 Sizga <b>{som(config.WELCOME_BONUS)}</b> sovg'a qilindi — birinchi taqdimot bepul!"
    await msg.answer(text, reply_markup=MAIN_KB)


def ensure_user(user) -> None:
    db.register_user(user.id, user.username, user.full_name, None)


@router.message(F.text == BTN_HELP)
@router.message(Command("help"))
async def help_(msg: Message):
    await msg.answer(
        "<b>Qanday ishlaydi?</b>\n"
        "1. «📊 Taqdimot yaratish» ni bosing va mavzuni yozing\n"
        "2. Tilni va slaydlar sonini tanlang\n"
        "3. Dizaynni tanlang — AI reja tuzadi (bepul)\n"
        f"4. Rejani tasdiqlang — balansdan {som(config.PRICE_PRESENTATION)} yechiladi\n"
        "5. Tayyor .pptx faylni oling — PowerPoint'da tahrirlash mumkin\n\n"
        "Xatolik bo'lsa pul avtomatik qaytariladi.\n"
        "/cancel — joriy amalni bekor qilish"
    )


@router.message(Command("cancel"))
async def cancel(msg: Message, state: FSMContext):
    if await state.get_state() == Create.working.state:
        return await msg.answer("⏳ Taqdimot tayyorlanmoqda, biroz kuting.")
    await state.clear()
    await msg.answer("Bekor qilindi.", reply_markup=MAIN_KB)


@router.message(F.text == BTN_BALANCE)
@router.message(Command("balance"))
async def balance(msg: Message):
    ensure_user(msg.from_user)
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Hisobni to'ldirish", callback_data="topup")
    left = db.balance(msg.from_user.id) // config.PRICE_PRESENTATION
    await msg.answer(
        f"💰 Balansingiz: <b>{som(db.balance(msg.from_user.id))}</b>\n"
        f"Bu {left} ta taqdimotga yetadi.",
        reply_markup=kb.as_markup(),
    )


@router.message(F.text == BTN_FILES)
async def my_files(msg: Message):
    orders = db.user_orders(msg.from_user.id)
    if not orders:
        return await msg.answer("Hali taqdimotlar yo'q. «📊 Taqdimot yaratish» ni bosing.")
    kb = InlineKeyboardBuilder()
    for o in orders:
        kb.button(text=f"📄 {o['topic'][:40]}", callback_data=f"file:{o['id']}")
    kb.adjust(1)
    await msg.answer("Oxirgi taqdimotlaringiz (qayta yuklab olish bepul):", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("file:"))
async def resend_file(cb: CallbackQuery):
    order_id = int(cb.data.split(":")[1])
    order = next((o for o in db.user_orders(cb.from_user.id, 50) if o["id"] == order_id), None)
    if not order or not order["file_path"]:
        return await cb.answer("Fayl topilmadi", show_alert=True)
    try:
        await cb.message.answer_document(FSInputFile(order["file_path"]))
    except FileNotFoundError:
        return await cb.answer("Fayl serverdan o'chirilgan", show_alert=True)
    await cb.answer()


@router.message(F.text == BTN_INVITE)
async def invite(msg: Message, bot: Bot):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref{msg.from_user.id}"
    await msg.answer(
        f"👥 Do'stlaringizni taklif qiling — har bir yangi do'st uchun sizga "
        f"<b>{som(config.REFERRAL_BONUS)}</b> bonus!\n\nSizning havolangiz:\n{link}"
    )


# ---------------- Hisobni to'ldirish (qo'lda tasdiqlash) ----------------

@router.callback_query(F.data == "topup")
async def topup(cb: CallbackQuery, state: FSMContext):
    if await state.get_state() == Create.working.state:
        return await cb.answer("Taqdimot tayyorlanmoqda, biroz kuting", show_alert=True)
    # Reja ma'lumotlari saqlanib qoladi — to'ldirgach «Tayyorlash» ni qayta bosish mumkin
    await state.set_state(Topup.receipt)
    await cb.message.answer(
        "💳 Quyidagi kartaga xohlagan summani o'tkazing:\n\n"
        f"<code>{config.PAYMENT_CARD}</code>\n{config.PAYMENT_CARD_OWNER}\n\n"
        "So'ng <b>to'lov chekining skrinshotini</b> shu yerga yuboring. "
        "Admin tekshirgach balansingiz to'ldiriladi (odatda 5–30 daqiqa).\n/cancel — bekor qilish"
    )
    await cb.answer()


@router.message(Topup.receipt, F.photo)
async def topup_receipt(msg: Message, state: FSMContext, bot: Bot):
    if "outline" in await state.get_data():
        await state.set_state(Create.plan)
    else:
        await state.clear()
    pay_id = db.create_payment(msg.from_user.id, msg.photo[-1].file_id)
    kb = InlineKeyboardBuilder()
    for a in TOPUP_AMOUNTS:
        kb.button(text=f"+{a}", callback_data=f"pay:{pay_id}:{a}")
    kb.button(text="❌ Rad etish", callback_data=f"pay:{pay_id}:0")
    kb.adjust(3)
    user = msg.from_user
    caption = (
        f"💳 To'lov #{pay_id}\nFoydalanuvchi: {user.full_name} "
        f"(@{user.username or '-'}, <code>{user.id}</code>)\nSummani tanlang:"
    )
    for admin in config.ADMIN_IDS:
        try:
            await bot.send_photo(admin, msg.photo[-1].file_id, caption=caption, reply_markup=kb.as_markup())
        except Exception:
            log.exception("Adminga yuborilmadi: %s", admin)
    await msg.answer("✅ Chek qabul qilindi. Tekshirilgach xabar beramiz.", reply_markup=MAIN_KB)


@router.message(Topup.receipt, ~F.text.in_({BTN_CREATE, BTN_BALANCE, BTN_FILES, BTN_INVITE, BTN_HELP}))
async def topup_need_photo(msg: Message):
    await msg.answer("Iltimos, to'lov chekini <b>rasm</b> ko'rinishida yuboring yoki /cancel.")


@router.callback_query(F.data.startswith("pay:"))
async def admin_payment(cb: CallbackQuery, bot: Bot):
    if cb.from_user.id not in config.ADMIN_IDS:
        return await cb.answer("Faqat admin uchun", show_alert=True)
    _, pay_id, amount = cb.data.split(":")
    amount = int(amount)
    row = db.resolve_payment(int(pay_id), amount, "approved" if amount else "rejected")
    if row is None:
        return await cb.answer("Bu to'lov allaqachon ko'rib chiqilgan", show_alert=True)
    result = f"✅ +{som(amount)}" if amount else "❌ Rad etildi"
    await cb.message.edit_caption(caption=(cb.message.caption or "") + f"\n\n{result} ({cb.from_user.full_name})")
    try:
        if amount:
            await bot.send_message(
                row["user_id"],
                f"✅ Balansingiz {som(amount)} ga to'ldirildi.\nJoriy balans: {som(db.balance(row['user_id']))}",
            )
        else:
            await bot.send_message(row["user_id"], "❌ To'lov tasdiqlanmadi. Savollar bo'lsa adminga yozing.")
    except Exception:
        log.warning("Foydalanuvchiga xabar yuborilmadi: %s", row["user_id"])
    await cb.answer()


# ---------------- Taqdimot yaratish ----------------

@router.message(F.text == BTN_CREATE)
@router.message(Command("new"))
async def create_start(msg: Message, state: FSMContext):
    if await state.get_state() == Create.working.state:
        return await msg.answer("⏳ Oldingi taqdimot hali tayyorlanmoqda, biroz kuting.")
    ensure_user(msg.from_user)
    await state.clear()
    await state.set_state(Create.topic)
    await msg.answer(
        "📝 Taqdimot <b>mavzusini</b> yozing.\n\n"
        "Masalan: <i>Sun'iy intellekt va kelajak kasblari</i>\n"
        "Aniqroq yozsangiz natija yaxshiroq bo'ladi (fan, sinf/kurs, nimaga e'tibor berish)."
    )


@router.message(Create.topic, F.text)
async def create_topic(msg: Message, state: FSMContext):
    topic = msg.text.strip()
    if topic.startswith("/") or topic in {BTN_CREATE, BTN_BALANCE, BTN_FILES, BTN_INVITE, BTN_HELP}:
        await state.clear()
        return await msg.answer("Bekor qilindi.", reply_markup=MAIN_KB)
    if len(topic) < 3:
        return await msg.answer("Mavzu kamida 3 ta belgidan iborat bo'lsin.")
    if len(topic) > 300:
        return await msg.answer("Mavzu juda uzun — 300 belgigacha qisqartiring.")
    await state.update_data(topic=topic)
    await state.set_state(Create.lang)
    kb = InlineKeyboardBuilder()
    for code, name in LANG_NAMES.items():
        kb.button(text=name, callback_data=f"lang:{code}")
    await msg.answer("🌐 Taqdimot qaysi tilda bo'lsin?", reply_markup=kb.as_markup())


@router.callback_query(Create.lang, F.data.startswith("lang:"))
async def create_lang(cb: CallbackQuery, state: FSMContext):
    await state.update_data(lang=cb.data.split(":")[1])
    await state.set_state(Create.slides)
    kb = InlineKeyboardBuilder()
    for n in SLIDE_OPTIONS:
        kb.button(text=f"{n} ta", callback_data=f"slides:{n}")
    kb.adjust(3)
    await cb.message.edit_text("📑 Nechta slayd bo'lsin? (muqova va yakuniy slayd bilan)", reply_markup=kb.as_markup())
    await cb.answer()


def template_kb(index: int, total: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="◀️", callback_data=f"tpl:go:{(index - 1) % total}")
    kb.button(text=f"{index + 1}/{total}", callback_data="tpl:noop")
    kb.button(text="▶️", callback_data=f"tpl:go:{(index + 1) % total}")
    kb.button(text="✅ Shu dizayn", callback_data=f"tpl:pick:{index}")
    kb.button(text="🎲 Tasodifiy", callback_data="tpl:random")
    kb.adjust(3, 2)
    return kb.as_markup()


@router.callback_query(Create.slides, F.data.startswith("slides:"))
async def create_slides(cb: CallbackQuery, state: FSMContext):
    await state.update_data(slides=int(cb.data.split(":")[1]))
    await state.set_state(Create.template)
    tpls = templates.all_templates()
    await cb.message.delete()
    await cb.message.answer_photo(
        FSInputFile(tpls[0].preview), caption="🎨 Dizaynni tanlang:", reply_markup=template_kb(0, len(tpls))
    )
    await cb.answer()


@router.callback_query(Create.template, F.data.startswith("tpl:"))
async def create_template(cb: CallbackQuery, state: FSMContext, bot: Bot):
    tpls = templates.all_templates()
    parts = cb.data.split(":")
    if parts[1] == "noop":
        return await cb.answer()
    if parts[1] == "go":
        i = int(parts[2])
        await cb.message.edit_media(
            InputMediaPhoto(media=FSInputFile(tpls[i].preview), caption="🎨 Dizaynni tanlang:"),
            reply_markup=template_kb(i, len(tpls)),
        )
        return await cb.answer()
    i = random.randrange(len(tpls)) if parts[1] == "random" else int(parts[2])
    await state.update_data(template=tpls[i].id)
    await cb.message.edit_caption(caption=f"🎨 Tanlangan dizayn: №{i + 1}")
    await cb.answer()
    await make_plan(cb.message, state)


def plan_text(data: dict) -> str:
    o = data["outline"]
    lines = "\n".join(f"{i}. {t}" for i, t in enumerate(o["slides"], 1))
    return (
        f"📋 <b>{o['title']}</b>\n<i>{o['subtitle']}</i>\n\n<b>Reja:</b>\n{lines}\n\n"
        f"Slaydlar: {data['slides']} ta · Til: {LANG_NAMES[data['lang']]}\n"
        f"💵 Narxi: <b>{som(config.PRICE_PRESENTATION)}</b>"
    )


def plan_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text=f"✅ Tayyorlash — {som(config.PRICE_PRESENTATION)}", callback_data="plan:ok")
    kb.button(text="🔄 Boshqa reja", callback_data="plan:again")
    kb.button(text="❌ Bekor qilish", callback_data="plan:cancel")
    kb.adjust(1, 2)
    return kb.as_markup()


async def make_plan(msg: Message, state: FSMContext):
    data = await state.get_data()
    wait = await msg.answer("🧠 Reja tuzilmoqda...")
    try:
        outline = await ai.make_outline(data["topic"], data["lang"], data["slides"])
    except ai.AIError as e:
        await state.set_state(Create.plan)
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Qayta urinish", callback_data="plan:again")
        return await wait.edit_text(f"⚠️ {e}", reply_markup=kb.as_markup())
    await state.update_data(outline=outline)
    await state.set_state(Create.plan)
    await wait.edit_text(plan_text(await state.get_data()), reply_markup=plan_kb())


@router.callback_query(Create.plan, F.data == "plan:again")
async def plan_again(cb: CallbackQuery, state: FSMContext):
    await cb.message.delete()
    await cb.answer()
    await make_plan(cb.message, state)


@router.callback_query(F.data == "plan:cancel")
async def plan_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.message.answer("Bekor qilindi.", reply_markup=MAIN_KB)
    await cb.answer()


@router.callback_query(Create.plan, F.data == "plan:ok")
async def plan_ok(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    uid = cb.from_user.id
    price = config.PRICE_PRESENTATION
    if not db.charge(uid, price):
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Hisobni to'ldirish", callback_data="topup")
        await cb.message.answer(
            f"Balansingizda mablag' yetarli emas: {som(db.balance(uid))}.\n"
            f"Taqdimot narxi — {som(price)}. To'ldirgach, yuqoridagi «✅ Tayyorlash» tugmasini qayta bosing.",
            reply_markup=kb.as_markup(),
        )
        return await cb.answer()

    await state.set_state(Create.working)
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer()
    order_id = db.create_order(uid, data["topic"], data["lang"], data["slides"], data["template"], price)
    status = await cb.message.answer("⏳ Boshlandi...")

    async def progress(text: str):
        try:
            await status.edit_text(text)
        except Exception:
            pass

    try:
        path = await service.generate(order_id, data["topic"], data["lang"], data["outline"], data["template"], progress)
    except Exception as e:
        log.exception("Generatsiya xatosi (order %s)", order_id)
        db.finish_order(order_id, "failed")
        db.add_balance(uid, price)
        await state.set_state(Create.plan)
        reason = str(e) if isinstance(e, ai.AIError) else "texnik xatolik"
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Qayta urinish", callback_data="plan:ok")
        return await status.edit_text(
            f"⚠️ Kechirasiz, {reason}. {som(price)} balansingizga qaytarildi.", reply_markup=kb.as_markup()
        )

    db.finish_order(order_id, "done", str(path))
    await state.clear()
    await status.delete()
    await cb.message.answer_document(
        FSInputFile(path),
        caption=(
            f"✅ <b>{data['outline']['title']}</b>\n\nPowerPoint, Google Slides yoki WPS'da ochib tahrirlashingiz mumkin.\n"
            f"Balans: {som(db.balance(uid))}"
        ),
        reply_markup=MAIN_KB,
    )


@router.message(StateFilter(Create.lang, Create.slides, Create.template, Create.plan))
async def use_buttons(msg: Message):
    await msg.answer("Iltimos, yuqoridagi tugmalardan foydalaning yoki /cancel.")


@router.message(Create.working)
async def busy(msg: Message):
    await msg.answer("⏳ Taqdimot tayyorlanmoqda, biroz kuting.")


# ---------------- Admin ----------------

@router.message(Command("stats"), F.from_user.id.in_(config.ADMIN_IDS))
async def admin_stats(msg: Message):
    s = db.stats()
    await msg.answer(
        f"👤 Foydalanuvchilar: {s['users']}\n📊 Tayyor taqdimotlar: {s['orders']}\n"
        f"💵 Tasdiqlangan to'lovlar: {som(s['revenue'])}\n⏳ Kutilayotgan to'lovlar: {s['pending_payments']}"
    )


@router.message(Command("add"), F.from_user.id.in_(config.ADMIN_IDS))
async def admin_add(msg: Message, command: CommandObject, bot: Bot):
    try:
        uid, amount = map(int, (command.args or "").split())
    except ValueError:
        return await msg.answer("Foydalanish: /add <user_id> <summa>  (manfiy summa — ayirish)")
    if not db.get_user(uid):
        return await msg.answer("Bunday foydalanuvchi yo'q")
    new = db.add_balance(uid, amount)
    await msg.answer(f"OK. Yangi balans: {som(new)}")
    try:
        await bot.send_message(uid, f"💰 Balansingiz o'zgardi: {amount:+} so'm. Joriy: {som(new)}")
    except Exception:
        pass


@router.message(Command("broadcast"), F.from_user.id.in_(config.ADMIN_IDS))
async def admin_broadcast(msg: Message, bot: Bot):
    if not msg.reply_to_message:
        return await msg.answer("Yubormoqchi bo'lgan xabarga javob (reply) qilib /broadcast yozing.")
    sent = 0
    for uid in db.all_user_ids():
        try:
            await msg.reply_to_message.copy_to(uid)
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)  # Telegram limiti: ~30 xabar/soniya
    await msg.answer(f"Yuborildi: {sent} ta")


@router.callback_query()
async def stale_button(cb: CallbackQuery):
    await cb.answer("Bu tugma eskirgan. Qaytadan boshlang: «📊 Taqdimot yaratish»", show_alert=True)


@router.message()
async def fallback(msg: Message):
    await msg.answer("Menyudan tanlang 👇", reply_markup=MAIN_KB)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi. .env faylini to'ldiring (.env.example ga qarang).")
    if config.DEMO_MODE:
        log.warning("DEMO rejim: ANTHROPIC_API_KEY yo'q — slaydlarda namuna matn chiqadi.")
    if not config.PEXELS_API_KEY:
        log.warning("PEXELS_API_KEY yo'q — slaydlar rasmsiz bo'ladi.")
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
