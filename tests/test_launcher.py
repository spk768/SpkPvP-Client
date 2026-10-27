import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "launcher"))
sys.path.insert(0, str(ROOT / "server"))

from spkpvp import client, gui, settings  # noqa: E402
from spkserver import app as store_app  # noqa: E402
from spkserver.config import Config  # noqa: E402


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # servidor da loja em modo dev
        self.store_cfg = Config(port=0, db_path=self.tmp / "store.db", dev=True)
        self.store, self.store_state = store_app.serve(self.store_cfg)
        self.store_cfg.public_url = f"http://127.0.0.1:{self.store.server_address[1]}"
        threading.Thread(target=self.store.serve_forever, daemon=True).start()

        self.env = mock.patch.dict(os.environ, {"SPKPVP_HOME": str(self.tmp / "home"),
                                                "SPKPVP_STORE_URL": self.store_cfg.public_url})
        self.env.start()
        self.server, self.app = gui.serve(0)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        for s in (self.server, self.store):
            s.shutdown()
            s.server_close()
        self.store_state.db.conn.close()
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def req(self, path, body=None, token=True, host=None, expect=200):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Token"] = self.app.token
        if host:
            headers["Host"] = host
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=headers)
        try:
            with urllib.request.urlopen(r, timeout=10) as resp:
                status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        self.assertEqual(status, expect, raw)
        return json.loads(raw) if raw[:1] in (b"{", b"[") else raw

    def test_static_and_security(self):
        self.assertIn(b"SpkPvP Client", self.req("/", token=False))
        self.req("/app.js", token=False)
        self.req("/api/state", token=False, expect=401)
        self.req("/api/state", host="evil.example", expect=403)
        self.req("/../gui.py", token=False, expect=404)
        self.req("/api/open-url", {"url": "file:///etc/passwd"}, expect=400)

    def test_modules_shared_with_mod(self):
        mods = self.req("/api/modules")
        self.assertTrue(next(m for m in mods if m["id"] == "fps")["enabled"])
        self.req("/api/modules", {"id": "fps", "enabled": False})
        inst = client.get_instance()
        saved = json.loads((client.config_dir(inst) / "modules.json").read_text())
        self.assertEqual(saved["fps"], {"enabled": False})
        self.req("/api/modules", {"id": "nope", "enabled": False}, expect=404)
        # só uma instância do client por versão
        self.assertEqual(client.get_instance().dir, inst.dir)

    def test_store_flow(self):
        self.req("/api/store/me", expect=409)  # sem conta
        self.req("/api/accounts/offline", {"name": "Steve"})
        self.req("/api/store/me", expect=401)
        cat = self.req("/api/store/catalog")
        self.assertTrue(cat["items"])
        self.req("/api/store/login", {})
        self.assertTrue(self.req("/api/state")["store_logged"])
        order = self.req("/api/store/checkout", {"items": ["cape_royal"], "method": "demo"})
        self.store_state.db.fulfill(order["id"])
        self.assertEqual(self.req(f"/api/store/orders/{order['id']}")["status"], "paid")
        me = self.req("/api/store/equip", {"slot": "cape", "cosmetic": "cape_royal"})
        self.assertEqual(me["equipped"], {"cape": "cape_royal"})
        self.req("/api/store/checkout", {"items": ["cape_royal"], "method": "demo"}, expect=409)

    def test_prepare_writes_config_and_mod(self):
        jar = self.tmp / "local.jar"
        jar.write_bytes(b"PK")
        settings.set("mod_url", str(jar))
        settings.set("performance_mods", [])
        inst = client.get_instance()
        client.prepare(inst, log=lambda m: None)
        self.assertEqual((inst.mods_dir / "spkpvp.jar").read_bytes(), b"PK")
        cfg = json.loads((client.config_dir(inst) / "client.json").read_text())
        self.assertEqual(cfg["api_url"], self.store_cfg.public_url)

    def test_play_requires_account(self):
        self.req("/api/play", {}, expect=409)


if __name__ == "__main__":
    unittest.main()
