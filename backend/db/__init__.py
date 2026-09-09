"""TRINETRA database layer — SQLite persistence (M5, §14).

Direct `sqlite3` + thin DAO + numbered SQL migrations via the
`user_version` pragma — no ORM, zero new dependencies.

Connection model (C3): EVERY thread owns its own connection via
`threading.local` — the writer thread, each API/request thread, and the
session thread never share a sqlite3 Connection (check_same_thread trap).
Pragmas are applied per connection: WAL, synchronous=NORMAL,
busy_timeout=5000, foreign_keys=ON.
"""

from backend.db.connection import Database, db_connection
from backend.db.dao import DAO
from backend.db.writer import WriterError, EventWriter

__all__ = ["Database", "db_connection", "DAO", "EventWriter", "WriterError"]
