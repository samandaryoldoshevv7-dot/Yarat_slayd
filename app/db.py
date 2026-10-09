"""SQLite: foydalanuvchilar, balans, buyurtmalar va to'lovlar."""
import sqlite3
import threading
from contextlib import contextmanager

from . import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    balance INTEGER NOT NULL DEFAULT 0,
    referred_by INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    lang TEXT NOT NULL,
    slides INTEGER NOT NULL,
    template TEXT,
    price INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    file_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    photo_file_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _connect() -> sqlite3.Connection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


_conn = None


@contextmanager
def tx():
    global _conn
    with _lock:
        if _conn is None:
            _conn = _connect()
            _conn.executescript(SCHEMA)
        try:
            yield _conn
            _conn.commit()
        except Exception:
            _conn.rollback()
            raise


def get_user(user_id: int):
    with tx() as c:
        return c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def register_user(user_id: int, username: str | None, full_name: str, referred_by: int | None) -> bool:
    """Yangi foydalanuvchi bo'lsa True qaytaradi (bonus beriladi)."""
    with tx() as c:
        if c.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone():
            c.execute("UPDATE users SET username=?, full_name=? WHERE id=?", (username, full_name, user_id))
            return False
        if referred_by == user_id or not (
            referred_by and c.execute("SELECT 1 FROM users WHERE id=?", (referred_by,)).fetchone()
        ):
            referred_by = None
        c.execute(
            "INSERT INTO users (id, username, full_name, balance, referred_by) VALUES (?,?,?,?,?)",
            (user_id, username, full_name, config.WELCOME_BONUS, referred_by),
        )
        if referred_by:
            c.execute("UPDATE users SET balance = balance + ? WHERE id=?", (config.REFERRAL_BONUS, referred_by))
        return True


def balance(user_id: int) -> int:
    row = get_user(user_id)
    return row["balance"] if row else 0


def add_balance(user_id: int, amount: int) -> int:
    with tx() as c:
        c.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, user_id))
        return c.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()["balance"]


def charge(user_id: int, amount: int) -> bool:
    """Balansdan yechadi. Mablag' yetmasa False."""
    with tx() as c:
        cur = c.execute(
            "UPDATE users SET balance = balance - ? WHERE id=? AND balance >= ?", (amount, user_id, amount)
        )
        return cur.rowcount == 1


def create_order(user_id: int, topic: str, lang: str, slides: int, template: str, price: int) -> int:
    with tx() as c:
        cur = c.execute(
            "INSERT INTO orders (user_id, topic, lang, slides, template, price) VALUES (?,?,?,?,?,?)",
            (user_id, topic, lang, slides, template, price),
        )
        return cur.lastrowid


def finish_order(order_id: int, status: str, file_path: str | None = None) -> None:
    with tx() as c:
        c.execute("UPDATE orders SET status=?, file_path=? WHERE id=?", (status, file_path, order_id))


def user_orders(user_id: int, limit: int = 10):
    with tx() as c:
        return c.execute(
            "SELECT * FROM orders WHERE user_id=? AND status='done' ORDER BY id DESC LIMIT ?", (user_id, limit)
        ).fetchall()


def create_payment(user_id: int, photo_file_id: str) -> int:
    with tx() as c:
        return c.execute(
            "INSERT INTO payments (user_id, photo_file_id) VALUES (?,?)", (user_id, photo_file_id)
        ).lastrowid


def resolve_payment(payment_id: int, amount: int, status: str):
    """To'lovni bir marta tasdiqlaydi/rad etadi. Allaqachon ko'rilgan bo'lsa None."""
    with tx() as c:
        row = c.execute("SELECT * FROM payments WHERE id=? AND status='pending'", (payment_id,)).fetchone()
        if not row:
            return None
        c.execute("UPDATE payments SET status=?, amount=? WHERE id=?", (status, amount, payment_id))
        if status == "approved":
            c.execute("UPDATE users SET balance = balance + ? WHERE id=?", (amount, row["user_id"]))
        return row


def stats() -> dict:
    with tx() as c:
        one = lambda q: c.execute(q).fetchone()[0]  # noqa: E731
        return {
            "users": one("SELECT COUNT(*) FROM users"),
            "orders": one("SELECT COUNT(*) FROM orders WHERE status='done'"),
            "revenue": one("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='approved'"),
            "pending_payments": one("SELECT COUNT(*) FROM payments WHERE status='pending'"),
        }


def all_user_ids() -> list[int]:
    with tx() as c:
        return [r[0] for r in c.execute("SELECT id FROM users").fetchall()]
