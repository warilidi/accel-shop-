"""Модуль для сбора и вывода статистики админ-панели."""

from typing import Dict, Any
from app.db import get_conn


def get_general_stats() -> Dict[str, Any]:
    """Получить общую статистику магазина."""
    with get_conn() as conn:
        # Общее количество заказов
        total_orders = conn.execute(
            "SELECT COUNT(*) as cnt FROM orders"
        ).fetchone()
        
        # Количество оплаченных заказов
        paid_orders = conn.execute(
            "SELECT COUNT(*) as cnt FROM orders WHERE payment_status = 'paid'"
        ).fetchone()
        
        # Общая выручка в USD и RUB
        revenue = conn.execute(
            "SELECT SUM(total_usd) as usd_sum, SUM(total_rub) as rub_sum "
            "FROM orders WHERE payment_status = 'paid'"
        ).fetchone()
        
        # Количество уникальных пользователей
        unique_users = conn.execute(
            "SELECT COUNT(DISTINCT tg_user_id) as cnt FROM orders"
        ).fetchone()
        
        # Количество в корзине (неоплаченные)
        pending_orders = conn.execute(
            "SELECT COUNT(*) as cnt FROM orders WHERE payment_status = 'pending'"
        ).fetchone()
        
        return {
            "total_orders": total_orders["cnt"] if total_orders else 0,
            "paid_orders": paid_orders["cnt"] if paid_orders else 0,
            "pending_orders": pending_orders["cnt"] if pending_orders else 0,
            "total_revenue_usd": revenue["usd_sum"] or 0.0,
            "total_revenue_rub": revenue["rub_sum"] or 0.0,
            "unique_users": unique_users["cnt"] if unique_users else 0,
        }


def get_product_stats() -> list[Dict[str, Any]]:
    """Получить статистику по товарам."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT 
                p.id,
                p.title,
                p.price_usd,
                p.stock,
                COUNT(o.id) as orders_count,
                SUM(o.qty) as total_qty_sold,
                SUM(CASE WHEN o.payment_status = 'paid' THEN o.total_usd ELSE 0 END) as revenue_usd
            FROM products p
            LEFT JOIN orders o ON p.id = o.product_id
            GROUP BY p.id
            ORDER BY orders_count DESC
            LIMIT 15
            """
        ).fetchall()
        
        return [dict(row) for row in rows]


def get_payment_method_stats() -> Dict[str, int]:
    """Получить статистику по методам оплаты."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT payment_method, COUNT(*) as cnt
            FROM orders
            WHERE payment_status = 'paid'
            GROUP BY payment_method
            """
        ).fetchall()
        
        return {row["payment_method"]: row["cnt"] for row in rows}


def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Получить статистику по конкретному пользователю."""
    with get_conn() as conn:
        orders = conn.execute(
            """
            SELECT COUNT(*) as cnt, SUM(total_usd) as total_usd
            FROM orders
            WHERE tg_user_id = ? AND payment_status = 'paid'
            """,
            (user_id,)
        ).fetchone()
        
        last_order = conn.execute(
            """
            SELECT * FROM orders
            WHERE tg_user_id = ?
            ORDER BY created_ts DESC
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()
        
        return {
            "orders_count": orders["cnt"] or 0,
            "total_spent": orders["total_usd"] or 0.0,
            "last_order": dict(last_order) if last_order else None,
        }


def get_recent_orders(limit: int = 10) -> list[Dict[str, Any]]:
    """Получить недавние заказы."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM orders
            ORDER BY created_ts DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        
        return [dict(row) for row in rows]


def get_low_stock_products(threshold: int = 5) -> list[Dict[str, Any]]:
    """Получить товары с низким остатком."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, price_usd, stock
            FROM products
            WHERE stock <= ?
            ORDER BY stock ASC
            """,
            (threshold,)
        ).fetchall()
        
        return [dict(row) for row in rows]
