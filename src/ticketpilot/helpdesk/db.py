from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = (
    (
        "CREATE TABLE IF NOT EXISTS customers (\n"
        "    id TEXT PRIMARY KEY,\n"
        "    email TEXT NOT NULL UNIQUE,\n"
        "    name TEXT NOT NULL,\n"
        "    company TEXT NOT NULL DEFAULT '',\n"
        "    status TEXT NOT NULL DEFAULT 'active',\n"
        "    fraud_flag INTEGER NOT NULL DEFAULT 0,\n"
        "    created_at TEXT NOT NULL\n"
        ");"
    ),
    (
        "CREATE TABLE IF NOT EXISTS subscriptions (\n"
        "    customer_id TEXT PRIMARY KEY REFERENCES customers(id),\n"
        "    plan TEXT NOT NULL,\n"
        "    seats INTEGER NOT NULL DEFAULT 1,\n"
        "    billing_cycle TEXT NOT NULL DEFAULT 'monthly',\n"
        "    status TEXT NOT NULL DEFAULT 'active',\n"
        "    renews_on TEXT,\n"
        "    cancel_at_period_end INTEGER NOT NULL DEFAULT 0\n"
        ");"
    ),
    (
        "CREATE TABLE IF NOT EXISTS orders (\n"
        "    id TEXT PRIMARY KEY,\n"
        "    customer_id TEXT NOT NULL REFERENCES customers(id),\n"
        "    kind TEXT NOT NULL,\n"
        "    description TEXT NOT NULL,\n"
        "    amount_cents INTEGER NOT NULL,\n"
        "    currency TEXT NOT NULL DEFAULT 'USD',\n"
        "    status TEXT NOT NULL,\n"
        "    created_at TEXT NOT NULL,\n"
        "    refunded_cents INTEGER NOT NULL DEFAULT 0\n"
        ");"
    ),
    (
        "CREATE TABLE IF NOT EXISTS refunds (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    order_id TEXT NOT NULL REFERENCES orders(id),\n"
        "    amount_cents INTEGER NOT NULL,\n"
        "    reason TEXT NOT NULL,\n"
        "    issued_by TEXT NOT NULL,\n"
        "    created_at TEXT NOT NULL\n"
        ");"
    ),
    (
        "CREATE TABLE IF NOT EXISTS tickets (\n"
        "    id TEXT PRIMARY KEY,\n"
        "    customer_email TEXT NOT NULL,\n"
        "    customer_name TEXT NOT NULL DEFAULT '',\n"
        "    subject TEXT NOT NULL,\n"
        "    body TEXT NOT NULL,\n"
        "    channel TEXT NOT NULL DEFAULT 'email',\n"
        "    status TEXT NOT NULL DEFAULT 'new',\n"
        "    assignee TEXT,\n"
        "    created_at TEXT NOT NULL,\n"
        "    triage_json TEXT,\n"
        "    proposal_json TEXT,\n"
        "    draft_json TEXT,\n"
        "    thread_id TEXT\n"
        ");"
    ),
    (
        "CREATE TABLE IF NOT EXISTS notes (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    ticket_id TEXT NOT NULL REFERENCES tickets(id),\n"
        "    author TEXT NOT NULL,\n"
        "    body TEXT NOT NULL,\n"
        "    created_at TEXT NOT NULL\n"
        ");"
    ),
    (
        "CREATE TABLE IF NOT EXISTS escalations (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    ticket_id TEXT NOT NULL REFERENCES tickets(id),\n"
        "    team TEXT NOT NULL,\n"
        "    reason TEXT NOT NULL,\n"
        "    escalated_by TEXT NOT NULL,\n"
        "    created_at TEXT NOT NULL\n"
        ");"
    ),
    (
        "CREATE TABLE IF NOT EXISTS password_resets (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    customer_id TEXT NOT NULL REFERENCES customers(id),\n"
        "    sent_to TEXT NOT NULL,\n"
        "    created_at TEXT NOT NULL\n"
        ");"
    ),
    (
        "CREATE TABLE IF NOT EXISTS audit_log (\n"
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    ts TEXT NOT NULL,\n"
        "    actor TEXT NOT NULL,\n"
        "    action TEXT NOT NULL,\n"
        "    target TEXT NOT NULL,\n"
        "    detail TEXT NOT NULL DEFAULT '{}'\n"
        ");"
    ),
)


class Database:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()
        with self.transaction() as connection:
            for statement in SCHEMA:
                connection.execute(statement)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                yield self._connection
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def close(self) -> None:
        self._connection.close()
