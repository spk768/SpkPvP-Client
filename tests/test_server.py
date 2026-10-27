import hashlib
import hmac
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from spkserver import app, catalog  # noqa: E402
from spkserver.config import Config  # noqa: E402
from spkserver.payments import http as payhttp, mercadopago, paypal  # noqa: E402

CPF = "52998224725"
PAYER = {"email": "a@b.com", "first_name": "Ana", "last_name": "Silva", "cpf": CPF}


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg = Config(port=0, db_path=Path(self.tmp.name) / "t.db", dev=True, mp_access_token="TEST",
                          paypal_client_id="id", paypal_secret="secret", mp_webhook_secret="whsec")
        self.server, self.store = app.serve(self.cfg)
        self.port = self.server.server_address[1]
        self.cfg.public_url = f"http://127.0.0.1:{self.port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.token = self.call("/api/auth/offline", {"name": "Steve"})["token"]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.store.db.conn.close()
        self.tmp.cleanup()

    def call(self, path, body=None, token=None, headers=None, expect=200):
        hdrs = {"Content-Type": "application/json", **(headers or {})}
        if token:
            hdrs["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        self.assertEqual(status, expect, raw)
        return json.loads(raw) if raw[:1] in (b"{", b"[") else raw

    def test_catalog_and_free_cape(self):
        cat = self.call("/api/catalog")
        self.assertIn("cape_ember", [i["id"] for i in cat["items"]])
        self.assertEqual({m["id"] for m in cat["methods"]},
                         {"pix", "boleto", "credit_card", "debit_card", "paypal", "demo"})
        me = self.call("/api/me", token=self.token)
        self.assertEqual(me["owned"], ["cape_spk"])
        self.call("/api/equip", {"slot": "cape", "cosmetic": "cape_spk"}, self.token)
        pub = self.call(f"/api/players/{me['uuid']}/cosmetics")
        self.assertTrue(pub["cape"]["texture"].endswith("/textures/cape_spk.png"))
        self.assertEqual(self.call("/textures/cape_spk.png")[:4], b"\x89PNG")

    def test_security(self):
        self.call("/api/me", expect=401)
        self.call("/api/me", token="nope", expect=401)
        self.call("/api/equip", {"slot": "cape", "cosmetic": "cape_royal"}, self.token, expect=403)
        self.call("/api/equip", {"slot": "wings", "cosmetic": "cape_spk"}, self.token, expect=400)
        self.call("/api/checkout", {"items": ["cape_spk"], "method": "demo"}, self.token, expect=400)
        self.call("/api/checkout", {"items": ["nope"], "method": "demo"}, self.token, expect=400)
        self.call("/api/checkout", {"items": ["cape_ember"], "method": "bitcoin"}, self.token, expect=400)
        self.cfg.dev = False
        self.call("/api/auth/offline", {"name": "Alex"}, expect=403)

    def test_demo_purchase_and_bundle(self):
        order = self.call("/api/checkout", {"items": ["bundle_starter"], "method": "demo"}, self.token)
        self.assertEqual(order["total"], 3490)
        self.call(f"/demo/pay?order={order['id']}", {})
        self.assertEqual(self.call(f"/api/orders/{order['id']}", token=self.token)["status"], "paid")
        me = self.call("/api/me", token=self.token)
        self.assertTrue({"cape_ember", "cape_ocean", "wings_angel"} <= set(me["owned"]))
        self.call("/api/equip", {"slot": "wings", "cosmetic": "wings_angel"}, self.token)
        self.call("/api/checkout", {"items": ["cape_ember"], "method": "demo"}, self.token, expect=409)
        # pagar de novo não duplica nada
        self.assertFalse(self.store.db.fulfill(order["id"]))
        # outro jogador não vê o pedido
        other = self.call("/api/auth/offline", {"name": "Alex"})["token"]
        self.call(f"/api/orders/{order['id']}", token=other, expect=404)

    def test_pix_flow_with_webhook(self):
        calls = []

        def fake(method, url, body=None, headers=None, **kw):
            calls.append((method, url, body, headers))
            if url.endswith("/v1/payments"):
                return {"id": 123, "point_of_interaction": {"transaction_data": {"qr_code": "000201PIX",
                                                                                   "qr_code_base64": "AAA"}}}
            if url.endswith("/v1/payments/123"):
                return {"id": 123, "status": "approved", "transaction_amount": 9.9,
                        "external_reference": order["id"]}
            raise AssertionError(url)

        with mock.patch.object(mercadopago, "request", fake):
            self.call("/api/checkout", {"items": ["cape_ember"], "method": "pix", "payer": {**PAYER, "cpf": "1"}},
                      self.token, expect=402)
            order = self.call("/api/checkout", {"items": ["cape_ember"], "method": "pix", "payer": PAYER},
                              self.token)
            self.assertEqual(order["details"]["qr_code"], "000201PIX")
            body = calls[-1][2]
            self.assertEqual(body["transaction_amount"], 9.9)
            self.assertEqual(body["payment_method_id"], "pix")
            self.assertEqual(calls[-1][3]["X-Idempotency-Key"], order["id"])

            # webhook com assinatura errada é recusado
            self.call("/webhooks/mercadopago?data.id=123&type=payment", {"type": "payment"},
                      headers={"x-signature": "ts=1,v1=bad", "x-request-id": "r"}, expect=401)
            sig = hmac.new(b"whsec", b"id:123;request-id:r;ts:1;", hashlib.sha256).hexdigest()
            self.call("/webhooks/mercadopago?data.id=123&type=payment", {"type": "payment"},
                      headers={"x-signature": f"ts=1,v1={sig}", "x-request-id": "r"})
        self.assertIn("cape_ember", self.call("/api/me", token=self.token)["owned"])

    def test_wrong_amount_is_not_fulfilled(self):
        def fake(method, url, body=None, headers=None, **kw):
            if url.endswith("/v1/payments"):
                return {"id": 9, "point_of_interaction": {"transaction_data": {}}}
            return {"id": 9, "status": "approved", "transaction_amount": 0.01}

        with mock.patch.object(mercadopago, "request", fake):
            order = self.call("/api/checkout", {"items": ["cape_royal"], "method": "pix", "payer": PAYER},
                              self.token)
            self.assertEqual(self.call(f"/api/orders/{order['id']}", token=self.token)["status"], "failed")
        self.assertNotIn("cape_royal", self.call("/api/me", token=self.token)["owned"])

    def test_boleto_requires_address(self):
        with mock.patch.object(mercadopago, "request", lambda *a, **k: {"id": 5, "barcode": {"content": "237"}}):
            self.call("/api/checkout", {"items": ["cape_ocean"], "method": "boleto", "payer": PAYER},
                      self.token, expect=402)
            addr = {"zip_code": "01310-100", "street_name": "Av. Paulista", "street_number": "1000",
                    "neighborhood": "Bela Vista", "city": "São Paulo", "federal_unit": "sp"}
            order = self.call("/api/checkout", {"items": ["cape_ocean"], "method": "boleto",
                                                "payer": {**PAYER, "address": addr}}, self.token)
        self.assertEqual(order["details"]["barcode"], "237")

    def test_card_uses_checkout_pro(self):
        seen = {}

        def fake(method, url, body=None, headers=None, **kw):
            seen["body"] = body
            return {"id": "pref", "init_point": "https://mp/checkout"}

        with mock.patch.object(mercadopago, "request", fake):
            order = self.call("/api/checkout", {"items": ["cape_ocean"], "method": "debit_card", "payer": {}},
                              self.token)
        self.assertEqual(order["details"], {"kind": "redirect", "url": "https://mp/checkout"})
        excluded = {t["id"] for t in seen["body"]["payment_methods"]["excluded_payment_types"]}
        self.assertNotIn("debit_card", excluded)
        self.assertIn("credit_card", excluded)

    def test_paypal_capture(self):
        def fake(method, url, body=None, headers=None, **kw):
            if url.endswith("/oauth2/token"):
                return {"access_token": "tok", "expires_in": 3600}
            if url.endswith("/v2/checkout/orders"):
                self.assertEqual(body["purchase_units"][0]["amount"], {"currency_code": "BRL", "value": "29.90"})
                return {"id": "PP1", "links": [{"rel": "payer-action", "href": "https://paypal/approve"}]}
            if url.endswith("/v2/checkout/orders/PP1"):
                return {"status": "APPROVED"}
            if url.endswith("/capture"):
                return {"status": "COMPLETED", "purchase_units": [{"payments": {"captures": [
                    {"status": "COMPLETED", "amount": {"value": "29.90"}}]}}]}
            raise AssertionError(url)

        with mock.patch.object(paypal, "request", fake):
            order = self.call("/api/checkout", {"items": ["wings_demon"], "method": "paypal"}, self.token)
            self.assertEqual(order["details"]["url"], "https://paypal/approve")
            page = self.call(f"/checkout/return?order={order['id']}")
            self.assertIn(b"aprovado", page)
        self.assertIn("wings_demon", self.call("/api/me", token=self.token)["owned"])

    def test_helpers(self):
        self.assertTrue(mercadopago.valid_cpf("529.982.247-25"))
        self.assertFalse(mercadopago.valid_cpf("111.111.111-11"))
        self.assertEqual(payhttp.to_cents("34.9"), 3490)
        self.assertEqual(payhttp.to_cents(0.1 + 0.2), 30)
        self.assertEqual(payhttp.from_cents(990), "9.90")
        # UUID offline idêntico ao do Minecraft
        self.assertEqual(app.offline_uuid("Notch"), "b50ad385829d3141a2167e7d7539ba7f")
        self.assertEqual(catalog.expand("bundle_starter"), ["cape_ember", "cape_ocean", "wings_angel"])


if __name__ == "__main__":
    unittest.main()
