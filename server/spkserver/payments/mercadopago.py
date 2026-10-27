"""Mercado Pago: Pix e boleto pela API de pagamentos; cartão de crédito e débito
pelo Checkout Pro (o cartão é digitado no site do Mercado Pago, nunca passa por nós).

Docs: https://www.mercadopago.com.br/developers/pt/reference
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re

from ..config import Config
from .http import PaymentError, from_cents, request, to_cents

API = "https://api.mercadopago.com"
# Tipos de pagamento do Checkout Pro; o método escolhido é o único não excluído.
PAYMENT_TYPES = ("credit_card", "debit_card", "prepaid_card", "ticket", "bank_transfer", "atm",
                 "digital_currency", "digital_wallet")


def _headers(cfg: Config, idempotency: str | None = None) -> dict:
    if not cfg.mp_access_token:
        raise PaymentError("Mercado Pago não configurado (MP_ACCESS_TOKEN)")
    h = {"Authorization": f"Bearer {cfg.mp_access_token}"}
    if idempotency:
        h["X-Idempotency-Key"] = idempotency
    return h


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def valid_cpf(cpf: str) -> bool:
    cpf = _digits(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(cpf[i]) * (size + 1 - i) for i in range(size))
        if (total * 10 % 11) % 10 != int(cpf[size]):
            return False
    return True


def _payer(payer: dict, need_address: bool = False) -> dict:
    email = (payer.get("email") or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise PaymentError("Informe um e-mail válido")
    first, last = (payer.get("first_name") or "").strip(), (payer.get("last_name") or "").strip()
    if not first or not last:
        raise PaymentError("Informe nome e sobrenome")
    cpf = _digits(payer.get("cpf", ""))
    if not valid_cpf(cpf):
        raise PaymentError("CPF inválido")
    out = {"email": email, "first_name": first, "last_name": last,
           "identification": {"type": "CPF", "number": cpf}}
    if need_address:
        addr = payer.get("address") or {}
        fields = {"zip_code": _digits(addr.get("zip_code", "")), "street_name": addr.get("street_name", "").strip(),
                  "street_number": str(addr.get("street_number", "")).strip(),
                  "neighborhood": addr.get("neighborhood", "").strip(), "city": addr.get("city", "").strip(),
                  "federal_unit": addr.get("federal_unit", "").strip().upper()}
        if len(fields["zip_code"]) != 8 or not all(fields.values()) or len(fields["federal_unit"]) != 2:
            raise PaymentError("Endereço completo é obrigatório para boleto (CEP, rua, número, bairro, cidade, UF)")
        out["address"] = fields
    return out


def create(cfg: Config, order: dict, method: str, payer: dict, description: str) -> tuple[str, dict]:
    """Cria a cobrança. Retorna (referência no Mercado Pago, dados para o launcher)."""
    notify = f"{cfg.public_url}/webhooks/mercadopago"
    amount = float(from_cents(order["total"]))
    if method in ("pix", "boleto"):
        body = {
            "transaction_amount": amount,
            "description": description,
            "payment_method_id": "pix" if method == "pix" else "bolbradesco",
            "payer": _payer(payer, need_address=method == "boleto"),
            "external_reference": order["id"],
            "notification_url": notify,
        }
        if method == "boleto":
            due = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=cfg.boleto_days)
            body["date_of_expiration"] = due.strftime("%Y-%m-%dT23:59:59.000-03:00")
        else:
            due = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=30)
            body["date_of_expiration"] = due.strftime("%Y-%m-%dT%H:%M:%S.000+00:00")
        pay = request("POST", f"{API}/v1/payments", body, _headers(cfg, order["id"]))
        if method == "pix":
            data = pay.get("point_of_interaction", {}).get("transaction_data", {})
            details = {"kind": "pix", "qr_code": data.get("qr_code"), "qr_code_base64": data.get("qr_code_base64"),
                       "ticket_url": data.get("ticket_url"), "expires": body["date_of_expiration"]}
        else:
            tx = pay.get("transaction_details", {})
            details = {"kind": "boleto", "url": tx.get("external_resource_url"),
                       "barcode": (pay.get("barcode") or {}).get("content") or tx.get("digitable_line"),
                       "expires": body["date_of_expiration"]}
        return str(pay["id"]), details

    if method in ("credit_card", "debit_card"):
        back = f"{cfg.public_url}/checkout/return?order={order['id']}"
        body = {
            "items": [{"id": order["id"], "title": description, "quantity": 1, "unit_price": amount,
                       "currency_id": cfg.currency}],
            "external_reference": order["id"],
            "notification_url": notify,
            "back_urls": {"success": back, "failure": back, "pending": back},
            "auto_return": "approved",
            "statement_descriptor": "SPKPVP",
            "payment_methods": {
                "excluded_payment_types": [{"id": t} for t in PAYMENT_TYPES if t != method],
                "installments": 12 if method == "credit_card" else 1,
            },
        }
        if payer.get("email"):
            body["payer"] = {"email": payer["email"]}
        pref = request("POST", f"{API}/checkout/preferences", body, _headers(cfg, order["id"]))
        return str(pref["id"]), {"kind": "redirect", "url": pref["init_point"]}

    raise PaymentError(f"Método não suportado pelo Mercado Pago: {method}")


def _status(pay: dict) -> tuple[str, int]:
    status = pay.get("status")
    mapped = {"approved": "paid", "rejected": "failed", "cancelled": "failed", "refunded": "refunded",
              "charged_back": "refunded"}.get(status, "pending")
    return mapped, to_cents(pay.get("transaction_amount") or 0)


def payment(cfg: Config, payment_id: str) -> dict:
    return request("GET", f"{API}/v1/payments/{payment_id}", headers=_headers(cfg))


def check(cfg: Config, order: dict) -> tuple[str, int]:
    """Consulta o status real de um pedido no Mercado Pago -> (status, valor pago em centavos)."""
    if order["method"] in ("pix", "boleto"):
        return _status(payment(cfg, order["provider_ref"]))
    # Checkout Pro: a preferência pode gerar vários pagamentos (tentativas); vale o aprovado.
    res = request("GET", f"{API}/v1/payments/search?external_reference={order['id']}&sort=date_created"
                         "&criteria=desc", headers=_headers(cfg))
    for pay in res.get("results", []):
        if pay.get("status") == "approved":
            return _status(pay)
    # Recusado no Checkout Pro não encerra o pedido: o jogador pode tentar outro cartão.
    return "pending", 0


def verify_signature(cfg: Config, signature: str, request_id: str, data_id: str) -> bool:
    """Valida o cabeçalho x-signature dos webhooks (HMAC-SHA256 com a chave secreta)."""
    if not cfg.mp_webhook_secret:
        return True  # sem chave: o status é sempre confirmado consultando a API
    parts = dict(p.strip().split("=", 1) for p in (signature or "").split(",") if "=" in p)
    ts, v1 = parts.get("ts"), parts.get("v1")
    if not ts or not v1:
        return False
    data_id = data_id.lower() if data_id.isalnum() else data_id
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    expected = hmac.new(cfg.mp_webhook_secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)
