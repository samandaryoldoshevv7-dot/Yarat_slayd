"""Kirish huquqlari: begona taqdimot, fayl havolalari, sessiya va CSRF himoyasi."""
import time

from app import sessions
from conftest import auth, make_user
from test_orders import BODY, wait_job


def make_order(client, uid):
    token = make_user(uid, balance=2000)
    j = wait_job(client, token, client.post("/api/generate", json=BODY, headers=auth(token)).json()["job"])
    assert j["status"] == "done"
    return token, j["order_id"]


def test_other_user_cannot_touch_order(client):
    _, oid = make_order(client, 20)
    other = make_user(21, balance=0)
    h = auth(other)
    for method, url in [("get", f"/api/download/{oid}"), ("get", f"/api/orders/{oid}/project"),
                        ("get", f"/api/orders/{oid}/preview/1"), ("get", f"/api/orders/{oid}/pdf"),
                        ("get", f"/api/orders/{oid}/image/0"), ("delete", f"/api/orders/{oid}/image/0"),
                        ("delete", f"/api/orders/{oid}"), ("get", f"/api/jobs/{oid}")]:
        r = getattr(client, method)(url, headers=h)
        assert r.status_code == 404, (url, r.status_code)
    r = client.post(f"/api/orders/{oid}/save", headers=h, json={"title": "x", "slides": [], "template": "01"})
    assert r.status_code == 404


def test_anonymous_gets_401(client):
    _, oid = make_order(client, 22)
    client.cookies.clear()
    assert client.get(f"/api/download/{oid}").status_code == 401
    assert client.post("/api/generate", json=BODY).status_code == 401


def test_session_token_in_url_is_not_accepted(client):
    token, oid = make_order(client, 23)
    client.cookies.clear()
    assert client.get(f"/api/download/{oid}?s={token}").status_code == 401


def test_file_token_works_only_for_reading_own_files(client):
    token, oid = make_order(client, 24)
    ft = client.get("/api/me", headers=auth(token)).json()["ft"]
    client.cookies.clear()
    assert client.get(f"/api/download/{oid}?t={ft}").status_code == 200
    # Fayl tokeni sessiya emas: tahrirlash, o'chirish, yaratish mumkin emas
    assert client.post(f"/api/orders/{oid}/save?t={ft}", json={}).status_code in (401, 422)
    assert client.delete(f"/api/orders/{oid}?t={ft}").status_code == 401
    assert client.post(f"/api/generate?t={ft}", json=BODY).status_code == 401
    # Soxtalashtirilgan yoki boshqa foydalanuvchiga tegishli token
    uid, exp, sig = ft.split(".")
    assert client.get(f"/api/download/{oid}?t=25.{exp}.{sig}").status_code == 401
    other_ft = sessions.file_token(25)
    assert client.get(f"/api/download/{oid}?t={other_ft}").status_code == 404


def test_file_token_expires(client):
    token, oid = make_order(client, 26)
    old = sessions.file_token(26, now=time.time() - sessions.FILE_TOKEN_TTL - 5)
    client.cookies.clear()
    assert client.get(f"/api/download/{oid}?t={old}").status_code == 401


def test_cross_site_post_blocked(client):
    token = make_user(27, balance=2000)
    r = client.post("/api/generate", json=BODY, headers={**auth(token), "Origin": "https://evil.example"})
    assert r.status_code == 403


def test_login_code_single_use(client):
    from app import db
    make_user(28)
    code = db.create_login_code(28)
    assert client.post("/api/login/code", json={"code": code}).status_code == 200
    assert client.post("/api/login/code", json={"code": code}).status_code == 400
