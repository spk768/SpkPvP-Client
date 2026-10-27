"""Requisições JSON para as APIs de pagamento (apenas biblioteca padrão)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class PaymentError(Exception):
    pass


def request(method: str, url: str, body=None, headers: dict | None = None, form: bytes | None = None,
            timeout: float = 30):
    hdrs = {"Accept": "application/json", **(headers or {})}
    data = None
    if form is not None:
        data = form
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif body is not None:
        data = json.dumps(body).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        raise PaymentError(f"{method} {url} falhou ({e.code}): {detail}") from None
    except urllib.error.URLError as e:
        raise PaymentError(f"Não foi possível conectar a {url}: {e.reason}") from None
    return json.loads(raw) if raw else {}


def to_cents(value) -> int:
    """Converte um valor decimal da API ("34.90" ou 34.9) em centavos, sem erro de float."""
    text = f"{float(value):.2f}" if not isinstance(value, str) else value
    whole, _, frac = text.partition(".")
    return int(whole) * 100 + int((frac + "00")[:2])


def from_cents(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"
