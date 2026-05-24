from __future__ import annotations

import json

from bot.database import db_transaction, now_iso


def compact_question_payload(questions: list[dict], fields: tuple[str, ...]) -> str:
    return json.dumps(
        [{k: q[k] for k in fields if k in q} for q in questions],
        ensure_ascii=False,
        separators=(',', ':'),
    )


async def create_attempt_with_session(
    *,
    user_id: int,
    chat_id: int,
    mode: str,
    difficulty: str,
    category: str,
    total_questions: int,
    question_order_json: str,
    order_hash: str,
    expires_at: int,
    quiz_mode: str,
) -> int:
    now = now_iso()
    async with db_transaction() as tx:
        cursor = await tx.execute(
            'INSERT INTO attempts (user_id, mode, difficulty, category, total_questions, question_order_json, order_hash, started_at, status, quiz_mode) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (user_id, mode, difficulty, category, total_questions, question_order_json, order_hash, now, 'active', quiz_mode),
        )
        attempt_id = cursor.lastrowid
        if not attempt_id:
            row = await (await tx.execute('SELECT last_insert_rowid() AS id')).fetchone()
            attempt_id = row['id']
        await tx.execute(
            'INSERT INTO active_sessions (attempt_id, user_id, chat_id, expires_at, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)',
            (attempt_id, user_id, chat_id, expires_at, 'active', now, now),
        )
    return int(attempt_id)
