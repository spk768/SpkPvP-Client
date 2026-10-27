"""Cliente da API da loja de cosméticos (pasta server/)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from . import auth, net, paths, settings

SESSION_JOIN = "https://sessionserver.mojang.com/session/minecraft/join"


class StoreError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def _tokens_file():
    return paths.root() / "store.json"


def _tokens() -> dict:
    try:
        return json.loads(_tokens_file().read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def _save_tokens(data: dict) -> None:
    f = _tokens_file()
    f.write_text(json.dumps(data), "utf-8")
    try:
        f.chmod(0o600)
    except OSError:
        pass


def call(path: str, body=None, token: str | None = None, method: str | None = None):
    url = settings.get("store_url").rstrip("/") + path
    headers = {"Content-Type": "application/json", "User-Agent": net.USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error") or f"Erro {e.code}"
        except ValueError:
            msg = f"Erro {e.code}"
        raise StoreError(msg, e.code) from None
    except urllib.error.URLError as e:
        raise StoreError(f"Loja indisponível ({url}): {e.reason}", 503) from None


def token_for(account: dict) -> str | None:
    return _tokens().get(account["uuid"])


def login(account: dict) -> dict:
    """Autentica a conta na loja. Contas Microsoft provam a posse da conta pelo
    protocolo de sessão da Mojang; contas offline só funcionam em servidor dev."""
    if account["type"] == "msa":
        account = auth.ensure_valid(account)
        server_id = call("/api/auth/challenge", {})["server_id"]
        req = urllib.request.Request(SESSION_JOIN, data=json.dumps({
            "accessToken": account["access_token"], "selectedProfile": account["uuid"].replace("-", ""),
            "serverId": server_id}).encode(), headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=20).close()
        except urllib.error.URLError as e:
            raise StoreError(f"A Mojang recusou a sessão: {e}", 401) from None
        res = call("/api/auth/verify", {"name": account["name"], "server_id": server_id})
    else:
        res = call("/api/auth/offline", {"name": account["name"]})
    tokens = _tokens()
    tokens[account["uuid"]] = res["token"]
    _save_tokens(tokens)
    return res


def logout(account: dict) -> None:
    tokens = _tokens()
    token = tokens.pop(account["uuid"], None)
    _save_tokens(tokens)
    if token:
        try:
            call("/api/auth/logout", {}, token)
        except StoreError:
            pass


def authed(account: dict, path: str, body=None):
    """Chamada autenticada; refaz o login uma vez se a sessão expirou."""
    token = token_for(account) or login(account)["token"]
    try:
        return call(path, body, token)
    except StoreError as e:
        if e.status != 401:
            raise
        return call(path, body, login(account)["token"])
