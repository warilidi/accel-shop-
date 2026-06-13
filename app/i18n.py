from __future__ import annotations

from typing import Any

DEFAULT_LANG = "ru"
SUPPORTED_LANGS = ("ru", "en")


def normalize_lang(lang: str | None) -> str:
    if lang in SUPPORTED_LANGS:
        return lang
    return DEFAULT_LANG


BUTTON_TEXTS: dict[str, dict[str, str]] = {
    "ru": {
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
        "pay": "Оплатить",
        "check_payment": "Проверить оплату",
        "subscribe": "Подписаться на канал",
        "subscribed": "Я подписался",
        "write_admin": "Написать админу",
    },
    "en": {
        "catalog": "Products & Services",
        "balance": "Balance",
        "wholesale": "Wholesale",
        "help": "Help",
        "profile": "Profile",
        "rules": "Rules",
        "crypto_usdt": "CryptoBot USDT",
        "crypto_ton": "CryptoBot TON",
        "bybit": "Bybit",
        "balance_pay": "Balance",
        "topup": "Top up balance",
        "history": "History",
        "back": "Back",
        "buy": "Buy",
        "confirm_paid": "I have paid",
        "agree": "Terms of Service",
        "privacy": "Privacy Policy",
        "pay": "Pay",
        "check_payment": "Check payment",
        "subscribe": "Subscribe to channel",
        "subscribed": "I subscribed",
        "write_admin": "Contact admin",
    },
}

PRODUCT_TYPE_HINTS_I18N: dict[str, dict[str, str]] = {
    "ru": {
        "CDK": "CD Keys: ключ и активация через сайт (обычно с временным входом).",
        "ACC": "Готовый аккаунт с активной подпиской.",
        "Code": "Код для активации подписки.",
        "Оф подписка": "Официальная подписка напрямую на сервис.",
        "Со входом": "Активация подписки с входом в аккаунт.",
        "Link": "Активация подписки по ссылке-приглашению.",
        "Verify": "Верификация аккаунта/подписки.",
        "Gift": "Подарок подписки на ваш аккаунт по почте.",
        "Приглашение": "Подключение по приглашению на почту.",
        "На ваш акк": "Подключение подписки на ваш личный аккаунт.",
        "Key": "Ключ активации продукта.",
        "E-Mail": "Активация/доступ через вашу почту.",
        "Boost": "Услуга буста для Discord.",
        "Пополнение": "Баланс пополняется по указанному курсу.",
        "Оф Подписка": "Официальная подписка напрямую на сервис.",
        "LINK": "Активация подписки ссылкой.",
        "CDK ": "CD Keys: ключ и активация через сайт (обычно с временным входом).",
        "Mail": "Активация через почту.",
    },
    "en": {
        "CDK": "CD Keys: activation key via website (usually with temporary login).",
        "ACC": "Ready account with an active subscription.",
        "Code": "Subscription activation code.",
        "Оф подписка": "Official subscription directly on the service.",
        "Со входом": "Subscription activation with account login.",
        "Link": "Subscription activation via invite link.",
        "Verify": "Account/subscription verification.",
        "Gift": "Subscription gift to your account via email.",
        "Приглашение": "Connection via email invitation.",
        "На ваш акк": "Subscription added to your personal account.",
        "Key": "Product activation key.",
        "E-Mail": "Activation/access via your email.",
        "Boost": "Discord boost service.",
        "Пополнение": "Balance top-up at the listed rate.",
        "Оф Подписка": "Official subscription directly on the service.",
        "LINK": "Subscription activation via link.",
        "CDK ": "CD Keys: activation key via website (usually with temporary login).",
        "Mail": "Activation via email.",
    },
}

TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        "lang.choose": "🌐 <b>Выберите язык</b>\nChoose your language:",
        "lang.saved": "Язык сохранён",
        "shop.footer": "— Админ/Связь/Опт — @Dolzu",
        "sub.welcome": (
            "👋 Добро пожаловать в <b>Accel Shop</b>!\n\n"
            "Для пользования ботом подпишитесь на наш информационный канал:"
        ),
        "sub.locked": (
            "🔒 <b>Доступ закрыт</b>\n\n"
            "Для использования магазина необходимо подписаться на наш канал:"
        ),
        "sub.alert": "Подпишитесь на канал!",
        "sub.not_yet": "❌ Вы ещё не подписались на канал. Подпишитесь и нажмите кнопку снова.",
        "sub.ok": "✅ Отлично! Добро пожаловать!",
        "start.text": (
            "👋 Приветствую в <b>Accel Shop</b>!\n\n"
            "🏪 Это цифровой магазин подписок на нейросети и популярные сервисы.\n"
            "Здесь аккаунты, подписки, сертификаты и многое другое!\n\n"
            "👇 Нажмите кнопку ниже чтобы начать.\n\n"
            "Информационный канал: @Accel_Shop"
        ),
        "menu.main": "🏠 Главное меню:",
        "menu.catalog": "🛍️ <b>Товары и услуги</b>\nВыберите раздел:",
        "menu.categories": "📂 Выберите раздел:",
        "menu.services": "📂 Выберите сервис:",
        "menu.balance": (
            "💳 <b>Ваш баланс</b>\n"
            "{balance_usd} $ / {balance_rub} ₽\n\n"
            "Используйте баланс для быстрых покупок без повторной оплаты."
        ),
        "menu.balance_topup": (
            "💳 <b>Пополнение баланса</b>\n\n"
            "Свяжитесь с администратором для пополнения баланса:\n"
            "@Dolzu\n\n"
            "Укажите желаемую сумму."
        ),
        "menu.balance_history_empty": "📜 <b>История заказов</b>\n\nНет заказов.",
        "menu.balance_history_title": "📜 <b>Последние 10 заказов:</b>\n",
        "menu.balance_history_paid": "✅ Оплачено",
        "menu.balance_history_pending": "⏳ Ожидание",
        "menu.rules": (
            "📚 <b>Правила и соглашения</b>\n\n"
            "Перед использованием магазина ознакомьтесь с документами:"
        ),
        "menu.profile": (
            "👤 <b>Ваш профиль</b>\n\n"
            "🆔 ID: <code>{uid}</code>\n"
            "👤 Имя: {full_name}\n"
            "📧 Username: {username}\n\n"
            "🛍️ Заказов выполнено: <b>{orders_count}</b>\n"
            "💰 Потрачено: <b>${spent}</b>\n"
            "💳 На балансе: <b>${balance_usd}</b> / <b>{balance_rub}₽</b>"
        ),
        "profile.username_missing": "не указан",
        "catalog.pick_product": "Выберите товар:",
        "product.not_found": "Товар не найден",
        "product.out_of_stock": "К сожалению, товара нет в наличии",
        "product.hint_default": "Уточняйте у администратора.",
        "product.in_stock": "В наличии",
        "product.no_stock": "Нет в наличии",
        "product.type_missing": "не указан",
        "product.out_of_stock_note": " · нет в наличии",
        "product.card": (
            "📦 <b>{title}</b>\n"
            "{desc}"
            "\n💰 Цена: <b>${price}</b>\n"
            "📊 Остаток: {stock} шт.\n"
            "🧩 Тип: {ptype}\n"
            "ℹ️ {hint}\n"
            "📌 {status}\n\n"
            "{footer}"
        ),
        "product.desc_line": "📝 {desc}\n",
        "qty.choose": "🔢 Выберите количество (1–{max_qty}):",
        "order.title": "💸 <b>Оформление заказа</b>\n➖➖➖➖➖➖➖➖➖\n",
        "order.body": (
            "📦 Товар: {title}\n"
            "🔢 Кол-во: {qty} шт.\n"
            "💰 Цена за шт.: {price} $\n"
            "💵 Итого: {total_usd} $ / {total_rub} ₽\n"
            "🔖 Код заказа: <code>{code}</code>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "Выберите способ оплаты:"
        ),
        "order.not_found": "Заказ не найден",
        "order.already_paid": "Заказ уже оплачен!",
        "order.insufficient_balance": "Недостаточно средств на балансе.\nТребуется: ${need}, у вас: ${have}",
        "order.withdraw_error": "Ошибка при снятии средств с баланса",
        "order.thanks": "Спасибо за покупку! 🎉",
        "order.stock_empty": (
            "⏳ Оплата получена, спасибо!\n\n"
            "Товар временно закончился — администратор свяжется с вами в ближайшее время."
        ),
        "order.paid_ok": "✅ <b>Оплата подтверждена!</b>\n\nВаш товар:\n\n{items}",
        "order.delivery": "\n\n📨 <b>Инструкция по активации:</b>\n{note}",
        "pay.crypto": (
            "💳 <b>Оплата через CryptoBot</b>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "📦 Товар: {title}\n"
            "🔢 Кол-во: {qty} шт.\n"
            "💵 Сумма: {amount} (+{fee}% комиссия)\n"
            "🔖 Код заказа: <code>{code}</code>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "Перейдите для оплаты:\n{link}\n\n"
            "⏰ Время на оплату: 15 минут\n"
            "🔄 Оплата будет подтверждена автоматически."
        ),
        "pay.crypto_fallback": (
            "💳 <b>Оплата через CryptoBot</b>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "📦 Товар: {title}\n"
            "🔢 Кол-во: {qty} шт.\n"
            "💵 Сумма: {amount} ₽ (+{fee}% комиссия)\n"
            "🔖 Код заказа: <code>{code}</code>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "Перейдите для оплаты:\n{link}\n\n"
            "⏰ Время на оплату: 15 минут"
        ),
        "pay.bybit": (
            "🔶 <b>Оплата через Bybit</b>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "📦 Товар: {title}\n"
            "🔢 Кол-во: {qty} шт.\n"
            "💵 Сумма: {total_rub} ₽\n"
            "🔖 Код заказа: <code>{code}</code>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "Переведите на Bybit UID: <code>{uid}</code>\n\n"
            "⏰ Время на оплату: 15 минут"
        ),
        "pay.check_unavailable": "Автоматическая проверка недоступна",
        "pay.check_error": "Ошибка проверки. Попробуйте позже.",
        "pay.check_ok": "Оплата подтверждена! 🎉",
        "pay.check_expired": "Инвойс истёк. Создайте новый заказ.",
        "pay.check_pending": "Оплата ещё не получена. Попробуйте позже.",
        "pay.insufficient_stock": "Недостаточно товара на складе",
    },
    "en": {
        "lang.choose": "🌐 <b>Choose your language</b>\nВыберите язык:",
        "lang.saved": "Language saved",
        "shop.footer": "— Admin/Contact/Wholesale — @Dolzu",
        "sub.welcome": (
            "👋 Welcome to <b>Accel Shop</b>!\n\n"
            "Subscribe to our info channel to use the bot:"
        ),
        "sub.locked": (
            "🔒 <b>Access restricted</b>\n\n"
            "Please subscribe to our channel to use the shop:"
        ),
        "sub.alert": "Please subscribe to the channel!",
        "sub.not_yet": "❌ You are not subscribed yet. Subscribe and tap the button again.",
        "sub.ok": "✅ Great! Welcome!",
        "start.text": (
            "👋 Welcome to <b>Accel Shop</b>!\n\n"
            "🏪 A digital store for AI subscriptions and popular services.\n"
            "Accounts, subscriptions, gift cards, and more!\n\n"
            "👇 Tap the button below to get started.\n\n"
            "Info channel: @Accel_Shop"
        ),
        "menu.main": "🏠 Main menu:",
        "menu.catalog": "🛍️ <b>Products & Services</b>\nChoose a section:",
        "menu.categories": "📂 Choose a section:",
        "menu.services": "📂 Choose a service:",
        "menu.balance": (
            "💳 <b>Your balance</b>\n"
            "{balance_usd} $ / {balance_rub} ₽\n\n"
            "Use your balance for quick purchases without paying again."
        ),
        "menu.balance_topup": (
            "💳 <b>Top up balance</b>\n\n"
            "Contact the administrator to top up your balance:\n"
            "@Dolzu\n\n"
            "Specify the amount you need."
        ),
        "menu.balance_history_empty": "📜 <b>Order history</b>\n\nNo orders yet.",
        "menu.balance_history_title": "📜 <b>Last 10 orders:</b>\n",
        "menu.balance_history_paid": "✅ Paid",
        "menu.balance_history_pending": "⏳ Pending",
        "menu.rules": (
            "📚 <b>Rules & agreements</b>\n\n"
            "Please read the documents before using the shop:"
        ),
        "menu.profile": (
            "👤 <b>Your profile</b>\n\n"
            "🆔 ID: <code>{uid}</code>\n"
            "👤 Name: {full_name}\n"
            "📧 Username: {username}\n\n"
            "🛍️ Completed orders: <b>{orders_count}</b>\n"
            "💰 Spent: <b>${spent}</b>\n"
            "💳 Balance: <b>${balance_usd}</b> / <b>{balance_rub}₽</b>"
        ),
        "profile.username_missing": "not set",
        "catalog.pick_product": "Choose a product:",
        "product.not_found": "Product not found",
        "product.out_of_stock": "Sorry, this product is out of stock",
        "product.hint_default": "Contact the administrator for details.",
        "product.in_stock": "In stock",
        "product.no_stock": "Out of stock",
        "product.type_missing": "not specified",
        "product.out_of_stock_note": " · out of stock",
        "product.card": (
            "📦 <b>{title}</b>\n"
            "{desc}"
            "\n💰 Price: <b>${price}</b>\n"
            "📊 Stock: {stock} pcs.\n"
            "🧩 Type: {ptype}\n"
            "ℹ️ {hint}\n"
            "📌 {status}\n\n"
            "{footer}"
        ),
        "product.desc_line": "📝 {desc}\n",
        "qty.choose": "🔢 Choose quantity (1–{max_qty}):",
        "order.title": "💸 <b>Checkout</b>\n➖➖➖➖➖➖➖➖➖\n",
        "order.body": (
            "📦 Product: {title}\n"
            "🔢 Qty: {qty} pcs.\n"
            "💰 Price per item: {price} $\n"
            "💵 Total: {total_usd} $ / {total_rub} ₽\n"
            "🔖 Order code: <code>{code}</code>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "Choose a payment method:"
        ),
        "order.not_found": "Order not found",
        "order.already_paid": "Order is already paid!",
        "order.insufficient_balance": "Insufficient balance.\nRequired: ${need}, you have: ${have}",
        "order.withdraw_error": "Failed to withdraw from balance",
        "order.thanks": "Thank you for your purchase! 🎉",
        "order.stock_empty": (
            "⏳ Payment received, thank you!\n\n"
            "The product is temporarily out of stock — an administrator will contact you soon."
        ),
        "order.paid_ok": "✅ <b>Payment confirmed!</b>\n\nYour product:\n\n{items}",
        "order.delivery": "\n\n📨 <b>Activation instructions:</b>\n{note}",
        "pay.crypto": (
            "💳 <b>Pay via CryptoBot</b>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "📦 Product: {title}\n"
            "🔢 Qty: {qty} pcs.\n"
            "💵 Amount: {amount} (+{fee}% fee)\n"
            "🔖 Order code: <code>{code}</code>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "Go to payment:\n{link}\n\n"
            "⏰ Time to pay: 15 minutes\n"
            "🔄 Payment will be confirmed automatically."
        ),
        "pay.crypto_fallback": (
            "💳 <b>Pay via CryptoBot</b>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "📦 Product: {title}\n"
            "🔢 Qty: {qty} pcs.\n"
            "💵 Amount: {amount} ₽ (+{fee}% fee)\n"
            "🔖 Order code: <code>{code}</code>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "Go to payment:\n{link}\n\n"
            "⏰ Time to pay: 15 minutes"
        ),
        "pay.bybit": (
            "🔶 <b>Pay via Bybit</b>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "📦 Product: {title}\n"
            "🔢 Qty: {qty} pcs.\n"
            "💵 Amount: {total_rub} ₽\n"
            "🔖 Order code: <code>{code}</code>\n"
            "➖➖➖➖➖➖➖➖➖\n"
            "Transfer to Bybit UID: <code>{uid}</code>\n\n"
            "⏰ Time to pay: 15 minutes"
        ),
        "pay.check_unavailable": "Automatic check is unavailable",
        "pay.check_error": "Check failed. Please try again later.",
        "pay.check_ok": "Payment confirmed! 🎉",
        "pay.check_expired": "Invoice expired. Please create a new order.",
        "pay.check_pending": "Payment not received yet. Please try again later.",
        "pay.insufficient_stock": "Not enough stock",
    },
}


def t(key: str, lang: str | None = None, **kwargs: Any) -> str:
    lang = normalize_lang(lang)
    template = TEXTS.get(lang, TEXTS[DEFAULT_LANG]).get(key)
    if template is None:
        template = TEXTS[DEFAULT_LANG].get(key, key)
    return template.format(**kwargs) if kwargs else template


def button_text(button_id: str, lang: str | None = None) -> str:
    lang = normalize_lang(lang)
    return BUTTON_TEXTS.get(lang, BUTTON_TEXTS[DEFAULT_LANG]).get(button_id, button_id)


def product_type_hint(product_type: str, lang: str | None = None) -> str:
    lang = normalize_lang(lang)
    hints = PRODUCT_TYPE_HINTS_I18N.get(lang, PRODUCT_TYPE_HINTS_I18N[DEFAULT_LANG])
    return hints.get(product_type, t("product.hint_default", lang))
