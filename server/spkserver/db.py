"""Banco SQLite: jogadores, sessões, pedidos, cosméticos comprados e equipados."""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from . import catalog

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    uuid TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    uuid TEXT NOT NULL REFERENCES users(uuid),
    expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS challenges (
    server_id TEXT PRIMARY KEY,
    expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    uuid TEXT NOT NULL REFERENCES users(uuid),
    items TEXT NOT NULL,
    total INTEGER NOT NULL,
    method TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_ref TEXT,
    status TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    created REAL NOT NULL,
    paid_at REAL
);
CREATE INDEX IF NOT EXISTS orders_provider_ref ON orders(provider, provider_ref);
CREATE TABLE IF NOT EXISTS owned (
    uuid TEXT NOT NULL REFERENCES users(uuid),
    cosmetic TEXT NOT NULL,
    order_id TEXT,
    acquired REAL NOT NULL,
    PRIMARY KEY (uuid, cosmetic)
);
CREATE TABLE IF NOT EXISTS equipped (
    uuid TEXT NOT NULL REFERENCES users(uuid),
    slot TEXT NOT NULL,
    cosmetic TEXT NOT NULL,
    PRIMARY KEY (uuid, slot)
);
"""

SESSION_TTL = 30 * 24 * 3600
FREE = [c["id"] for c in catalog.COSMETICS.values() if c["price"] == 0]


def normalize_uuid(value: str) -> str:
    return value.replace("-", "").lower()


class DB:
    def __init__(self, path: Path | str) -> None:
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    def _q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, args).fetchall()

    # ------------------------------------------------------------ jogadores
    def upsert_user(self, uuid: str, name: str) -> None:
        uuid = normalize_uuid(uuid)
        now = time.time()
        with self.lock:
            self.conn.execute("INSERT INTO users(uuid, name, created) VALUES (?, ?, ?) "
                              "ON CONFLICT(uuid) DO UPDATE SET name = excluded.name", (uuid, name, now))
            for cid in FREE:
                self.conn.execute("INSERT OR IGNORE INTO owned(uuid, cosmetic, acquired) VALUES (?, ?, ?)",
                                  (uuid, cid, now))

    def user(self, uuid: str) -> dict | None:
        rows = self._q("SELECT uuid, name FROM users WHERE uuid = ?", (normalize_uuid(uuid),))
        return dict(rows[0]) if rows else None

    # ------------------------------------------------------------ sessões
    def new_challenge(self) -> str:
        server_id = secrets.token_hex(16)
        with self.lock:
            self.conn.execute("DELETE FROM challenges WHERE expires < ?", (time.time(),))
            self.conn.execute("INSERT INTO challenges VALUES (?, ?)", (server_id, time.time() + 120))
        return server_id

    def consume_challenge(self, server_id: str) -> bool:
        with self.lock:
            cur = self.conn.execute("DELETE FROM challenges WHERE server_id = ? AND expires >= ?",
                                    (server_id, time.time()))
            return cur.rowcount == 1

    def new_session(self, uuid: str) -> str:
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.conn.execute("DELETE FROM sessions WHERE expires < ?", (time.time(),))
            self.conn.execute("INSERT INTO sessions VALUES (?, ?, ?)",
                              (token, normalize_uuid(uuid), time.time() + SESSION_TTL))
        return token

    def session_user(self, token: str) -> dict | None:
        rows = self._q("SELECT u.uuid, u.name FROM sessions s JOIN users u ON u.uuid = s.uuid "
                       "WHERE s.token = ? AND s.expires >= ?", (token, time.time()))
        return dict(rows[0]) if rows else None

    def delete_session(self, token: str) -> None:
        self._q("DELETE FROM sessions WHERE token = ?", (token,))

    # ------------------------------------------------------------ cosméticos
    def owned(self, uuid: str) -> list[str]:
        return [r["cosmetic"] for r in self._q("SELECT cosmetic FROM owned WHERE uuid = ? ORDER BY acquired",
                                               (normalize_uuid(uuid),))]

    def equipped(self, uuid: str) -> dict[str, str]:
        return {r["slot"]: r["cosmetic"] for r in self._q("SELECT slot, cosmetic FROM equipped WHERE uuid = ?",
                                                          (normalize_uuid(uuid),))}

    def equip(self, uuid: str, slot: str, cosmetic: str | None) -> None:
        uuid = normalize_uuid(uuid)
        if slot not in catalog.SLOTS:
            raise ValueError("Slot inválido")
        with self.lock:
            if cosmetic is None:
                self.conn.execute("DELETE FROM equipped WHERE uuid = ? AND slot = ?", (uuid, slot))
                return
            item = catalog.COSMETICS.get(cosmetic)
            if not item or item["type"] != slot:
                raise ValueError("Cosmético inválido para este slot")
            if cosmetic not in self.owned(uuid):
                raise PermissionError("Você não possui este cosmético")
            self.conn.execute("INSERT OR REPLACE INTO equipped VALUES (?, ?, ?)", (uuid, slot, cosmetic))

    # ------------------------------------------------------------ pedidos
    def create_order(self, uuid: str, items: list[str], total: int, method: str, provider: str) -> str:
        order_id = "spk_" + secrets.token_hex(10)
        self._q("INSERT INTO orders(id, uuid, items, total, method, provider, status, created) "
                "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
                (order_id, normalize_uuid(uuid), json.dumps(items), total, method, provider, time.time()))
        return order_id

    def update_order(self, order_id: str, provider_ref: str | None = None, details: dict | None = None,
                     status: str | None = None) -> None:
        with self.lock:
            if provider_ref is not None:
                self.conn.execute("UPDATE orders SET provider_ref = ? WHERE id = ?", (provider_ref, order_id))
            if details is not None:
                self.conn.execute("UPDATE orders SET details = ? WHERE id = ?", (json.dumps(details), order_id))
            if status is not None:
                self.conn.execute("UPDATE orders SET status = ? WHERE id = ? AND status = 'pending'",
                                  (status, order_id))

    def order(self, order_id: str) -> dict | None:
        rows = self._q("SELECT * FROM orders WHERE id = ?", (order_id,))
        return self._order_dict(rows[0]) if rows else None

    def order_by_ref(self, provider: str, ref: str) -> dict | None:
        rows = self._q("SELECT * FROM orders WHERE provider = ? AND provider_ref = ?", (provider, ref))
        return self._order_dict(rows[0]) if rows else None

    def orders(self, uuid: str) -> list[dict]:
        return [self._order_dict(r) for r in self._q("SELECT * FROM orders WHERE uuid = ? ORDER BY created DESC",
                                                     (normalize_uuid(uuid),))]

    @staticmethod
    def _order_dict(row: sqlite3.Row) -> dict:
        data = dict(row)
        data["items"] = json.loads(data["items"])
        data["details"] = json.loads(data["details"] or "{}")
        return data

    def fulfill(self, order_id: str) -> bool:
        """Marca o pedido como pago e entrega os cosméticos. Idempotente:
        retorna False se o pedido já tinha sido pago (ou não está pendente)."""
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                cur = self.conn.execute("UPDATE orders SET status = 'paid', paid_at = ? "
                                        "WHERE id = ? AND status = 'pending'", (time.time(), order_id))
                if cur.rowcount != 1:
                    self.conn.execute("ROLLBACK")
                    return False
                row = self.conn.execute("SELECT uuid, items FROM orders WHERE id = ?", (order_id,)).fetchone()
                now = time.time()
                for item in json.loads(row["items"]):
                    for cid in catalog.expand(item):
                        self.conn.execute("INSERT OR IGNORE INTO owned VALUES (?, ?, ?, ?)",
                                          (row["uuid"], cid, order_id, now))
                self.conn.execute("COMMIT")
                return True
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
