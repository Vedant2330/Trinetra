"""TRINETRA DB connection management (M5, §14, C3).

Per-thread connections via threading.local. Pragmas on EVERY connection:
  - journal_mode=WAL        (writer + readers concurrently)
  - synchronous=NORMAL      (WAL-safe, durable enough for MVP)
  - busy_timeout=5000 ms   (writer/API contention)
  - foreign_keys=ON         (schema integrity)

Migration runner: transactional, numbered, recorded in `user_version`.
A failing migration ROLLS BACK and leaves user_version untouched
(architect mandate — tested with an injected-bad-SQL migration).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger("trinetra.db")

_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA foreign_keys=ON",
)


def apply_pragmas(conn: sqlite3.Connection) -> None:
    for stmt in _PRAGMAS:
        conn.execute(stmt)


def _statements(sql: str) -> list[str]:
    """Split a migration script into individual statements (semicolon-
    terminated). Comments are stripped first; trivial splitter — the
    frozen §14 schema has no semicolons inside strings/expressions."""
    lines = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    out = []
    for stmt in "\n".join(lines).split(";"):
        if stmt.strip():
            out.append(stmt.strip())
    return out


class Database:
    """One logical database = one file + per-thread connections.

    `conn()` returns the CALLING thread's connection (created on first
    use, cached in a threading.local). `close()` closes only the calling
    thread's connection; `close_all()` is for tests/teardown.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._local = threading.local()
        self._all_conns_lock = threading.Lock()
        self._all_conns: list[sqlite3.Connection] = []
        self._conn_owners: dict[int, threading.Thread] = {}
        if self.path != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)

    # ---- per-thread connections (C3) + dead-thread reaping (M6 churn) ----

    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            self._reap_dead()            # churn guard: reap dead threads
            c = sqlite3.connect(str(self.path), timeout=5.0)
            c.row_factory = sqlite3.Row
            apply_pragmas(c)
            self._local.conn = c
            with self._all_conns_lock:
                self._all_conns.append(c)
                self._conn_owners[id(c)] = threading.current_thread()
        return c

    def _reap_dead(self) -> None:
        """Close connections whose owning thread has DIED. Session
        threads are per-session; without this, 10 sessions leak ~30 fds
        (db + wal + shm per connection). Called on every new-connection
        creation (cheap: no locks held during close)."""
        with self._all_conns_lock:
            dead_conns = [c for c, t in zip(self._all_conns,
                                            (self._conn_owners.get(id(c))
                                             for c in self._all_conns))
                          if t is not None and not t.is_alive()]
            for c in dead_conns:
                try:
                    c.close()
                except sqlite3.Error:
                    pass
                self._all_conns.remove(c)
                self._conn_owners.pop(id(c), None)

    def close(self) -> None:
        c = getattr(self._local, "conn", None)
        if c is not None:
            try:
                c.close()
            except sqlite3.Error:
                pass
            self._local.conn = None

    def close_all(self) -> None:
        with self._all_conns_lock:
            for c in self._all_conns:
                try:
                    c.close()
                except sqlite3.Error:
                    pass
            self._all_conns.clear()
            self._conn_owners.clear()

    # ---- migrations (§14: numbered SQL, user_version pragma) ----

    def migrate(self, migrations: dict[int, str]) -> int:
        """Apply pending migrations IN ORDER, each inside a transaction.

        Returns the number applied. A failed migration rolls back and
        raises; user_version is NOT advanced on failure. Statements are
        executed one-by-one (NOT executescript — that API issues its own
        COMMIT and would break the all-or-nothing guarantee).
        """
        conn = self.conn()
        applied = 0
        for version in sorted(migrations):
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            if current >= version:
                continue
            log.info("applying migration %d", version)
            try:
                conn.execute("BEGIN IMMEDIATE")
                for stmt in _statements(migrations[version]):
                    conn.execute(stmt)
                conn.execute(f"PRAGMA user_version = {int(version)}")
                conn.commit()
                applied += 1
            except sqlite3.Error:
                conn.rollback()
                log.exception("migration %d failed — rolled back", version)
                raise
        return applied

    def user_version(self) -> int:
        return int(self.conn().execute("PRAGMA user_version").fetchone()[0])


def db_connection(path: str | Path) -> Database:
    """Convenience constructor (used by lifespan and tests)."""
    return Database(path)


def _singleton_ref() -> None:  # pragma: no cover — doc anchor
    """The app-scoped Database lives in backend.main lifespan (C1);
    modules receive it — no module-level global state here."""


def resolve_path(path: str | Path) -> Path:  # pragma: no cover — helper
    return Path(path)
