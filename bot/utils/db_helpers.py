import json
import os
from bot.database import db_transaction, get_db, now_iso
from bot.config import ROOT, VOCABULARY_PATH, LEVEL_THRESHOLDS
from bot.quiz_engine import level_name

async def load_vocabulary(db) -> list:
    from bot.database import set_json_fallback

    try:
        cursor = await db.execute('SELECT COUNT(*) as c FROM vocabulary')
        row = await cursor.fetchone()
    except Exception:
        logger = __import__('logging').getLogger(__name__)
        logger.exception('db_fetch_vocab_count_failed_falling_back_to_json')
        return _load_vocab_json_fallback()

    json_path = VOCABULARY_PATH or str(ROOT / 'data/vocabulary.json')
    if row and row['c'] > 0 and not os.path.exists(json_path):
        cursor = await db.execute('SELECT * FROM vocabulary ORDER BY id')
        vocab = await cursor.fetchall()
        set_json_fallback({'source': 'db', 'data': [dict(v) for v in vocab]})
        return vocab
    if not os.path.exists(json_path):
        return []

    with open(json_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    existing_rows = await (await db.execute('SELECT LOWER(english) AS english FROM vocabulary')).fetchall()
    existing_en = {r['english'] for r in existing_rows}
    seen_en = set()
    seen_pair = set()
    cleaned = []
    primary_updates = []
    for item in raw:
        eng = (item.get('english', '') or '').strip().lower()
        uzb = (item.get('uzbek', '') or '').strip()
        cat = item.get('category', 'General') or 'General'
        src = item.get('source', 'Admin') or 'Admin'
        diff = item.get('difficulty')
        if not eng or not uzb:
            continue
        if src == 'User SAT Core':
            primary_updates.append((uzb, cat, src, diff, eng))
        pk = f"{eng}:{uzb.lower()}"
        if eng in existing_en or eng in seen_en or pk in seen_pair:
            continue
        seen_en.add(eng)
        seen_pair.add(pk)
        cleaned.append((eng, uzb, cat, src, diff))

    if primary_updates:
        await db.executemany(
            'UPDATE vocabulary SET uzbek = ?, category = ?, source = ?, difficulty = ? WHERE LOWER(english) = ?',
            primary_updates,
        )
    if cleaned:
        await db.executemany(
            'INSERT INTO vocabulary (english, uzbek, category, source, difficulty) VALUES (?, ?, ?, ?, ?)',
            cleaned,
        )
    if primary_updates or cleaned:
        await db.commit()
    cursor = await db.execute('SELECT * FROM vocabulary ORDER BY id')
    vocab = await cursor.fetchall()
    set_json_fallback({'source': 'db', 'data': [dict(v) for v in vocab]})
    return vocab

async def upsert_user(db, telegram_id: int, username: str = None, first_name: str = None) -> dict:
    now = now_iso()
    try:
        async with db_transaction() as tx:
            await tx.execute(
                'INSERT INTO users (telegram_id, username, first_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?) '
                'ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name, updated_at=excluded.updated_at',
                (telegram_id, username, first_name, now, now),
            )
            cursor = await tx.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
            user = await cursor.fetchone()
            if user:
                await tx.execute('INSERT OR IGNORE INTO settings (user_id, updated_at) VALUES (?, ?)', (user['id'], now))
                await tx.execute('INSERT OR IGNORE INTO statistics (user_id, updated_at) VALUES (?, ?)', (user['id'], now))
        return user
    except Exception:
        logger = __import__('logging').getLogger(__name__)
        logger.exception('upsert_user_failed tg_id=%s', telegram_id)
        return {'id': 0, 'telegram_id': telegram_id, 'username': username, 'first_name': first_name}

async def ensure_settings(db, user_id: int):
    cursor = await db.execute('SELECT id FROM settings WHERE user_id = ?', (user_id,))
    if not await cursor.fetchone():
        await db.execute('INSERT INTO settings (user_id, updated_at) VALUES (?, ?)', (user_id, now_iso()))
        await db.commit()

async def ensure_statistics(db, user_id: int):
    cursor = await db.execute('SELECT id FROM statistics WHERE user_id = ?', (user_id,))
    if not await cursor.fetchone():
        await db.execute('INSERT INTO statistics (user_id, updated_at) VALUES (?, ?)', (user_id, now_iso()))
        await db.commit()

async def add_xp(db, user_id: int, amount: int) -> dict:
    async with db_transaction() as tx:
        cursor = await tx.execute('SELECT xp, level FROM statistics WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        old_level = row['level'] if row else 1
        old_xp = row['xp'] if row else 0
        new_xp = old_xp + amount
        new_level = 1
        for i in range(len(LEVEL_THRESHOLDS) - 1, -1, -1):
            if new_xp >= LEVEL_THRESHOLDS[i]:
                new_level = i
                break
        await tx.execute('UPDATE statistics SET xp = ?, level = ? WHERE user_id = ?', (new_xp, new_level, user_id))
    leveled_up = new_level > old_level
    return {'xp': new_xp, 'level': new_level, 'leveled_up': leveled_up, 'level_name': level_name(new_level)}

def row_get(row, key: str, default=None):
    if row is None:
        return default
    if hasattr(row, 'keys') and key in row.keys():
        return row[key]
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


async def weakness_data(db, user_id: int) -> list:
    try:
        cursor = await db.execute('''
            SELECT a.is_correct, v.category FROM answers a
            JOIN vocabulary v ON v.id = a.question_id
            WHERE a.attempt_id IN (SELECT id FROM attempts WHERE user_id = ?)
            ORDER BY a.answered_at DESC LIMIT 200
        ''', (user_id,))
        return await cursor.fetchall()
    except Exception:
        return []

async def record_mistake(db, user_id: int, vocab_id: int, english: str, uzbek: str, category: str):
    now = now_iso()
    try:
        async with db_transaction() as tx:
            await tx.execute(
                'INSERT INTO mistakes (user_id, vocab_id, english, uzbek, category, wrong_count, last_wrong_at) VALUES (?, ?, ?, ?, ?, 1, ?) '
                'ON CONFLICT(user_id, vocab_id) DO UPDATE SET wrong_count = wrong_count + 1, last_wrong_at = excluded.last_wrong_at',
                (user_id, vocab_id, english, uzbek, category, now),
            )
    except Exception:
        pass

async def clear_mistake(db, user_id: int, vocab_id: int):
    async with db_transaction() as tx:
        await tx.execute('DELETE FROM mistakes WHERE user_id = ? AND vocab_id = ?', (user_id, vocab_id))

async def get_mistakes(db, user_id: int) -> list:
    cursor = await db.execute('SELECT * FROM mistakes WHERE user_id = ? ORDER BY wrong_count DESC, last_wrong_at DESC', (user_id,))
    return await cursor.fetchall()

async def mistake_count(db, user_id: int) -> int:
    cursor = await db.execute('SELECT COUNT(*) as c FROM mistakes WHERE user_id = ?', (user_id,))
    row = await cursor.fetchone()
    return row['c'] if row else 0


def _load_vocab_json_fallback() -> list:
    import json as _json
    from bot.database import set_json_fallback

    json_path = VOCABULARY_PATH or str(ROOT / 'data/vocabulary.json')
    if not os.path.exists(json_path):
        return []
    with open(json_path, 'r', encoding='utf-8') as f:
        raw = _json.load(f)
    set_json_fallback({'source': 'json_fallback', 'data': raw, 'count': len(raw)})
    logger = __import__('logging').getLogger(__name__)
    logger.warning('vocab_loaded_via_json_fallback count=%s', len(raw))
    return [dict(item) for item in raw]
