from datetime import datetime

from bot.config import WIN_SCORE_THRESHOLD
from bot.database import db_transaction, now_iso


def _completion_seconds(started_at: str, finished_at: str) -> int:
    try:
        start_dt = datetime.fromisoformat(started_at)
        end_dt = datetime.fromisoformat(finished_at)
        return max(0, int((end_dt - start_dt).total_seconds()))
    except (TypeError, ValueError):
        return 0


async def _ensure_statistics(db, user_id: int, now: str) -> None:
    await db.execute(
        'INSERT OR IGNORE INTO statistics (user_id, updated_at) VALUES (?, ?)',
        (user_id, now),
    )


async def _update_statistics(db, attempt: dict, now: str) -> None:
    if attempt['status'] not in ('completed', 'timed_out'):
        return
    if attempt.get('quiz_mode') == 'mock':
        return

    score = attempt['score'] or 0
    seconds = attempt['completion_seconds']
    is_win = 1 if score >= WIN_SCORE_THRESHOLD and attempt['status'] == 'completed' else 0
    await _ensure_statistics(db, attempt['user_id'], now)
    await db.execute(
        '''
        UPDATE statistics
        SET attempts_count = attempts_count + 1,
            total_score = total_score + ?,
            best_score = MAX(best_score, ?),
            best_time = CASE
                WHEN ? IS NOT NULL AND (best_time IS NULL OR ? < best_time) THEN ?
                ELSE best_time
            END,
            correct_answers = correct_answers + ?,
            wrong_answers = wrong_answers + ?,
            current_win_streak = CASE WHEN ? = 1 THEN current_win_streak + 1 ELSE 0 END,
            best_win_streak = MAX(best_win_streak, CASE WHEN ? = 1 THEN current_win_streak + 1 ELSE best_win_streak END),
            favorite_mode = ?,
            updated_at = ?
        WHERE user_id = ?
        ''',
        (
            score,
            score,
            seconds,
            seconds,
            seconds,
            attempt['correct_count'] or 0,
            attempt['wrong_count'] or 0,
            is_win,
            is_win,
            attempt['mode'],
            now,
            attempt['user_id'],
        ),
    )


async def _upsert_leaderboard(db, attempt: dict, now: str) -> None:
    if attempt['status'] not in ('completed', 'timed_out'):
        return
    if attempt.get('quiz_mode') == 'mock':
        return
    await db.execute(
        '''
        INSERT INTO leaderboard (attempt_id, user_id, score, completion_seconds, mode, finished_at)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(attempt_id) DO UPDATE SET
            score=excluded.score,
            completion_seconds=excluded.completion_seconds,
            mode=excluded.mode,
            finished_at=excluded.finished_at
        ''',
        (
            attempt['id'],
            attempt['user_id'],
            attempt['score'] or 0,
            attempt['completion_seconds'] or 0,
            attempt['mode'],
            attempt['finished_at'] or now,
        ),
    )


async def finish_attempt(db, attempt_id: int, status: str) -> dict | None:
    if status not in ('completed', 'timed_out', 'cancelled'):
        raise ValueError(f'Invalid attempt status: {status}')

    now = now_iso()
    attempt = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
    if not attempt:
        return None

    seconds = _completion_seconds(attempt['started_at'], now)
    async with db_transaction() as tx:
        cursor = await tx.execute(
            'UPDATE attempts SET status = ?, finished_at = ?, completion_seconds = ? WHERE id = ? AND status = ?',
            (status, now, seconds, attempt_id, 'active'),
        )
        await tx.execute(
            'UPDATE active_sessions SET status = ?, updated_at = ? WHERE attempt_id = ? AND status = ?',
            (status, now, attempt_id, 'active'),
        )
        if cursor.rowcount != 1:
            return await (await tx.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()

        finished = await (await tx.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
        if finished:
            await _update_statistics(tx, dict(finished), now)
            await _upsert_leaderboard(tx, dict(finished), now)
        return dict(finished) if finished else None
