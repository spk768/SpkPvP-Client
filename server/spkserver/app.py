"""Servidor HTTP da loja de cosméticos do SpkPvP (apenas biblioteca padrão).

- Login pelo launcher com a conta Minecraft (protocolo de sessão da Mojang, o
  mesmo que servidores usam para verificar jogadores) ou offline em modo dev.
- Catálogo, compra (Pix, boleto, cartão de crédito/débito, PayPal), guarda-roupa.
- Endpoint público com os cosméticos equipados de cada jogador, lido pelo mod.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import threading
import time
import traceback
import urllib.parse
import uuid as uuidlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import catalog, payments
from .config import Config
from .db import DB, normalize_uuid
from .payments.http import PaymentError, request

SESSION_SERVER = "https://sessionserver.mojang.com/session/minecraft/hasJoined"
NAME_RE = re.compile(r"[A-Za-z0-9_]{3,16}")


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def offline_uuid(name: str) -> str:
    """UUID que o Minecraft usa para contas offline (OfflinePlayer:<nome>)."""
    digest = bytearray(hashlib.md5(f"OfflinePlayer:{name}".encode()).digest())
    digest[6] = digest[6] & 0x0F | 0x30
    digest[8] = digest[8] & 0x3F | 0x80
    return uuidlib.UUID(bytes=bytes(digest)).hex


class Store:
    """Regras da loja, independentes do HTTP."""

    def __init__(self, cfg: Config, db: DB | None = None) -> None:
        self.cfg = cfg
        self.db = db or DB(cfg.db_path)
        self._last_check: dict[str, float] = {}
        self._check_lock = threading.Lock()

    def item_dict(self, item: dict) -> dict:
        data = dict(item)
        data["texture"] = f"{self.cfg.public_url}{item['texture']}"
        return data

    def catalog(self) -> dict:
        return {"items": [self.item_dict(i) for i in catalog.all_items()], "slots": list(catalog.SLOTS),
                "methods": payments.available(self.cfg), "currency": self.cfg.currency}

    def me(self, user: dict) -> dict:
        orders = [{k: o[k] for k in ("id", "items", "total", "method", "status", "created", "paid_at")}
                  for o in self.db.orders(user["uuid"])[:20]]
        return {"uuid": user["uuid"], "name": user["name"], "owned": self.db.owned(user["uuid"]),
                "equipped": self.db.equipped(user["uuid"]), "orders": orders}

    def player_cosmetics(self, uuid: str) -> dict:
        equipped = self.db.equipped(uuid)
        return {slot: {"id": cid, "texture": f"{self.cfg.public_url}{catalog.COSMETICS[cid]['texture']}"}
                for slot, cid in equipped.items() if cid in catalog.COSMETICS}

    # ------------------------------------------------------------ compra
    def checkout(self, user: dict, items: list, method: str, payer: dict) -> dict:
        if method not in {m["id"] for m in payments.available(self.cfg)}:
            raise ApiError(400, "Método de pagamento indisponível")
        if not isinstance(items, list) or not items or len(items) > 20:
            raise ApiError(400, "Carrinho vazio")
        items = list(dict.fromkeys(str(i) for i in items))
        owned = set(self.db.owned(user["uuid"]))
        total, names = 0, []
        for item_id in items:
            try:
                item = catalog.get(item_id)
            except KeyError:
                raise ApiError(400, f"Item inexistente: {item_id}") from None
            if item["price"] <= 0:
                raise ApiError(400, f"{item['name']} é gratuito")
            if set(catalog.expand(item_id)) <= owned:
                raise ApiError(409, f"Você já possui {item['name']}")
            total += item["price"]
            names.append(item["name"])
        provider = payments.METHODS[method][0]
        order_id = self.db.create_order(user["uuid"], items, total, method, provider)
        order = self.db.order(order_id)
        description = f"SpkPvP - {', '.join(names)}"[:200]
        try:
            ref, details = payments.create(self.cfg, order, method, payer or {}, description)
        except PaymentError as e:
            self.db.update_order(order_id, status="failed", details={"error": str(e)})
            raise ApiError(402, str(e)) from None
        self.db.update_order(order_id, provider_ref=ref, details=details)
        return self.public_order(self.db.order(order_id))

    @staticmethod
    def public_order(order: dict) -> dict:
        return {k: order[k] for k in ("id", "items", "total", "method", "status", "details", "created", "paid_at")}

    def sync(self, order: dict, force: bool = False) -> dict:
        """Confirma com o provedor o status de um pedido pendente e entrega os itens se pago."""
        if order["status"] != "pending" or not order.get("provider_ref"):
            return order
        with self._check_lock:
            if not force and time.time() - self._last_check.get(order["id"], 0) < 4:
                return order
            self._last_check[order["id"]] = time.time()
        try:
            status, paid = payments.check(self.cfg, order)
        except PaymentError:
            traceback.print_exc()
            return order
        if status == "paid" and paid >= order["total"]:
            self.db.fulfill(order["id"])
        elif status == "paid":
            self.db.update_order(order["id"], status="failed",
                                 details={**order["details"], "error": f"Valor pago incorreto ({paid})"})
        elif status == "failed":
            self.db.update_order(order["id"], status="failed")
        return self.db.order(order["id"])

    # ------------------------------------------------------------ login
    def verify_join(self, name: str, server_id: str) -> dict:
        if not NAME_RE.fullmatch(name or "") or not self.db.consume_challenge(server_id or ""):
            raise ApiError(401, "Desafio de login inválido ou expirado")
        query = urllib.parse.urlencode({"username": name, "serverId": server_id})
        try:
            profile = request("GET", f"{SESSION_SERVER}?{query}")
        except PaymentError as e:
            raise ApiError(502, f"Sessão da Mojang indisponível: {e}") from None
        if not profile or "id" not in profile:
            raise ApiError(401, "A Mojang não confirmou a sessão desta conta")
        return self.login(profile["id"], profile["name"])

    def login(self, uuid: str, name: str) -> dict:
        self.db.upsert_user(uuid, name)
        return {"token": self.db.new_session(uuid), "uuid": normalize_uuid(uuid), "name": name}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

ROUTES: list[tuple[str, re.Pattern, str]] = []


def route(method: str, pattern: str):
    def deco(fn):
        ROUTES.append((method, re.compile(f"^{pattern}$"), fn.__name__))
        return fn
    return deco


PAGE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>SpkPvP</title>
<style>body{{background:#1e1e1e;color:#e8e8e8;font:15px/1.5 system-ui,sans-serif;display:grid;place-items:center;
min-height:100vh;margin:0}}.box{{background:#262626;border:1px solid #3a3a3a;padding:32px;max-width:420px;text-align:center}}
button{{background:#5cbf86;border:0;padding:10px 22px;font-weight:700;cursor:pointer}}</style></head>
<body><div class="box"><h2>{title}</h2><p>{body}</p></div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    store: Store
    protocol_version = "HTTP/1.1"
    server_version = "SpkPvP"

    def log_message(self, fmt, *args) -> None:
        pass

    # ------------------------------------------------------------ helpers
    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(status, json.dumps(data).encode(), "application/json; charset=utf-8",
                   {"Cache-Control": "no-store"})

    def _page(self, title: str, body: str, status: int = 200) -> None:
        self._send(status, PAGE.format(title=html.escape(title), body=body).encode(), "text/html; charset=utf-8")

    def _raw_body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 1_000_000:
            raise ApiError(413, "Corpo muito grande")
        return self.rfile.read(length) if length else b""

    def _body(self) -> dict:
        raw = self._raw_body()
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            raise ApiError(400, "JSON inválido") from None
        if not isinstance(data, dict):
            raise ApiError(400, "JSON inválido")
        return data

    def _user(self) -> dict:
        auth = self.headers.get("Authorization", "")
        user = self.store.db.session_user(auth[7:]) if auth.startswith("Bearer ") else None
        if not user:
            raise ApiError(401, "Faça login")
        return user

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_OPTIONS(self) -> None:
        self._send(204, b"", "text/plain", {"Access-Control-Allow-Headers": "Authorization, Content-Type",
                                             "Access-Control-Allow-Methods": "GET, POST"})

    def _dispatch(self, method: str) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        for m, pattern, name in ROUTES:
            match = pattern.match(parsed.path)
            if m == method and match:
                try:
                    getattr(self, name)(query, *match.groups())
                except ApiError as e:
                    self._json({"error": str(e)}, e.status)
                except Exception as e:  # noqa: BLE001
                    traceback.print_exc()
                    self._json({"error": f"Erro interno: {e}"}, 500)
                return
        self._json({"error": "rota não encontrada"}, 404)

    # ------------------------------------------------------------ público
    @route("GET", "/")
    def index(self, query) -> None:
        self._page("SpkPvP", "Servidor da loja de cosméticos do SpkPvP Client.")

    @route("GET", "/api/catalog")
    def get_catalog(self, query) -> None:
        self._json(self.store.catalog())

    @route("GET", r"/textures/([a-z0-9_]+)\.png")
    def texture(self, query, cid) -> None:
        path = self.store.cfg.textures_dir / f"{cid}.png"
        if not path.is_file():
            raise ApiError(404, "textura não encontrada")
        self._send(200, path.read_bytes(), "image/png", {"Cache-Control": "public, max-age=3600"})

    @route("GET", r"/api/players/([0-9a-fA-F-]{32,36})/cosmetics")
    def player_cosmetics(self, query, uuid) -> None:
        self._json(self.store.player_cosmetics(uuid))

    # ------------------------------------------------------------ login
    @route("POST", "/api/auth/challenge")
    def challenge(self, query) -> None:
        self._json({"server_id": self.store.db.new_challenge(), "offline": self.store.cfg.dev})

    @route("POST", "/api/auth/verify")
    def verify(self, query) -> None:
        body = self._body()
        self._json(self.store.verify_join(str(body.get("name", "")), str(body.get("server_id", ""))))

    @route("POST", "/api/auth/offline")
    def offline(self, query) -> None:
        if not self.store.cfg.dev:
            raise ApiError(403, "Contas offline só são aceitas em modo de desenvolvimento")
        name = str(self._body().get("name", ""))
        if not NAME_RE.fullmatch(name):
            raise ApiError(400, "Nome inválido")
        self._json(self.store.login(offline_uuid(name), name))

    @route("POST", "/api/auth/logout")
    def logout(self, query) -> None:
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            self.store.db.delete_session(auth[7:])
        self._json({"ok": True})

    # ------------------------------------------------------------ jogador
    @route("GET", "/api/me")
    def me(self, query) -> None:
        self._json(self.store.me(self._user()))

    @route("POST", "/api/equip")
    def equip(self, query) -> None:
        user = self._user()
        body = self._body()
        try:
            self.store.db.equip(user["uuid"], str(body.get("slot", "")), body.get("cosmetic") or None)
        except ValueError as e:
            raise ApiError(400, str(e)) from None
        except PermissionError as e:
            raise ApiError(403, str(e)) from None
        self._json(self.store.me(user))

    @route("POST", "/api/checkout")
    def checkout(self, query) -> None:
        user = self._user()
        body = self._body()
        self._json(self.store.checkout(user, body.get("items"), str(body.get("method", "")),
                                       body.get("payer") if isinstance(body.get("payer"), dict) else {}))

    @route("GET", r"/api/orders/(spk_[0-9a-f]+)")
    def get_order(self, query, order_id) -> None:
        user = self._user()
        order = self.store.db.order(order_id)
        if not order or order["uuid"] != user["uuid"]:
            raise ApiError(404, "Pedido não encontrado")
        self._json(Store.public_order(self.store.sync(order)))

    # ------------------------------------------------------------ pagamentos
    @route("GET", "/checkout/return")
    def checkout_return(self, query) -> None:
        order = self.store.db.order(query.get("order", ""))
        if not order:
            return self._page("Pedido não encontrado", "Volte ao launcher.", 404)
        order = self.store.sync(order, force=True)
        if order["status"] == "paid":
            self._page("Pagamento aprovado!", "Seus cosméticos já estão no guarda-roupa. Pode voltar ao launcher.")
        else:
            self._page("Pagamento em processamento",
                       "Assim que o pagamento for confirmado, os cosméticos aparecem no launcher automaticamente.")

    @route("POST", "/webhooks/mercadopago")
    def webhook_mp(self, query) -> None:
        body = self._body()
        data_id = str(query.get("data.id") or (body.get("data") or {}).get("id") or "")
        if not payments.mercadopago.verify_signature(self.store.cfg, self.headers.get("x-signature", ""),
                                                     self.headers.get("x-request-id", ""), data_id):
            raise ApiError(401, "assinatura inválida")
        topic = query.get("type") or query.get("topic") or body.get("type")
        if topic == "payment" and data_id.isdigit():
            try:
                pay = payments.mercadopago.payment(self.store.cfg, data_id)
            except PaymentError:
                traceback.print_exc()
                raise ApiError(502, "falha ao consultar pagamento") from None
            order = self.store.db.order(str(pay.get("external_reference") or ""))
            if order:
                self.store.sync(order, force=True)
        self._json({"ok": True})

    @route("POST", "/webhooks/paypal")
    def webhook_paypal(self, query) -> None:
        event = self._body()
        if not payments.paypal.verify_webhook(self.store.cfg, self.headers, event):
            raise ApiError(401, "assinatura inválida")
        ref = payments.paypal.order_id_from_event(event)
        order = self.store.db.order_by_ref("paypal", ref) if ref else None
        if order:
            self.store.sync(order, force=True)
        self._json({"ok": True})

    @route("GET", "/demo/pay")
    def demo_page(self, query) -> None:
        order = self.store.db.order(query.get("order", ""))
        if not self.store.cfg.dev or not order or order["provider"] != "demo":
            return self._page("Indisponível", "Pagamento de demonstração desativado.", 404)
        total = f"R$ {order['total'] / 100:.2f}".replace(".", ",")
        self._page("Pagamento de demonstração",
                   f"Pedido {html.escape(order['id'])} — {total}<br><br>"
                   f'<form method="post" action="/demo/pay?order={html.escape(order["id"])}">'
                   f'<button>Aprovar pagamento</button></form>')

    @route("POST", "/demo/pay")
    def demo_pay(self, query) -> None:
        order = self.store.db.order(query.get("order", ""))
        if not self.store.cfg.dev or not order or order["provider"] != "demo":
            return self._page("Indisponível", "Pagamento de demonstração desativado.", 404)
        self.store.db.fulfill(order["id"])
        self._page("Pagamento aprovado!", "Pode voltar ao launcher.")


def serve(cfg: Config, db: DB | None = None) -> tuple[ThreadingHTTPServer, Store]:
    store = Store(cfg, db)
    handler = type("BoundHandler", (Handler,), {"store": store})
    server = ThreadingHTTPServer((cfg.host, cfg.port), handler)
    server.daemon_threads = True
    return server, store


def main() -> int:
    cfg = Config.from_env()
    server, store = serve(cfg)
    methods = ", ".join(m["label"] for m in payments.available(cfg)) or "nenhum (configure as chaves)"
    print(f"SpkPvP store em http://{cfg.host}:{server.server_address[1]} (público: {cfg.public_url})")
    print(f"Métodos de pagamento: {methods}{'  [modo dev]' if cfg.dev else ''}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
