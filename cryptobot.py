from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

API_BASE = "https://pay.crypt.bot/api"


@dataclass
class Invoice:
    invoice_id: int
    bot_invoice_url: str
    mini_app_invoice_url: str
    status: str
    amount: str
    asset: str


async def _request(
    token: str,
    method: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = {"Crypto-Pay-API-Token": token}
    url = f"{API_BASE}/{method}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as resp:
            data = await resp.json()
            if not data.get("ok"):
                error = data.get("error", {})
                raise RuntimeError(
                    f"CryptoBot API error: {error.get('code')} — {error.get('name')}"
                )
            return data["result"]


async def create_invoice(
    token: str,
    asset: str,
    amount: float,
    description: str = "",
    paid_btn_name: str = "callback",
    paid_btn_url: str = "https://t.me",
    expires_in: int = 900,
) -> Invoice:
    params: dict[str, Any] = {
        "asset": asset,
        "amount": f"{amount:.8f}".rstrip("0").rstrip("."),
        "expires_in": expires_in,
    }
    if description:
        params["description"] = description[:1024]
    if paid_btn_name:
        params["paid_btn_name"] = paid_btn_name
    if paid_btn_url:
        params["paid_btn_url"] = paid_btn_url

    result = await _request(token, "createInvoice", params)
    return Invoice(
        invoice_id=int(result["invoice_id"]),
        bot_invoice_url=result.get("bot_invoice_url", ""),
        mini_app_invoice_url=result.get("mini_app_invoice_url", ""),
        status=result.get("status", ""),
        amount=result.get("amount", ""),
        asset=result.get("asset", asset),
    )


async def get_invoices(
    token: str,
    invoice_ids: list[int] | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    if invoice_ids:
        params["invoice_ids"] = ",".join(str(i) for i in invoice_ids)
    if status:
        params["status"] = status
    result = await _request(token, "getInvoices", params)
    return result.get("items", [])


async def check_invoice_status(token: str, invoice_id: int) -> str:
    invoices = await get_invoices(token, invoice_ids=[invoice_id])
    if not invoices:
        return "not_found"
    return invoices[0].get("status", "unknown")
