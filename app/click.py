"""Click orqali avtomatik to'lov (Click SHOP API: Prepare va Complete).

Ishlash tartibi:
  1. Foydalanuvchi summani tanlaydi -> biz hisob-faktura (invoice) yaratamiz va Click to'lov sahifasiga yuboramiz.
  2. Click serverimizga /click/prepare so'rovini yuboradi -> invoice mavjudligi va summani tekshiramiz.
  3. Foydalanuvchi to'lagach Click /click/complete yuboradi -> balans avtomatik to'ldiriladi.

Click kabinetida "Prepare URL" va "Complete URL" sifatida quyidagilar ko'rsatiladi:
  https://<sayt>/click/prepare  va  https://<sayt>/click/complete
"""
import hashlib
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Request

from . import config, db, notify

log = logging.getLogger("click")
router = APIRouter()

PAY_URL = "https://my.click.uz/services/pay"

# Click xato kodlari
OK, SIGN_FAILED, BAD_AMOUNT, BAD_ACTION, ALREADY_PAID, NOT_FOUND, NO_TRANSACTION, UPDATE_FAILED, BAD_REQUEST, CANCELLED = (
    0, -1, -2, -3, -4, -5, -6, -7, -8, -9,
)


def pay_url(invoice_id: int, amount: int, return_url: str = "") -> str:
    params = {
        "service_id": config.CLICK_SERVICE_ID,
        "merchant_id": config.CLICK_MERCHANT_ID,
        "amount": amount,
        "transaction_param": invoice_id,
    }
    if return_url:
        params["return_url"] = return_url
    return f"{PAY_URL}?{urlencode(params)}"


def create_payment(user_id: int, amount: int) -> str:
    invoice_id = db.create_click_invoice(user_id, amount)
    back = config.SITE_URL or (f"https://t.me/{config.BOT_USERNAME}" if config.BOT_USERNAME else "")
    return pay_url(invoice_id, amount, back)


def _sign(f: dict, with_prepare_id: bool) -> str:
    parts = [f.get("click_trans_id", ""), f.get("service_id", ""), config.CLICK_SECRET_KEY,
             f.get("merchant_trans_id", "")]
    if with_prepare_id:
        parts.append(f.get("merchant_prepare_id", ""))
    parts += [f.get("amount", ""), f.get("action", ""), f.get("sign_time", "")]
    return hashlib.md5("".join(parts).encode()).hexdigest()


def _answer(f: dict, error: int, note: str, **extra) -> dict:
    out = {"click_trans_id": f.get("click_trans_id"), "merchant_trans_id": f.get("merchant_trans_id"),
           "error": error, "error_note": note}
    out.update(extra)
    if error != OK:
        log.warning("Click javobi %s: %s (%s)", error, note, f.get("merchant_trans_id"))
    return out


def _check(f: dict, action: str, with_prepare_id: bool):
    """Umumiy tekshiruvlar. Xato bo'lsa (kod, izoh), aks holda (None, invoice)."""
    required = ["click_trans_id", "service_id", "merchant_trans_id", "amount", "action", "sign_time", "sign_string"]
    if with_prepare_id:
        required.append("merchant_prepare_id")
    if not config.CLICK_ENABLED or any(f.get(k) in (None, "") for k in required):
        return (BAD_REQUEST, "Error in request from click"), None
    if f["service_id"] != str(config.CLICK_SERVICE_ID):
        return (BAD_REQUEST, "Unknown service"), None
    if f["sign_string"].lower() != _sign(f, with_prepare_id):
        return (SIGN_FAILED, "SIGN CHECK FAILED!"), None
    if f["action"] != action:
        return (BAD_ACTION, "Action not found"), None
    try:
        invoice = db.get_click_invoice(int(f["merchant_trans_id"]))
    except ValueError:
        invoice = None
    if invoice is None:
        return (NOT_FOUND, "User does not exist"), None
    try:
        amount_ok = abs(float(f["amount"]) - invoice["amount"]) < 0.01
    except ValueError:
        amount_ok = False
    if not amount_ok:
        return (BAD_AMOUNT, "Incorrect parameter amount"), None
    if invoice["status"] == "paid":
        return (ALREADY_PAID, "Already paid"), None
    if invoice["status"] == "cancelled":
        return (CANCELLED, "Transaction cancelled"), None
    return None, invoice


@router.post("/click/prepare")
async def prepare(request: Request):
    f = {k: str(v) for k, v in (await request.form()).items()}
    err, invoice = _check(f, "0", with_prepare_id=False)
    if err:
        return _answer(f, *err)
    db.prepare_click_invoice(invoice["id"], f["click_trans_id"])
    return _answer(f, OK, "Success", merchant_prepare_id=invoice["id"])


@router.post("/click/complete")
async def complete(request: Request):
    f = {k: str(v) for k, v in (await request.form()).items()}
    err, invoice = _check(f, "1", with_prepare_id=True)
    if err:
        return _answer(f, *err)
    if f["merchant_prepare_id"] != str(invoice["id"]) or invoice["status"] != "prepared":
        return _answer(f, NO_TRANSACTION, "Transaction does not exist")

    # Click to'lov amalga oshmaganini xabar qilsa (error < 0) — bekor qilamiz
    try:
        click_error = int(f.get("error") or 0)
    except ValueError:
        click_error = 0
    if click_error < 0:
        db.cancel_click_invoice(invoice["id"])
        return _answer(f, CANCELLED, "Transaction cancelled")

    if not db.complete_click_invoice(invoice["id"]):
        return _answer(f, UPDATE_FAILED, "Failed to update user")
    balance = db.balance(invoice["user_id"])
    await notify.send_message(
        invoice["user_id"],
        f"✅ Click orqali {invoice['amount']:,} so'm qabul qilindi.\nJoriy balans: {balance:,} so'm".replace(",", " "),
    )
    return _answer(f, OK, "Success", merchant_confirm_id=invoice["id"])
