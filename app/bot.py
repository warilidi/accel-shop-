from __future__ import annotations

import asyncio
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
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.catalog_data import PRODUCT_TYPE_HINTS
from app.config import load_settings
from app.db import (
    add_custom_product,
    add_product_payload,
    create_order,
    get_all_user_ids,
    get_order,
    get_product,
    init_db,
    list_categories,
    list_products,
    list_subcategories,
    mark_order_paid,
    pop_payloads,
    replace_product_payloads,
    update_product_content,
)

router = Router()
ADMIN_FOOTER = "— 💎 Админ/Связь/Опт - @Dolzu"
settings = load_settings()


class BuyFlow(StatesGroup):
    choose_qty = State()


class AdminFlow(StatesGroup):
    add_payload_wait = State()
    add_product_wait = State()
    broadcast_wait = State()


def normalize_tg_link(value: str, fallback: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return fallback
    if raw.startswith("@"):
        return f"https://t.me/{raw[1:]}"
    if raw.startswith("t.me/"):
        return f"https://{raw}"
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return fallback


def main_kb() -> InlineKeyboardMarkup:
    wholesale_link = normalize_tg_link(settings.wholesale_link, "https://t.me/Dolzu")
    help_link = normalize_tg_link(settings.help_link, "https://t.me/Dolzu")
    rules_link = normalize_tg_link(settings.rules_link, "https://telegra.ph/Pravila-magazina-05-28")
    kb = InlineKeyboardBuilder()
    kb.button(text="🛍️ Товары и услуги", callback_data="menu:catalog")
    kb.button(text="💳 Баланс", callback_data="menu:balance")
    kb.button(text="💎 Опт", url=wholesale_link)
    kb.button(text="🛟 Помощь", url=help_link)
    kb.button(text="📜 Правила", url=rules_link)
    kb.adjust(1, 1, 2, 1)
    return kb.as_markup()


def categories_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in list_categories():
        kb.button(text=c["name"], callback_data=f"cat:{c['id']}")
    kb.button(text="◀️ Назад", callback_data="go:main")
    kb.adjust(1)
    return kb.as_markup()


def subcategories_kb(category_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in list_subcategories(category_id):
        kb.button(text=s["name"], callback_data=f"sub:{s['id']}")
    kb.button(text="◀️ Назад", callback_data="menu:catalog")
    kb.adjust(1)
    return kb.as_markup()


def products_kb(subcategory_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in list_products(subcategory_id):
        stock = "✅" if p["stock"] > 0 else "❌"
        kb.button(
            text=f"{stock} {p['title']} — ${fmt_money(p['price_usd'])}",
            callback_data=f"prod:{p['id']}",
        )
    kb.button(text="◀️ Назад", callback_data="go:cats")
    kb.adjust(1)
    return kb.as_markup()


def qty_kb(product_id: int, max_qty: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for qty in range(1, max_qty + 1):
        kb.button(text=str(qty), callback_data=f"qty:{product_id}:{qty}")
    kb.button(text="◀️ Назад", callback_data=f"prod:{product_id}")
    kb.adjust(4)
    return kb.as_markup()


def pay_kb(order_code: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="CryptoBot USDT", callback_data=f"pay:crypto_usdt:{order_code}")
    kb.button(text="CryptoBot TON", callback_data=f"pay:crypto_ton:{order_code}")
    kb.button(text="Bybit", callback_data=f"pay:bybit:{order_code}")
    kb.adjust(1)
    return kb.as_markup()


def fmt_money(v: float) -> str:
    s = f"{v:.2f}"
    s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


async def send_paid_notify_to_admin(order_code: str) -> None:
    if not settings.notify_bot_token or settings.notify_chat_id is None:
        return

    order = get_order(order_code)
    if not order:
        return
    product = get_product(int(order["product_id"]))
    title = product["title"] if product else "Товар не найден"
    text = (
        "💸 Новая оплата\n"
        f"Заказ: {order['order_code']}\n"
        f"Пользователь: {order['tg_user_id']}\n"
        f"Товар: {title}\n"
        f"Кол-во: {order['qty']} шт.\n"
        f"Сумма: {fmt_money(order['total_usd'])}$ ({fmt_money(order['total_rub'])}₽)"
    )

    try:
        notify_bot = Bot(
            token=settings.notify_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        await notify_bot.send_message(settings.notify_chat_id, text)
        await notify_bot.session.close()
    except Exception:
        return


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        commands=[BotCommand(command="start", description="Запустить бота")],
        scope=BotCommandScopeAllPrivateChats(),
    )

    admin_commands = [
        BotCommand(command="admin", description="Панель админа"),
        BotCommand(command="additem", description="Добавить товар"),
        BotCommand(command="addpayload", description="Добавить 1 выдачу"),
        BotCommand(command="setpayloads", description="Заменить всю выдачу"),
        BotCommand(command="setname", description="Изменить название"),
        BotCommand(command="setdesc", description="Изменить описание"),
        BotCommand(command="setdelivery", description="Текст после оплаты"),
        BotCommand(command="setstock", description="Изменить остаток"),
        BotCommand(command="order", description="Проверить заказ"),
        BotCommand(command="broadcast", description="Сделать рассылку"),
    ]
    for admin_id in settings.admin_ids:
        await bot.set_my_commands(
            commands=admin_commands,
            scope=BotCommandScopeChat(chat_id=admin_id),
        )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    text = (
        "✨ Добро пожаловать в Accel Shop!\n"
        "🏆 Премиум-магазин подписок на нейросети и популярные сервисы.\n"
        "🧩 Здесь аккаунты, подписки, сертификаты и многое другое.\n"
        "👇 Нажмите кнопку ниже, чтобы начать работу с ботом."
    )
    await message.answer(text, reply_markup=main_kb())


@router.callback_query(F.data == "go:main")
async def cb_main(callback: CallbackQuery) -> None:
    await callback.message.edit_text("🏠 Главное меню:", reply_markup=main_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:catalog")
async def cb_catalog(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "🛍️ Товары и услуги\nВыберите раздел:",
        reply_markup=categories_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "go:cats")
async def cb_go_cats(callback: CallbackQuery) -> None:
    await callback.message.edit_text("📂 Выберите раздел:", reply_markup=categories_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:balance")
async def cb_balance(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "💳 Баланс пока в разработке.\n"
        "Сейчас можно оплачивать каждый заказ отдельно через CryptoBot / Bybit.",
        reply_markup=main_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def cb_category(callback: CallbackQuery) -> None:
    category_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "🧠 Выберите сервис:",
        reply_markup=subcategories_kb(category_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sub:"))
async def cb_subcategory(callback: CallbackQuery) -> None:
    sub_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "🧾 Доступные товары:",
        reply_markup=products_kb(sub_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prod:"))
async def cb_product(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":")[1])
    product = get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    ptype = (product["product_type"] or "").strip()
    hint = PRODUCT_TYPE_HINTS.get(ptype, "Описание типа уточняйте у администратора.")
    status = "В наличии" if product["stock"] > 0 else "Нет в наличии"
    text = (
        f"📦 {product['title']}\n"
        f"💰 Цена: ${fmt_money(product['price_usd'])}\n"
        f"📦 Остаток: {product['stock']} шт.\n"
        f"🧩 Тип: {ptype or 'Не указан'}\n"
        f"ℹ️ {hint}\n"
        f"📌 Статус: {status}\n\n"
        f"{ADMIN_FOOTER}"
    )

    description = (product["description"] or "").strip()
    if description:
        text = (
            f"📦 {product['title']}\n"
            f"📝 Описание: {description}\n"
            f"💰 Цена: ${fmt_money(product['price_usd'])}\n"
            f"📦 Остаток: {product['stock']} шт.\n"
            f"🧩 Тип: {ptype or 'Не указан'}\n"
            f"ℹ️ {hint}\n"
            f"📌 Статус: {status}\n\n"
            f"{ADMIN_FOOTER}"
        )

    kb = InlineKeyboardBuilder()
    if product["stock"] > 0:
        kb.button(text="🛍 Купить", callback_data=f"buy:{product_id}")
    kb.button(text="◀️ Назад", callback_data=f"sub:{product['subcategory_id']}")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(callback: CallbackQuery, state: FSMContext) -> None:
    product_id = int(callback.data.split(":")[1])
    product = get_product(product_id)
    if not product or product["stock"] <= 0:
        await callback.answer("Нет в наличии", show_alert=True)
        return
    await state.set_state(BuyFlow.choose_qty)
    await state.update_data(product_id=product_id)
    await callback.message.edit_text(
        f"🔢 Выберите количество (1-{min(product['stock'], 12)}):",
        reply_markup=qty_kb(product_id, min(product["stock"], 12)),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("qty:"))
async def cb_qty(callback: CallbackQuery, state: FSMContext) -> None:
    _, product_id_s, qty_s = callback.data.split(":")
    product_id = int(product_id_s)
    qty = int(qty_s)
    product = get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return
    if qty > product["stock"]:
        await callback.answer("Недостаточно товара", show_alert=True)
        return

    price = float(product["price_usd"])
    total_usd = qty * price
    total_rub = total_usd * settings.rub_per_usd
    order_code = str(randint(10000000, 99999999))
    now_ts = int(time.time())
    deadline = now_ts + 15 * 60
    create_order(
        order_code=order_code,
        tg_user_id=callback.from_user.id,
        product_id=product_id,
        qty=qty,
        price_usd=price,
        total_usd=total_usd,
        total_rub=total_rub,
        payment_method="none",
        payment_deadline_ts=deadline,
        created_ts=now_ts,
    )

    text = (
        "💸 Выберите способ оплаты:\n\n"
        f"📃 Товар: {product['title']}\n"
        f"💰 Цена: {fmt_money(price)} $\n"
        f"📦 Кол-во: {qty} шт.\n"
        f"💡 Заказ: {order_code}\n"
        f"🕐 Итоговая сумма: {fmt_money(total_rub)} ₽"
    )
    await callback.message.edit_text(text, reply_markup=pay_kb(order_code))
    await callback.answer()


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(callback: CallbackQuery) -> None:
    _, method, order_code = callback.data.split(":")
    order = get_order(order_code)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    product = get_product(int(order["product_id"]))
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    if method in {"crypto_usdt", "crypto_ton"}:
        plus = settings.cryptobot_invoice_add_percent
        total_rub = float(order["total_rub"]) * (1 + plus / 100)
        asset = "USDT" if method == "crypto_usdt" else "TON"
        pay_link = f"https://t.me/CryptoBot?start=invoice-{order_code}-{asset}"
        payment_name = f"CryptoBot {asset}"
        text = (
            "➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"📃 Товар: {product['title']}\n"
            f"💰 Цена: {fmt_money(order['price_usd'])} $\n"
            f"📦 Кол-во: {order['qty']} шт.\n"
            f"💡 Заказ: {order['order_code']}\n"
            f"🕐 Итоговая сумма: {fmt_money(total_rub)} ₽\n"
            f"💲 Способ оплаты: {payment_name}\n"
            "➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"Для оплаты перейдите по ссылке:\n{pay_link}\n"
            f"(+%{plus})\n"
            "⏰ Время на оплату: 15 минут\n"
            "➖➖➖➖➖➖➖➖➖➖➖➖"
        )
    else:
        text = (
            "➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"📃 Товар: {product['title']}\n"
            f"💰 Цена: {fmt_money(order['price_usd'])} $\n"
            f"📦 Кол-во: {order['qty']} шт.\n"
            f"💡 Заказ: {order['order_code']}\n"
            f"🕐 Итоговая сумма: {fmt_money(order['total_rub'])} ₽\n"
            "💲 Способ оплаты: Bybit\n"
            "➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"Для оплаты пришлите деньги на Bybit UID {settings.bybit_uid}!\n\n"
            "⏰ Время на оплату: 15 минут\n"
            "➖➖➖➖➖➖➖➖➖➖➖➖"
        )

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Я оплатил", callback_data=f"paid:{order_code}")
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("paid:"))
async def cb_paid(callback: CallbackQuery) -> None:
    order_code = callback.data.split(":")[1]
    order = mark_order_paid(order_code)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    await send_paid_notify_to_admin(order_code)
    payloads = pop_payloads(int(order["product_id"]), int(order["qty"]))
    product = get_product(int(order["product_id"]))
    delivery_text = (product["delivery_text"] or "").strip() if product else ""

    if not payloads:
        text = "Платеж отмечен как полученный.\nТовар закончился, администратор скоро свяжется с вами."
        if delivery_text:
            text = f"{text}\n\n📨 Информация по выдаче:\n{delivery_text}"
        await callback.message.edit_text(f"{text}\n\n{ADMIN_FOOTER}")
    else:
        data = "\n\n".join(f"{idx + 1}) {v}" for idx, v in enumerate(payloads))
        extra = f"\n\n📨 Информация по выдаче:\n{delivery_text}" if delivery_text else ""
        await callback.message.edit_text(
            "✅ Оплата подтверждена!\nВаш товар:\n\n"
            f"{data}{extra}\n\n{ADMIN_FOOTER}"
        )
    await callback.answer("Спасибо за оплату!")


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    text = (
        "Админ-команды:\n"
        "/additem - добавить новый товар\n"
        "/addpayload <product_id> | <данные> - добавить 1 товарную единицу\n"
        "/setpayloads <product_id> | строка1 ; строка2 - заменить всю выдачу\n"
        "/setname <product_id> | новое название - поменять название\n"
        "/setdesc <product_id> | новое описание - поменять описание\n"
        "/setdelivery <product_id> | текст - сообщение после оплаты\n"
        "/setstock <product_id> <qty> - установить остаток\n"
        "/broadcast - рассылка по покупателям\n"
        "/order <код> - проверить заказ"
    )
    await message.answer(text)


@router.message(Command("additem"))
async def cmd_additem(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    await state.set_state(AdminFlow.add_product_wait)
    await message.answer(
        "Формат:\n"
        "Категория | Подкатегория | Название | ЦенаUSD | Тип | Остаток\n"
        "Пример:\n"
        "Другие сервисы | Telegram Premium | Telegram Premium 3m | 7.5 | ACC | 5"
    )


@router.message(AdminFlow.add_product_wait)
async def state_add_product(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = [x.strip() for x in (message.text or "").split("|")]
    if len(parts) != 6:
        await message.answer("Неверный формат.")
        return
    category, subcategory, title, price_s, ptype, stock_s = parts
    try:
        price = float(price_s.replace(",", "."))
        stock = int(stock_s)
    except ValueError:
        await message.answer("Цена/остаток указаны неверно.")
        return
    product_id = add_custom_product(category, subcategory, title, price, ptype, stock)
    await state.clear()
    await message.answer(f"✅ Товар добавлен. product_id={product_id}")


@router.message(Command("addpayload"))
async def cmd_addpayload(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    if not message.text:
        return
    rest = message.text.replace("/addpayload", "", 1).strip()
    if "|" not in rest:
        await message.answer("Формат: /addpayload <product_id> | <данные>")
        return
    pid_s, payload = [x.strip() for x in rest.split("|", 1)]
    try:
        pid = int(pid_s)
    except ValueError:
        await message.answer("product_id должен быть числом")
        return
    ok = add_product_payload(pid, payload)
    await message.answer("✅ Добавлено" if ok else "❌ Товар не найден")


@router.message(Command("setstock"))
async def cmd_setstock(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Формат: /setstock <product_id> <qty>")
        return
    try:
        pid = int(parts[1])
        qty = int(parts[2])
    except ValueError:
        await message.answer("product_id и qty должны быть числами")
        return
    product = get_product(pid)
    if not product:
        await message.answer("Товар не найден")
        return
    current = int(product["stock"])
    delta = qty - current
    from app.db import adjust_stock

    ok = adjust_stock(pid, delta)
    await message.answer("✅ Остаток обновлен" if ok else "❌ Ошибка обновления")


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
        await message.answer("product_id должен быть числом")
        return
    ok = update_product_content(pid, title=title)
    await message.answer("✅ Название обновлено" if ok else "❌ Товар не найден")


@router.message(Command("setdesc"))
async def cmd_setdesc(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    rest = (message.text or "").replace("/setdesc", "", 1).strip()
    if "|" not in rest:
        await message.answer("Формат: /setdesc <product_id> | <новое описание>")
        return
    pid_s, description = [x.strip() for x in rest.split("|", 1)]
    try:
        pid = int(pid_s)
    except ValueError:
        await message.answer("product_id должен быть числом")
        return
    ok = update_product_content(pid, description=description)
    await message.answer("✅ Описание обновлено" if ok else "❌ Товар не найден")


@router.message(Command("setdelivery"))
async def cmd_setdelivery(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    rest = (message.text or "").replace("/setdelivery", "", 1).strip()
    if "|" not in rest:
        await message.answer("Формат: /setdelivery <product_id> | <текст после оплаты>")
        return
    pid_s, delivery_text = [x.strip() for x in rest.split("|", 1)]
    try:
        pid = int(pid_s)
    except ValueError:
        await message.answer("product_id должен быть числом")
        return
    ok = update_product_content(pid, delivery_text=delivery_text)
    await message.answer("✅ Текст выдачи обновлен" if ok else "❌ Товар не найден")


@router.message(Command("setpayloads"))
async def cmd_setpayloads(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    rest = (message.text or "").replace("/setpayloads", "", 1).strip()
    if "|" not in rest:
        await message.answer("Формат: /setpayloads <product_id> | строка1 ; строка2 ; строка3")
        return
    pid_s, payloads_blob = [x.strip() for x in rest.split("|", 1)]
    try:
        pid = int(pid_s)
    except ValueError:
        await message.answer("product_id должен быть числом")
        return
    payloads = [item.strip() for item in payloads_blob.split(";") if item.strip()]
    ok = replace_product_payloads(pid, payloads)
    await message.answer(
        f"✅ Выдача заменена. Записей: {len(payloads)}" if ok else "❌ Товар не найден"
    )


@router.message(Command("order"))
async def cmd_order(message: Message) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Формат: /order <код>")
        return
    order = get_order(parts[1].strip())
    if not order:
        await message.answer("Заказ не найден")
        return
    await message.answer(
        f"Заказ {order['order_code']}\n"
        f"Статус: {order['payment_status']}\n"
        f"Метод: {order['payment_method']}\n"
        f"Сумма: {fmt_money(order['total_usd'])}$ ({fmt_money(order['total_rub'])}₽)"
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    await state.set_state(AdminFlow.broadcast_wait)
    await message.answer("Отправьте текст рассылки одним сообщением.")


@router.message(AdminFlow.broadcast_wait)
async def state_broadcast(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user.id not in settings.admin_ids:
        return
    await state.clear()
    text = message.text or ""
    user_ids = get_all_user_ids()
    ok_count = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            ok_count += 1
            await asyncio.sleep(0.03)
        except Exception:
            continue
    await message.answer(f"Рассылка завершена. Доставлено: {ok_count}/{len(user_ids)}")


async def run_bot() -> None:
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await bot.delete_webhook(drop_pending_updates=True)
    await setup_bot_commands(bot)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    init_db()
    asyncio.run(run_bot())
