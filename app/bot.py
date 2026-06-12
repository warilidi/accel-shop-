from __future__ import annotations

import asyncio
import logging
import os
import time
from random import randint

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
    TelegramObject,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.catalog_data import PRODUCT_TYPE_HINTS
from app.config import load_settings
from app.cryptobot import check_invoice_status, create_invoice
from app.db import (
    add_balance,
    add_custom_product,
    add_product_payload,
    adjust_stock,
    cancel_expired_orders,
    count_orders,
    create_order,
    get_all_orders,
    get_all_user_ids,
    get_button_text,
    get_conn,
    get_order,
    get_pending_crypto_orders,
    get_product,
    get_subcategory,
    get_user_balance,
    get_visual,
    init_db,
    list_all_buttons,
    list_categories,
    list_products,
    list_subcategories,
    list_visuals,
    mark_order_paid,
    pop_payloads,
    rename_category,
    rename_subcategory,
    replace_product_payloads,
    reset_all_buttons,
    reset_button_text,
    set_balance,
    set_button_text,
    set_order_invoice_id,
    set_order_payment_method,
    set_visual,
    update_product_content,
    withdraw_balance,
)

logger = logging.getLogger(__name__)

# ─── Инициализация ────────────────────────────────────────────────────────────

router = Router()
settings = load_settings()

# Подпись под каждым сообщением со стороны магазина
SHOP_FOOTER = "— 💎 Админ/Связь/Опт — @Dolzu"

# Картинки по умолчанию (можно переопределить через /setimage)
VISUALS: dict[str, str] = {}

# Все доступные ключи для картинок
VISUAL_KEYS = [
    "start", "categories", "rules",
    "chatgpt", "perplexity", "grok", "gemini", "cursor", "claude",
    "spotify", "windows", "discord", "apple", "amazon",
    "capcut", "picsart", "youtube", "gmail",
]

# Маппинг названия подкатегории → ключ картинки
SERVICE_IMAGE_MAP = {
    "chatgpt":     "chatgpt",
    "perplexity":  "perplexity",
    "grok":        "grok",
    "gemini":      "gemini",
    "cursor":      "cursor",
    "claude":      "claude",
    "suno ai":     "chatgpt",
    "spotify":     "spotify",
    "windows":     "windows",
    "discord":     "discord",
    "apple":       "apple",
    "amazon prime": "amazon",
    "capcut":      "capcut",
    "picsart":     "picsart",
    "youtube":     "youtube",
    "почты gmail": "gmail",
    "netflix":     "categories",
    "steam":       "categories",
}


# ─── FSM-состояния ─────────────────────────────────────────────────────────

class BuyFlow(StatesGroup):
    choose_qty = State()
    choose_payment_method = State()


class AdminFlow(StatesGroup):
    add_product_wait = State()
    broadcast_wait   = State()
    set_balance_wait = State()
    edit_product_wait = State()


# ─── Вспомогательные функции ───────────────────────────────────────────────

def fmt(v: float) -> str:
    """Форматирует число: убирает лишние нули, меняет точку на запятую."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def get_image(key: str) -> str:
    """Возвращает картинку из БД, иначе из дефолтного словаря."""
    return get_visual(key) or VISUALS.get(key, "")


def get_service_image(subcategory_name: str) -> str:
    """Возвращает картинку для конкретного сервиса по его названию."""
    key = SERVICE_IMAGE_MAP.get((subcategory_name or "").strip().lower(), "")
    return get_image(key) if key else ""


def normalize_link(value: str, fallback: str) -> str:
    """Превращает @username или t.me/... в полный https://t.me/... URL."""
    raw = (value or "").strip()
    if not raw:
        return fallback
    if raw.startswith("@"):
        return f"https://t.me/{raw[1:]}"
    if raw.startswith("t.me/"):
        return f"https://{raw}"
    if raw.startswith("http"):
        return raw
    return fallback


# ─── Клавиатуры ───────────────────────────────────────────────────────────

def main_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("catalog"),   callback_data="menu:catalog")
    kb.button(text=get_button_text("balance"),   callback_data="menu:balance")
    kb.button(text=get_button_text("wholesale"), url=normalize_link(settings.wholesale_link, "https://t.me/Dolzu"))
    kb.button(text=get_button_text("help"),      url=normalize_link(settings.help_link, "https://t.me/Dolzu"))
    kb.button(text=get_button_text("profile"),   callback_data="menu:profile")
    kb.button(text=get_button_text("rules"),     callback_data="menu:rules")
    kb.adjust(1, 1, 2, 2)
    return kb.as_markup()


def rules_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("agree"),
              url="https://telegra.ph/POLZOVATELSKOE-SOGLASHENIE-01-07-19")
    kb.button(text=get_button_text("privacy"),
              url="https://telegra.ph/Politika-konfidencialnosti-01-07-38")
    kb.button(text=get_button_text("back"), callback_data="go:main")
    kb.adjust(1)
    return kb.as_markup()


def categories_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cat in list_categories():
        kb.button(text=cat["name"], callback_data=f"cat:{cat['id']}")
    kb.button(text=get_button_text("back"), callback_data="go:main")
    kb.adjust(1)
    return kb.as_markup()


def subcategories_kb(category_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for sub in list_subcategories(category_id):
        kb.button(text=sub["name"], callback_data=f"sub:{sub['id']}")
    kb.button(text=get_button_text("back"), callback_data="menu:catalog")
    kb.adjust(1)
    return kb.as_markup()


def products_kb(subcategory_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in list_products(subcategory_id):
        icon  = "✅" if p["stock"] > 0 else "❌"
        title = p["title"]
        ptype = (p["product_type"] or "").strip()
        # Добавляем [тип] если его ещё нет в названии
        if ptype and not title.startswith("["):
            title = f"[{ptype}] {title}"
        kb.button(
            text=f"{icon} {title} — ${fmt(p['price_usd'])}",
            callback_data=f"prod:{p['id']}",
        )
    kb.button(text=get_button_text("back"), callback_data="go:cats")
    kb.adjust(1)
    return kb.as_markup()


def qty_kb(product_id: int, max_qty: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i in range(1, max_qty + 1):
        kb.button(text=str(i), callback_data=f"qty:{product_id}:{i}")
    kb.button(text=get_button_text("back"), callback_data=f"prod:{product_id}")
    kb.adjust(4)
    return kb.as_markup()


def pay_kb(order_code: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("crypto_usdt"), callback_data=f"pay:crypto_usdt:{order_code}")
    kb.button(text=get_button_text("crypto_ton"),  callback_data=f"pay:crypto_ton:{order_code}")
    kb.button(text=get_button_text("bybit"),       callback_data=f"pay:bybit:{order_code}")
    kb.button(text=get_button_text("balance_pay"), callback_data=f"pay:balance:{order_code}")
    kb.adjust(1)
    return kb.as_markup()


def balance_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("topup"),   callback_data="balance:topup")
    kb.button(text=get_button_text("history"), callback_data="balance:history")
    kb.button(text=get_button_text("back"),    callback_data="go:main")
    kb.adjust(1)
    return kb.as_markup()


# ─── Утилиты для отправки/редактирования ──────────────────────────────────────

async def send_with_photo(message: Message, text: str, kb: InlineKeyboardMarkup, photo: str) -> None:
    """Отправляет новое сообщение — с фото если есть, без если нет."""
    if photo:
        await message.answer_photo(photo=photo, caption=text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


async def safe_edit(callback: CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> None:
    """
    Редактирует сообщение независимо от того, есть в нём фото или нет.
    Если редактировать нельзя — удаляет старое и шлёт новое.
    """
    msg = callback.message
    if msg.photo or msg.video or msg.document:
        try:
            await msg.edit_caption(caption=text, reply_markup=kb)
        except Exception:
            try:
                await msg.delete()
            except Exception:
                pass
            await msg.answer(text, reply_markup=kb)
    else:
        try:
            await msg.edit_text(text, reply_markup=kb)
        except Exception:
            await msg.answer(text, reply_markup=kb)


# ─── Уведомления ──────────────────────────────────────────────────────────

async def notify_admin_about_payment(order_code: str) -> None:
    """Если настроен второй бот-нотификатор — шлёт ему уведомление об оплате."""
    if not settings.notify_bot_token or not settings.notify_chat_id:
        return
    order = get_order(order_code)
    if not order:
        return
    product = get_product(int(order["product_id"]))
    title = product["title"] if product else "—"
    text = (
        "💸 <b>Новая оплата!</b>\n"
        f"📋 Заказ: <code>{order['order_code']}</code>\n"
        f"👤 Пользователь: <code>{order['tg_user_id']}</code>\n"
        f"📦 Товар: {title}\n"
        f"🔢 Кол-во: {order['qty']} шт.\n"
        f"💰 Сумма: {fmt(order['total_usd'])}$ ({fmt(order['total_rub'])}₽)"
    )
    try:
        bot = Bot(token=settings.notify_bot_token,
                  default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        await bot.send_message(settings.notify_chat_id, text)
        await bot.session.close()
    except Exception:
        pass


async def _fulfill_order(bot: Bot, order_code: str) -> None:
    """Подтверждает оплату, выдаёт товар и уведомляет пользователя."""
    order = get_order(order_code)
    if not order or order["payment_status"] == "paid":
        return

    mark_order_paid(order_code)
    await notify_admin_about_payment(order_code)

    product       = get_product(int(order["product_id"]))
    payloads      = pop_payloads(int(order["product_id"]), int(order["qty"]))
    delivery_note = (product["delivery_text"] or "").strip() if product else ""
    extra         = f"\n\n📨 <b>Инструкция по активации:</b>\n{delivery_note}" if delivery_note else ""

    if not payloads:
        text = (
            "⏳ Оплата получена, спасибо!\n\n"
            "Товар временно закончился — администратор свяжется с вами в ближайшее время."
            f"{extra}\n\n{SHOP_FOOTER}"
        )
    else:
        items = "\n\n".join(f"{i + 1}) <code>{v}</code>" for i, v in enumerate(payloads))
        text  = (
            "✅ <b>Оплата подтверждена автоматически!</b>\n\n"
            f"Ваш товар:\n\n{items}"
            f"{extra}\n\n{SHOP_FOOTER}"
        )

    try:
        await bot.send_message(
            int(order["tg_user_id"]),
            text,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        logger.exception("Failed to send fulfillment message to user %s", order["tg_user_id"])


async def _payment_checker(bot: Bot) -> None:
    """Фоновая задача: периодически проверяет статус оплаты CryptoBot инвойсов."""
    if not settings.cryptobot_api_token:
        logger.info("CRYPTOBOT_API_TOKEN not set — auto-check disabled")
        return

    interval = settings.payment_check_interval
    logger.info("Payment checker started (interval=%ds)", interval)

    while True:
        await asyncio.sleep(interval)
        try:
            cancel_expired_orders()

            pending = get_pending_crypto_orders()
            if not pending:
                continue

            for order in pending:
                invoice_id = int(order["invoice_id"])
                try:
                    status = await check_invoice_status(
                        settings.cryptobot_api_token, invoice_id
                    )
                except Exception:
                    logger.exception("Error checking invoice %d", invoice_id)
                    continue

                if status == "paid":
                    logger.info(
                        "Invoice %d paid — fulfilling order %s",
                        invoice_id,
                        order["order_code"],
                    )
                    await _fulfill_order(bot, order["order_code"])
        except Exception:
            logger.exception("Payment checker iteration error")


# ─── Команды бота (меню) ──────────────────────────────────────────────────

async def setup_commands(bot: Bot) -> None:
    # Для всех пользователей — только /start
    await bot.set_my_commands(
        commands=[BotCommand(command="start", description="Запустить бота")],
        scope=BotCommandScopeAllPrivateChats(),
    )
    # Для каждого админа — полный список команд
    admin_cmds = [
        BotCommand(command="admin",       description="Список всех команд"),
        BotCommand(command="additem",     description="Добавить товар"),
        BotCommand(command="editproduct", description="Редактировать товар"),
        BotCommand(command="addpayload",  description="Добавить 1 единицу выдачи"),
        BotCommand(command="setpayloads", description="Заменить всю выдачу"),
        BotCommand(command="setname",     description="Переименовать товар"),
        BotCommand(command="setdesc",     description="Изменить описание товара"),
        BotCommand(command="setdelivery", description="Текст инструкции после оплаты"),
        BotCommand(command="setstock",    description="Установить остаток"),
        BotCommand(command="setimage",    description="Установить картинку экрана"),
        BotCommand(command="images",      description="Статус всех картинок"),
        BotCommand(command="getfileid",   description="Получить file_id фото"),
        BotCommand(command="order",       description="Проверить заказ по коду"),
        BotCommand(command="orders",      description="Все заказы с фильтрами"),
        BotCommand(command="broadcast",   description="Рассылка всем покупателям"),
        BotCommand(command="setbalance",  description="Установить баланс пользователю"),
        BotCommand(command="setbutton",   description="Изменить текст кнопки"),
        BotCommand(command="buttons",     description="Список всех кнопок"),
        BotCommand(command="resetbutton", description="Вернуть кнопку к стандарту"),
        BotCommand(command="resetallbuttons", description="Вернуть все кнопки"),
        BotCommand(command="setcategory", description="Переименовать категорию"),
        BotCommand(command="setsubcategory", description="Переименовать подкатегорию"),
    ]
    for admin_id in settings.admin_ids:
        try:
            await bot.set_my_commands(
                commands=admin_cmds,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except Exception:
            pass


# ─── Проверка подписки на канал ────────────────────────────────────────────

# Канал всегда обязателен — задан жёстко
REQUIRED_CHANNEL_USERNAME = "accel_shop"
REQUIRED_CHANNEL_ID       = "@accel_shop"  # строка работает в get_chat_member


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    """Проверяет, подписан ли пользователь на канал @accel_shop."""
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL_ID, user_id=user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception:
        return True  # если бот не может проверить (не добавлен в канал) — пропускаем


def subscribe_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text="📢 Подписаться на канал",
        url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}",
    )
    kb.button(text="✅ Я подписался", callback_data="check_subscription")
    kb.adjust(1)
    return kb.as_markup()


async def require_subscription(bot: Bot, user_id: int, callback: CallbackQuery | None = None) -> bool:
    """
    Проверяет подписку. Если не подписан — показывает заглушку и возвращает False.
    Используй: if not await require_subscription(bot, uid, callback): return
    """
    if await is_subscribed(bot, user_id):
        return True
    text = (
        "🔒 <b>Доступ закрыт</b>\n\n"
        "Для использования магазина необходимо подписаться на наш канал:"
    )
    if callback:
        try:
            await callback.message.answer(text, reply_markup=subscribe_kb())
        except Exception:
            pass
        await callback.answer("Подпишитесь на канал!", show_alert=True)
    return False


# ─── /start ───────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    if not await is_subscribed(bot, user_id):
        await message.answer(
            "👋 Добро пожаловать в <b>Accel Shop</b>!\n\n"
            "Для пользования ботом подпишитесь на наш информационный канал:",
            reply_markup=subscribe_kb(),
        )
        return

    text = (
        "👋 Приветствую в <b>Accel Shop</b>!\n\n"
        "🏪 Это цифровой магазин подписок на нейросети и популярные сервисы.\n"
        "Здесь аккаунты, подписки, сертификаты и многое другое!\n\n"
        "👇 Нажмите кнопку ниже чтобы начать.\n\n"
        "Информационный канал: @Accel_Shop"
    )
    await send_with_photo(message, text, main_kb(), get_image("start"))


@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery, bot: Bot) -> None:
    user_id = callback.from_user.id
    if not await is_subscribed(bot, user_id):
        await callback.answer(
            "❌ Вы ещё не подписались на канал. Подпишитесь и нажмите кнопку снова.",
            show_alert=True,
        )
        return

    await callback.answer("✅ Отлично! Добро пожаловать!")
    text = (
        "👋 Приветствую в <b>Accel Shop</b>!\n\n"
        "🏪 Это цифровой магазин подписок на нейросети и популярные сервисы.\n"
        "Здесь аккаунты, подписки, сертификаты и многое другое!\n\n"
        "👇 Нажмите кнопку ниже чтобы начать.\n\n"
        "Информационный канал: @Accel_Shop"
    )
    photo = get_image("start")
    if photo:
        await callback.message.answer_photo(photo=photo, caption=text, reply_markup=main_kb())
    else:
        await callback.message.answer(text, reply_markup=main_kb())


# ─── Навигация главного меню ──────────────────────────────────────────────

@router.callback_query(F.data == "go:main")
async def cb_go_main(callback: CallbackQuery) -> None:
    await safe_edit(callback, "🏠 Главное меню:", main_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:catalog")
async def cb_catalog(callback: CallbackQuery, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    text  = "🛍️ <b>Товары и услуги</b>\nВыберите раздел:"
    photo = get_image("categories")
    if photo:
        await callback.message.answer_photo(photo=photo, caption=text, reply_markup=categories_kb())
    else:
        await safe_edit(callback, text, categories_kb())
    await callback.answer()


@router.callback_query(F.data == "go:cats")
async def cb_go_cats(callback: CallbackQuery, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    await safe_edit(callback, "📂 Выберите раздел:", categories_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:balance")
async def cb_balance(callback: CallbackQuery, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    uid = callback.from_user.id
    balance_usd, balance_rub = get_user_balance(uid)
    text = (
        "💳 <b>Ваш баланс</b>\n"
        f"💰 {fmt(balance_usd)} $ / {fmt(balance_rub)} ₽\n\n"
        "Используйте баланс для быстрых покупок без повторной оплаты."
    )
    await safe_edit(callback, text, balance_kb())
    await callback.answer()


@router.callback_query(F.data == "balance:topup")
async def cb_balance_topup(callback: CallbackQuery, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    text = (
        "💳 <b>Пополнение баланса</b>\n\n"
        "Свяжитесь с администратором для пополнения баланса:\n"
        "@Dolzu\n\n"
        "Укажите желаемую сумму."
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Написать админу", url="https://t.me/Dolzu")
    kb.button(text=get_button_text("back"), callback_data="menu:balance")
    kb.adjust(1)
    await safe_edit(callback, text, kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "balance:history")
async def cb_balance_history(callback: CallbackQuery, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    uid = callback.from_user.id
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT total_usd, total_rub, payment_status, created_ts FROM orders WHERE tg_user_id = ? ORDER BY created_ts DESC LIMIT 10",
            (uid,),
        ).fetchall()
    if not rows:
        text = "📜 <b>История заказов</b>\n\nНет заказов."
    else:
        lines = ["📜 <b>Последние 10 заказов:</b>\n"]
        for row in rows:
            status = "✅ Оплачено" if row["payment_status"] == "paid" else "⏳ Ожидание"
            lines.append(f"{fmt(row['total_usd'])}$ — {status}")
        text = "\n".join(lines)
    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("back"), callback_data="menu:balance")
    await safe_edit(callback, text, kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "menu:rules")
async def cb_rules(callback: CallbackQuery, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    text = (
        "📚 <b>Правила и соглашения</b>\n\n"
        "Перед использованием магазина ознакомьтесь с документами:"
    )
    photo = get_image("rules")
    if photo:
        await callback.message.answer_photo(photo=photo, caption=text, reply_markup=rules_kb())
    else:
        await callback.message.answer(text, reply_markup=rules_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:profile")
async def cb_profile(callback: CallbackQuery, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    uid       = callback.from_user.id
    username  = callback.from_user.username
    full_name = callback.from_user.full_name or "—"

    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt, SUM(total_usd) as total "
            "FROM orders WHERE tg_user_id = ? AND payment_status = 'paid'",
            (uid,),
        ).fetchone()

    orders_count = int(row["cnt"])   if row and row["cnt"]   else 0
    total_spent  = float(row["total"]) if row and row["total"] else 0.0
    balance_usd, balance_rub = get_user_balance(uid)

    text = (
        "👤 <b>Ваш профиль</b>\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"👤 Имя: {full_name}\n"
        f"📧 Username: {'@' + username if username else 'не указан'}\n\n"
        f"🛍️ Заказов выполнено: <b>{orders_count}</b>\n"
        f"💰 Потрачено: <b>${fmt(total_spent)}</b>\n"
        f"💳 На балансе: <b>${fmt(balance_usd)}</b> / <b>{fmt(balance_rub)}₽</b>"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("back"), callback_data="go:main")
    await safe_edit(callback, text, kb.as_markup())
    await callback.answer()


# ─── Каталог ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cat:"))
async def cb_category(callback: CallbackQuery, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    cat_id = int(callback.data.split(":")[1])
    await safe_edit(callback, "📂 Выберите сервис:", subcategories_kb(cat_id))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:"))
async def cb_subcategory(callback: CallbackQuery, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    sub_id  = int(callback.data.split(":")[1])
    sub     = get_subcategory(sub_id)
    name    = sub["name"] if sub else ""
    photo   = get_service_image(name)
    text    = f"🧾 <b>{name}</b>\nВыберите товар:" if name else "🧾 Выберите товар:"

    if photo:
        await callback.message.answer_photo(photo=photo, caption=text, reply_markup=products_kb(sub_id))
    else:
        await safe_edit(callback, text, products_kb(sub_id))
    await callback.answer()


@router.callback_query(F.data.startswith("prod:"))
async def cb_product(callback: CallbackQuery, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    product_id = int(callback.data.split(":")[1])
    product    = get_product(product_id)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    ptype  = (product["product_type"] or "").strip()
    hint   = PRODUCT_TYPE_HINTS.get(ptype, "Уточняйте у администратора.")
    status = "✅ В наличии" if product["stock"] > 0 else "❌ Нет в наличии"
    desc   = (product["description"] or "").strip()

    text = (
        f"📦 <b>{product['title']}</b>\n"
        + (f"📝 {desc}\n" if desc else "")
        + f"\n💰 Цена: <b>${fmt(product['price_usd'])}</b>\n"
        f"📊 Остаток: {product['stock']} шт.\n"
        f"🧩 Тип: {ptype or 'не указан'}\n"
        f"ℹ️ {hint}\n"
        f"📌 {status}\n\n"
        f"{SHOP_FOOTER}"
    )

    kb = InlineKeyboardBuilder()
    if product["stock"] > 0:
        kb.button(text=get_button_text("buy"), callback_data=f"buy:{product_id}")
    kb.button(text=get_button_text("back"), callback_data=f"sub:{product['subcategory_id']}")
    kb.adjust(1)

    await safe_edit(callback, text, kb.as_markup())
    await callback.answer()


# ─── Покупка ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    product_id = int(callback.data.split(":")[1])
    product    = get_product(product_id)

    if not product or product["stock"] <= 0:
        await callback.answer("К сожалению, товара нет в наличии", show_alert=True)
        return

    max_qty = min(product["stock"], 12)
    await state.set_state(BuyFlow.choose_qty)
    await state.update_data(product_id=product_id)
    await safe_edit(callback, f"🔢 Выберите количество (1–{max_qty}):", qty_kb(product_id, max_qty))
    await callback.answer()


@router.callback_query(F.data.startswith("qty:"))
async def cb_qty(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    _, pid_s, qty_s = callback.data.split(":")
    product_id = int(pid_s)
    qty        = int(qty_s)
    product    = get_product(product_id)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return
    if qty > product["stock"]:
        await callback.answer("Недостаточно товара на складе", show_alert=True)
        return

    price     = float(product["price_usd"])
    total_usd = round(qty * price, 2)
    total_rub = round(total_usd * settings.rub_per_usd, 2)
    code      = str(randint(10_000_000, 99_999_999))
    now       = int(time.time())

    create_order(
        order_code=code,
        tg_user_id=callback.from_user.id,
        product_id=product_id,
        qty=qty,
        price_usd=price,
        total_usd=total_usd,
        total_rub=total_rub,
        payment_method="pending",
        payment_deadline_ts=now + 15 * 60,
        created_ts=now,
    )

    text = (
        "💸 <b>Оформление заказа</b>\n"
        "➖➖➖➖➖➖➖➖➖\n"
        f"📦 Товар: {product['title']}\n"
        f"🔢 Кол-во: {qty} шт.\n"
        f"💰 Цена за шт.: {fmt(price)} $\n"
        f"💵 Итого: {fmt(total_usd)} $ / {fmt(total_rub)} ₽\n"
        f"🔖 Код заказа: <code>{code}</code>\n"
        "➖➖➖➖➖➖➖➖➖\n"
        "Выберите способ оплаты:"
    )
    await safe_edit(callback, text, pay_kb(code))
    await callback.answer()


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(callback: CallbackQuery, bot: Bot) -> None:
    if not await require_subscription(bot, callback.from_user.id, callback):
        return
    _, method, code = callback.data.split(":")
    order   = get_order(code)
    product = get_product(int(order["product_id"])) if order else None

    if not order or not product:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    if method == "balance":
        uid = callback.from_user.id
        balance_usd, balance_rub = get_user_balance(uid)
        total_usd = float(order["total_usd"])
        total_rub = float(order["total_rub"])
        
        if balance_usd < total_usd:
            await callback.answer(
                f"Недостаточно средств на балансе.\n"
                f"Требуется: ${fmt(total_usd)}, у вас: ${fmt(balance_usd)}",
                show_alert=True
            )
            return
        
        if not withdraw_balance(uid, total_usd, total_rub):
            await callback.answer("Ошибка при снятии средств с баланса", show_alert=True)
            return
        
        from app.db import mark_order_paid
        mark_order_paid(code)
        await notify_admin_about_payment(code)
        
        payloads      = pop_payloads(int(order["product_id"]), int(order["qty"]))
        delivery_note = (product["delivery_text"] or "").strip() if product else ""
        extra         = f"\n\n📨 <b>Инструкция по активации:</b>\n{delivery_note}" if delivery_note else ""
        
        if not payloads:
            text = (
                "⏳ Оплата получена, спасибо!\n\n"
                "Товар временно закончился — администратор свяжется с вами в ближайшее время."
                f"{extra}\n\n{SHOP_FOOTER}"
            )
        else:
            items = "\n\n".join(f"{i + 1}) <code>{v}</code>" for i, v in enumerate(payloads))
            text  = (
                "✅ <b>Оплата подтверждена!</b>\n\n"
                f"Ваш товар:\n\n{items}"
                f"{extra}\n\n{SHOP_FOOTER}"
            )
        
        await safe_edit(callback, text, InlineKeyboardBuilder().as_markup())
        await callback.answer("Спасибо за покупку! 🎉")
        return

    extra_pct = settings.cryptobot_invoice_add_percent

    if method in ("crypto_usdt", "crypto_ton"):
        asset = "USDT" if method == "crypto_usdt" else "TON"
        total_usd = round(float(order["total_usd"]) * (1 + extra_pct / 100), 2)

        set_order_payment_method(code, method)

        if settings.cryptobot_api_token:
            try:
                invoice = await create_invoice(
                    token=settings.cryptobot_api_token,
                    asset=asset,
                    amount=total_usd,
                    description=f"Заказ {code}: {product['title']} x{order['qty']}",
                    expires_in=900,
                )
                set_order_invoice_id(code, invoice.invoice_id)
                pay_link = invoice.bot_invoice_url

                text = (
                    "💳 <b>Оплата через CryptoBot</b>\n"
                    "➖➖➖➖➖➖➖➖➖\n"
                    f"📦 Товар: {product['title']}\n"
                    f"🔢 Кол-во: {order['qty']} шт.\n"
                    f"💵 Сумма: {fmt(total_usd)} $ (+{extra_pct}% комиссия)\n"
                    f"🔖 Код заказа: <code>{order['order_code']}</code>\n"
                    "➖➖➖➖➖➖➖➖➖\n"
                    f"Перейдите для оплаты:\n{pay_link}\n\n"
                    "⏰ Время на оплату: 15 минут\n"
                    "🔄 Оплата будет подтверждена автоматически."
                )
                kb = InlineKeyboardBuilder()
                kb.button(text="💳 Оплатить", url=pay_link)
                kb.button(text="🔄 Проверить оплату", callback_data=f"check:{code}")
                kb.adjust(1)
                await safe_edit(callback, text, kb.as_markup())
                await callback.answer()
                return
            except Exception:
                logger.exception("Failed to create CryptoBot invoice for order %s", code)

        pay_link = f"https://t.me/CryptoBot?start=invoice-{code}-{asset}"
        total_rub = round(float(order["total_rub"]) * (1 + extra_pct / 100), 2)
        text = (
            "💳 <b>Оплата через CryptoBot</b>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            f"📦 Товар: {product['title']}\n"
            f"🔢 Кол-во: {order['qty']} шт.\n"
            f"💵 Сумма: {fmt(total_rub)} ₽ (+{extra_pct}% комиссия)\n"
            f"🔖 Код заказа: <code>{order['order_code']}</code>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            f"Перейдите для оплаты:\n{pay_link}\n\n"
            "⏰ Время на оплату: 15 минут"
        )
    else:
        set_order_payment_method(code, "bybit")
        text = (
            "🔶 <b>Оплата через Bybit</b>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            f"📦 Товар: {product['title']}\n"
            f"🔢 Кол-во: {order['qty']} шт.\n"
            f"💵 Сумма: {fmt(order['total_rub'])} ₽\n"
            f"🔖 Код заказа: <code>{order['order_code']}</code>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            f"Переведите на Bybit UID: <code>{settings.bybit_uid}</code>\n\n"
            "⏰ Время на оплату: 15 минут"
        )

    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("confirm_paid"), callback_data=f"paid:{code}")
    await safe_edit(callback, text, kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("check:"))
async def cb_check_payment(callback: CallbackQuery) -> None:
    code = callback.data.split(":")[1]
    order = get_order(code)

    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    if order["payment_status"] == "paid":
        await callback.answer("Заказ уже оплачен!", show_alert=True)
        return

    if not settings.cryptobot_api_token or order["invoice_id"] == 0:
        await callback.answer("Автоматическая проверка недоступна", show_alert=True)
        return

    try:
        status = await check_invoice_status(
            settings.cryptobot_api_token, int(order["invoice_id"])
        )
    except Exception:
        logger.exception("Failed to check invoice %s", order["invoice_id"])
        await callback.answer("Ошибка проверки. Попробуйте позже.", show_alert=True)
        return

    if status == "paid":
        bot_instance = callback.bot
        await _fulfill_order(bot_instance, code)
        await callback.answer("Оплата подтверждена! 🎉", show_alert=True)
    elif status == "expired":
        await callback.answer(
            "Инвойс истёк. Создайте новый заказ.", show_alert=True
        )
    else:
        await callback.answer(
            "Оплата ещё не получена. Попробуйте позже.", show_alert=True
        )


@router.callback_query(F.data.startswith("paid:"))
async def cb_paid(callback: CallbackQuery) -> None:
    code  = callback.data.split(":")[1]
    order = get_order(code)

    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    if order["payment_status"] == "paid":
        await callback.answer("Заказ уже оплачен!", show_alert=True)
        return

    mark_order_paid(code)
    await notify_admin_about_payment(code)

    product       = get_product(int(order["product_id"]))
    payloads      = pop_payloads(int(order["product_id"]), int(order["qty"]))
    delivery_note = (product["delivery_text"] or "").strip() if product else ""
    extra         = f"\n\n📨 <b>Инструкция по активации:</b>\n{delivery_note}" if delivery_note else ""

    if not payloads:
        text = (
            "⏳ Оплата получена, спасибо!\n\n"
            "Товар временно закончился — администратор свяжется с вами в ближайшее время."
            f"{extra}\n\n{SHOP_FOOTER}"
        )
    else:
        items = "\n\n".join(f"{i + 1}) <code>{v}</code>" for i, v in enumerate(payloads))
        text  = (
            "✅ <b>Оплата подтверждена!</b>\n\n"
            f"Ваш товар:\n\n{items}"
            f"{extra}\n\n{SHOP_FOOTER}"
        )

    await safe_edit(callback, text, InlineKeyboardBuilder().as_markup())
    await callback.answer("Спасибо за покупку! 🎉")


# ─── Получение file_id фото ───────────────────────────────────────────────

@router.message(Command("getfileid"))
async def cmd_getfileid(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    await message.answer(
        "📸 Отправьте фото следующим сообщением — я верну его <code>file_id</code>.\n"
        "Затем используйте: <code>/setimage ключ file_id</code>"
    )


@router.message(F.photo)
async def handle_photo(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    file_id = message.photo[-1].file_id
    await message.answer(
        f"📋 <b>file_id:</b>\n<code>{file_id}</code>\n\n"
        f"Пример: <code>/setimage start {file_id}</code>\n\n"
        f"Ключи: <code>{', '.join(VISUAL_KEYS)}</code>"
    )


# ─── Картинки ──────────────────────────────────────────────────────────

@router.message(Command("setimage"))
async def cmd_setimage(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) != 3:
        await message.answer(f"Формат: /setimage <ключ> <file_id>\nКлючи: {', '.join(VISUAL_KEYS)}")
        return
    key, value = parts[1].lower(), parts[2].strip()
    if key not in VISUAL_KEYS:
        await message.answer(f"Неизвестный ключ. Доступные: {', '.join(VISUAL_KEYS)}")
        return
    set_visual(key, value)
    await message.answer(f"✅ Картинка для <b>{key}</b> обновлена.")


@router.message(Command("images"))
async def cmd_images(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    saved = {r["key"]: r["value"] for r in list_visuals()}
    lines = []
    for key in VISUAL_KEYS:
        has = bool(saved.get(key) or VISUALS.get(key))
        lines.append(f"{'✅' if has else '❌'} {key}")
    await message.answer("🖼 <b>Картинки:</b>\n" + "\n".join(lines))


# ─── Управление товарами ──────────────────────────────────────────────

@router.message(Command("additem"))
async def cmd_additem(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    await state.set_state(AdminFlow.add_product_wait)
    await message.answer(
        "📦 Введите данные товара в формате:\n"
        "<code>Категория | Подкатегория | Название | Цена$ | Тип | Остаток</code>\n\n"
        "Пример:\n"
        "<code>Другие сервисы | Telegram | Telegram Premium 3m | 7.5 | ACC | 5</code>"
    )


@router.message(AdminFlow.add_product_wait)
async def state_add_product(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = [p.strip() for p in (message.text or "").split("|")]
    if len(parts) != 6:
        await message.answer("Неверный формат. Нужно ровно 6 полей через |")
        return
    category, subcategory, title, price_s, ptype, stock_s = parts
    try:
        price = float(price_s.replace(",", "."))
        stock = int(stock_s)
    except ValueError:
        await message.answer("Цена и остаток должны быть числами.")
        return
    pid = add_custom_product(category, subcategory, title, price, ptype, stock)
    await state.clear()
    await message.answer(f"✅ Товар добавлен.\n🆔 product_id = <code>{pid}</code>")


@router.message(Command("editproduct"))
async def cmd_editproduct(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    await state.set_state(AdminFlow.edit_product_wait)
    await message.answer(
        "✏️ Редактирование товара\n\n"
        "Введите данные в формате:\n"
        "<code>product_id | название | описание | цена | тип | остаток</code>\n\n"
        "Пример:\n"
        "<code>1 | Telegram Premium | 3 месяца доступа | 7.5 | ACC | 5</code>"
    )


@router.message(AdminFlow.edit_product_wait)
async def state_editproduct(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = [p.strip() for p in (message.text or "").split("|")]
    if len(parts) != 6:
        await message.answer("Неверный формат. Нужно ровно 6 полей через |")
        return
    
    try:
        pid = int(parts[0])
        title = parts[1]
        desc = parts[2]
        price = float(parts[3].replace(",", "."))
        ptype = parts[4]
        stock = int(parts[5])
    except ValueError:
        await message.answer("Неверный формат данных. Проверьте числовые поля.")
        return
    
    product = get_product(pid)
    if not product:
        await message.answer("❌ Товар не найден.")
        return
    
    # Обновляем название, описание, тип
    update_product_content(pid, title=title, description=desc)
    
    # Обновляем цену и остаток через UPDATE
    with get_conn() as conn:
        conn.execute(
            "UPDATE products SET price_usd = ?, product_type = ? WHERE id = ?",
            (price, ptype, pid),
        )
        conn.commit()
    
    # Обновляем остаток
    current_stock = int(product["stock"])
    delta = stock - current_stock
    adjust_stock(pid, delta)
    
    await state.clear()
    await message.answer(
        f"✅ Товар обновлен!\n"
        f"🆔 ID: {pid}\n"
        f"📝 Название: {title}\n"
        f"💰 Цена: ${fmt(price)}\n"
        f"📊 Остаток: {stock} шт."
    )


@router.message(Command("addpayload"))
async def cmd_addpayload(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    rest = (message.text or "").replace("/addpayload", "", 1).strip()
    if "|" not in rest:
        await message.answer("Формат: /addpayload <product_id> | <данные>")
        return
    pid_s, payload = [x.strip() for x in rest.split("|", 1)]
    try:
        pid = int(pid_s)
    except ValueError:
        await message.answer("product_id должен быть числом.")
        return
    ok = add_product_payload(pid, payload)
    await message.answer("✅ Единица выдачи добавлена." if ok else "❌ Товар не найден.")


@router.message(Command("setpayloads"))
async def cmd_setpayloads(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    rest = (message.text or "").replace("/setpayloads", "", 1).strip()
    if "|" not in rest:
        await message.answer("Формат: /setpayloads <product_id> | строка1 ; строка2 ; строка3")
        return
    pid_s, blob = [x.strip() for x in rest.split("|", 1)]
    try:
        pid = int(pid_s)
    except ValueError:
        await message.answer("product_id должен быть числом.")
        return
    items = [x.strip() for x in blob.split(";") if x.strip()]
    ok    = replace_product_payloads(pid, items)
    await message.answer(f"✅ Выдача заменена. Записей: {len(items)}" if ok else "❌ Товар не найден.")


@router.message(Command("setstock"))
async def cmd_setstock(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: /setstock <product_id> <количество>")
        return
    try:
        pid, qty = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("product_id и количество должны быть числами.")
        return
    product = get_product(pid)
    if not product:
        await message.answer("❌ Товар не найден.")
        return
    delta = qty - int(product["stock"])
    ok    = adjust_stock(pid, delta)
    await message.answer(f"✅ Остаток установлен: {qty} шт." if ok else "❌ Ошибка обновления.")


@router.message(Command("setname"))
async def cmd_setname(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    rest = (message.text or "").replace("/setname", "", 1).strip()
    if "|" not in rest:
        await message.answer("Формат: /setname <product_id> | <новое название>")
        return
    pid_s, title = [x.strip() for x in rest.split("|", 1)]
    try:
        pid = int(pid_s)
    except ValueError:
        await message.answer("product_id должен быть числом.")
        return
    ok = update_product_content(pid, title=title)
    await message.answer("✅ Название обновлено." if ok else "❌ Товар не найден.")


@router.message(Command("setdesc"))
async def cmd_setdesc(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    rest = (message.text or "").replace("/setdesc", "", 1).strip()
    if "|" not in rest:
        await message.answer("Формат: /setdesc <product_id> | <описание>")
        return
    pid_s, desc = [x.strip() for x in rest.split("|", 1)]
    try:
        pid = int(pid_s)
    except ValueError:
        await message.answer("product_id должен быть числом.")
        return
    ok = update_product_content(pid, description=desc)
    await message.answer("✅ Описание обновлено." if ok else "❌ Товар не найден.")


@router.message(Command("setdelivery"))
async def cmd_setdelivery(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    rest = (message.text or "").replace("/setdelivery", "", 1).strip()
    if "|" not in rest:
        await message.answer("Формат: /setdelivery <product_id> | <инструкция после оплаты>")
        return
    pid_s, delivery = [x.strip() for x in rest.split("|", 1)]
    try:
        pid = int(pid_s)
    except ValueError:
        await message.answer("product_id должен быть числом.")
        return
    ok = update_product_content(pid, delivery_text=delivery)
    await message.answer("✅ Инструкция по выдаче обновлена." if ok else "❌ Товар не найден.")


# ─── Заказы ───────────────────────────────────────────────────────────

@router.message(Command("order"))
async def cmd_order(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Формат: /order <код заказа>")
        return
    order = get_order(parts[1].strip())
    if not order:
        await message.answer("❌ Заказ не найден.")
        return
    product = get_product(int(order["product_id"]))
    title   = product["title"] if product else "—"
    await message.answer(
        f"📋 <b>Заказ {order['order_code']}</b>\n\n"
        f"📦 Товар: {title}\n"
        f"🔢 Кол-во: {order['qty']} шт.\n"
        f"💰 Сумма: {fmt(order['total_usd'])}$ / {fmt(order['total_rub'])}₽\n"
        f"💳 Метод: {order['payment_method']}\n"
        f"📌 Статус: {order['payment_status']}\n"
        f"👤 User ID: <code>{order['tg_user_id']}</code>"
    )


# ─── Управление балансом ──────────────────────────────────────────────

@router.message(Command("setbalance"))
async def cmd_setbalance(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    await state.set_state(AdminFlow.set_balance_wait)
    await message.answer(
        "💳 Установить баланс пользователю\n\n"
        "Формат: <code>user_id | сумма_usd</code>\n\n"
        "Пример: <code>123456789 | 50.50</code>"
    )


@router.message(AdminFlow.set_balance_wait)
async def state_set_balance(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = [p.strip() for p in (message.text or "").split("|")]
    if len(parts) != 2:
        await message.answer("Неверный формат. Нужно: user_id | сумма_usd")
        return
    try:
        uid = int(parts[0])
        amount_usd = float(parts[1].replace(",", "."))
    except ValueError:
        await message.answer("user_id должен быть числом, сумма — числом.")
        return
    
    amount_rub = round(amount_usd * settings.rub_per_usd, 2)
    set_balance(uid, amount_usd, amount_rub)
    await state.clear()
    await message.answer(f"✅ Баланс установлен.\n👤 User: {uid}\n💰 Баланс: ${fmt(amount_usd)} / {fmt(amount_rub)}₽")


# ─── Управление кнопками ──────────────────────────────────────────────

@router.message(Command("setbutton"))
async def cmd_setbutton(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    rest = (message.text or "").replace("/setbutton", "", 1).strip()
    if "|" not in rest:
        await message.answer("Формат: /setbutton <button_id> | <новый текст>")
        return
    bid, text = [x.strip() for x in rest.split("|", 1)]
    
    all_buttons = list_all_buttons()
    if bid not in all_buttons:
        available = ", ".join(all_buttons.keys())
        await message.answer(f"❌ Неизвестная кнопка. Доступные: {available}")
        return
    
    set_button_text(bid, text)
    await message.answer(f"✅ Кнопка <b>{bid}</b> обновлена на <b>{text}</b>")


@router.message(Command("buttons"))
async def cmd_buttons(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    all_buttons = list_all_buttons()
    lines = ["🔘 <b>Все доступные кнопки:</b>\n"]
    for bid, btext in sorted(all_buttons.items()):
        lines.append(f"<code>{bid}</code> → {btext}")
    await message.answer("\n".join(lines))


@router.message(Command("resetbutton"))
async def cmd_resetbutton(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Формат: /resetbutton <button_id>")
        return
    bid = parts[1].strip()
    
    all_buttons = list_all_buttons()
    if bid not in all_buttons:
        await message.answer(f"❌ Неизвестная кнопка: {bid}")
        return
    
    reset_button_text(bid)
    await message.answer(f"✅ Кнопка <b>{bid}</b> вернена к стандарту")


@router.message(Command("resetallbuttons"))
async def cmd_resetallbuttons(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    reset_all_buttons()
    await message.answer("✅ Все кнопки вернены к стандартам")


# ─── Переименование категорий / подкатегорий ──────────────────────────────

@router.message(Command("setcategory"))
async def cmd_setcategory(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    rest = (message.text or "").replace("/setcategory", "", 1).strip()
    if "|" not in rest:
        cats = list_categories()
        lines = ["Формат: /setcategory <id> | <новое название>\n\n📂 Текущие категории:"]
        for cat in cats:
            lines.append(f"  <code>{cat['id']}</code> — {cat['name']}")
        await message.answer("\n".join(lines))
        return
    cid_s, new_name = [x.strip() for x in rest.split("|", 1)]
    try:
        cid = int(cid_s)
    except ValueError:
        await message.answer("ID категории должен быть числом.")
        return
    ok = rename_category(cid, new_name)
    await message.answer(f"✅ Категория переименована в <b>{new_name}</b>" if ok else "❌ Категория не найдена.")


@router.message(Command("setsubcategory"))
async def cmd_setsubcategory(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    rest = (message.text or "").replace("/setsubcategory", "", 1).strip()
    if "|" not in rest:
        cats = list_categories()
        lines = ["Формат: /setsubcategory <id> | <новое название>\n\n📂 Текущие подкатегории:"]
        for cat in cats:
            subs = list_subcategories(cat["id"])
            lines.append(f"\n<b>{cat['name']}</b>:")
            for sub in subs:
                lines.append(f"  <code>{sub['id']}</code> — {sub['name']}")
        await message.answer("\n".join(lines))
        return
    sid_s, new_name = [x.strip() for x in rest.split("|", 1)]
    try:
        sid = int(sid_s)
    except ValueError:
        await message.answer("ID подкатегории должен быть числом.")
        return
    ok = rename_subcategory(sid, new_name)
    await message.answer(f"✅ Подкатегория переименована в <b>{new_name}</b>" if ok else "❌ Подкатегория не найдена.")


# ─── Список заказов (админ) ───────────────────────────────────────────────

ORDERS_PAGE_SIZE = 8

# Цветовые эмодзи для статусов
ORDER_STATUS_ICON = {
    "paid":    "🟢",
    "pending": "🟡",
    "expired": "🔴",
    "cancelled": "⛔",
}

ORDER_STATUS_LABEL = {
    "paid":    "Оплачен",
    "pending": "Ожидает",
    "expired": "Истёк",
    "cancelled": "Отменён",
}


def orders_text(orders: list, page: int, total: int, status_filter: str | None) -> str:
    """Формирует текст списка заказов."""
    import datetime
    filter_label = {
        None:      "Все",
        "paid":    "🟢 Оплаченные",
        "pending": "🟡 Ожидающие",
        "expired": "🔴 Истёкшие",
    }.get(status_filter, "Все")

    pages_total = max(1, (total + ORDERS_PAGE_SIZE - 1) // ORDERS_PAGE_SIZE)
    header = (
        f"📋 <b>Заказы</b> — {filter_label}\n"
        f"Всего: {total} | Стр. {page + 1}/{pages_total}\n"
        "➖➖➖➖➖➖➖➖➖\n\n"
    )
    if not orders:
        return header + "Заказов не найдено."

    lines = []
    for o in orders:
        status = o["payment_status"]
        icon   = ORDER_STATUS_ICON.get(status, "⚪")
        label  = ORDER_STATUS_LABEL.get(status, status)
        title  = (o["product_title"] or "—")[:22]
        ts     = datetime.datetime.fromtimestamp(o["created_ts"]).strftime("%d.%m %H:%M")
        lines.append(
            f"{icon} <code>{o['order_code']}</code> | {ts}\n"
            f"   📦 {title} × {o['qty']} шт. | 💵 {fmt(o['total_usd'])}$\n"
            f"   👤 <code>{o['tg_user_id']}</code> | {label}"
        )
    return header + "\n\n".join(lines)


def orders_kb(page: int, total: int, status_filter: str | None) -> InlineKeyboardMarkup:
    """Клавиатура для /orders: фильтры + пагинация."""
    kb = InlineKeyboardBuilder()

    # Строка фильтров
    filters = [
        ("Все",       None),
        ("🟢",        "paid"),
        ("🟡",        "pending"),
        ("🔴",        "expired"),
    ]
    for label, f in filters:
        active = "·" if f == status_filter else ""
        sf_str = f or "all"
        kb.button(
            text=f"{active}{label}{active}",
            callback_data=f"orders:filter:{sf_str}:0",
        )
    kb.adjust(4)

    # Пагинация
    pages_total = max(1, (total + ORDERS_PAGE_SIZE - 1) // ORDERS_PAGE_SIZE)
    sf_str = status_filter or "all"
    nav_row = []
    if page > 0:
        nav_row.append(("◀️", f"orders:page:{sf_str}:{page - 1}"))
    nav_row.append((f"{page + 1}/{pages_total}", "orders:noop"))
    if (page + 1) * ORDERS_PAGE_SIZE < total:
        nav_row.append(("▶️", f"orders:page:{sf_str}:{page + 1}"))

    for label, cb in nav_row:
        kb.button(text=label, callback_data=cb)
    kb.adjust(4, len(nav_row))

    # Кнопка закрыть
    kb.button(text="✖️ Закрыть", callback_data="orders:close")
    kb.adjust(4, len(nav_row), 1)
    return kb.as_markup()


@router.message(Command("orders"))
async def cmd_orders(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    total  = count_orders()
    orders = get_all_orders(limit=ORDERS_PAGE_SIZE, offset=0)
    await message.answer(
        orders_text(orders, 0, total, None),
        reply_markup=orders_kb(0, total, None),
    )


@router.callback_query(F.data.startswith("orders:filter:"))
async def cb_orders_filter(callback: CallbackQuery) -> None:
    if callback.from_user.id not in settings.admin_ids:
        await callback.answer()
        return
    # orders:filter:<status>:<page>
    parts        = callback.data.split(":")
    sf_raw       = parts[2]
    status_filter = None if sf_raw == "all" else sf_raw
    page         = int(parts[3])
    total        = count_orders(status_filter)
    orders       = get_all_orders(limit=ORDERS_PAGE_SIZE, offset=page * ORDERS_PAGE_SIZE, status_filter=status_filter)
    try:
        await callback.message.edit_text(
            orders_text(orders, page, total, status_filter),
            reply_markup=orders_kb(page, total, status_filter),
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("orders:page:"))
async def cb_orders_page(callback: CallbackQuery) -> None:
    if callback.from_user.id not in settings.admin_ids:
        await callback.answer()
        return
    # orders:page:<status>:<page>
    parts         = callback.data.split(":")
    sf_raw        = parts[2]
    status_filter = None if sf_raw == "all" else sf_raw
    page          = int(parts[3])
    total         = count_orders(status_filter)
    orders        = get_all_orders(limit=ORDERS_PAGE_SIZE, offset=page * ORDERS_PAGE_SIZE, status_filter=status_filter)
    try:
        await callback.message.edit_text(
            orders_text(orders, page, total, status_filter),
            reply_markup=orders_kb(page, total, status_filter),
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "orders:noop")
async def cb_orders_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "orders:close")
async def cb_orders_close(callback: CallbackQuery) -> None:
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()


# ─── Рассылка ──────────────────────────────────────────────────────────

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    await state.set_state(AdminFlow.broadcast_wait)
    await message.answer("📢 Отправьте текст рассылки одним сообщением.")


@router.message(AdminFlow.broadcast_wait)
async def state_broadcast(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    await state.clear()
    text     = message.text or ""
    user_ids = get_all_user_ids()
    sent     = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            continue
    await message.answer(f"📢 Рассылка завершена.\nДоставлено: {sent} из {len(user_ids)}")


# ─── Админ-панель ──────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    text = (
        "🛠 <b>Админ-панель — список команд</b>\n"
        "➖➖➖➖➖➖➖➖➖➖\n\n"

        "📦 <b>Товары</b>\n"
        "<b>/additem</b> — добавить новый товар.\n"
        "Формат: <code>Категория | Подкатегория | Название | Цена | Тип | Остаток</code>\n"
        "Категорию и подкатегорию можно указать частично, например: <code>Нейросети | ChatGPT | ...</code>\n\n"

        "<b>/editproduct</b> — редактировать существующий товар.\n"
        "Формат: <code>ID | название | описание | цена | тип | остаток</code>\n\n"

        "<b>/setname</b> <code>ID | новое название</code>\n"
        "<b>/setdesc</b> <code>ID | описание товара</code>\n"
        "<b>/setstock</b> <code>ID количество</code>\n\n"

        "🗝 <b>Выдача</b>\n"
        "<b>/addpayload</b> <code>ID | данные</code> — добавить 1 единицу.\n"
        "<b>/setpayloads</b> <code>ID | ключ1 ; ключ2 ; ключ3</code> — заменить всё.\n"
        "<b>/setdelivery</b> <code>ID | инструкция</code> — текст после оплаты.\n\n"

        "🖼 <b>Картинки</b>\n"
        "<b>/getfileid</b> — получить file_id отправленного фото.\n"
        "<b>/setimage</b> <code>ключ file_id</code> — установить картинку.\n"
        "<b>/images</b> — статус всех картинок.\n\n"

        "💳 <b>Баланс</b>\n"
        "<b>/setbalance</b> — установить баланс пользователю.\n\n"

        "🔘 <b>Кнопки</b>\n"
        "<b>/setbutton</b> <code>button_id | новый текст</code> — изменить кнопку.\n"
        "<b>/buttons</b> — список всех кнопок.\n"
        "<b>/resetbutton</b> <code>button_id</code> — вернуть кнопку.\n"
        "<b>/resetallbuttons</b> — вернуть все кнопки.\n\n"

        "📂 <b>Категории</b>\n"
        "<b>/setcategory</b> <code>ID | новое название</code> — переименовать категорию.\n"
        "<b>/setsubcategory</b> <code>ID | новое название</code> — переименовать подкатегорию.\n\n"

        "📋 <b>Прочее</b>\n"
        "<b>/order</b> <code>код</code> — информация о конкретном заказе.\n"
        "<b>/orders</b> — все заказы: фильтры по статусу, пагинация.\n"
        "<b>/broadcast</b> — рассылка всем покупателям.\n\n"

        "➖➖➖➖➖➖➖➖➖➖\n"
        "💡 <b>Как узнать product_id?</b>\n"
        "Сделайте тестовую покупку и используйте /order — там будет product_id."
    )
    await message.answer(text)


# ─── Запуск ────────────────────────────────────────────────────────────

async def run() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await bot.delete_webhook(drop_pending_updates=True)
    await setup_commands(bot)

    asyncio.create_task(_payment_checker(bot))

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    init_db()
    asyncio.run(run())
