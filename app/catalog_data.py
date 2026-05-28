from __future__ import annotations

PRODUCT_TYPE_HINTS: dict[str, str] = {
    "CDK": "CD Keys: ключ и активация через сайт (обычно с временным входом).",
    "ACC": "Готовый аккаунт с активной подпиской.",
    "Code": "Код для активации подписки.",
    "Оф подписка": "Официальная подписка напрямую на сервис.",
    "Со входом": "Активация подписки с входом в аккаунт.",
    "Link": "Активация подписки по ссылке-приглашению.",
    "✅": "Верификация аккаунта/подписки.",
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
}


def p(title: str, price_usd: float, product_type: str | None = None, stock: int = 20) -> dict:
    return {
        "title": title,
        "price_usd": price_usd,
        "product_type": product_type or "",
        "stock": stock,
    }


DEFAULT_CATALOG = [
    {
        "name": "Нейросети",
        "items": [
            {
                "name": "ChatGPT",
                "products": [
                    p("🤖 ChatGPT Plus 1m (NW)", 5, "CDK"),
                    p("🤖 ChatGPT Plus 1m", 19, "CDK"),
                    p("🤖 ChatGPT Plus 1m Turkey", 20, "CDK"),
                    p("🤖 ChatGPT Plus 1m (W10D)", 4, "ACC"),
                    p("🤖 ChatGPT Plus 1m (NW)", 3.5, "ACC"),
                    p("🤖 ChatGPT Pro 1m", 5, "ACC"),
                    p("🤖 ChatGPT Go 6m", 10, "ACC"),
                ],
            },
            {
                "name": "Perplexity",
                "products": [
                    p("🤖 Perplexity Pro 12m", 9, "Code"),
                    p("🤖 Perplexity 12m Pro", 5.5, "ACC"),
                    p("🤖 Perplexity Pro 1m", 33, "Оф Подписка"),
                    p("🤖 Perplexity Pro 1m", 27, "ACC"),
                ],
            },
            {
                "name": "Grok",
                "products": [
                    p("🤖 Grok Super 1m (W14D)", 12, "ACC"),
                    p("🤖 Grok Super 12m", 55, "ACC"),
                    p("🤖 Grok Super 3m", 20, "ACC"),
                    p("🤖 Grok Super 5m", 35, "ACC"),
                    p("🤖 Grok Super 2m", 18, "CDK"),
                    p("🤖 Grok Super 1m", 15, "CDK"),
                    p("🤖 Grok Super 12m", 110, "Со входом"),
                ],
            },
            {
                "name": "Gemini",
                "products": [
                    p("🤖 Gemini Pixel Pro 12m (NW)", 2.5, "ACC"),
                    p("🤖 Gemini Pro +5TB ☁ 18m", 3.5, "LINK"),
                    p("🤖 Gemini Pro 3m", 1),
                    p("🤖 Gemini Pro 4m +5TB ☁ 4m", 1),
                    p("🤖 Google AI Pro 12m Old Gmail", 3, "ACC"),
                    p("🤖 Account Verification", 3, "✅"),
                ],
            },
            {
                "name": "Claude",
                "products": [
                    p("🤖 Claude Pro 1m on your E-Mail", 17, "Link"),
                    p("🤖 Claude Pro 1m", 18.5, "Gift"),
                    p("🤖 Claude Pro 1m", 18.5, "CDK"),
                    p("🤖 Claude Max 5x", 60, "CDK"),
                    p("🤖 Claude Max 20x", 104, "CDK"),
                    p("🤖 Claude Max 20x", 110, "ACC"),
                ],
            },
            {
                "name": "Cursor",
                "products": [
                    p("✴️ Cursor Pro 1m", 36, "Оф подписка"),
                    p("✴️ Cursor Pro+ 1m", 77, "Оф подписка"),
                    p("✴️ Cursor Ultra 1m", 230, "Оф подписка"),
                    p("✴️ Cursor Teams 1m", 77, "Оф подписка"),
                    p("✴️ Cursor Pro 1m", 22.5, "ACC"),
                    p("✴️ Cursor Edu Pro 12m", 34, "ACC"),
                    p("✴️ Cursor Pro 1m", 20, "ACC"),
                    p("✴️ Cursor Ultra 1m", 200, "ACC"),
                    p("✴️ Cursor Ultra 1m (NW)", 145, "ACC"),
                ],
            },
            {
                "name": "Suno AI",
                "products": [
                    p("Suno AI Pro 1m", 24, "Со входом"),
                ],
            },
        ],
    },
    {
        "name": "Другие сервисы",
        "items": [
            {
                "name": "Spotify",
                "products": [
                    p("✴️ Spotify Individual 1m", 6),
                    p("✴️ Spotify Individual 3m", 17),
                    p("✴️ Spotify Individual 6m", 25),
                    p("✴️ Spotify Individual 12m", 33),
                    p("✴️ Spotify Duo 1m", 5),
                    p("✴️ Spotify Duo 3m", 20),
                    p("✴️ Spotify Duo 6m", 28.5),
                    p("✴️ Spotify Duo 12m", 45),
                    p("✴️ Spotify Family 1m", 3.5, "Приглашение"),
                    p("✴️ Spotify Family 3m", 7, "Приглашение"),
                    p("✴️ Spotify Family 6m", 13, "Приглашение"),
                    p("✴️ Spotify Family 12m", 18, "Приглашение"),
                    p("✴️ Spotify Family 1m", 7, "На ваш акк"),
                ],
            },
            {
                "name": "Netflix",
                "products": [
                    p("✴️ Netflix Premium 4K 1m", 3, "ACC"),
                    p("✴️ Netflix Premium 4K 3m", 7, "ACC"),
                    p("✴️ Netflix Premium 4K 6m", 13.5, "ACC"),
                    p("✴️ Netflix Premium 4K 12m", 18.5, "ACC"),
                ],
            },
            {"name": "Discord", "products": [p("🐸 Discord Boost 1m", 1.3, "Boost")]},
            {"name": "Почты Gmail", "products": [p("✴️ Gmail Account", 0.5, "ACC")]},
            {
                "name": "YouTube",
                "products": [
                    p("🎞 YouTube Premium 12m", 37, "Оф подписка"),
                    p("🎞 YouTube Premium 1m", 1, "ACC"),
                ],
            },
            {"name": "Picsart", "products": [p("Picsart Gold 12m", 11, "ACC")]},
            {
                "name": "Amazon Prime",
                "products": [p("❤️ Amazon Prime 1m", 6, "ACC"), p("❤️ Amazon Prime 6m", 15, "ACC")],
            },
            {"name": "CapCut", "products": [p("🖼 CapCut Pro 1m", 2, "ACC")]},
            {
                "name": "Apple",
                "products": [
                    p("🍎 Apple Music 1m", 5.5),
                    p("🍎 iPad Сертификат", 15),
                    p("🍎 Обычный Apple сертификат", 15),
                    p("🍎 Моментальный Apple сертификат", 22),
                ],
            },
            {
                "name": "Windows",
                "products": [
                    p("👩‍💻 Windows Key", 1, "Key"),
                    p("✴️ Adobe Creative 3m on your E-Mail", 12, "E-Mail"),
                ],
            },
            {"name": "Steam", "products": [p("Steam 0.016$ : 1 rub", 0.016, "Пополнение")]},
        ],
    },
]
