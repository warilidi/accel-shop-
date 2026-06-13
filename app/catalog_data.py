from __future__ import annotations

PRODUCT_TYPE_HINTS: dict[str, str] = {
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
                    p("[CDK] ChatGPT Plus 1m (NW)", 5, "CDK"),
                    p("[CDK] ChatGPT Plus 1m", 19, "CDK"),
                    p("[CDK] ChatGPT Plus 1m Turkey", 20, "CDK"),
                    p("[ACC] ChatGPT Plus 1m (W10D)", 3.5, "ACC"),
                    p("[ACC] ChatGPT Plus 1m (NW)", 3.5, "ACC"),
                    p("[ACC] ChatGPT Plus 1m (FW)", 5, "ACC"),
                    p("[CDK] ChatGPT Plus 1m (FW)", 2.5, "CDK"),
                    p("[Mail] ChatGPT Plus 1m (FW)", 6, "Mail"),
                    p("[ACC] ChatGPT Pro 1m", 5, "ACC"),
                    p("[ACC] ChatGPT Go 6m", 10, "ACC"),
                    p("[ACC] ChatGPT Pro X5 (FW)", 85, "ACC"),
                    p("[ACC] ChatGPT Pro X20 (FW)", 140, "ACC"),
                    p("[ACC] ChatGPT Pro X5 (NW)", 70, "ACC"),
                    p("[ACC] ChatGPT Pro X20 (NW)", 50, "ACC"),
                    p("[CDK] ChatGPT Pro X5 (FW)", 75, "CDK"),
                    p("[CDK] ChatGPT Pro X20 (FW)", 140, "CDK"),
                ],
            },
            {
                "name": "Perplexity",
                "products": [
                    p("[Code] Perplexity Pro 12m", 9, "Code"),
                    p("[ACC] Perplexity 12m Pro", 5.5, "ACC"),
                    p("[Оф Подписка] Perplexity Pro 1m", 33, "Оф Подписка"),
                    p("[ACC] Perplexity Pro 1m", 27, "ACC"),
                ],
            },
            {
                "name": "Grok",
                "products": [
                    p("[ACC] Grok Super 1m (W14D)", 12, "ACC"),
                    p("[ACC] Grok Super 12m", 55, "ACC"),
                    p("[ACC] Grok Super 3m", 20, "ACC"),
                    p("[ACC] Grok Super 5m", 35, "ACC"),
                    p("[CDK] Grok Super 2m", 18, "CDK"),
                    p("[CDK] Grok Super 1m", 15, "CDK"),
                    p("[Со входом] Grok Super 12m", 110, "Со входом"),
                ],
            },
            {
                "name": "Gemini",
                "products": [
                    p("[ACC] Gemini Pixel Pro 12m (NW)", 2.5, "ACC"),
                    p("[LINK] Gemini Pro +5TB 18m", 3.5, "LINK"),
                    p("Gemini Pro 3m", 1),
                    p("Gemini Pro 4m +5TB 4m", 1),
                    p("[ACC] Google AI Pro 12m Old Gmail", 3, "ACC"),
                    p("Account Verification", 3, "Verify"),
                ],
            },
            {
                "name": "Claude",
                "products": [
                    p("[Link] Claude Pro 1m on your E-Mail", 17, "Link"),
                    p("[Gift] Claude Pro 1m", 18.5, "Gift"),
                    p("[CDK] Claude Pro 1m", 18.5, "CDK"),
                    p("[CDK] Claude Max 5x", 60, "CDK"),
                    p("[CDK] Claude Max 20x", 104, "CDK"),
                    p("[ACC] Claude Max 20x", 110, "ACC"),
                ],
            },
            {
                "name": "Cursor",
                "products": [
                    p("[Оф подписка] Cursor Pro 1m", 36, "Оф подписка"),
                    p("[Оф подписка] Cursor Pro+ 1m", 77, "Оф подписка"),
                    p("[Оф подписка] Cursor Ultra 1m", 230, "Оф подписка"),
                    p("[Оф подписка] Cursor Teams 1m", 77, "Оф подписка"),
                    p("[ACC] Cursor Pro 1m", 22.5, "ACC"),
                    p("[ACC] Cursor Edu Pro 12m", 34, "ACC"),
                    p("[ACC] Cursor Pro 1m", 20, "ACC"),
                    p("[ACC] Cursor Ultra 1m", 200, "ACC"),
                    p("[ACC] Cursor Ultra 1m (NW)", 145, "ACC"),
                ],
            },
            {
                "name": "Suno AI",
                "products": [
                    p("[Со входом] Suno AI Pro 1m", 24, "Со входом"),
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
                    p("Spotify Individual 1m", 6),
                    p("Spotify Individual 3m", 17),
                    p("Spotify Individual 6m", 25),
                    p("Spotify Individual 12m", 33),
                    p("Spotify Duo 1m", 5),
                    p("Spotify Duo 3m", 20),
                    p("Spotify Duo 6m", 28.5),
                    p("Spotify Duo 12m", 45),
                    p("[Приглашение] Spotify Family 1m", 3.5, "Приглашение"),
                    p("[Приглашение] Spotify Family 3m", 7, "Приглашение"),
                    p("[Приглашение] Spotify Family 6m", 13, "Приглашение"),
                    p("[Приглашение] Spotify Family 12m", 18, "Приглашение"),
                    p("[На ваш акк] Spotify Family 1m", 7, "На ваш акк"),
                ],
            },
            {
                "name": "Netflix",
                "products": [
                    p("[ACC] Netflix Premium 4K 1m", 3, "ACC"),
                    p("[ACC] Netflix Premium 4K 3m", 7, "ACC"),
                    p("[ACC] Netflix Premium 4K 6m", 13.5, "ACC"),
                    p("[ACC] Netflix Premium 4K 12m", 18.5, "ACC"),
                ],
            },
            {"name": "Discord", "products": [p("Discord Boost 1m", 1.3, "Boost")]},
            {"name": "Почты Gmail", "products": [p("Gmail Account", 0.5, "ACC")]},
            {
                "name": "YouTube",
                "products": [
                    p("[Оф подписка] YouTube Premium 12m", 37, "Оф подписка"),
                    p("[ACC] YouTube Premium 1m", 1, "ACC"),
                ],
            },
            {"name": "Picsart", "products": [p("Picsart Gold 12m", 11, "ACC")]},
            {
                "name": "Amazon Prime",
                "products": [p("Amazon Prime 1m", 6, "ACC"), p("Amazon Prime 6m", 15, "ACC")],
            },
            {"name": "CapCut", "products": [p("CapCut Pro 1m", 2, "ACC")]},
            {
                "name": "Apple",
                "products": [
                    p("Apple Music 1m", 5.5),
                    p("iPad Сертификат", 15),
                    p("Обычный Apple сертификат", 15),
                    p("Моментальный Apple сертификат", 22),
                ],
            },
            {
                "name": "Windows",
                "products": [
                    p("[Key] Windows Key", 1, "Key"),
                    p("[E-Mail] Adobe Creative 3m on your E-Mail", 12, "E-Mail"),
                ],
            },
            {"name": "Steam", "products": [p("Steam 0.016$ : 1 rub", 0.016, "Пополнение")]},
            {"name": "NordVPN", "products": [p("Nord VPN", 5, "ACC")]},
            {
                "name": "Canva",
                "products": [
                    p("Canva Edu 12m", 3, "ACC"),
                    p("Canva Reseller Panel up to 500 members", 13, "ACC"),
                ],
            },
            {"name": "Kiro", "products": [p("Kiro Pro 1m", 3.5, "ACC")]},
            {"name": "LinkedIn", "products": [p("LinkedIn Premium Career 3m", 1, "ACC")]},
            {"name": "Lovable", "products": [p("Lovable Pro 1m", 2, "ACC")]},
            {"name": "Veo 3", "products": [p("Veo 3 Ultra 25k Credits (Fw24h)", 2, "ACC")]},
            {"name": "Notion", "products": [p("Notion Business 3m (Link)", 4, "Link")]},
        ],
    },
    {
        "name": "Накрутка",
        "items": [],
    },
    {
        "name": "Игры",
        "items": [],
    },
]
