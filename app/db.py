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
CREATE TABLE IF NOT EXISTS web_logins (
    token TEXT PRIMARY KEY,
    user_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS login_codes (
    code TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS web_sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS click_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    click_trans_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    paid_at TEXT
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    photo_file_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Eski bazalarga yangi ustunlar (mavjud ma'lumot saqlanadi)
MIGRATIONS = [
    ("orders", "finished_at", "TEXT"),
    ("orders", "refunded", "INTEGER NOT NULL DEFAULT 0"),
]


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
            for table, col, decl in MIGRATIONS:
                cols = {r["name"] for r in _conn.execute(f"PRAGMA table_info({table})")}
                if col not in cols:
                    _conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
            _conn.commit()
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


def start_order(user_id: int, topic: str, lang: str, slides: int, template: str, price: int) -> int | None:
    """Balansdan yechish va buyurtma ochish — bitta tranzaksiyada. Mablag' yetmasa None.

    Yarmida xato bo'lsa ikkalasi ham bekor bo'ladi: pul yechilib, buyurtma ochilmay qolmaydi.
    """
    with tx() as c:
        cur = c.execute(
            "UPDATE users SET balance = balance - ? WHERE id=? AND balance >= ?", (price, user_id, price)
        )
        if cur.rowcount != 1:
            return None
        return c.execute(
            "INSERT INTO orders (user_id, topic, lang, slides, template, price) VALUES (?,?,?,?,?,?)",
            (user_id, topic, lang, slides, template, price),
        ).lastrowid


def finish_order(order_id: int, status: str, file_path: str | None = None) -> None:
    with tx() as c:
        c.execute("UPDATE orders SET status=?, file_path=?, finished_at=COALESCE(finished_at, CURRENT_TIMESTAMP) WHERE id=?",
                  (status, file_path, order_id))


def fail_order(order_id: int) -> int:
    """Buyurtmani muvaffaqiyatsiz deb belgilaydi va pulni qaytaradi — faqat bir marta.

    Qaytarilgan summani beradi (allaqachon yakunlangan yoki qaytarilgan bo'lsa 0).
    """
    with tx() as c:
        row = c.execute("SELECT user_id, price FROM orders WHERE id=? AND status='pending' AND refunded=0",
                        (order_id,)).fetchone()
        if not row:
            return 0
        c.execute("UPDATE orders SET status='failed', refunded=1, finished_at=CURRENT_TIMESTAMP WHERE id=?",
                  (order_id,))
        c.execute("UPDATE users SET balance = balance + ? WHERE id=?", (row["price"], row["user_id"]))
        return row["price"]


def stuck_orders():
    """Tugallanmay qolgan buyurtmalar (server yarmida to'xtasa shunday qoladi)."""
    with tx() as c:
        return c.execute("SELECT * FROM orders WHERE status='pending' ORDER BY id").fetchall()


def user_has_pending(user_id: int) -> bool:
    with tx() as c:
        return c.execute("SELECT 1 FROM orders WHERE user_id=? AND status='pending'",
                         (user_id,)).fetchone() is not None


def delete_order(order_id: int, user_id: int) -> bool:
    """Foydalanuvchi o'z taqdimotini o'chiradi (yozuv hisob-kitob uchun qoladi, mavzu va fayl o'chadi)."""
    with tx() as c:
        cur = c.execute("UPDATE orders SET status='deleted', file_path=NULL, topic='' "
                        "WHERE id=? AND user_id=? AND status='done'", (order_id, user_id))
        return cur.rowcount == 1


def delete_account_data(user_id: int) -> list[int]:
    """Foydalanuvchi ma'lumotlarini o'chiradi: ism, username, mavzular, sessiyalar.

    Telegram ID, balans va to'lov yozuvlari hisob-kitob uchun qoladi (aks holda qayta kirganda sovg'a bonusi
    yana berilib qolardi). Fayllari o'chirilishi kerak bo'lgan buyurtmalar ro'yxatini qaytaradi.
    """
    with tx() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM orders WHERE user_id=?", (user_id,)).fetchall()]
        c.execute("UPDATE orders SET topic='', file_path=NULL, status=CASE WHEN status='done' THEN 'deleted' "
                  "ELSE status END WHERE user_id=?", (user_id,))
        c.execute("UPDATE users SET full_name='', username=NULL WHERE id=?", (user_id,))
        c.execute("DELETE FROM web_sessions WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM login_codes WHERE user_id=?", (user_id,))
        c.execute("DELETE FROM web_logins WHERE user_id=?", (user_id,))
        return ids


def get_secret(name: str) -> str:
    """Server siri (havolalarni imzolash uchun). Bir marta yaratiladi va bazada saqlanadi."""
    import secrets

    with tx() as c:
        row = c.execute("SELECT value FROM kv WHERE key=?", (name,)).fetchone()
        if row:
            return row["value"]
        value = secrets.token_hex(32)
        c.execute("INSERT INTO kv (key, value) VALUES (?,?)", (name, value))
        return value


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


# ---------------- Sayt orqali kirish (Telegram bot tasdiqlaydi) ----------------

def create_login(token: str) -> None:
    with tx() as c:
        c.execute("DELETE FROM web_logins WHERE created_at < datetime('now', '-1 hour')")
        c.execute("INSERT INTO web_logins (token) VALUES (?)", (token,))


def confirm_login(token: str, user_id: int) -> bool:
    with tx() as c:
        cur = c.execute(
            "UPDATE web_logins SET user_id=? WHERE token=? AND user_id IS NULL "
            "AND created_at >= datetime('now', '-15 minutes')",
            (user_id, token),
        )
        return cur.rowcount == 1


def take_login(token: str) -> int | None:
    """Tasdiqlangan kirish tokenini bir marta ishlatadi va user_id qaytaradi."""
    with tx() as c:
        row = c.execute("SELECT user_id FROM web_logins WHERE token=?", (token,)).fetchone()
        if not row or row["user_id"] is None:
            return None
        c.execute("DELETE FROM web_logins WHERE token=?", (token,))
        return row["user_id"]


def create_session(token: str, user_id: int) -> None:
    with tx() as c:
        c.execute("INSERT INTO web_sessions (token, user_id) VALUES (?,?)", (token, user_id))


def session_user(token: str) -> int | None:
    with tx() as c:
        row = c.execute(
            "SELECT user_id FROM web_sessions WHERE token=? AND created_at >= datetime('now', '-30 days')",
            (token,),
        ).fetchone()
        return row["user_id"] if row else None


def delete_session(token: str) -> None:
    with tx() as c:
        c.execute("DELETE FROM web_sessions WHERE token=?", (token,))


def get_order(order_id: int):
    with tx() as c:
        return c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()


# ---------------- Click hisob-fakturalari ----------------

def create_click_invoice(user_id: int, amount: int) -> int:
    with tx() as c:
        return c.execute("INSERT INTO click_invoices (user_id, amount) VALUES (?,?)", (user_id, amount)).lastrowid


def get_click_invoice(invoice_id: int):
    with tx() as c:
        return c.execute("SELECT * FROM click_invoices WHERE id=?", (invoice_id,)).fetchone()


def prepare_click_invoice(invoice_id: int, click_trans_id: str) -> None:
    with tx() as c:
        c.execute(
            "UPDATE click_invoices SET status='prepared', click_trans_id=? WHERE id=? AND status IN ('new','prepared')",
            (click_trans_id, invoice_id),
        )


def complete_click_invoice(invoice_id: int) -> bool:
    """Bir marta to'langan deb belgilaydi va balansni to'ldiradi. Allaqachon to'langan bo'lsa False."""
    with tx() as c:
        cur = c.execute(
            "UPDATE click_invoices SET status='paid', paid_at=CURRENT_TIMESTAMP WHERE id=? AND status='prepared'",
            (invoice_id,),
        )
        if cur.rowcount != 1:
            return False
        row = c.execute("SELECT user_id, amount FROM click_invoices WHERE id=?", (invoice_id,)).fetchone()
        c.execute("UPDATE users SET balance = balance + ? WHERE id=?", (row["amount"], row["user_id"]))
        c.execute(
            "INSERT INTO payments (user_id, amount, status, photo_file_id) VALUES (?,?,'approved',?)",
            (row["user_id"], row["amount"], f"click:{invoice_id}"),
        )
        return True


def cancel_click_invoice(invoice_id: int) -> None:
    with tx() as c:
        c.execute("UPDATE click_invoices SET status='cancelled' WHERE id=? AND status != 'paid'", (invoice_id,))


# ---------------- Admin panel ----------------

def admin_stats() -> dict:
    with tx() as c:
        one = lambda q: c.execute(q).fetchone()[0]  # noqa: E731
        return {
            "users": one("SELECT COUNT(*) FROM users"),
            "users_today": one("SELECT COUNT(*) FROM users WHERE date(created_at)=date('now')"),
            "orders": one("SELECT COUNT(*) FROM orders WHERE status='done'"),
            "orders_today": one("SELECT COUNT(*) FROM orders WHERE status='done' AND date(created_at)=date('now')"),
            "failed_today": one("SELECT COUNT(*) FROM orders WHERE status='failed' AND date(created_at)=date('now')"),
            "revenue": one("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='approved'"),
            "pending_payments": one("SELECT COUNT(*) FROM payments WHERE status='pending'"),
            "balance_total": one("SELECT COALESCE(SUM(balance),0) FROM users"),
            # Haqiqiy tayyorlanish vaqti (soniya) — saytdagi va'dalarni shu bilan tekshirish mumkin
            "avg_seconds_7d": one("SELECT CAST(COALESCE(AVG((julianday(finished_at)-julianday(created_at))*86400),0) "
                                  "AS INTEGER) FROM orders WHERE status IN ('done','deleted') AND finished_at IS NOT NULL "
                                  "AND created_at >= datetime('now','-7 days')"),
        }


def pending_payments():
    with tx() as c:
        return c.execute(
            "SELECT p.*, u.full_name, u.username FROM payments p LEFT JOIN users u ON u.id=p.user_id "
            "WHERE p.status='pending' ORDER BY p.id"
        ).fetchall()


def get_payment(payment_id: int):
    with tx() as c:
        return c.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()


def list_users(q: str = "", limit: int = 50):
    with tx() as c:
        if q:
            like = f"%{q.lstrip('@')}%"
            return c.execute(
                "SELECT * FROM users WHERE CAST(id AS TEXT) LIKE ? OR username LIKE ? OR full_name LIKE ? "
                "ORDER BY created_at DESC LIMIT ?", (like, like, like, limit)).fetchall()
        return c.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()


def recent_orders(limit: int = 50):
    with tx() as c:
        return c.execute(
            "SELECT o.*, u.full_name, u.username FROM orders o LEFT JOIN users u ON u.id=o.user_id "
            "ORDER BY o.id DESC LIMIT ?", (limit,)).fetchall()


# ---------------- Telegram orqali kod bilan kirish ----------------

LOGIN_CODE_TTL = "-2 minutes"


def create_login_code(user_id: int) -> str:
    """Foydalanuvchiga 5 xonali bir martalik kod (2 daqiqa amal qiladi)."""
    import secrets

    with tx() as c:
        c.execute("DELETE FROM login_codes WHERE user_id=? OR created_at < datetime('now', ?)",
                  (user_id, LOGIN_CODE_TTL))
        while True:
            code = f"{secrets.randbelow(90000) + 10000}"
            if not c.execute("SELECT 1 FROM login_codes WHERE code=?", (code,)).fetchone():
                break
        c.execute("INSERT INTO login_codes (code, user_id) VALUES (?,?)", (code, user_id))
        return code


def take_login_code(code: str) -> int | None:
    with tx() as c:
        row = c.execute("SELECT user_id FROM login_codes WHERE code=? AND created_at >= datetime('now', ?)",
                        (code, LOGIN_CODE_TTL)).fetchone()
        c.execute("DELETE FROM login_codes WHERE code=?", (code,))
        return row["user_id"] if row else None
