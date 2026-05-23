import os
import aiosqlite
import pytest
import pytest_asyncio

from bot.database import _column_exists, _migrate_schema


OLD_ATTEMPTS_DDL = '''
    CREATE TABLE IF NOT EXISTS attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        mode TEXT NOT NULL,
        difficulty TEXT NOT NULL DEFAULT 'easy',
        score INTEGER NOT NULL DEFAULT 0,
        total_questions INTEGER NOT NULL,
        current_index INTEGER NOT NULL DEFAULT 0,
        question_order_json TEXT NOT NULL,
        order_hash TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        completion_seconds INTEGER,
        status TEXT NOT NULL DEFAULT 'active',
        correct_count INTEGER NOT NULL DEFAULT 0,
        wrong_count INTEGER NOT NULL DEFAULT 0
    );
'''

OLD_STATISTICS_DDL = '''
    CREATE TABLE IF NOT EXISTS statistics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        attempts_count INTEGER NOT NULL DEFAULT 0,
        total_score INTEGER NOT NULL DEFAULT 0,
        best_score INTEGER NOT NULL DEFAULT 0,
        best_time INTEGER,
        correct_answers INTEGER NOT NULL DEFAULT 0,
        wrong_answers INTEGER NOT NULL DEFAULT 0,
        current_win_streak INTEGER NOT NULL DEFAULT 0,
        best_win_streak INTEGER NOT NULL DEFAULT 0,
        daily_streak INTEGER NOT NULL DEFAULT 0,
        last_quiz_date TEXT,
        favorite_mode TEXT,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
'''


@pytest_asyncio.fixture
async def old_db():
    db = await aiosqlite.connect(':memory:')
    db.row_factory = aiosqlite.Row
    await db.executescript(OLD_ATTEMPTS_DDL)
    await db.executescript(OLD_STATISTICS_DDL)
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_missing_columns_detected(old_db):
    assert not await _column_exists(old_db, 'attempts', 'category')
    assert not await _column_exists(old_db, 'attempts', 'quiz_mode')
    assert not await _column_exists(old_db, 'statistics', 'xp')
    assert not await _column_exists(old_db, 'statistics', 'level')


@pytest.mark.asyncio
async def test_migration_adds_columns(old_db):
    await _migrate_schema(old_db)
    assert await _column_exists(old_db, 'attempts', 'category')
    assert await _column_exists(old_db, 'attempts', 'quiz_mode')
    assert await _column_exists(old_db, 'statistics', 'xp')
    assert await _column_exists(old_db, 'statistics', 'level')


@pytest.mark.asyncio
async def test_migration_idempotent(old_db):
    await _migrate_schema(old_db)
    await _migrate_schema(old_db)
    assert await _column_exists(old_db, 'attempts', 'category')
    assert await _column_exists(old_db, 'statistics', 'xp')


@pytest.mark.asyncio
async def test_insert_after_migration(old_db):
    await _migrate_schema(old_db)
    await old_db.execute('''
        INSERT INTO attempts (user_id, mode, difficulty, category, total_questions,
            question_order_json, order_hash, started_at, status, quiz_mode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (1, 'eng_uzb', 'easy', 'Algebra', 10, '[]', 'hash123', '2024-01-01', 'active', 'standard'))
    row = await (await old_db.execute('SELECT * FROM attempts WHERE id = 1')).fetchone()
    assert row['category'] == 'Algebra'
    assert row['quiz_mode'] == 'standard'
