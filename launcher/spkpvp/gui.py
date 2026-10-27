"""Interface gráfica do SpkPvP Client: servidor local + página web.

Mesma arquitetura e visual do PackLauncher: a interface roda em uma janela de
aplicativo do Chrome/Edge/Chromium quando disponível, ou no navegador padrão.
"""
from __future__ import annotations

import json
import mimetypes
import os
import queue
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__, auth, client, java, launch, paths, settings, store

WEB_DIR = Path(__file__).parent / "web"

# ---------------------------------------------------------------------------
# Eventos e tarefas em segundo plano
# ---------------------------------------------------------------------------

class Hub:
    """Distribui eventos para os clientes conectados via Server-Sent Events."""

    def __init__(self) -> None:
        self.clients: set[queue.Queue] = set()
        self.lock = threading.Lock()
        self.last_disconnect = time.time()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self.lock:
            self.clients.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self.lock:
            self.clients.discard(q)
            self.last_disconnect = time.time()

    def publish(self, event: str, data) -> None:
        with self.lock:
            for q in self.clients:
                q.put((event, data))


class Task:
    def __init__(self, tasks: "Tasks", title: str, instance: str | None) -> None:
        self.id = secrets.token_hex(4)
        self.tasks = tasks
        self.title = title
        self.instance = instance
        self.status = "running"
        self.message = ""
        self.done = 0
        self.total = 0
        self._last_emit = 0.0

    def as_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "instance": self.instance, "status": self.status,
                "message": self.message, "done": self.done, "total": self.total}

    def log(self, msg: str) -> None:
        self.message = msg
        if self.instance:
            self.tasks.app.add_log(self.instance, msg)
        self.emit(force=True)

    def progress(self, done: int, total: int) -> None:
        self.done, self.total = done, total
        self.emit(force=done == total)

    def emit(self, force: bool = False) -> None:
        now = time.time()
        if force or now - self._last_emit > 0.15:
            self._last_emit = now
            self.tasks.app.hub.publish("task", self.as_dict())


class Tasks:
    def __init__(self, app: "App") -> None:
        self.app = app
        self.items: dict[str, Task] = {}

    def start(self, title: str, fn, instance: str | None = None) -> Task:
        task = Task(self, title, instance)
        self.items[task.id] = task
        task.emit(force=True)

        def worker():
            try:
                fn(task)
                task.status = "done"
            except Exception as e:
                traceback.print_exc()
                task.status = "error"
                task.message = str(e)
                if task.instance:
                    self.app.add_log(task.instance, f"Erro: {e}")
            task.emit(force=True)
            self.app.hub.publish("state", None)
            threading.Timer(30, lambda: self.items.pop(task.id, None)).start()

        threading.Thread(target=worker, daemon=True).start()
        return task

    def busy(self, instance: str) -> bool:
        return any(t.instance == instance and t.status == "running" for t in self.items.values())


# ---------------------------------------------------------------------------
# Estado da aplicação
# ---------------------------------------------------------------------------

LOG_KEY = "client"


class App:
    def __init__(self) -> None:
        self.hub = Hub()
        self.tasks = Tasks(self)
        self.proc: subprocess.Popen | None = None
        self.logs: dict[str, deque] = {}
        self.token = secrets.token_urlsafe(24)
        self.login_cancel: threading.Event | None = None

    def add_log(self, key: str, line: str) -> None:
        self.logs.setdefault(key, deque(maxlen=3000)).append(line)
        self.hub.publish("log", {"instance": key, "line": line})

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def state(self) -> dict:
        default = auth.get_default()
        accounts = [{k: a[k] for k in ("name", "uuid", "type")} for a in auth.list_accounts()]
        cfg = settings.load()
        inst = client.get_instance(create=False)
        return {
            "version": __version__,
            "accounts": accounts,
            "default_account": default["uuid"] if default else None,
            "store_logged": bool(default and store.token_for(default)),
            "running": self.running,
            "tasks": [t.as_dict() for t in self.tasks.items.values()],
            "instance": inst and {"name": inst.name, "minecraft": inst.minecraft, "playtime": inst.playtime,
                                  "last_played": inst.last_played, "memory_mb": inst.memory_mb,
                                  "effective_memory": inst.effective_memory, "jvm_args": inst.jvm_args,
                                  "width": inst.width, "height": inst.height, "game_dir": str(inst.game_dir)},
            "settings": {k: cfg.get(k) for k in ("default_memory_mb", "download_workers", "msa_client_id",
                                                  "auto_download_java", "minecraft", "store_url", "mod_url")},
            "data_dir": str(paths.root()),
        }

    def account(self) -> dict:
        account = auth.get_default()
        if not account:
            raise ValueError("Adicione uma conta primeiro")
        return account

    # ------------------------------------------------------------ ações
    def play(self) -> dict:
        if self.running:
            raise ValueError("O jogo já está aberto")
        if self.tasks.busy(LOG_KEY):
            raise ValueError("Aguarde a tarefa em andamento terminar")
        account = self.account()
        self.logs[LOG_KEY] = deque(maxlen=3000)

        def on_exit(code: int) -> None:
            self.proc = None
            self.hub.publish("state", None)
            self.hub.publish("exit", {"instance": LOG_KEY, "code": code})

        def run(task: Task) -> None:
            inst = client.get_instance()
            client.prepare(inst, task.log)
            proc = launch.launch(inst, account, lambda m: self.add_log(LOG_KEY, m), task.progress, on_exit)
            if proc.poll() is None:
                self.proc = proc
            task.log("Jogo iniciado")

        return self.tasks.start("Iniciando SpkPvP", run, LOG_KEY).as_dict()

    def stop(self) -> None:
        if self.running:
            self.proc.terminate()  # type: ignore[union-attr]

    def login_microsoft(self) -> dict:
        self.login_cancel = cancel = threading.Event()

        def show(url: str, code: str) -> None:
            self.hub.publish("login", {"url": url, "code": code})

        def run(task: Task) -> None:
            acc = auth.login_microsoft(show, cancel.is_set)
            task.log(f"Logado como {acc['name']}")
            self.hub.publish("login", {"done": True, "name": acc["name"]})
        return self.tasks.start("Login Microsoft", run).as_dict()


def open_external(target: str) -> None:
    if sys.platform == "win32":
        os.startfile(target)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", target])


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


ROUTES: list[tuple[str, re.Pattern, str]] = []


def route(method: str, pattern: str):
    def deco(fn):
        ROUTES.append((method, re.compile(f"^{pattern}$"), fn.__name__))
        return fn
    return deco


class Handler(BaseHTTPRequestHandler):
    app: App
    port: int
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args) -> None:  # silencioso
        pass

    # ------------------------------------------------------------ helpers
    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status: int = 200) -> None:
        self._send(status, json.dumps(data).encode(), "application/json; charset=utf-8")

    def _json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw) if raw else {}

    def _host_ok(self) -> bool:
        # Evita DNS rebinding: só aceita o host local exato
        return self.headers.get("Host") in (f"127.0.0.1:{self.port}", f"localhost:{self.port}")

    def _authorized(self, query: dict) -> bool:
        token = self.headers.get("X-Token") or query.get("t", [""])[0]
        return secrets.compare_digest(token, self.app.token)

    # ------------------------------------------------------------ dispatch
    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        if not self._host_ok():
            self._send(403, b"forbidden", "text/plain")
            return
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        path = parsed.path
        if not path.startswith("/api/"):
            if method == "GET":
                self._static(path)
            else:
                self._send(405, b"", "text/plain")
            return
        if not self._authorized(query):
            self._json({"error": "não autorizado"}, 401)
            return
        for m, pattern, name in ROUTES:
            match = pattern.match(path)
            if m == method and match:
                try:
                    getattr(self, name)(query, *match.groups())
                except ApiError as e:
                    self._json({"error": str(e)}, e.status)
                except store.StoreError as e:
                    self._json({"error": str(e)}, e.status if 400 <= e.status < 600 else 400)
                except ValueError as e:
                    self._json({"error": str(e)}, 409)
                except KeyError as e:
                    self._json({"error": str(e).strip("'")}, 404)
                except Exception as e:
                    traceback.print_exc()
                    self._json({"error": str(e)}, 400)
                return
        self._json({"error": "rota não encontrada"}, 404)

    def _static(self, path: str) -> None:
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (WEB_DIR / rel).resolve()
        if WEB_DIR.resolve() not in target.parents or not target.is_file():
            self._send(404, b"not found", "text/plain")
            return
        ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype)

    # ------------------------------------------------------------ eventos / estado
    @route("GET", "/api/events")
    def events(self, query) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        q = self.app.hub.subscribe()
        try:
            self.wfile.write(b"event: hello\ndata: {}\n\n")
            self.wfile.flush()
            while True:
                try:
                    event, data = q.get(timeout=15)
                    chunk = f"event: {event}\ndata: {json.dumps(data)}\n\n"
                except queue.Empty:
                    chunk = ": ping\n\n"
                self.wfile.write(chunk.encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            self.app.hub.unsubscribe(q)
            self.close_connection = True

    @route("GET", "/api/state")
    def get_state(self, query) -> None:
        self._json(self.app.state())

    @route("GET", "/api/logs")
    def get_logs(self, query) -> None:
        self._json(list(self.app.logs.get(LOG_KEY, [])))

    # ------------------------------------------------------------ jogo
    @route("POST", "/api/play")
    def play(self, query) -> None:
        self._json(self.app.play())

    @route("POST", "/api/stop")
    def stop(self, query) -> None:
        self.app.stop()
        self._json({"ok": True})

    @route("GET", "/api/modules")
    def modules(self, query) -> None:
        self._json(client.read_modules(client.get_instance()))

    @route("POST", "/api/modules")
    def set_module(self, query) -> None:
        body = self._json_body()
        client.set_module(client.get_instance(), str(body["id"]), bool(body["enabled"]))
        self._json({"ok": True})

    @route("POST", "/api/instance")
    def save_instance(self, query) -> None:
        inst = client.get_instance()
        body = self._json_body()
        for key in ("memory_mb", "width", "height"):
            if key in body:
                setattr(inst, key, max(0, int(body[key] or 0)))
        if "jvm_args" in body:
            inst.jvm_args = str(body["jvm_args"]).strip()
        inst.save()
        self.app.hub.publish("state", None)
        self._json({"ok": True})

    @route("POST", "/api/open-folder")
    def open_folder(self, query) -> None:
        sub = self._json_body().get("sub", "")
        if sub == "data":
            folder = paths.root()
        else:
            inst = client.get_instance()
            folder = inst.game_dir / sub if sub in ("", "mods", "config", "screenshots", "resourcepacks",
                                                    "logs") else inst.game_dir
        folder.mkdir(parents=True, exist_ok=True)
        open_external(str(folder))
        self._json({"ok": True})

    @route("POST", "/api/open-url")
    def open_url(self, query) -> None:
        url = str(self._json_body().get("url", ""))
        if not re.match(r"^https?://", url):
            raise ApiError(400, "URL inválida")
        webbrowser.open(url)
        self._json({"ok": True})

    # ------------------------------------------------------------ loja
    @route("GET", "/api/store/catalog")
    def store_catalog(self, query) -> None:
        self._json(store.call("/api/catalog"))

    @route("POST", "/api/store/login")
    def store_login(self, query) -> None:
        res = store.login(self.app.account())
        self.app.hub.publish("state", None)
        self._json({"name": res["name"]})

    @route("POST", "/api/store/logout")
    def store_logout(self, query) -> None:
        store.logout(self.app.account())
        self.app.hub.publish("state", None)
        self._json({"ok": True})

    @route("GET", "/api/store/me")
    def store_me(self, query) -> None:
        account = self.app.account()
        if not store.token_for(account):
            raise ApiError(401, "Entre na loja")
        self._json(store.authed(account, "/api/me"))

    @route("POST", "/api/store/equip")
    def store_equip(self, query) -> None:
        self._json(store.authed(self.app.account(), "/api/equip", self._json_body()))

    @route("POST", "/api/store/checkout")
    def store_checkout(self, query) -> None:
        self._json(store.authed(self.app.account(), "/api/checkout", self._json_body()))

    @route("GET", r"/api/store/orders/(spk_[0-9a-f]+)")
    def store_order(self, query, order_id) -> None:
        self._json(store.authed(self.app.account(), f"/api/orders/{order_id}"))

    # ------------------------------------------------------------ contas
    @route("POST", "/api/accounts/offline")
    def add_offline(self, query) -> None:
        try:
            acc = auth.add_offline(self._json_body().get("name", "").strip())
        except auth.AuthError as e:
            raise ApiError(400, str(e))
        auth.set_default(acc["uuid"])
        self.app.hub.publish("state", None)
        self._json({"ok": True})

    @route("POST", "/api/accounts/microsoft")
    def login_microsoft(self, query) -> None:
        if not settings.get("msa_client_id"):
            raise ApiError(400, "Configure o Client ID do Azure em Configurações para usar contas Microsoft")
        self._json(self.app.login_microsoft())

    @route("POST", "/api/accounts/microsoft/cancel")
    def cancel_login(self, query) -> None:
        if self.app.login_cancel:
            self.app.login_cancel.set()
        self._json({"ok": True})

    @route("POST", "/api/accounts/default")
    def default_account(self, query) -> None:
        auth.set_default(self._json_body()["uuid"])
        self.app.hub.publish("state", None)
        self._json({"ok": True})

    @route("POST", "/api/accounts/remove")
    def remove_account(self, query) -> None:
        auth.remove(self._json_body()["uuid"])
        self.app.hub.publish("state", None)
        self._json({"ok": True})

    # ------------------------------------------------------------ configurações
    @route("POST", "/api/settings")
    def save_settings(self, query) -> None:
        body = self._json_body()
        data = settings.load()
        if "default_memory_mb" in body:
            data["default_memory_mb"] = max(512, int(body["default_memory_mb"]))
        if "download_workers" in body:
            data["download_workers"] = min(32, max(1, int(body["download_workers"])))
        for key in ("msa_client_id", "store_url", "mod_url"):
            if key in body:
                data[key] = str(body[key]).strip()
        if not data.get("store_url"):
            data["store_url"] = settings.DEFAULTS["store_url"]
        if "auto_download_java" in body:
            data["auto_download_java"] = bool(body["auto_download_java"])
        settings.save(data)
        self.app.hub.publish("state", None)
        self._json({"ok": True})

    @route("GET", "/api/java")
    def list_java(self, query) -> None:
        found = [{"path": c, "major": java.probe(c)} for c in java.candidates()]
        self._json([f for f in found if f["major"]])


# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------

def _app_browser() -> str | None:
    """Encontra um navegador Chromium para abrir a interface como janela de app."""
    names = ["msedge", "chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
             "brave-browser", "brave"]
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    if sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""),
                     os.environ.get("LOCALAPPDATA", "")):
            for rel in (r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
                        r"BraveSoftware\Brave-Browser\Application\brave.exe"):
                p = Path(base) / rel
                if base and p.is_file():
                    return str(p)
    if sys.platform == "darwin":
        for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                  "/Applications/Chromium.app/Contents/MacOS/Chromium"):
            if os.path.isfile(p):
                return p
    return None


def serve(port: int = 0) -> tuple[ThreadingHTTPServer, App]:
    app = App()
    handler = type("BoundHandler", (Handler,), {"app": app})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    handler.port = server.server_address[1]
    return server, app


def main(open_window: bool = True, port: int = 0) -> int:
    server, app = serve(port)
    url = f"http://127.0.0.1:{server.server_address[1]}/#t={app.token}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"SpkPvP Client {__version__} rodando em {url}")
    print("Feche a janela do launcher (ou Ctrl+C) para sair.")

    window = None
    if open_window:
        browser = _app_browser()
        if browser:
            profile = paths.root() / "ui-profile"
            window = subprocess.Popen([browser, f"--app={url}", f"--user-data-dir={profile}",
                                       "--window-size=1280,800", "--no-first-run",
                                       "--no-default-browser-check"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            webbrowser.open(url)
    try:
        started = time.time()
        if window:
            window.wait()
        if not window or time.time() - started < 5:
            # Sem janela própria (ou o navegador repassou a janela a um processo já aberto):
            # encerra quando nenhuma aba estiver conectada por 20s
            while True:
                time.sleep(2)
                idle = not app.hub.clients and time.time() - app.hub.last_disconnect > 20
                if open_window and idle and not app.running:
                    break
        while app.running:  # não derruba o jogo aberto (a saída dele passa pelo launcher)
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    server.shutdown()
    return 0
