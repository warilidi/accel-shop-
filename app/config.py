from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_ids: set[int]
    admin_contact: str
    wholesale_link: str
    help_link: str
    rules_link: str
    bybit_uid: str
    rub_per_usd: float
    cryptobot_invoice_add_percent: int
    notify_bot_token: str
    notify_chat_id: int | None
    cryptobot_api_token: str
    payment_check_interval: int


def _parse_admin_ids(raw: str) -> set[int]:
    result: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        result.add(int(item))
    return result


def load_settings() -> Settings:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is required in .env file")

    notify_chat_raw = os.getenv("NOTIFY_CHAT_ID", "").strip()
    notify_chat_id = int(notify_chat_raw) if notify_chat_raw else None

    return Settings(
        bot_token=token,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
        admin_contact=os.getenv("ADMIN_CONTACT", "@Dolzu").strip(),
        wholesale_link=os.getenv("WHOLESALE_LINK", "https://t.me/Dolzu").strip(),
        help_link=os.getenv("HELP_LINK", "https://t.me/Dolzu").strip(),
        rules_link=os.getenv("RULES_LINK", "https://telegra.ph/Pravila-magazina-05-28").strip(),
        bybit_uid=os.getenv("BYBIT_UID", "565720761").strip(),
        rub_per_usd=float(os.getenv("RUB_PER_USD", "70.9")),
        cryptobot_invoice_add_percent=int(os.getenv("CRYPTOBOT_INVOICE_ADD_PERCENT", "3")),
        notify_bot_token=os.getenv("NOTIFY_BOT_TOKEN", "").strip(),
        notify_chat_id=notify_chat_id,
        cryptobot_api_token=os.getenv("CRYPTOBOT_API_TOKEN", "").strip(),
        payment_check_interval=int(os.getenv("PAYMENT_CHECK_INTERVAL", "30")),
    )
