from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_sessionfinish(session, exitstatus):
    try:
        from bot import database

        conn = getattr(database, "_db_conn", None)
        if conn is not None:
            asyncio.run(conn.close())
            database._db_conn = None
            database._db_lock = None
    except Exception:
        pass
