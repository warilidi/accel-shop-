# Премиум эмодзи Telegram с их ID
# Получены через @Emoji_ID_Extractor_bot

PREMIUM_EMOJI = {
    "chatgpt":    "5206660927339924387",     # ChatGPT
    "perplexity": "5206188648441091805",    # Perplexity
    "grok":       "5190533058855475557",    # Грок
    "gemini":     "5206660927339924387",    # Гемини
    "claude":     "5208665212483310136",    # Клауд
    "cursor":     "5190540811271444031",    # Курсор
    "suno":       "5188184931515273709",    # Сuno
    "spotify":    "5247139001239891698",    # Спотифай
    "netflix":    "5246799187722400555",    # Нетфликс
    "discord":    "5249197140978200533",    # Дискорд
    "gmail":      "5307602416961609760",    # Гмаил
    "youtube":    "5248965805449700363",    # Ютуб
    "pixeart":    "5323670946177901423",    # Пиксарт
    "amazon":     "5194993116104375139",    # Амазон
    "capcut":     "5246889012668426695",    # Капкут
    "apple":      "5398012024003246287",    # Апл
    "windows":    "5420334850236246677",    # Виндоус
    "steam":      "5244814844112167852",    # Стим
    "adobe":      "5305721281415505693",    # Адоб
}

# Маппинг названий товаров/типов на ключи эмодзи
PRODUCT_TYPE_EMOJI = {
    "chatgpt":    ("chatgpt", "💬"),
    "perplexity": ("perplexity", "🔍"),
    "grok":       ("grok", "🧠"),
    "gemini":     ("gemini", "✨"),
    "claude":     ("claude", "🤖"),
    "cursor":     ("cursor", "⌨️"),
    "suno":       ("suno", "🎵"),
    "spotify":    ("spotify", "🎵"),
    "netflix":    ("netflix", "📺"),
    "discord":    ("discord", "💬"),
    "gmail":      ("gmail", "📧"),
    "youtube":    ("youtube", "▶️"),
    "pixeart":    ("pixeart", "🎨"),
    "amazon":     ("amazon", "🛍️"),
    "capcut":     ("capcut", "✂️"),
    "apple":      ("apple", "🍎"),
    "windows":    ("windows", "🪟"),
    "steam":      ("steam", "🎮"),
    "adobe":      ("adobe", "📐"),
}


def premium_emoji(emoji_key: str, fallback: str = "📦") -> str:
    """
    Возвращает HTML-тег с премиум-эмодзи для Telegram
    
    Аргументы:
        emoji_key: ключ из PREMIUM_EMOJI
        fallback: стандартный эмодзи если ID не найден
    
    Возвращает:
        HTML-строка с тегом <tg-emoji> или обычный эмодзи
    
    Пример:
        premium_emoji("chatgpt", "💬")  # Возвращает <tg-emoji emoji-id="...">💬</tg-emoji>
    """
    emoji_id = PREMIUM_EMOJI.get(emoji_key.lower())
    if not emoji_id:
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def get_product_emoji(product_name: str) -> tuple[str, str]:
    """
    Получает ключ эмодзи и fallback по названию товара
    
    Аргументы:
        product_name: название товара
    
    Возвращает:
        кортеж (emoji_key, fallback_emoji)
    """
    product_lower = product_name.lower()
    
    # Ищем точное совпадение
    for key, (emoji_key, fallback) in PRODUCT_TYPE_EMOJI.items():
        if key in product_lower:
            return emoji_key, fallback
    
    # Если не найдено, возвращаем default
    return "chatgpt", "📦"


def get_product_emoji_html(product_name: str) -> str:
    """
    Возвращает готовый HTML-тег премиум-эмодзи для продукта

    Аргументы:
        product_name: название товара

    Возвращает:
        HTML-строка с премиум-эмодзи
    """
    emoji_key, fallback = get_product_emoji(product_name)
    return premium_emoji(emoji_key, fallback)


# custom_emoji_id для иконок кнопок (icon_custom_emoji_id), по подстроке названия товара.
# Порядок важен: проверяется сверху вниз, первое совпадение выигрывает.
BUTTON_ICON_BY_TITLE = [
    ("nordvpn",  "5239963889004732575"),
    ("canva",    "5309754771102525647"),
    ("kiro",     "5239963889004732575"),
    ("linkedin", "5239963889004732575"),
    ("lovable",  "5239963889004732575"),
    ("veo 3",    "5206660927339924387"),
    ("veo3",     "5206660927339924387"),
]


def get_button_icon_id(product_title: str) -> str | None:
    """
    Возвращает icon_custom_emoji_id для кнопки товара по названию,
    либо None если совпадение не найдено.
    """
    title_lower = product_title.lower()
    for key, emoji_id in BUTTON_ICON_BY_TITLE:
        if key in title_lower:
            return emoji_id
    return None
