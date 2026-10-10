"""To'lovlar: Click callbacklari takrorlansa ham balans bir marta to'ldiriladi."""
import hashlib

import pytest

from app import click, config, db
from conftest import make_user


@pytest.fixture
def click_on(monkeypatch):
    monkeypatch.setattr(config, "CLICK_SERVICE_ID", "111")
    monkeypatch.setattr(config, "CLICK_MERCHANT_ID", "222")
    monkeypatch.setattr(config, "CLICK_SECRET_KEY", "test-secret")
    monkeypatch.setattr(config, "CLICK_ENABLED", True)


def signed(action: str, invoice: int, amount: int, prepare_id: str = "", trans="9001", error="0"):
    f = {"click_trans_id": trans, "service_id": "111", "click_paydoc_id": "1", "merchant_trans_id": str(invoice),
         "amount": str(amount), "action": action, "error": error, "error_note": "Success", "sign_time": "2026-10-10 10:00:00"}
    if prepare_id:
        f["merchant_prepare_id"] = prepare_id
    parts = [f["click_trans_id"], f["service_id"], "test-secret", f["merchant_trans_id"]]
    if prepare_id:
        parts.append(prepare_id)
    parts += [f["amount"], f["action"], f["sign_time"]]
    f["sign_string"] = hashlib.md5("".join(parts).encode()).hexdigest()
    return f


def test_click_complete_twice_credits_once(client, click_on):
    make_user(10, balance=0)
    inv = db.create_click_invoice(10, 5000)
    assert client.post("/click/prepare", data=signed("0", inv, 5000)).json()["error"] == 0
    first = client.post("/click/complete", data=signed("1", inv, 5000, str(inv))).json()
    assert first["error"] == 0
    second = client.post("/click/complete", data=signed("1", inv, 5000, str(inv))).json()
    assert second["error"] == click.ALREADY_PAID
    assert db.balance(10) == 5000


def test_click_bad_sign_and_amount(client, click_on):
    make_user(11)
    inv = db.create_click_invoice(11, 5000)
    bad = signed("0", inv, 5000)
    bad["sign_string"] = "0" * 32
    assert client.post("/click/prepare", data=bad).json()["error"] == click.SIGN_FAILED
    assert client.post("/click/prepare", data=signed("0", inv, 4000)).json()["error"] == click.BAD_AMOUNT
    assert db.balance(11) == 0


def test_click_cancelled_payment_not_credited(client, click_on):
    make_user(12)
    inv = db.create_click_invoice(12, 5000)
    client.post("/click/prepare", data=signed("0", inv, 5000))
    r = client.post("/click/complete", data=signed("1", inv, 5000, str(inv), error="-5017")).json()
    assert r["error"] == click.CANCELLED
    assert db.balance(12) == 0


def test_card_receipt_approved_once():
    make_user(13)
    pid = db.create_payment(13, "photo")
    assert db.resolve_payment(pid, 10000, "approved") is not None
    assert db.resolve_payment(pid, 10000, "approved") is None
    assert db.balance(13) == 10000
