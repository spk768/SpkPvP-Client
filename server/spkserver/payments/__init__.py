"""Métodos de pagamento e o provedor responsável por cada um."""
from __future__ import annotations

from ..config import Config
from . import mercadopago, paypal
from .http import PaymentError

METHODS = {
    "pix": ("mercadopago", "Pix"),
    "boleto": ("mercadopago", "Boleto bancário"),
    "credit_card": ("mercadopago", "Cartão de crédito"),
    "debit_card": ("mercadopago", "Cartão de débito"),
    "paypal": ("paypal", "PayPal"),
    "demo": ("demo", "Demonstração (sem cobrança)"),
}

__all__ = ["METHODS", "PaymentError", "available", "create", "check"]


def available(cfg: Config) -> list[dict]:
    enabled = {"mercadopago": bool(cfg.mp_access_token),
               "paypal": bool(cfg.paypal_client_id and cfg.paypal_secret),
               "demo": cfg.dev}
    return [{"id": m, "label": label, "provider": p} for m, (p, label) in METHODS.items() if enabled[p]]


def create(cfg: Config, order: dict, method: str, payer: dict, description: str) -> tuple[str, dict]:
    provider = METHODS[method][0]
    if provider == "mercadopago":
        return mercadopago.create(cfg, order, method, payer, description)
    if provider == "paypal":
        return paypal.create(cfg, order, description)
    return order["id"], {"kind": "redirect", "url": f"{cfg.public_url}/demo/pay?order={order['id']}"}


def check(cfg: Config, order: dict) -> tuple[str, int]:
    """Status real do pagamento no provedor -> ("paid"|"pending"|"failed"|"refunded", centavos pagos)."""
    if order["provider"] == "mercadopago":
        return mercadopago.check(cfg, order)
    if order["provider"] == "paypal":
        return paypal.check(cfg, order)
    return "pending", 0
