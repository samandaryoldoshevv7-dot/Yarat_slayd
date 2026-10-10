"""Pul yechish, buyurtma, xatoda pulni qaytarish va server qayta ishga tushishi."""
import time

import pytest

from app import ai, db, service, web
from conftest import auth, make_user

OUTLINE = {"title": "Qayta ishlash", "subtitle": "Taqdimot",
           "slides": ["Kirish", "Asosiy qism", "Muammolar", "Xulosa"]}
BODY = {"topic": "Qayta ishlash", "lang": "uz", "slides": 7, "template": "01", "outline": OUTLINE}


def wait_job(client, token, job, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{job}", headers=auth(token)).json()
        if j["status"] != "working":
            return j
        time.sleep(0.2)
    raise AssertionError("Vazifa tugamadi")


def test_generate_success_charges_once(client):
    token = make_user(1, balance=2000)
    r = client.post("/api/generate", json=BODY, headers=auth(token))
    assert r.status_code == 200, r.text
    j = wait_job(client, token, r.json()["job"])
    assert j["status"] == "done", j
    assert db.balance(1) == 0
    d = client.get(j["download"], headers=auth(token))
    assert d.status_code == 200 and d.content[:2] == b"PK"  # .pptx = zip
    orders = client.get("/api/orders", headers=auth(token)).json()
    assert len(orders) == 1 and orders[0]["editable"]


def test_not_enough_balance_creates_no_order(client):
    token = make_user(2, balance=1999)
    r = client.post("/api/generate", json=BODY, headers=auth(token))
    assert r.status_code == 402
    assert db.balance(2) == 1999
    assert db.recent_orders() == []


def test_ai_failure_refunds_exactly_once(client, monkeypatch):
    async def boom(*a, **k):
        raise ai.AIError("AI hozir band")
    monkeypatch.setattr(service, "generate", boom)
    token = make_user(3, balance=2000)
    r = client.post("/api/generate", json=BODY, headers=auth(token))
    j = wait_job(client, token, r.json()["job"])
    assert j["status"] == "failed" and "qaytarildi" in j["step"]
    assert db.balance(3) == 2000
    order = db.get_order(j["order_id"])
    assert order["status"] == "failed" and order["refunded"] == 1
    # Qayta chaqirish pulni ikkinchi marta qaytarmaydi
    assert db.fail_order(order["id"]) == 0
    assert db.balance(3) == 2000


def test_unexpected_error_hides_details(client, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("/secret/path GEMINI_API_KEY=abc")
    monkeypatch.setattr(service, "generate", boom)
    token = make_user(4, balance=2000)
    j = wait_job(client, token, client.post("/api/generate", json=BODY, headers=auth(token)).json()["job"])
    assert j["status"] == "failed"
    assert "secret" not in j["step"] and "GEMINI" not in j["step"]
    assert db.balance(4) == 2000


def test_second_order_blocked_while_pending(client):
    token = make_user(5, balance=10000)
    db.start_order(5, "Birinchi", "uz", 7, "01", 2000)
    r = client.post("/api/generate", json=BODY, headers=auth(token))
    assert r.status_code == 409
    assert db.balance(5) == 8000


def test_finished_order_is_not_refunded():
    make_user(6, balance=2000)
    oid = db.start_order(6, "Mavzu", "uz", 7, "01", 2000)
    db.finish_order(oid, "done", "/tmp/x.pptx")
    assert db.fail_order(oid) == 0
    assert db.balance(6) == 0


def test_restart_recovers_stuck_orders(client):
    token = make_user(7, balance=4000)
    oid = db.start_order(7, "To'xtab qolgan", "uz", 7, "01", 2000)
    assert db.balance(7) == 2000
    # Server qayta ishga tushdi: xotiradagi vazifalar yo'q
    web.jobs.clear()
    recovered = service.recover_stuck_orders()
    assert [r["order_id"] for r in recovered] == [oid]
    assert db.balance(7) == 4000
    assert service.recover_stuck_orders() == []  # ikkinchi marta qaytarilmaydi
    assert db.balance(7) == 4000
    # Sayt holatni bazadan oladi
    j = client.get(f"/api/jobs/{oid}", headers=auth(token)).json()
    assert j["status"] == "failed"


def test_job_status_survives_restart_for_done_order(client):
    token = make_user(8, balance=2000)
    j = wait_job(client, token, client.post("/api/generate", json=BODY, headers=auth(token)).json()["job"])
    web.jobs.clear()
    again = client.get(f"/api/jobs/{j['order_id']}", headers=auth(token)).json()
    assert again["status"] == "done" and again["download"]


def test_start_order_is_atomic(monkeypatch):
    """Buyurtma yozilmasa, pul ham yechilmaydi."""
    make_user(9, balance=2000)
    with pytest.raises(Exception):
        db.start_order(9, None, "uz", 7, "01", 2000)  # topic NOT NULL — INSERT xato beradi
    assert db.balance(9) == 2000
