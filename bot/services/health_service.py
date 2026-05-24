from __future__ import annotations

import os
import time
from typing import Any

from bot.config import DATABASE_PATH
from bot.database import integrity_check, is_db_healthy, sqlite_file_stats
from bot.runtime_state import runtime_state


async def health_snapshot() -> dict[str, Any]:
    ok = await is_db_healthy()
    runtime_state.last_db_check_ok = ok
    runtime_state.last_db_check_at = time.time()
    runtime_state.last_db_error = '' if ok else 'db_unhealthy'
    stats = sqlite_file_stats(DATABASE_PATH)
    return {
        'ok': ok and runtime_state.vocabulary_count > 0,
        'flask_alive': runtime_state.flask_alive,
        'polling_alive': runtime_state.polling_alive,
        'scheduler_alive': dict(runtime_state.scheduler_alive),
        'db_alive': ok,
        'db_integrity_ok': await integrity_check() if ok else False,
        'vocabulary_loaded': runtime_state.vocabulary_count > 0,
        'vocabulary_count': runtime_state.vocabulary_count,
        'last_successful_db_check': runtime_state.last_db_check_at if ok else None,
        'wal_size': stats['wal_size'],
        'db_size': stats['db_size'],
        'uptime_seconds': runtime_state.snapshot()['uptime_seconds'],
        'render_disk_mounted': os.path.isdir('/data') if os.name == 'posix' else None,
    }


async def admin_diagnostics() -> dict[str, Any]:
    snap = await health_snapshot()
    snap.update(runtime_state.snapshot())
    return snap
