"""Testlar haqiqiy bazaga, AI'ga, Telegram'ga yoki to'lov tizimiga tegmaydi.

Har test vaqtinchalik papkada yangi SQLite baza bilan ishlaydi, AI — DEMO rejimda, rasmlar o'chiq.
"""
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="yaratslayd-tests-")
os.environ.update({
    "AI_PROVIDER": "demo", "GEMINI_API_KEY": "", "GROQ_API_KEY": "", "ANTHROPIC_API_KEY": "",
    "IMAGE_PROVIDER": "none", "BOT_TOKEN": "", "BOT_USERNAME": "TestBot", "ADMIN_IDS": "",
    "CLICK_SERVICE_ID": "", "CLICK_MERCHANT_ID": "", "CLICK_SECRET_KEY": "",
    "DB_PATH": str(Path(_TMP) / "test.db"), "OUTPUT_DIR": str(Path(_TMP) / "out"),
    "PRICE_PRESENTATION": "2000", "WELCOME_BONUS": "2000",
})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import config, db, preview, web  # noqa: E402


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    """Har test uchun bo'sh baza va fayllar papkasi."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "out")
    if db._conn is not None:
        db._conn.close()
    db._conn = None
    web.jobs.clear()
    web._plan_hits.clear()
    web._user_hits.clear()
    # LibreOffice sekin — alohida testdan tashqari slayd rasmlari yasalmaydi
    monkeypatch.setattr(preview, "available", lambda: False)
    yield
    if db._conn is not None:
        db._conn.close()
    db._conn = None


@pytest.fixture
def client():
    with TestClient(web.app) as c:
        yield c


def make_user(uid: int, balance: int = 0, name: str = "Test") -> str:
    """Foydalanuvchi va sessiya yaratadi, sessiya tokenini qaytaradi."""
    db.register_user(uid, f"user{uid}", name, None)
    with db.tx() as c:
        c.execute("UPDATE users SET balance=? WHERE id=?", (balance, uid))
    token = f"session-{uid}"
    db.create_session(token, uid)
    return token


def auth(token: str) -> dict:
    return {"X-Session": token}
