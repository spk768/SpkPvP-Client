"""PayPal (Orders v2): o jogador aprova no site do PayPal e o pedido é capturado na volta.

Docs: https://developer.paypal.com/docs/api/orders/v2/
"""
from __future__ import annotations

import base64
import threading
import time

from ..config import Config
from .http import PaymentError, from_cents, request, to_cents

_token: dict = {"value": "", "expires": 0.0, "key": ""}
_lock = threading.Lock()


def _base(cfg: Config) -> str:
    return "https://api-m.sandbox.paypal.com" if cfg.paypal_sandbox else "https://api-m.paypal.com"


def _headers(cfg: Config, request_id: str | None = None) -> dict:
    if not cfg.paypal_client_id or not cfg.paypal_secret:
        raise PaymentError("PayPal não configurado (PAYPAL_CLIENT_ID / PAYPAL_SECRET)")
    key = f"{cfg.paypal_client_id}:{cfg.paypal_sandbox}"
    with _lock:
        if _token["key"] != key or _token["expires"] < time.time() + 60:
            basic = base64.b64encode(f"{cfg.paypal_client_id}:{cfg.paypal_secret}".encode()).decode()
            res = request("POST", f"{_base(cfg)}/v1/oauth2/token", form=b"grant_type=client_credentials",
                          headers={"Authorization": f"Basic {basic}"})
            _token.update(value=res["access_token"], expires=time.time() + int(res.get("expires_in", 300)), key=key)
        h = {"Authorization": f"Bearer {_token['value']}"}
    if request_id:
        h["PayPal-Request-Id"] = request_id
    return h


def create(cfg: Config, order: dict, description: str) -> tuple[str, dict]:
    back = f"{cfg.public_url}/checkout/return?order={order['id']}"
    body = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": order["id"],
            "custom_id": order["id"],
            "description": description[:127],
            "amount": {"currency_code": cfg.currency, "value": from_cents(order["total"])},
        }],
        "payment_source": {"paypal": {"experience_context": {
            "brand_name": "SpkPvP", "user_action": "PAY_NOW", "shipping_preference": "NO_SHIPPING",
            "locale": "pt-BR", "return_url": back, "cancel_url": back,
        }}},
    }
    res = request("POST", f"{_base(cfg)}/v2/checkout/orders", body, _headers(cfg, order["id"]))
    link = next((l["href"] for l in res.get("links", []) if l.get("rel") in ("payer-action", "approve")), None)
    if not link:
        raise PaymentError("PayPal não retornou o link de aprovação")
    return res["id"], {"kind": "redirect", "url": link}


def _captured(res: dict) -> tuple[str, int]:
    for unit in res.get("purchase_units", []):
        for cap in unit.get("payments", {}).get("captures", []):
            if cap.get("status") == "COMPLETED":
                return "paid", to_cents(cap["amount"]["value"])
            if cap.get("status") == "PENDING":
                return "pending", 0
    return "pending", 0


def check(cfg: Config, order: dict) -> tuple[str, int]:
    """Consulta o pedido no PayPal; se o jogador já aprovou, captura o pagamento."""
    ref = order["provider_ref"]
    res = request("GET", f"{_base(cfg)}/v2/checkout/orders/{ref}", headers=_headers(cfg))
    status = res.get("status")
    if status == "APPROVED":
        res = request("POST", f"{_base(cfg)}/v2/checkout/orders/{ref}/capture", {},
                      _headers(cfg, f"capture-{order['id']}"))
        status = res.get("status")
    if status == "COMPLETED":
        return _captured(res)
    if status == "VOIDED":
        return "failed", 0
    return "pending", 0


def verify_webhook(cfg: Config, headers, event: dict) -> bool:
    """Confirma a autenticidade do webhook com a API do PayPal."""
    if not cfg.paypal_webhook_id:
        return True  # sem webhook id: o status é sempre confirmado consultando a API
    body = {
        "auth_algo": headers.get("PAYPAL-AUTH-ALGO"),
        "cert_url": headers.get("PAYPAL-CERT-URL"),
        "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID"),
        "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG"),
        "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME"),
        "webhook_id": cfg.paypal_webhook_id,
        "webhook_event": event,
    }
    try:
        res = request("POST", f"{_base(cfg)}/v1/notifications/verify-webhook-signature", body, _headers(cfg))
    except PaymentError:
        return False
    return res.get("verification_status") == "SUCCESS"


def order_id_from_event(event: dict) -> str | None:
    """Id do pedido PayPal citado num evento de webhook."""
    resource = event.get("resource") or {}
    if event.get("event_type", "").startswith("CHECKOUT.ORDER"):
        return resource.get("id")
    return (resource.get("supplementary_data") or {}).get("related_ids", {}).get("order_id")
