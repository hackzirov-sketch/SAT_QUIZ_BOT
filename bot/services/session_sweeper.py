import asyncio
import logging
import time

from bot.config import SESSION_SWEEP_INTERVAL
from bot.database import get_db
from bot.services.attempt_service import finish_attempt

logger = logging.getLogger(__name__)


async def expire_overdue_sessions(limit: int = 100) -> int:
    db = await get_db()
    now_ts = int(time.time())
    rows = await (
        await db.execute(
            '''
            SELECT a.id
            FROM attempts a
            JOIN active_sessions s ON s.attempt_id = a.id
            WHERE a.status = 'active'
              AND s.status = 'active'
              AND s.expires_at > 0
              AND s.expires_at <= ?
            ORDER BY s.expires_at ASC
            LIMIT ?
            ''',
            (now_ts, limit),
        )
    ).fetchall()

    expired = 0
    for row in rows:
        finished = await finish_attempt(db, row['id'], 'timed_out')
        if finished and finished['status'] == 'timed_out':
            expired += 1
    return expired


async def run_session_sweeper() -> None:
    while True:
        try:
            expired = await expire_overdue_sessions()
            if expired:
                logger.info("expired_sessions count=%s", expired)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("session_sweeper_failed")
        await asyncio.sleep(SESSION_SWEEP_INTERVAL)
