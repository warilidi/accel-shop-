from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.catalog_data import DEFAULT_CATALOG

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

    conn.commit()

    cur.execute("SELECT COUNT(*) as c FROM categories")
    if cur.fetchone()["c"] == 0:
        seed_catalog(conn, DEFAULT_CATALOG)

    conn.close()


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
) -> int:
    with get_conn() as conn:
        cur = conn.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
        category = cur.fetchone()
        if not category:
            conn.execute("INSERT INTO categories(name) VALUES(?)", (category_name,))
            category_id = conn.execute("SELECT last_insert_rowid() AS i").fetchone()["i"]
        else:
            category_id = category["id"]

        cur = conn.execute(
            "SELECT id FROM subcategories WHERE category_id = ? AND name = ?",
            (category_id, subcategory_name),
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

        conn.execute(
            """
            INSERT INTO products(subcategory_id, title, product_type, price_usd, stock)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sub_id, title, product_type, price_usd, stock),
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
