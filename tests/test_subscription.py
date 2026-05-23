import pytest
import pytest_asyncio
import aiosqlite
from datetime import datetime, timezone
from aiogram.types import Chat, Message, User
from bot.database import _column_exists, _migrate_schema

OLD_USERS_DDL = '''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER NOT NULL UNIQUE,
        username TEXT,
        first_name TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
'''


@pytest_asyncio.fixture
async def old_db():
    db = await aiosqlite.connect(':memory:')
    db.row_factory = aiosqlite.Row
    await db.executescript(OLD_USERS_DDL)
    await db.execute(
        "INSERT INTO users (telegram_id, username, first_name, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (12345, 'existing_user', 'Existing', '2024-01-01T00:00:00', '2024-01-01T00:00:00'),
    )
    await db.commit()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_column_added_by_migration(old_db):
    assert not await _column_exists(old_db, 'users', 'subscription_required')
    await _migrate_schema(old_db)
    assert await _column_exists(old_db, 'users', 'subscription_required')


@pytest.mark.asyncio
async def test_existing_user_gets_subscription_required_0(old_db):
    await _migrate_schema(old_db)
    row = await (await old_db.execute(
        'SELECT subscription_required FROM users WHERE telegram_id = ?', (12345,)
    )).fetchone()
    assert row['subscription_required'] == 0


@pytest.mark.asyncio
async def test_new_user_gets_subscription_required_1(old_db):
    await _migrate_schema(old_db)
    await old_db.execute(
        "INSERT INTO users (telegram_id, username, first_name, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (99999, 'new_user', 'New', '2025-01-01T00:00:00', '2025-01-01T00:00:00'),
    )
    await old_db.commit()
    row = await (await old_db.execute(
        'SELECT subscription_required FROM users WHERE telegram_id = ?', (99999,)
    )).fetchone()
    assert row['subscription_required'] == 1


@pytest.mark.asyncio
async def test_migration_idempotent(old_db):
    await _migrate_schema(old_db)
    await _migrate_schema(old_db)
    row = await (await old_db.execute(
        'SELECT subscription_required FROM users WHERE telegram_id = ?', (12345,)
    )).fetchone()
    assert row['subscription_required'] == 0


@pytest.mark.asyncio
async def test_mark_subscription_ok(old_db):
    await _migrate_schema(old_db)
    await old_db.execute('UPDATE users SET subscription_required = 1 WHERE telegram_id = ?', (12345,))
    await old_db.commit()
    row = await (await old_db.execute(
        'SELECT subscription_required FROM users WHERE telegram_id = ?', (12345,)
    )).fetchone()
    assert row['subscription_required'] == 1
    await old_db.execute('UPDATE users SET subscription_required = 0 WHERE telegram_id = ?', (12345,))
    await old_db.commit()
    row = await (await old_db.execute(
        'SELECT subscription_required FROM users WHERE telegram_id = ?', (12345,)
    )).fetchone()
    assert row['subscription_required'] == 0


@pytest.mark.asyncio
async def test_start_command_requires_subscription_for_non_admin(monkeypatch):
    from bot import subscription

    called = False
    answers = []

    async def handler(_event, _data):
        nonlocal called
        called = True

    async def fake_missing_subscriptions(_bot, _user_id, *, force_refresh=False):
        return [{'chat_id': '@mathacademy01', 'title': 'Kanalimiz', 'link': 'https://t.me/mathacademy01'}]

    async def fake_answer(_self, text, **_kwargs):
        answers.append(text)

    monkeypatch.setattr(subscription, 'missing_subscriptions', fake_missing_subscriptions)
    monkeypatch.setattr(Message, 'answer', fake_answer)

    message = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(id=123456789, type='private'),
        from_user=User(id=123456789, is_bot=False, first_name='Test'),
        text='/start',
    )

    await subscription.SubscriptionMiddleware()(handler, message, {'bot': object()})

    assert called is False
    assert answers
    assert 'Botdan foydalanish' in answers[0]
