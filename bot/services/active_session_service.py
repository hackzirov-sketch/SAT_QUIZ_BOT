import time

from bot.services.attempt_service import finish_attempt


async def get_resumable_attempt(db, user_id: int) -> tuple[dict, dict] | tuple[None, None]:
    session = await (await db.execute(
        '''
        SELECT s.*
        FROM active_sessions s
        JOIN attempts a ON a.id = s.attempt_id
        WHERE s.user_id = ? AND s.status = ? AND a.status = ?
        ORDER BY s.updated_at DESC
        LIMIT 1
        ''',
        (user_id, 'active', 'active'),
    )).fetchone()
    if not session:
        return None, None

    if session['expires_at'] and int(time.time()) >= session['expires_at']:
        await finish_attempt(db, session['attempt_id'], 'timed_out')
        return None, None

    attempt = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (session['attempt_id'],))).fetchone()
    if not attempt:
        return None, None
    return dict(attempt), dict(session)
