"""Configuração do servidor, lida de variáveis de ambiente."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes", "sim")


@dataclass
class Config:
    host: str = "127.0.0.1"
    port: int = 8787
    # URL pública do servidor (usada nos links de retorno e webhooks dos pagamentos)
    public_url: str = "http://127.0.0.1:8787"
    db_path: Path = Path("spkpvp.db")
    # Modo de desenvolvimento: libera contas offline e o método de pagamento "demo"
    dev: bool = False
    currency: str = "BRL"
    # Mercado Pago: Pix, boleto, cartão de crédito e débito
    mp_access_token: str = ""
    mp_webhook_secret: str = ""
    # PayPal
    paypal_client_id: str = ""
    paypal_secret: str = ""
    paypal_sandbox: bool = True
    paypal_webhook_id: str = ""
    # Dias até o vencimento do boleto
    boleto_days: int = 3
    textures_dir: Path = field(default_factory=lambda: Path(__file__).parent / "textures")

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            host=os.environ.get("SPK_HOST", "127.0.0.1"),
            port=int(os.environ.get("SPK_PORT", "8787")),
            public_url=os.environ.get("SPK_PUBLIC_URL", "").rstrip("/")
            or f"http://127.0.0.1:{os.environ.get('SPK_PORT', '8787')}",
            db_path=Path(os.environ.get("SPK_DB", "spkpvp.db")),
            dev=_bool("SPK_DEV"),
            mp_access_token=os.environ.get("MP_ACCESS_TOKEN", ""),
            mp_webhook_secret=os.environ.get("MP_WEBHOOK_SECRET", ""),
            paypal_client_id=os.environ.get("PAYPAL_CLIENT_ID", ""),
            paypal_secret=os.environ.get("PAYPAL_SECRET", ""),
            paypal_sandbox=os.environ.get("PAYPAL_ENV", "sandbox") != "live",
            paypal_webhook_id=os.environ.get("PAYPAL_WEBHOOK_ID", ""),
            boleto_days=int(os.environ.get("SPK_BOLETO_DAYS", "3")),
        )
