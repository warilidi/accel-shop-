from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.catalog_data import DEFAULT_CATALOG
from app.emoji_ids import strip_unicode_emoji

DB_PATH = Path("shop.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS subcategories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(category_id, name),
            FOREIGN KEY(category_id) REFERENCES categories(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcategory_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            product_type TEXT NOT NULL DEFAULT '',
            price_usd REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            payloads_json TEXT NOT NULL DEFAULT '[]',
            delivery_text TEXT NOT NULL DEFAULT '',
            image_url TEXT NOT NULL DEFAULT '',
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(subcategory_id) REFERENCES subcategories(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_code TEXT NOT NULL UNIQUE,
            tg_user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty INTEGER NOT NULL,
            price_usd REAL NOT NULL,
            total_usd REAL NOT NULL,
            total_rub REAL NOT NULL,
            payment_method TEXT NOT NULL,
            payment_status TEXT NOT NULL DEFAULT 'pending',
            payment_deadline_ts INTEGER NOT NULL,
            created_ts INTEGER NOT NULL,
            payment_meta TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS visuals (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_balances (
            tg_user_id INTEGER PRIMARY KEY,
            balance_usd REAL NOT NULL DEFAULT 0,
            balance_rub REAL NOT NULL DEFAULT 0,
            updated_ts INTEGER NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS button_texts (
            button_id TEXT PRIMARY KEY,
            text TEXT NOT NULL
        )
        """
    )
    # Lightweight migration for existing databases.
    try:
        cur.execute("ALTER TABLE products ADD COLUMN description TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE products ADD COLUMN delivery_text TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_balances (
                tg_user_id INTEGER PRIMARY KEY,
                balance_usd REAL NOT NULL DEFAULT 0,
                balance_rub REAL NOT NULL DEFAULT 0,
                updated_ts INTEGER NOT NULL
            )
            """
        )
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS button_texts (
                button_id TEXT PRIMARY KEY,
                text TEXT NOT NULL
            )
            """
        )
    except sqlite3.OperationalError:
        pass
    try:
        cur.execute("ALTER TABLE orders ADD COLUMN invoice_id INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    conn.commit()

    cur.execute("SELECT COUNT(*) as c FROM categories")
    if cur.fetchone()["c"] == 0:
        seed_catalog(conn, DEFAULT_CATALOG)

    seed_extra_products(conn)
    migrate_legacy_extra_subcategory(conn)

    conn.close()


EXTRA_PRODUCTS = [
    # (category, subcategory, title, price_usd, product_type, stock)
    ("Другие сервисы", "NordVPN", "Nord VPN", 5, "ACC", 5),
    ("Другие сервисы", "Canva", "Canva Edu 12m", 3, "ACC", 5),
    ("Другие сервисы", "Canva", "Canva Reseller Panel up to 500 members", 13, "ACC", 5),
    ("Другие сервисы", "Kiro", "Kiro Pro 1m", 3.5, "ACC", 5),
    ("Другие сервисы", "LinkedIn", "LinkedIn Premium Career 3m", 1, "ACC", 5),
    ("Другие сервисы", "Lovable", "Lovable Pro 1m", 2, "ACC", 5),
    ("Другие сервисы", "Veo 3", "Veo 3 Ultra 25k Credits (Fw24h)", 2, "ACC", 5),
    ("Другие сервисы", "Notion", "Notion Business 3m (Link)", 4, "Link", 5),
]

# Миграция со старой вложенной подкатегории «Другие сервисы»
LEGACY_EXTRA_MIGRATIONS = [
    ("NordVPN - Nord VPN", "Другие сервисы", "NordVPN", "Nord VPN"),
    ("Canva - Canva Edu 12m", "Другие сервисы", "Canva", "Canva Edu 12m"),
    ("Canva - Canva Reseller Panel up to 500 members", "Другие сервисы", "Canva", "Canva Reseller Panel up to 500 members"),
    ("Kiro - Kiro Pro 1m", "Другие сервисы", "Kiro", "Kiro Pro 1m"),
    ("LinkedIn - LinkedIn Premium Career 3m", "Другие сервисы", "LinkedIn", "LinkedIn Premium Career 3m"),
    ("Lovable - Lovable Pro 1m", "Другие сервисы", "Lovable", "Lovable Pro 1m"),
    ("Veo 3 - Veo 3 Ultra 25k Credits (Fw24h)", "Другие сервисы", "Veo 3", "Veo 3 Ultra 25k Credits (Fw24h)"),
]


def _get_or_create_subcategory(cur: sqlite3.Cursor, category_id: int, subcategory_name: str) -> int:
    cur.execute(
        "SELECT id FROM subcategories WHERE category_id = ? AND LOWER(name) = LOWER(?)",
        (category_id, subcategory_name),
    )
    sub = cur.fetchone()
    if sub:
        return int(sub["id"])
    cur.execute(
        "INSERT INTO subcategories(category_id, name) VALUES(?, ?)",
        (category_id, subcategory_name),
    )
    return int(cur.lastrowid)


def migrate_legacy_extra_subcategory(conn: sqlite3.Connection) -> None:
    """Переносит товары из вложенной подкатегории «Другие сервисы» в отдельные разделы."""
    cur = conn.cursor()
    for old_title, category_name, new_sub_name, new_title in LEGACY_EXTRA_MIGRATIONS:
        cur.execute("SELECT id FROM products WHERE title = ?", (old_title,))
        product = cur.fetchone()
        if not product:
            continue

        cur.execute(
            "SELECT id FROM categories WHERE LOWER(name) LIKE LOWER(?)",
            (f"%{category_name}%",),
        )
        category = cur.fetchone()
        if not category:
            continue

        sub_id = _get_or_create_subcategory(cur, int(category["id"]), new_sub_name)
        cur.execute(
            "UPDATE products SET subcategory_id = ?, title = ? WHERE id = ?",
            (sub_id, new_title, int(product["id"])),
        )

    cur.execute(
        """
        SELECT s.id FROM subcategories s
        JOIN categories c ON c.id = s.category_id
        WHERE LOWER(c.name) LIKE LOWER(?) AND LOWER(s.name) = LOWER(?)
        """,
        ("%Другие сервисы%", "Другие сервисы"),
    )
    legacy_sub = cur.fetchone()
    if legacy_sub:
        legacy_sub_id = int(legacy_sub["id"])
        cur.execute(
            "SELECT COUNT(*) AS c FROM products WHERE subcategory_id = ?",
            (legacy_sub_id,),
        )
        if int(cur.fetchone()["c"]) == 0:
            cur.execute("DELETE FROM subcategories WHERE id = ?", (legacy_sub_id,))

    conn.commit()


def seed_extra_products(conn: sqlite3.Connection) -> None:
    """Idempotently ensure EXTRA_PRODUCTS exist (added once, won't duplicate on restart)."""
    cur = conn.cursor()
    for category_name, subcategory_name, title, price, ptype, stock in EXTRA_PRODUCTS:
        cur.execute("SELECT id FROM products WHERE title = ?", (title,))
        if cur.fetchone():
            continue

        cur.execute("SELECT id FROM categories WHERE LOWER(name) LIKE LOWER(?)", (f"%{category_name}%",))
        category = cur.fetchone()
        if not category:
            cur.execute("INSERT INTO categories(name) VALUES(?)", (category_name,))
            category_id = cur.lastrowid
        else:
            category_id = category["id"]

        cur.execute(
            "SELECT id FROM subcategories WHERE category_id = ? AND LOWER(name) = LOWER(?)",
            (category_id, subcategory_name),
        )
        sub = cur.fetchone()
        if not sub:
            sub_id = _get_or_create_subcategory(cur, category_id, subcategory_name)
        else:
            sub_id = sub["id"]

        cur.execute(
            """
            INSERT INTO products(subcategory_id, title, product_type, price_usd, stock, payloads_json)
            VALUES (?, ?, ?, ?, ?, '[]')
            """,
            (sub_id, title, ptype, price, stock),
        )
    conn.commit()


def seed_catalog(conn: sqlite3.Connection, catalog: list[dict[str, Any]]) -> None:
    cur = conn.cursor()
    for category in catalog:
        cur.execute("INSERT INTO categories(name) VALUES(?)", (category["name"],))
        category_id = cur.lastrowid
        for sub in category["items"]:
            cur.execute(
                "INSERT INTO subcategories(category_id, name) VALUES(?, ?)",
                (category_id, sub["name"]),
            )
            sub_id = cur.lastrowid
            for prod in sub["products"]:
                cur.execute(
                    """
                    INSERT INTO products(subcategory_id, title, product_type, price_usd, stock)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    (
                        sub_id,
                        prod["title"],
                        prod.get("product_type", ""),
                        float(prod["price_usd"]),
                        int(prod.get("stock", 0)),
                    ),
                )
    conn.commit()


def list_categories() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT id, name FROM categories ORDER BY id").fetchall()


def rename_category(category_id: int, new_name: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not row:
            return False
        conn.execute("UPDATE categories SET name = ? WHERE id = ?", (new_name.strip(), category_id))
        conn.commit()
        return True


def rename_subcategory(subcategory_id: int, new_name: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM subcategories WHERE id = ?", (subcategory_id,)).fetchone()
        if not row:
            return False
        conn.execute("UPDATE subcategories SET name = ? WHERE id = ?", (new_name.strip(), subcategory_id))
        conn.commit()
        return True


def list_subcategories(category_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, name FROM subcategories WHERE category_id = ? ORDER BY id",
            (category_id,),
        ).fetchall()


def get_subcategory(subcategory_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT id, category_id, name FROM subcategories WHERE id = ?",
            (subcategory_id,),
        ).fetchone()


def list_products(subcategory_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT id, title, description, product_type, price_usd, stock, delivery_text, image_url
            FROM products
            WHERE subcategory_id = ? AND is_active = 1
            ORDER BY id
            """,
            (subcategory_id,),
        ).fetchall()


def get_product(product_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT p.id, p.subcategory_id, p.title, p.description, p.product_type, p.price_usd, p.stock,
                   p.payloads_json, p.delivery_text, p.image_url,
                   s.name as subcategory_name, c.name as category_name
            FROM products p
            JOIN subcategories s ON s.id = p.subcategory_id
            JOIN categories c ON c.id = s.category_id
            WHERE p.id = ? AND p.is_active = 1
            """,
            (product_id,),
        ).fetchone()


def adjust_stock(product_id: int, delta: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
        row = cur.fetchone()
        if not row:
            return False
        new_stock = row["stock"] + delta
        if new_stock < 0:
            return False
        conn.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
        conn.commit()
        return True


def add_product_payload(product_id: int, payload_text: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT payloads_json FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return False
        payloads = json.loads(row["payloads_json"])
        payloads.append(payload_text.strip())
        conn.execute(
            "UPDATE products SET payloads_json = ?, stock = stock + 1 WHERE id = ?",
            (json.dumps(payloads, ensure_ascii=False), product_id),
        )
        conn.commit()
        return True


def replace_product_payloads(product_id: int, payloads: list[str]) -> bool:
    cleaned = [item.strip() for item in payloads if item.strip()]
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE products SET payloads_json = ?, stock = ? WHERE id = ?",
            (json.dumps(cleaned, ensure_ascii=False), len(cleaned), product_id),
        )
        conn.commit()
        return True


def update_product_content(
    product_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    delivery_text: str | None = None,
) -> bool:
    fields: list[str] = []
    values: list[Any] = []
    if title is not None:
        fields.append("title = ?")
        values.append(title.strip())
    if description is not None:
        fields.append("description = ?")
        values.append(description.strip())
    if delivery_text is not None:
        fields.append("delivery_text = ?")
        values.append(delivery_text.strip())
    if not fields:
        return False
    values.append(product_id)

    with get_conn() as conn:
        row = conn.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
        if not row:
            return False
        conn.execute(f"UPDATE products SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
        return True


def pop_payloads(product_id: int, qty: int) -> list[str]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT payloads_json, stock FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if not row:
            return []
        payloads = json.loads(row["payloads_json"])
        if len(payloads) < qty:
            return []
        issued = payloads[:qty]
        left = payloads[qty:]
        conn.execute(
            "UPDATE products SET payloads_json = ?, stock = ? WHERE id = ?",
            (json.dumps(left, ensure_ascii=False), len(left), product_id),
        )
        conn.commit()
        return issued


def create_order(
    order_code: str,
    tg_user_id: int,
    product_id: int,
    qty: int,
    price_usd: float,
    total_usd: float,
    total_rub: float,
    payment_method: str,
    payment_deadline_ts: int,
    created_ts: int,
    payment_meta: str = "",
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO orders(
                order_code, tg_user_id, product_id, qty, price_usd, total_usd, total_rub,
                payment_method, payment_deadline_ts, created_ts, payment_meta
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_code,
                tg_user_id,
                product_id,
                qty,
                price_usd,
                total_usd,
                total_rub,
                payment_method,
                payment_deadline_ts,
                created_ts,
                payment_meta,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def mark_order_paid(order_code: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        conn.execute("UPDATE orders SET payment_status = 'paid' WHERE order_code = ?", (order_code,))
        conn.commit()
        return conn.execute("SELECT * FROM orders WHERE order_code = ?", (order_code,)).fetchone()


def get_order(order_code: str) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM orders WHERE order_code = ?", (order_code,)).fetchone()


def add_custom_product(
    category_name: str,
    subcategory_name: str,
    title: str,
    price_usd: float,
    product_type: str,
    stock: int,
    payloads: list[str] | None = None,
) -> int:
    with get_conn() as conn:
        # Try exact match first, then case-insensitive partial match
        cur = conn.execute("SELECT id, name FROM categories WHERE LOWER(name) = LOWER(?)", (category_name,))
        category = cur.fetchone()
        if not category:
            # Try partial/contains match (e.g. "Нейросети" matches "🤖 Нейросети")
            cur = conn.execute(
                "SELECT id, name FROM categories WHERE LOWER(name) LIKE LOWER(?)",
                (f"%{category_name}%",),
            )
            category = cur.fetchone()
        if not category:
            conn.execute("INSERT INTO categories(name) VALUES(?)", (category_name,))
            category_id = conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
        else:
            category_id = category["id"]

        # Try exact match first, then case-insensitive partial match
        cur = conn.execute(
            "SELECT id FROM subcategories WHERE category_id = ? AND LOWER(name) = LOWER(?)",
            (category_id, subcategory_name),
        )
        sub = cur.fetchone()
        if not sub:
            cur = conn.execute(
                "SELECT id FROM subcategories WHERE category_id = ? AND LOWER(name) LIKE LOWER(?)",
                (category_id, f"%{subcategory_name}%"),
            )
            sub = cur.fetchone()
        if not sub:
            conn.execute(
                "INSERT INTO subcategories(category_id, name) VALUES(?, ?)",
                (category_id, subcategory_name),
            )
            sub_id = conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
        else:
            sub_id = sub["id"]

        cleaned_payloads = [p.strip() for p in (payloads or []) if p.strip()]
        final_stock = len(cleaned_payloads) if cleaned_payloads else stock
        conn.execute(
            """
            INSERT INTO products(subcategory_id, title, product_type, price_usd, stock, payloads_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (sub_id, title, product_type, price_usd, final_stock, json.dumps(cleaned_payloads, ensure_ascii=False)),
        )
        product_id = int(conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"])
        conn.commit()
        return product_id


def get_all_user_ids() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT tg_user_id FROM orders").fetchall()
        return [int(r["tg_user_id"]) for r in rows]


def set_visual(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO visuals(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key.strip().lower(), value.strip()),
        )
        conn.commit()


def get_visual(key: str) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM visuals WHERE key = ?",
            (key.strip().lower(),),
        ).fetchone()
        return row["value"] if row else ""


def list_visuals() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT key, value FROM visuals ORDER BY key").fetchall()


# ─── Balance functions ─────────────────────────────────────────────────────


def get_user_balance(tg_user_id: int) -> tuple[float, float]:
    """Returns (balance_usd, balance_rub) for user, or (0.0, 0.0) if not found."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT balance_usd, balance_rub FROM user_balances WHERE tg_user_id = ?",
            (tg_user_id,),
        ).fetchone()
        if row:
            return float(row["balance_usd"]), float(row["balance_rub"])
        return 0.0, 0.0


def add_balance(tg_user_id: int, amount_usd: float, amount_rub: float) -> bool:
    """Add funds to user balance."""
    import time
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_balances(tg_user_id, balance_usd, balance_rub, updated_ts)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(tg_user_id) DO UPDATE SET 
                balance_usd = balance_usd + ?,
                balance_rub = balance_rub + ?,
                updated_ts = ?
            """,
            (tg_user_id, amount_usd, amount_rub, int(time.time()), amount_usd, amount_rub, int(time.time())),
        )
        conn.commit()
        return True


def withdraw_balance(tg_user_id: int, amount_usd: float, amount_rub: float) -> bool:
    """Withdraw funds from user balance. Returns False if insufficient funds."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT balance_usd FROM user_balances WHERE tg_user_id = ?",
            (tg_user_id,),
        ).fetchone()
        if not row or row["balance_usd"] < amount_usd:
            return False
        import time
        conn.execute(
            "UPDATE user_balances SET balance_usd = balance_usd - ?, balance_rub = balance_rub - ?, updated_ts = ? WHERE tg_user_id = ?",
            (amount_usd, amount_rub, int(time.time()), tg_user_id),
        )
        conn.commit()
        return True


def set_balance(tg_user_id: int, amount_usd: float, amount_rub: float) -> bool:
    """Set exact balance for user (admin function)."""
    import time
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO user_balances(tg_user_id, balance_usd, balance_rub, updated_ts)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(tg_user_id) DO UPDATE SET 
                balance_usd = ?,
                balance_rub = ?,
                updated_ts = ?
            """,
            (tg_user_id, amount_usd, amount_rub, int(time.time()), amount_usd, amount_rub, int(time.time())),
        )
        conn.commit()
        return True


# ─── Button texts functions ─────────────────────────────────────────────────

# Default button texts
DEFAULT_BUTTON_TEXTS = {
    "catalog": "Товары и услуги",
    "balance": "Баланс",
    "wholesale": "Опт",
    "help": "Помощь",
    "profile": "Профиль",
    "rules": "Правила",
    "crypto_usdt": "CryptoBot USDT",
    "crypto_ton": "CryptoBot TON",
    "bybit": "Bybit",
    "balance_pay": "Баланс",
    "topup": "Пополнить баланс",
    "history": "История",
    "back": "Назад",
    "buy": "Купить",
    "confirm_paid": "Я оплатил",
    "agree": "Пользовательское соглашение",
    "privacy": "Политика конфиденциальности",
}


def get_button_text(button_id: str) -> str:
    """Get button text from DB or use default."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT text FROM button_texts WHERE button_id = ?",
            (button_id,),
        ).fetchone()
        if row:
            return strip_unicode_emoji(row["text"])
    return strip_unicode_emoji(DEFAULT_BUTTON_TEXTS.get(button_id, button_id))


def set_button_text(button_id: str, text: str) -> bool:
    """Set button text in DB."""
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO button_texts(button_id, text)
            VALUES(?, ?)
            ON CONFLICT(button_id) DO UPDATE SET text = excluded.text
            """,
            (button_id, text.strip()),
        )
        conn.commit()
        return True


def list_all_buttons() -> dict[str, str]:
    """Get all available button IDs with their current texts."""
    with get_conn() as conn:
        rows = conn.execute("SELECT button_id, text FROM button_texts").fetchall()
        custom = {r["button_id"]: r["text"] for r in rows}
    
    result = DEFAULT_BUTTON_TEXTS.copy()
    result.update(custom)
    return result


def reset_button_text(button_id: str) -> bool:
    """Reset button text to default."""
    with get_conn() as conn:
        conn.execute("DELETE FROM button_texts WHERE button_id = ?", (button_id,))
        conn.commit()
        return True


def reset_all_buttons() -> bool:
    """Reset all button texts to defaults."""
    with get_conn() as conn:
        conn.execute("DELETE FROM button_texts")
        conn.commit()
        return True


# ─── Invoice / auto-payment helpers ──────────────────────────────────────


def set_order_invoice_id(order_code: str, invoice_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET invoice_id = ? WHERE order_code = ?",
            (invoice_id, order_code),
        )
        conn.commit()


def set_order_payment_method(order_code: str, method: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE orders SET payment_method = ? WHERE order_code = ?",
            (method, order_code),
        )
        conn.commit()


def get_pending_crypto_orders() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT * FROM orders
            WHERE payment_status = 'pending'
              AND invoice_id > 0
              AND payment_method IN ('crypto_usdt', 'crypto_ton')
            ORDER BY created_ts
            """,
        ).fetchall()


def get_all_orders(
    limit: int = 20,
    offset: int = 0,
    status_filter: str | None = None,
) -> list[sqlite3.Row]:
    """Возвращает все заказы с пагинацией и необязательной фильтрацией по статусу."""
    with get_conn() as conn:
        if status_filter:
            return conn.execute(
                """
                SELECT o.*, p.title as product_title
                FROM orders o
                LEFT JOIN products p ON o.product_id = p.id
                WHERE o.payment_status = ?
                ORDER BY o.created_ts DESC
                LIMIT ? OFFSET ?
                """,
                (status_filter, limit, offset),
            ).fetchall()
        else:
            return conn.execute(
                """
                SELECT o.*, p.title as product_title
                FROM orders o
                LEFT JOIN products p ON o.product_id = p.id
                ORDER BY o.created_ts DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()


def count_orders(status_filter: str | None = None) -> int:
    """Считает общее количество заказов (опционально по статусу)."""
    with get_conn() as conn:
        if status_filter:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM orders WHERE payment_status = ?",
                (status_filter,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as cnt FROM orders").fetchone()
        return int(row["cnt"]) if row else 0


def cancel_expired_orders() -> list[sqlite3.Row]:
    import time
    now = int(time.time())
    with get_conn() as conn:
        expired = conn.execute(
            """
            SELECT * FROM orders
            WHERE payment_status = 'pending'
              AND payment_deadline_ts < ?
            """,
            (now,),
        ).fetchall()
        if expired:
            conn.execute(
                """
                UPDATE orders SET payment_status = 'expired'
                WHERE payment_status = 'pending'
                  AND payment_deadline_ts < ?
                """,
                (now,),
            )
            conn.commit()
        return expired
