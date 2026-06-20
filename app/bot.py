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

from app.config import load_settings
from app.cryptobot import check_invoice_status, create_invoice
from app.emoji_ids import (
    format_subcategory_header,
    get_button_icon_id,
    get_category_icon_id,
    get_menu_button_icon_id,
    get_subcategory_icon_id,
    get_subcategory_visual_key,
    localized_visual_key,
    normalize_visual_input_key,
    ru_visual_keys,
    en_visual_keys,
    strip_unicode_emoji,
)
from app.i18n import normalize_lang, product_type_hint, t, translate_category
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
    get_user_lang,
    get_visual,
    init_db,
    list_all_buttons,
    list_categories,
    list_products,
    list_subcategories,
    list_visuals,
    mark_order_paid,
    mark_order_awaiting_confirm,
    pop_payloads,
    rename_category,
    rename_subcategory,
    replace_product_payloads,
    reset_all_buttons,
    reset_button_text,
    set_balance,
    set_user_lang,
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

# Картинки по умолчанию (можно переопределить через /setimage)
VISUALS: dict[str, str] = {}

# Ключи картинок для админ-команд
VISUAL_KEYS_RU = ru_visual_keys()
VISUAL_KEYS_EN = en_visual_keys()


# ─── FSM-состояния ─────────────────────────────────────────────────────────

class BuyFlow(StatesGroup):
    choose_qty = State()
    choose_payment_method = State()


class AdminFlow(StatesGroup):
    add_product_wait = State()
    broadcast_wait   = State()
    set_balance_wait = State()
    edit_product_wait = State()


# ─── Язык ────────────────────────────────────────────────────────────────────

def lang_of(user_id: int) -> str:
    return normalize_lang(get_user_lang(user_id))


def has_lang(user_id: int) -> bool:
    return get_user_lang(user_id) is not None


def footer(lang: str) -> str:
    return t("shop.footer", lang)


def language_kb(lang: str, return_to: str = "start") -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🇷🇺 Русский", callback_data=f"lang:ru:{return_to}")
    kb.button(text="🇬🇧 English", callback_data=f"lang:en:{return_to}")
    if return_to == "profile":
        kb.button(text=get_button_text("back", lang), callback_data="menu:profile")
        kb.adjust(2, 1)
    else:
        kb.adjust(2)
    return kb.as_markup()


async def prompt_language(message: Message) -> None:
    await message.answer(t("lang.choose", "ru"), reply_markup=language_kb("ru", "start"))


def profile_language_label(lang: str) -> str:
    return t("profile.language_ru" if lang == "ru" else "profile.language_en", lang)


async def show_profile_screen(callback: CallbackQuery, lang: str) -> None:
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
    username_text = f"@{username}" if username else t("profile.username_missing", lang)

    text = t(
        "menu.profile", lang,
        uid=uid,
        full_name=full_name,
        username=username_text,
        orders_count=orders_count,
        spent=fmt(total_spent),
        balance_usd=fmt(balance_usd),
        balance_rub=fmt(balance_rub),
    )
    text += "\n" + t("profile.current_language", lang, language=profile_language_label(lang))

    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("change_language", lang), callback_data="profile:language")
    kb.button(text=get_button_text("back", lang), callback_data="go:main")
    kb.adjust(1)

    photo = get_image("profile", lang)
    await replace_screen(callback, text, kb.as_markup(), photo=photo or None)


async def show_start_screen_message(message: Message, lang: str) -> None:
    await send_with_photo(message, t("start.text", lang), main_kb(lang), get_image("start", lang))


async def show_start_screen_callback(callback: CallbackQuery, lang: str) -> None:
    photo = get_image("start", lang)
    await replace_screen(
        callback,
        t("start.text", lang),
        main_kb(lang),
        photo=photo or None,
    )


# ─── Вспомогательные функции ───────────────────────────────────────────────

def fmt(v: float) -> str:
    """Форматирует число: убирает лишние нули, меняет точку на запятую."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def get_image(key: str, lang: str | None = None) -> str:
    """Возвращает картинку из БД по языку (start / start_en), с fallback на ru."""
    if lang:
        localized = localized_visual_key(key, lang)
        value = get_visual(localized) or VISUALS.get(localized, "")
        if value:
            return value
    return get_visual(key) or VISUALS.get(key, "")


def get_service_image(subcategory_name: str, lang: str | None = None) -> str:
    """Возвращает картинку для конкретного сервиса по его названию."""
    key = get_subcategory_visual_key(subcategory_name)
    return get_image(key, lang) if key else ""


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

def _icon_button(
    kb: InlineKeyboardBuilder,
    text: str,
    icon_id: str | None = None,
    **kwargs,
) -> None:
    if icon_id:
        kb.button(text=text, icon_custom_emoji_id=icon_id, **kwargs)
    else:
        kb.button(text=text, **kwargs)


def main_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    _icon_button(kb, get_button_text("catalog", lang),   get_menu_button_icon_id("catalog"),   callback_data="menu:catalog")
    _icon_button(kb, get_button_text("balance", lang),   get_menu_button_icon_id("balance"),   callback_data="menu:balance")
    _icon_button(kb, get_button_text("wholesale", lang), get_menu_button_icon_id("wholesale"), url=normalize_link(settings.wholesale_link, "https://t.me/Dolzu"))
    _icon_button(kb, get_button_text("help", lang),      get_menu_button_icon_id("help"),      url=normalize_link(settings.help_link, "https://t.me/Dolzu"))
    _icon_button(kb, get_button_text("profile", lang),   get_menu_button_icon_id("profile"),   callback_data="menu:profile")
    _icon_button(kb, get_button_text("rules", lang),     get_menu_button_icon_id("rules"),     callback_data="menu:rules")
    kb.adjust(1, 1, 2, 2)
    return kb.as_markup()


def rules_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("agree", lang),
              url="https://telegra.ph/POLZOVATELSKOE-SOGLASHENIE-01-07-19")
    kb.button(text=get_button_text("privacy", lang),
              url="https://telegra.ph/Politika-konfidencialnosti-01-07-38")
    kb.button(text=get_button_text("back", lang), callback_data="go:main")
    kb.adjust(1)
    return kb.as_markup()


def categories_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for cat in list_categories():
        name = translate_category(strip_unicode_emoji(cat["name"]), lang)
        icon_id = get_category_icon_id(cat["name"])
        _icon_button(kb, name, icon_id, callback_data=f"cat:{cat['id']}")
    kb.button(text=get_button_text("back", lang), callback_data="go:main")
    kb.adjust(1)
    return kb.as_markup()


def subcategories_kb(category_id: int, lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for sub in list_subcategories(category_id):
        name = strip_unicode_emoji(sub["name"])
        icon_id = get_subcategory_icon_id(sub["name"])
        _icon_button(kb, name, icon_id, callback_data=f"sub:{sub['id']}")
    kb.button(text=get_button_text("back", lang), callback_data="menu:catalog")
    kb.adjust(1)
    return kb.as_markup()


def products_kb(subcategory_id: int, lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    sub = get_subcategory(subcategory_id)
    sub_name = sub["name"] if sub else ""
    for p in list_products(subcategory_id):
        title = strip_unicode_emoji(p["title"])
        ptype = strip_unicode_emoji((p["product_type"] or "").strip())
        if ptype and not title.startswith("["):
            title = f"[{ptype}] {title}"
        price_part = f" — ${fmt(p['price_usd'])}"
        stock_note = "" if p["stock"] > 0 else t("product.out_of_stock_note", lang)
        btn_text = f"{title}{price_part}{stock_note}"
        icon_id = get_button_icon_id(p["title"], sub_name)
        _icon_button(kb, btn_text, icon_id, callback_data=f"prod:{p['id']}")
    kb.button(text=get_button_text("back", lang), callback_data="go:cats")
    kb.adjust(1)
    return kb.as_markup()


def qty_kb(product_id: int, max_qty: int, lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i in range(1, max_qty + 1):
        kb.button(text=str(i), callback_data=f"qty:{product_id}:{i}")
    kb.button(text=get_button_text("back", lang), callback_data=f"prod:{product_id}")
    kb.adjust(4)
    return kb.as_markup()


def pay_kb(order_code: str, lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("crypto_usdt", lang), callback_data=f"pay:crypto_usdt:{order_code}")
    kb.button(text=get_button_text("crypto_ton", lang),  callback_data=f"pay:crypto_ton:{order_code}")
    kb.button(text=get_button_text("bybit", lang),       callback_data=f"pay:bybit:{order_code}")
    kb.button(text=get_button_text("balance_pay", lang), callback_data=f"pay:balance:{order_code}")
    kb.adjust(1)
    return kb.as_markup()


def balance_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("topup", lang),   callback_data="balance:topup")
    kb.button(text=get_button_text("history", lang), callback_data="balance:history")
    kb.button(text=get_button_text("back", lang),    callback_data="go:main")
    kb.adjust(1)
    return kb.as_markup()


# ─── Утилиты для отправки/редактирования ──────────────────────────────────────

async def send_with_photo(message: Message, text: str, kb: InlineKeyboardMarkup, photo: str) -> None:
    """Отправляет новое сообщение — с фото если есть, без если нет."""
    if photo:
        await message.answer_photo(photo=photo, caption=text, reply_markup=kb)
    else:
        await message.answer(text, reply_markup=kb)


async def replace_screen(
    callback: CallbackQuery,
    text: str,
    kb: InlineKeyboardMarkup,
    photo: str | None = None,
) -> None:
    """Удаляет текущее сообщение и показывает новый экран (без дублей в чате)."""
    chat_id = callback.message.chat.id
    try:
        await callback.message.delete()
    except Exception:
        pass
    if photo:
        await callback.bot.send_photo(chat_id, photo=photo, caption=text, reply_markup=kb)
    else:
        await callback.bot.send_message(chat_id, text, reply_markup=kb)


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

async def notify_admin_about_payment(order_code: str, *, awaiting_confirm: bool = False) -> None:
    """Если настроен второй бот-нотификатор — шлёт ему уведомление об оплате."""
    if not settings.notify_bot_token or not settings.notify_chat_id:
        return
    order = get_order(order_code)
    if not order:
        return
    product = get_product(int(order["product_id"]))
    title = product["title"] if product else "—"
    header = "⏳ <b>Ожидает подтверждения!</b>" if awaiting_confirm else "💸 <b>Новая оплата!</b>"
    extra = f"\nПодтвердить: <code>/confirmorder {order_code}</code>" if awaiting_confirm else ""
    text = (
        f"{header}\n"
        f"📋 Заказ: <code>{order['order_code']}</code>\n"
        f"👤 Пользователь: <code>{order['tg_user_id']}</code>\n"
        f"📦 Товар: {title}\n"
        f"🔢 Кол-во: {order['qty']} шт.\n"
        f"💰 Сумма: {fmt(order['total_usd'])}$ ({fmt(order['total_rub'])}₽)"
        f"{extra}"
    )
    try:
        bot = Bot(token=settings.notify_bot_token,
                  default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        await bot.send_message(settings.notify_chat_id, text)
        await bot.session.close()
    except Exception:
        pass


async def _fulfill_order(bot: Bot, order_code: str) -> str | None:
    """Подтверждает оплату, выдаёт товар и уведомляет пользователя. Возвращает текст для экрана."""
    order = get_order(order_code)
    if not order or order["payment_status"] == "paid":
        return None

    mark_order_paid(order_code)
    await notify_admin_about_payment(order_code)

    product       = get_product(int(order["product_id"]))
    payloads      = pop_payloads(int(order["product_id"]), int(order["qty"]))
    delivery_note = (product["delivery_text"] or "").strip() if product else ""
    lang          = lang_of(int(order["tg_user_id"]))
    text          = order_success_text(lang, payloads, delivery_note)

    try:
        await bot.send_message(
            int(order["tg_user_id"]),
            text,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        logger.exception("Failed to send fulfillment message to user %s", order["tg_user_id"])
    return text


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
        BotCommand(command="setimage",    description="Картинка RU (русский)"),
        BotCommand(command="setimage_en", description="Картинка EN (английский)"),
        BotCommand(command="images",      description="Статус картинок RU"),
        BotCommand(command="images_en",   description="Статус картинок EN"),
        BotCommand(command="getfileid",   description="Получить file_id фото"),
        BotCommand(command="getfield",    description="Алиас getfileid"),
        BotCommand(command="order",       description="Проверить заказ по коду"),
        BotCommand(command="confirmorder", description="Подтвердить оплату заказа"),
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


def subscribe_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(
        text=get_button_text("subscribe", lang),
        url=f"https://t.me/{REQUIRED_CHANNEL_USERNAME}",
    )
    kb.button(text=get_button_text("subscribed", lang), callback_data="check_subscription")
    kb.adjust(1)
    return kb.as_markup()


async def require_subscription(
    bot: Bot, user_id: int, callback: CallbackQuery | None = None, lang: str | None = None,
) -> bool:
    """
    Проверяет подписку. Если не подписан — показывает заглушку и возвращает False.
    Используй: if not await require_subscription(bot, uid, callback): return
    """
    lang = normalize_lang(lang or lang_of(user_id))
    if await is_subscribed(bot, user_id):
        return True
    text = t("sub.locked", lang)
    if callback:
        try:
            await callback.message.answer(text, reply_markup=subscribe_kb(lang))
        except Exception:
            pass
        await callback.answer(t("sub.alert", lang), show_alert=True)
    return False


def order_success_text(lang: str, payloads: list[str], delivery_note: str) -> str:
    extra = t("order.delivery", lang, note=delivery_note) if delivery_note else ""
    if not payloads:
        return f"{t('order.stock_empty', lang)}{extra}\n\n{footer(lang)}"
    items = "\n\n".join(f"{i + 1}) <code>{v}</code>" for i, v in enumerate(payloads))
    return f"{t('order.paid_ok', lang, items=items)}{extra}\n\n{footer(lang)}"


# ─── /start ───────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    if not has_lang(user_id):
        await prompt_language(message)
        return

    lang = lang_of(user_id)
    if not await is_subscribed(bot, user_id):
        await message.answer(t("sub.welcome", lang), reply_markup=subscribe_kb(lang))
        return

    await show_start_screen_message(message, lang)


@router.callback_query(F.data.startswith("lang:"))
async def cb_language(callback: CallbackQuery, bot: Bot) -> None:
    parts = callback.data.split(":")
    lang = normalize_lang(parts[1])
    return_to = parts[2] if len(parts) > 2 else "start"
    set_user_lang(callback.from_user.id, lang)
    await callback.answer(t("lang.saved", lang))

    if not await is_subscribed(bot, callback.from_user.id):
        await replace_screen(callback, t("sub.welcome", lang), subscribe_kb(lang))
        return

    if return_to == "profile":
        await show_profile_screen(callback, lang)
        return

    await show_start_screen_callback(callback, lang)


@router.callback_query(F.data == "profile:language")
async def cb_profile_language(callback: CallbackQuery, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    await replace_screen(
        callback,
        t("lang.choose", lang),
        language_kb(lang, "profile"),
    )
    await callback.answer()


@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery, bot: Bot) -> None:
    user_id = callback.from_user.id
    lang = lang_of(user_id)
    if not await is_subscribed(bot, user_id):
        await callback.answer(t("sub.not_yet", lang), show_alert=True)
        return

    await callback.answer(t("sub.ok", lang))
    await show_start_screen_callback(callback, lang)


# ─── Навигация главного меню ──────────────────────────────────────────────

@router.callback_query(F.data == "go:main")
async def cb_go_main(callback: CallbackQuery) -> None:
    lang = lang_of(callback.from_user.id)
    photo = get_image("start", lang)
    await replace_screen(callback, t("menu.main", lang), main_kb(lang), photo=photo or None)
    await callback.answer()


@router.callback_query(F.data == "menu:catalog")
async def cb_catalog(callback: CallbackQuery, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    photo = get_image("categories", lang)
    await replace_screen(callback, t("menu.catalog", lang), categories_kb(lang), photo=photo or None)
    await callback.answer()


@router.callback_query(F.data == "go:cats")
async def cb_go_cats(callback: CallbackQuery, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    photo = get_image("categories", lang)
    await replace_screen(callback, t("menu.categories", lang), categories_kb(lang), photo=photo or None)
    await callback.answer()


@router.callback_query(F.data == "menu:balance")
async def cb_balance(callback: CallbackQuery, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    uid = callback.from_user.id
    balance_usd, balance_rub = get_user_balance(uid)
    text = t(
        "menu.balance", lang,
        balance_usd=fmt(balance_usd),
        balance_rub=fmt(balance_rub),
    )
    photo = get_image("balance", lang)
    await replace_screen(callback, text, balance_kb(lang), photo=photo or None)
    await callback.answer()


@router.callback_query(F.data == "balance:topup")
async def cb_balance_topup(callback: CallbackQuery, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    text = t("menu.balance_topup", lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("write_admin", lang), url="https://t.me/Dolzu")
    kb.button(text=get_button_text("back", lang), callback_data="menu:balance")
    kb.adjust(1)
    await safe_edit(callback, text, kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "balance:history")
async def cb_balance_history(callback: CallbackQuery, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    uid = callback.from_user.id
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT total_usd, total_rub, payment_status, created_ts FROM orders WHERE tg_user_id = ? ORDER BY created_ts DESC LIMIT 10",
            (uid,),
        ).fetchall()
    if not rows:
        text = t("menu.balance_history_empty", lang)
    else:
        lines = [t("menu.balance_history_title", lang)]
        for row in rows:
            status = (
                t("menu.balance_history_paid", lang)
                if row["payment_status"] == "paid"
                else t("menu.balance_history_pending", lang)
            )
            lines.append(f"{fmt(row['total_usd'])}$ — {status}")
        text = "\n".join(lines)
    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("back", lang), callback_data="menu:balance")
    await safe_edit(callback, text, kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "menu:rules")
async def cb_rules(callback: CallbackQuery, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    photo = get_image("rules", lang)
    await replace_screen(callback, t("menu.rules", lang), rules_kb(lang), photo=photo or None)
    await callback.answer()


@router.callback_query(F.data == "menu:profile")
async def cb_profile(callback: CallbackQuery, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    await show_profile_screen(callback, lang)
    await callback.answer()


# ─── Каталог ───────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cat:"))
async def cb_category(callback: CallbackQuery, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    cat_id = int(callback.data.split(":")[1])
    await replace_screen(callback, t("menu.services", lang), subcategories_kb(cat_id, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("sub:"))
async def cb_subcategory(callback: CallbackQuery, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    sub_id  = int(callback.data.split(":")[1])
    sub     = get_subcategory(sub_id)
    name    = sub["name"] if sub else ""
    photo   = get_service_image(name, lang)
    text    = format_subcategory_header(name, lang)
    await replace_screen(callback, text, products_kb(sub_id, lang), photo=photo or None)
    await callback.answer()


@router.callback_query(F.data.startswith("prod:"))
async def cb_product(callback: CallbackQuery, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    product_id = int(callback.data.split(":")[1])
    product    = get_product(product_id)

    if not product:
        await callback.answer(t("product.not_found", lang), show_alert=True)
        return

    ptype  = (product["product_type"] or "").strip()
    hint   = product_type_hint(ptype, lang)
    status = t("product.in_stock", lang) if product["stock"] > 0 else t("product.no_stock", lang)
    desc   = (product["description"] or "").strip()
    desc_line = t("product.desc_line", lang, desc=desc) if desc else ""

    text = t(
        "product.card", lang,
        title=product["title"],
        desc=desc_line,
        price=fmt(product["price_usd"]),
        stock=product["stock"],
        ptype=ptype or t("product.type_missing", lang),
        hint=hint,
        status=status,
        footer=footer(lang),
    )

    kb = InlineKeyboardBuilder()
    if product["stock"] > 0:
        kb.button(text=get_button_text("buy", lang), callback_data=f"buy:{product_id}")
    kb.button(text=get_button_text("back", lang), callback_data=f"sub:{product['subcategory_id']}")
    kb.adjust(1)

    await replace_screen(callback, text, kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    product_id = int(callback.data.split(":")[1])
    product    = get_product(product_id)

    if not product or product["stock"] <= 0:
        await callback.answer(t("product.out_of_stock", lang), show_alert=True)
        return

    max_qty = min(product["stock"], 12)
    await state.set_state(BuyFlow.choose_qty)
    await state.update_data(product_id=product_id)
    await replace_screen(callback, t("qty.choose", lang, max_qty=max_qty), qty_kb(product_id, max_qty, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("qty:"))
async def cb_qty(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    _, pid_s, qty_s = callback.data.split(":")
    product_id = int(pid_s)
    qty        = int(qty_s)
    product    = get_product(product_id)

    if not product:
        await callback.answer(t("product.not_found", lang), show_alert=True)
        return
    if qty > product["stock"]:
        await callback.answer(t("pay.insufficient_stock", lang), show_alert=True)
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

    text = t("order.title", lang) + t(
        "order.body", lang,
        title=product["title"],
        qty=qty,
        price=fmt(price),
        total_usd=fmt(total_usd),
        total_rub=fmt(total_rub),
        code=code,
    )
    await replace_screen(callback, text, pay_kb(code, lang))
    await callback.answer()


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(callback: CallbackQuery, bot: Bot) -> None:
    lang = lang_of(callback.from_user.id)
    if not await require_subscription(bot, callback.from_user.id, callback, lang):
        return
    _, method, code = callback.data.split(":")
    order   = get_order(code)
    product = get_product(int(order["product_id"])) if order else None

    if not order or not product:
        await callback.answer(t("order.not_found", lang), show_alert=True)
        return

    if method == "balance":
        uid = callback.from_user.id
        balance_usd, balance_rub = get_user_balance(uid)
        total_usd = float(order["total_usd"])
        total_rub = float(order["total_rub"])

        if balance_usd < total_usd:
            await callback.answer(
                t("order.insufficient_balance", lang, need=fmt(total_usd), have=fmt(balance_usd)),
                show_alert=True,
            )
            return

        if not withdraw_balance(uid, total_usd, total_rub):
            await callback.answer(t("order.withdraw_error", lang), show_alert=True)
            return

        from app.db import mark_order_paid
        mark_order_paid(code)
        await notify_admin_about_payment(code)

        payloads      = pop_payloads(int(order["product_id"]), int(order["qty"]))
        delivery_note = (product["delivery_text"] or "").strip() if product else ""
        text = order_success_text(lang, payloads, delivery_note)

        await replace_screen(callback, text, InlineKeyboardBuilder().as_markup())
        await callback.answer(t("order.thanks", lang))
        return

    extra_pct = settings.cryptobot_invoice_add_percent

    if method in ("crypto_usdt", "crypto_ton"):
        asset = "USDT" if method == "crypto_usdt" else "TON"
        total_usd = round(float(order["total_usd"]) * (1 + extra_pct / 100), 2)
        set_order_payment_method(code, method)

        if not settings.cryptobot_api_token:
            kb = InlineKeyboardBuilder()
            kb.button(text=get_button_text("back", lang), callback_data="go:main")
            await replace_screen(callback, t("pay.crypto_unavailable", lang), kb.as_markup())
            await callback.answer()
            return

        try:
 invoice = await create_invoice(
                    token=settings.cryptobot_api_token,
                    asset=asset,
                    amount=invoice_amount,
                description=f"Order {code}: {product['title']} x{order['qty']}",
                expires_in=900,
            )
            set_order_invoice_id(code, invoice.invoice_id)
            pay_link = invoice.bot_invoice_url

            text = t(
                "pay.crypto", lang,
                title=product["title"],
                qty=order["qty"],
                amount=f"{fmt(total_usd)} $",
                fee=extra_pct,
                code=order["order_code"],
                link=pay_link,
            )
            kb = InlineKeyboardBuilder()
            kb.button(text=get_button_text("pay", lang), url=pay_link)
            kb.button(text=get_button_text("check_payment", lang), callback_data=f"check:{code}")
            kb.adjust(1)
            await replace_screen(callback, text, kb.as_markup())
            await callback.answer()
            return
        except Exception:
            logger.exception("Failed to create CryptoBot invoice for order %s", code)
            kb = InlineKeyboardBuilder()
            kb.button(text=get_button_text("back", lang), callback_data="go:main")
            await replace_screen(
                callback,
                t("pay.invoice_error", lang, code=order["order_code"]),
                kb.as_markup(),
            )
            await callback.answer()
            return

    set_order_payment_method(code, "bybit")
    text = t(
        "pay.bybit", lang,
        title=product["title"],
        qty=order["qty"],
        total_rub=fmt(order["total_rub"]),
        code=order["order_code"],
        uid=settings.bybit_uid,
    )

    kb = InlineKeyboardBuilder()
    kb.button(text=get_button_text("confirm_paid", lang), callback_data=f"paid:{code}")
    await replace_screen(callback, text, kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("check:"))
async def cb_check_payment(callback: CallbackQuery) -> None:
    lang = lang_of(callback.from_user.id)
    code = callback.data.split(":")[1]
    order = get_order(code)

    if not order:
        await callback.answer(t("order.not_found", lang), show_alert=True)
        return

    if order["payment_status"] == "paid":
        await callback.answer(t("order.already_paid", lang), show_alert=True)
        return

    if not settings.cryptobot_api_token or order["invoice_id"] == 0:
        await callback.answer(t("pay.check_unavailable", lang), show_alert=True)
        return

    try:
        status = await check_invoice_status(
            settings.cryptobot_api_token, int(order["invoice_id"])
        )
    except Exception:
        logger.exception("Failed to check invoice %s", order["invoice_id"])
        await callback.answer(t("pay.check_error", lang), show_alert=True)
        return

    if status == "paid":
        text = await _fulfill_order(callback.bot, code)
        if text:
            await replace_screen(callback, text, InlineKeyboardBuilder().as_markup())
        await callback.answer(t("pay.check_ok", lang), show_alert=True)
    elif status == "expired":
        await callback.answer(t("pay.check_expired", lang), show_alert=True)
    else:
        await callback.answer(t("pay.check_pending", lang), show_alert=True)


@router.callback_query(F.data.startswith("paid:"))
async def cb_paid(callback: CallbackQuery) -> None:
    lang = lang_of(callback.from_user.id)
    code  = callback.data.split(":")[1]
    order = get_order(code)

    if not order:
        await callback.answer(t("order.not_found", lang), show_alert=True)
        return

    if order["payment_status"] == "paid":
        await callback.answer(t("order.already_paid", lang), show_alert=True)
        return

    if order["payment_status"] == "awaiting_confirm":
        await callback.answer(t("order.already_submitted", lang), show_alert=True)
        return

    method = (order["payment_method"] or "").lower()
    if method in ("crypto_usdt", "crypto_ton"):
        await callback.answer(t("pay.use_check_button", lang), show_alert=True)
        return

    if method != "bybit":
        await callback.answer(t("pay.use_check_button", lang), show_alert=True)
        return

    mark_order_awaiting_confirm(code)
    await notify_admin_about_payment(code, awaiting_confirm=True)

    text = t("order.awaiting_confirm", lang, code=code)
    await replace_screen(callback, text, InlineKeyboardBuilder().as_markup())
    await callback.answer()


# ─── Получение file_id фото ───────────────────────────────────────────────

def _format_media_id_reply(message: Message) -> str | None:
    """Собирает file_id / custom_emoji_id из фото, файла или стикера в сообщении."""
    lines: list[str] = []

    if message.photo:
        file_id = message.photo[-1].file_id
        lines.append(f"📋 <b>file_id:</b>\n<code>{file_id}</code>")
        lines.append(f"Пример: <code>/setimage start {file_id}</code>")

    if message.sticker:
        lines.append(f"📋 <b>file_id:</b>\n<code>{message.sticker.file_id}</code>")
        if message.sticker.custom_emoji_id:
            lines.append(
                f"🎨 <b>custom_emoji_id:</b>\n<code>{message.sticker.custom_emoji_id}</code>"
            )

    if message.document and not message.photo:
        lines.append(f"📋 <b>file_id:</b>\n<code>{message.document.file_id}</code>")
        if message.document.mime_type:
            lines.append(f"Тип: <code>{message.document.mime_type}</code>")

    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji" and entity.custom_emoji_id:
                lines.append(
                    f"🎨 <b>custom_emoji_id:</b>\n<code>{entity.custom_emoji_id}</code>"
                )

    if not lines:
        return None

    if message.photo:
        file_id = message.photo[-1].file_id
        lines.append(f"Пример RU: <code>/setimage start {file_id}</code>")
        lines.append(f"Пример EN: <code>/setimage_en start {file_id}</code>")

    return "\n\n".join(lines)


@router.message(Command("getfileid", "getfield"))
async def cmd_getfileid(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    reply = _format_media_id_reply(message)
    if reply:
        await message.answer(reply)
        return
    await message.answer(
        "📸 Отправьте фото, файл или премиум-эмодзи вместе с командой — "
        "или следующим сообщением.\n"
        "Я верну <code>file_id</code> или <code>custom_emoji_id</code>.\n\n"
        "Затем:\n"
        "RU: <code>/setimage ключ file_id</code>\n"
        "EN: <code>/setimage_en ключ file_id</code>"
    )


@router.message(F.photo | F.sticker | F.document)
async def handle_photo(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    if await state.get_state():
        return
    reply = _format_media_id_reply(message)
    if reply:
        await message.answer(reply)


# ─── Картинки ──────────────────────────────────────────────────────────

def _format_visual_keys(keys: list[str]) -> str:
    return ", ".join(f"<code>{k}</code>" for k in keys)


async def _cmd_set_visual(message: Message, lang: str) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = (message.text or "").split(maxsplit=2)
    cmd = "/setimage_en" if lang == "en" else "/setimage"
    allowed = VISUAL_KEYS_RU
    if len(parts) != 3:
        await message.answer(
            f"Формат: {cmd} <ключ> <file_id>\n"
            f"Ключи: {_format_visual_keys(allowed)}"
        )
        return
    storage_key = normalize_visual_input_key(parts[1], lang)
    if not storage_key:
        await message.answer(
            f"Неизвестный ключ. Доступные: {_format_visual_keys(allowed)}"
        )
        return
    set_visual(storage_key, parts[2].strip())
    label = "EN" if lang == "en" else "RU"
    await message.answer(f"✅ Картинка [{label}] <b>{storage_key}</b> обновлена.")


@router.message(Command("setimage"))
async def cmd_setimage(message: Message) -> None:
    await _cmd_set_visual(message, "ru")


@router.message(Command("setimage_en"))
async def cmd_setimage_en(message: Message) -> None:
    await _cmd_set_visual(message, "en")


async def _cmd_list_visuals(message: Message, lang: str) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    saved = {r["key"]: r["value"] for r in list_visuals()}
    keys = VISUAL_KEYS_EN if lang == "en" else VISUAL_KEYS_RU
    label = "EN" if lang == "en" else "RU"
    lines = [f"🖼 <b>Картинки [{label}]:</b>"]
    for key in keys:
        has = bool(saved.get(key) or VISUALS.get(key))
        display = key.removesuffix("_en") if lang == "en" else key
        lines.append(f"{'✅' if has else '❌'} {display}")
    await message.answer("\n".join(lines))


@router.message(Command("images"))
async def cmd_images(message: Message) -> None:
    await _cmd_list_visuals(message, "ru")


@router.message(Command("images_en"))
async def cmd_images_en(message: Message) -> None:
    await _cmd_list_visuals(message, "en")


# ─── Управление товарами ──────────────────────────────────────────────

@router.message(Command("additem"))
async def cmd_additem(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    await state.set_state(AdminFlow.add_product_wait)
    await message.answer(
        "📦 Введите данные товара в формате:\n"
        "<code>Категория | Подкатегория | Название | Цена$ | Тип | Остаток | Ключи</code>\n\n"
        "Поле «Ключи» необязательно — несколько ключей разделяйте символом <code>;</code>.\n"
        "Если ключи указаны, остаток будет рассчитан автоматически по их количеству.\n\n"
        "Пример без ключей:\n"
        "<code>Другие сервисы | Telegram | Telegram Premium 3m | 7.5 | ACC | 5</code>\n\n"
        "Пример с ключами:\n"
        "<code>Другие сервисы | Telegram | Telegram Premium 3m | 7.5 | ACC | 0 | login1:pass1 ; login2:pass2</code>"
    )


@router.message(AdminFlow.add_product_wait)
async def state_add_product(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = [p.strip() for p in (message.text or "").split("|")]
    if len(parts) not in (6, 7):
        await message.answer("Неверный формат. Нужно 6 или 7 полей через |")
        return
    category, subcategory, title, price_s, ptype, stock_s = parts[:6]
    keys_s = parts[6] if len(parts) == 7 else ""
    try:
        price = float(price_s.replace(",", "."))
        stock = int(stock_s)
    except ValueError:
        await message.answer("Цена и остаток должны быть числами.")
        return
    payloads = [k.strip() for k in keys_s.split(";") if k.strip()] if keys_s else []
    pid = add_custom_product(category, subcategory, title, price, ptype, stock, payloads)
    await state.clear()
    if payloads:
        await message.answer(
            f"✅ Товар добавлен.\n🆔 product_id = <code>{pid}</code>\n🔑 Ключей загружено: {len(payloads)}"
        )
    else:
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


@router.message(Command("confirmorder"))
async def cmd_confirmorder(message: Message, bot: Bot) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Формат: /confirmorder <код заказа>")
        return
    code = parts[1].strip()
    order = get_order(code)
    if not order:
        await message.answer("❌ Заказ не найден.")
        return
    if order["payment_status"] == "paid":
        await message.answer("✅ Заказ уже оплачен и выдан.")
        return
    if order["payment_status"] not in ("awaiting_confirm", "pending"):
        await message.answer(f"❌ Нельзя подтвердить заказ со статусом: {order['payment_status']}")
        return

    text = await _fulfill_order(bot, code)
    if text:
        await message.answer(f"✅ Заказ <code>{code}</code> подтверждён, товар выдан пользователю.")
    else:
        await message.answer("❌ Не удалось подтвердить заказ.")


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
    kb.button(text="Закрыть", callback_data="orders:close")
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
        "<b>/getfileid</b> или <b>/getfield</b> — file_id / custom_emoji_id картинки.\n"
        "<b>/setimage</b> <code>ключ file_id</code> — картинка RU.\n"
        "<b>/setimage_en</b> <code>ключ file_id</code> — картинка EN.\n"
        "<b>/images</b> — статус картинок RU.\n"
        "<b>/images_en</b> — статус картинок EN.\n\n"

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
        "<b>/confirmorder</b> <code>код</code> — подтвердить оплату Bybit вручную.\n"
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

