import re

# Премиум эмодзи Telegram с их ID
# Получены через @Emoji_ID_Extractor_bot

_UNICODE_EMOJI_RE = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "\uFE0F"
    "\u200D"
    "]+",
    flags=re.UNICODE,
)


def strip_unicode_emoji(text: str) -> str:
    """Убирает обычные Unicode-эмодзи из строки (премиум через icon_custom_emoji_id / tg-emoji)."""
    cleaned = _UNICODE_EMOJI_RE.sub("", text or "")
    return re.sub(r"\s{2,}", " ", cleaned).strip()

PREMIUM_EMOJI = {
    "chatgpt":    "5190529511212485938",     # ChatGPT
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
    "nordvpn":    "5239963889004732575",
    "canva":      "5309754771102525647",
    "kiro":       "5239963889004732575",
    "linkedin":   "5239963889004732575",
    "lovable":    "5239963889004732575",
    "veo3":       "5206660927339924387",
    "notion":     "5239963889004732575",
}

# icon_custom_emoji_id для кнопок категорий каталога
CATEGORY_ICON = {
    "нейросети":       "5206323862601504338",
    "другие сервисы":  "5203975636477055920",
    "накрутка":        "5204381382037509272",
    "игры":            "5204187760616840144",
}

# icon_custom_emoji_id для кнопок главного меню
MENU_BUTTON_ICONS = {
    "catalog":   "5370983124794625878",
    "balance":   "5373032434080175696",
    "wholesale": "5373162670373491228",
    "help":      "5370596461773870097",
    "profile":   "5373063868945814451",
    "rules":     "5373181929006848898",
}

# Маппинг названий товаров/типов на ключи эмодзи
PRODUCT_TYPE_EMOJI = {
    "chatgpt":    ("chatgpt", "💬"),
    "perplexity": ("perplexity", "🔍"),
    "grok":       ("grok", "🧠"),
    "gemini":     ("gemini", "✨"),
    "google ai":  ("gemini", "✨"),
    "claude":     ("claude", "🤖"),
    "cursor":     ("cursor", "⌨️"),
    "suno":       ("suno", "🎵"),
    "spotify":    ("spotify", "🎵"),
    "netflix":    ("netflix", "📺"),
    "discord":    ("discord", "💬"),
    "gmail":      ("gmail", "📧"),
    "youtube":    ("youtube", "▶️"),
    "pixeart":    ("pixeart", "🎨"),
    "picsart":    ("pixeart", "🎨"),
    "amazon":     ("amazon", "🛍️"),
    "capcut":     ("capcut", "✂️"),
    "apple":      ("apple", "🍎"),
    "ipad":       ("apple", "🍎"),
    "windows":    ("windows", "🪟"),
    "steam":      ("steam", "🎮"),
    "adobe":      ("adobe", "📐"),
    "notion":     ("notion", "📝"),
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


# Точное совпадение названия подкатегории (приоритет над подстрокой)
SUBCATEGORY_ICON_EXACT = {
    "chatgpt":    "chatgpt",
    "perplexity": "perplexity",
    "grok":       "grok",
    "gemini":     "gemini",
    "claude":     "claude",
    "cursor":     "cursor",
    "suno ai":    "suno",
    "spotify":    "spotify",
    "netflix":    "netflix",
    "discord":    "discord",
    "почты gmail": "gmail",
    "youtube":    "youtube",
    "picsart":    "pixeart",
    "amazon prime": "amazon",
    "capcut":     "capcut",
    "apple":      "apple",
    "windows":    "windows",
    "steam":      "steam",
    "nordvpn":    "nordvpn",
    "canva":      "canva",
    "kiro":       "kiro",
    "linkedin":   "linkedin",
    "lovable":    "lovable",
    "veo 3":      "veo3",
    "notion":     "notion",
}

# Ключи картинок (/setimage) для каждой подкатегории
SUBCATEGORY_VISUAL_KEY_EXACT = {
    "chatgpt":      "chatgpt",
    "perplexity":   "perplexity",
    "grok":         "grok",
    "gemini":       "gemini",
    "claude":       "claude",
    "cursor":       "cursor",
    "suno ai":      "suno",
    "spotify":      "spotify",
    "netflix":      "netflix",
    "discord":      "discord",
    "почты gmail":  "gmail",
    "youtube":      "youtube",
    "picsart":      "picsart",
    "amazon prime": "amazon",
    "capcut":       "capcut",
    "apple":        "apple",
    "windows":      "windows",
    "steam":        "steam",
    "nordvpn":      "nordvpn",
    "canva":        "canva",
    "kiro":         "kiro",
    "linkedin":     "linkedin",
    "lovable":      "lovable",
    "veo 3":        "veo3",
    "notion":       "notion",
}

# Алиасы в названии товара → ключ PREMIUM_EMOJI
_TITLE_ICON_ALIASES = [
    ("google ai",    "gemini"),
    ("amazon prime", "amazon"),
    ("veo 3",        "veo3"),
    ("suno ai",      "suno"),
    ("picsart",      "pixeart"),
    ("почты gmail",  "gmail"),
    ("nord vpn",     "nordvpn"),
    ("adobe",        "adobe"),
]


def _build_button_icon_by_title() -> list[tuple[str, str]]:
    """Все сервисы с явной привязкой icon_custom_emoji_id по подстроке в названии."""
    seen: set[str] = set()
    items: list[tuple[str, str]] = []
    for alias, emoji_key in sorted(_TITLE_ICON_ALIASES, key=lambda x: len(x[0]), reverse=True):
        emoji_id = PREMIUM_EMOJI.get(emoji_key)
        if emoji_id and alias not in seen:
            items.append((alias, emoji_id))
            seen.add(alias)
    for emoji_key in sorted(PREMIUM_EMOJI.keys(), key=len, reverse=True):
        emoji_id = PREMIUM_EMOJI[emoji_key]
        if emoji_key not in seen:
            items.append((emoji_key, emoji_id))
            seen.add(emoji_key)
    return items


BUTTON_ICON_BY_TITLE = _build_button_icon_by_title()


def get_subcategory_emoji_key(subcategory_name: str) -> str | None:
    """Ключ PREMIUM_EMOJI по названию подкатегории."""
    sub_lower = strip_unicode_emoji(subcategory_name).lower().strip()
    if sub_lower in SUBCATEGORY_ICON_EXACT:
        return SUBCATEGORY_ICON_EXACT[sub_lower]
    for key, emoji_key in sorted(
        SUBCATEGORY_ICON_EXACT.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if key in sub_lower:
            return emoji_key
    return None


def get_subcategory_visual_key(subcategory_name: str) -> str | None:
    """Ключ картинки (/setimage) по названию подкатегории."""
    sub_lower = strip_unicode_emoji(subcategory_name).lower().strip()
    if sub_lower in SUBCATEGORY_VISUAL_KEY_EXACT:
        return SUBCATEGORY_VISUAL_KEY_EXACT[sub_lower]
    for key, visual_key in sorted(
        SUBCATEGORY_VISUAL_KEY_EXACT.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if key in sub_lower:
            return visual_key
    return None


# Все ключи картинок сервисов для /setimage и /images
SERVICE_VISUAL_KEYS = sorted(set(SUBCATEGORY_VISUAL_KEY_EXACT.values()))

# Ключи картинок экранов главного меню
SCREEN_VISUAL_KEYS = ["start", "categories", "rules", "balance", "profile"]

VISUAL_LANG_SUFFIX = "_en"


def localized_visual_key(base_key: str, lang: str | None = None) -> str:
    """Ключ картинки для языка: ru → start, en → start_en."""
    from app.i18n import normalize_lang

    if normalize_lang(lang) == "en":
        return f"{base_key}{VISUAL_LANG_SUFFIX}"
    return base_key


def all_visual_keys() -> list[str]:
    """Все ключи /setimage: русские и английские варианты."""
    keys: list[str] = []
    for base in [*SCREEN_VISUAL_KEYS, *SERVICE_VISUAL_KEYS]:
        keys.append(base)
        keys.append(f"{base}{VISUAL_LANG_SUFFIX}")
    return keys


def get_category_icon_id(category_name: str) -> str | None:
    """icon_custom_emoji_id для кнопки категории."""
    key = strip_unicode_emoji(category_name).lower().strip()
    return CATEGORY_ICON.get(key)


def get_menu_button_icon_id(button_id: str) -> str | None:
    """icon_custom_emoji_id для кнопки главного меню."""
    return MENU_BUTTON_ICONS.get(button_id)


def get_subcategory_icon_id(subcategory_name: str) -> str | None:
    """icon_custom_emoji_id для кнопки подкатегории."""
    emoji_key = get_subcategory_emoji_key(subcategory_name)
    if emoji_key:
        return PREMIUM_EMOJI.get(emoji_key)
    return None


def get_subcategory_emoji_html(subcategory_name: str) -> str:
    """HTML с премиум-эмодзи для заголовка подкатегории."""
    emoji_key = get_subcategory_emoji_key(subcategory_name)
    if not emoji_key:
        return ""
    fallback = "📦"
    for _, (ek, fb) in PRODUCT_TYPE_EMOJI.items():
        if ek == emoji_key:
            fallback = fb
            break
    return premium_emoji(emoji_key, fallback)


def format_subcategory_header(subcategory_name: str, lang: str | None = None) -> str:
    """Заголовок экрана товаров: премиум-иконка + название сервиса."""
    from app.i18n import normalize_lang, t

    lang = normalize_lang(lang)
    clean_name = strip_unicode_emoji(subcategory_name)
    icon = get_subcategory_emoji_html(subcategory_name)
    pick = t("catalog.pick_product", lang)
    if icon:
        return f"{icon} <b>{clean_name}</b>\n{pick}"
    if clean_name:
        return f"<b>{clean_name}</b>\n{pick}"
    return pick


def get_button_icon_id(product_title: str, subcategory_name: str | None = None) -> str | None:
    """
    Возвращает icon_custom_emoji_id для кнопки товара по названию,
    либо None если совпадение не найдено.

    Сначала проверяет BUTTON_ICON_BY_TITLE (ручные привязки),
    затем PREMIUM_EMOJI по подстроке в названии товара,
    затем по названию подкатегории (например Apple → iPad Сертификат).
    """
    title_lower = product_title.lower()
    for key, emoji_id in BUTTON_ICON_BY_TITLE:
        if key in title_lower:
            return emoji_id
    # Длинные ключи первыми: «google ai» важнее «gmail» в «Old Gmail»
    for key, (emoji_key, _) in sorted(
        PRODUCT_TYPE_EMOJI.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if key in title_lower:
            return PREMIUM_EMOJI.get(emoji_key)
    if subcategory_name:
        emoji_key = get_subcategory_emoji_key(subcategory_name)
        if emoji_key:
            return PREMIUM_EMOJI.get(emoji_key)
    return None
