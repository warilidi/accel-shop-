"""Расширенные админ-команды для панели управления."""

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode

from app.config import load_settings
from app.admin_stats import (
    get_general_stats,
    get_product_stats,
    get_payment_method_stats,
    get_user_stats,
    get_recent_orders,
    get_low_stock_products,
)
from app.db import get_product, get_order

settings = load_settings()
admin_router = Router()


def fmt(v: float) -> str:
    """Форматирует число."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


# ─── Статистика ─────────────────────────────────────────────────────

@admin_router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """Получить общую статистику магазина."""
    if message.from_user.id not in settings.admin_ids:
        return
    
    stats = get_general_stats()
    
    text = (
        "📊 <b>Статистика магазина</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n\n"
        
        "<b>📦 Заказы</b>\n"
        f"Всего: <b>{stats['total_orders']}</b> заказов\n"
        f"✅ Оплачено: <b>{stats['paid_orders']}</b> (${fmt(stats['total_revenue_usd'])})\n"
        f"⏳ Ожидание: <b>{stats['pending_orders']}</b>\n\n"
        
        "<b>💰 Выручка</b>\n"
        f"USD: ${fmt(stats['total_revenue_usd'])}\n"
        f"RUB: {fmt(stats['total_revenue_rub'])}₽\n\n"
        
        "<b>👥 Пользователи</b>\n"
        f"Уникальные: <b>{stats['unique_users']}</b>"
    )
    
    await message.answer(text)


@admin_router.message(Command("topproducts"))
async def cmd_topproducts(message: Message) -> None:
    """Показать топ товаров по продажам."""
    if message.from_user.id not in settings.admin_ids:
        return
    
    stats = get_product_stats()
    
    if not stats:
        await message.answer("📦 Нет данных о продажах.")
        return
    
    lines = ["🏆 <b>ТОП товаров по продажам</b>\n"]
    
    for i, product in enumerate(stats, 1):
        if product["orders_count"] == 0:
            continue
        lines.append(
            f"{i}. <b>{product['title']}</b>\n"
            f"   📊 Продано: {product['total_qty_sold']} шт. ({product['orders_count']} заказов)\n"
            f"   💰 Выручка: ${fmt(product['revenue_usd'] or 0)}\n"
            f"   📦 Остаток: {product['stock']} шт.\n"
        )
    
    await message.answer("\n".join(lines))


@admin_router.message(Command("lowstock"))
async def cmd_lowstock(message: Message) -> None:
    """Показать товары с низким остатком."""
    if message.from_user.id not in settings.admin_ids:
        return
    
    products = get_low_stock_products(threshold=5)
    
    if not products:
        await message.answer("✅ Все товары в наличии!")
        return
    
    lines = ["⚠️ <b>Товары с низким остатком</b>\n"]
    
    for product in products:
        status = "🔴" if product["stock"] == 0 else "🟡"
        lines.append(
            f"{status} <b>{product['title']}</b>\n"
            f"   🆔 ID: {product['id']}\n"
            f"   💰 Цена: ${fmt(product['price_usd'])}\n"
            f"   📦 Остаток: <b>{product['stock']} шт.</b>\n"
        )
    
    await message.answer("\n".join(lines))


@admin_router.message(Command("paymentmethods"))
async def cmd_paymentmethods(message: Message) -> None:
    """Показать статистику по методам оплаты."""
    if message.from_user.id not in settings.admin_ids:
        return
    
    stats = get_payment_method_stats()
    
    if not stats:
        await message.answer("📊 Нет данных о платежах.")
        return
    
    lines = ["💳 <b>Методы оплаты</b>\n"]
    
    method_names = {
        "balance": "💳 Баланс",
        "crypto_usdt": "💰 CryptoBot USDT",
        "crypto_ton": "💎 CryptoBot TON",
        "bybit": "🔶 Bybit",
    }
    
    for method, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        name = method_names.get(method, method)
        lines.append(f"{name}: <b>{count}</b> платежей")
    
    total = sum(stats.values())
    lines.append(f"\n<b>Всего:</b> {total} платежей")
    
    await message.answer("\n".join(lines))


@admin_router.message(Command("recentorders"))
async def cmd_recentorders(message: Message) -> None:
    """Показать последние заказы."""
    if message.from_user.id not in settings.admin_ids:
        return
    
    orders = get_recent_orders(limit=10)
    
    if not orders:
        await message.answer("📋 Нет заказов.")
        return
    
    lines = ["📋 <b>Последние 10 заказов</b>\n"]
    
    for order in orders:
        status_emoji = "✅" if order["payment_status"] == "paid" else "⏳"
        product = get_product(int(order["product_id"]))
        title = product["title"] if product else "—"
        
        lines.append(
            f"{status_emoji} <b>{order['order_code']}</b>\n"
            f"   👤 ID: {order['tg_user_id']}\n"
            f"   📦 Товар: {title}\n"
            f"   💰 Сумма: ${fmt(order['total_usd'])}\n"
        )
    
    await message.answer("\n".join(lines))


@admin_router.message(Command("userinfo"))
async def cmd_userinfo(message: Message) -> None:
    """Получить информацию о пользователе."""
    if message.from_user.id not in settings.admin_ids:
        return
    
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Формат: /userinfo <user_id>")
        return
    
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("user_id должен быть числом.")
        return
    
    stats = get_user_stats(user_id)
    
    text = (
        f"👤 <b>Информация о пользователе {user_id}</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖\n\n"
        f"🛍️ Заказов: <b>{stats['orders_count']}</b>\n"
        f"💰 Потрачено: <b>${fmt(stats['total_spent'])}</b>\n"
    )
    
    if stats["last_order"]:
        lo = stats["last_order"]
        text += (
            f"\n📦 <b>Последний заказ:</b>\n"
            f"Код: <code>{lo['order_code']}</code>\n"
            f"Сумма: ${fmt(lo['total_usd'])}\n"
        )
    
    await message.answer(text)


@admin_router.message(Command("searchorder"))
async def cmd_searchorder(message: Message) -> None:
    """Поиск заказа по коду или user_id."""
    if message.from_user.id not in settings.admin_ids:
        return
    
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Формат: /searchorder <код_заказа_или_user_id>")
        return
    
    query = parts[1].strip()
    
    # Пробуем как код заказа
    order = get_order(query)
    
    if order:
        product = get_product(int(order["product_id"]))
        title = product["title"] if product else "—"
        
        await message.answer(
            f"📋 <b>Заказ {order['order_code']}</b>\n\n"
            f"👤 User ID: <code>{order['tg_user_id']}</code>\n"
            f"📦 Товар: {title}\n"
            f"🔢 Кол-во: {order['qty']}\n"
            f"💰 Сумма: ${fmt(order['total_usd'])} / {fmt(order['total_rub'])}₽\n"
            f"💳 Метод: {order['payment_method']}\n"
            f"📌 Статус: {order['payment_status']}"
        )
    else:
        await message.answer(f"❌ Заказ <code>{query}</code> не найден.")
