import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import aiosqlite
import os
from typing import Optional

from bot.config import DB_BUSY_TIMEOUT_MS

DB_PATH: str = ''
_db_conn: Optional[aiosqlite.Connection] = None
_db_lock: Optional[asyncio.Lock] = None


async def _connect(db_path: str) -> aiosqlite.Connection:
    db = await aiosqlite.connect(db_path, timeout=max(DB_BUSY_TIMEOUT_MS / 1000, 1))
    db.row_factory = aiosqlite.Row
    await db.execute('PRAGMA foreign_keys=ON')
    await db.execute(f'PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS}')
    await db.execute('PRAGMA journal_mode=WAL')
    await db.execute('PRAGMA synchronous=NORMAL')
    await db.execute('PRAGMA cache_size=-8000')
    return db

async def init_db(db_path: str):
    global DB_PATH, _db_conn, _db_lock
    DB_PATH = db_path
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = await _connect(db_path)
    await db.executescript('''
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        PRAGMA cache_size=-8000;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL UNIQUE,
            username TEXT,
            first_name TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            preferred_mode TEXT NOT NULL DEFAULT 'eng_uzb',
            preferred_difficulty TEXT NOT NULL DEFAULT 'easy',
            question_count INTEGER NOT NULL DEFAULT 50,
            sound_enabled INTEGER NOT NULL DEFAULT 1,
            timer_visible INTEGER NOT NULL DEFAULT 1,
            minimal_mode INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            mode TEXT NOT NULL,
            difficulty TEXT NOT NULL DEFAULT 'easy',
            category TEXT NOT NULL DEFAULT '',
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
            wrong_count INTEGER NOT NULL DEFAULT 0,
            quiz_mode TEXT NOT NULL DEFAULT 'standard',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            question_index INTEGER NOT NULL,
            selected_answer TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            answered_at TEXT NOT NULL,
            FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
            UNIQUE (attempt_id, question_index)
        );
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            score INTEGER NOT NULL,
            completion_seconds INTEGER NOT NULL,
            mode TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
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
            xp INTEGER NOT NULL DEFAULT 0,
            level INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS active_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            last_message_id INTEGER,
            expires_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            english TEXT NOT NULL,
            uzbek TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            source TEXT NOT NULL DEFAULT 'Admin',
            difficulty TEXT
        );
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            achievement_key TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            unlocked_at TEXT NOT NULL,
            attempt_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE SET NULL,
            UNIQUE (user_id, achievement_key)
        );
        CREATE TABLE IF NOT EXISTS question_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            attempt_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            mode TEXT NOT NULL,
            answered_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (attempt_id) REFERENCES attempts(id) ON DELETE CASCADE,
            UNIQUE (attempt_id, position)
        );
        CREATE TABLE IF NOT EXISTS user_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (user_id, key)
        );
        CREATE TABLE IF NOT EXISTS mistakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vocab_id INTEGER NOT NULL,
            english TEXT NOT NULL,
            uzbek TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT '',
            wrong_count INTEGER NOT NULL DEFAULT 1,
            last_wrong_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (user_id, vocab_id)
        );
        CREATE TABLE IF NOT EXISTS daily_challenge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            questions_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS daily_leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            challenge_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            score INTEGER NOT NULL DEFAULT 0,
            total_questions INTEGER NOT NULL DEFAULT 10,
            completion_seconds INTEGER NOT NULL DEFAULT 0,
            finished_at TEXT NOT NULL,
            FOREIGN KEY (challenge_id) REFERENCES daily_challenge(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (challenge_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS duel_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            mode TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            chat_id INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS duel_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            player1_id INTEGER NOT NULL,
            player2_id INTEGER,
            player1_score INTEGER NOT NULL DEFAULT 0,
            player2_score INTEGER NOT NULL DEFAULT 0,
            player1_time INTEGER NOT NULL DEFAULT 0,
            player2_time INTEGER NOT NULL DEFAULT 0,
            questions_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            winner_id INTEGER,
            created_at TEXT NOT NULL,
            finished_at TEXT,
            group_id INTEGER,
            channel_id INTEGER,
            FOREIGN KEY (player1_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (player2_id) REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS channel_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL UNIQUE,
            chat_type TEXT NOT NULL,
            chat_title TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            weekly_report INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_vocabulary_english ON vocabulary(english);
        CREATE INDEX IF NOT EXISTS idx_vocabulary_category ON vocabulary(category);
        CREATE INDEX IF NOT EXISTS idx_attempts_user_status ON attempts(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_attempts_user_finished ON attempts(user_id, finished_at);
        CREATE INDEX IF NOT EXISTS idx_leaderboard_rank ON leaderboard(score DESC, completion_seconds ASC, finished_at ASC);
        CREATE INDEX IF NOT EXISTS idx_answers_attempt ON answers(attempt_id);
        CREATE INDEX IF NOT EXISTS idx_active_sessions_status ON active_sessions(status);
        CREATE INDEX IF NOT EXISTS idx_active_sessions_attempt_status ON active_sessions(attempt_id, status);
        CREATE INDEX IF NOT EXISTS idx_active_sessions_user_status ON active_sessions(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_active_sessions_expires ON active_sessions(expires_at, status);
    ''')
    try:
        await db.execute('ALTER TABLE duel_queue ADD COLUMN chat_id INTEGER NOT NULL DEFAULT 0')
    except aiosqlite.OperationalError:
        pass
    await db.commit()
    _db_conn = db
    _db_lock = asyncio.Lock()
    return db

async def get_db() -> aiosqlite.Connection:
    global _db_conn, _db_lock
    if _db_conn is None:
        if not DB_PATH:
            raise RuntimeError('Database is not initialized')
        _db_conn = await _connect(DB_PATH)
    if _db_lock is None:
        _db_lock = asyncio.Lock()
    return _db_conn

def get_db_sync() -> aiosqlite.Connection:
    global _db_conn
    return _db_conn

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def db_transaction(mode: str = 'IMMEDIATE'):
    """Serialize writes on the shared SQLite connection and rollback on errors."""
    global _db_lock
    db = await get_db()
    if _db_lock is None:
        _db_lock = asyncio.Lock()
    async with _db_lock:
        await db.execute(f'BEGIN {mode}')
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
        else:
            await db.commit()
