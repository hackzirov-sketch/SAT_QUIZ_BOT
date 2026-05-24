import pytest

from bot.database import (
    backup_sqlite,
    integrity_check,
    is_db_healthy,
    set_json_fallback,
    get_json_fallback,
    sqlite_file_stats,
    wal_checkpoint,
)


@pytest.mark.asyncio
async def test_db_health_check_returns_bool():
    healthy = await is_db_healthy()
    assert isinstance(healthy, bool)


@pytest.mark.asyncio
async def test_db_health_check_returns_false_when_not_initialized():
    from bot import database as db_mod

    old_path = db_mod.DB_PATH
    old_conn = db_mod._db_conn
    old_lock = db_mod._db_lock

    db_mod.DB_PATH = ""
    db_mod._db_conn = None
    db_mod._db_lock = None

    healthy = await is_db_healthy()
    assert not healthy

    db_mod.DB_PATH = old_path
    db_mod._db_conn = old_conn
    db_mod._db_lock = old_lock


def test_json_fallback_set_and_get():
    set_json_fallback({"source": "test", "data": [1, 2, 3]})
    fb = get_json_fallback()
    assert fb is not None
    assert fb["source"] == "test"
    assert fb["data"] == [1, 2, 3]


def test_json_fallback_clear():
    set_json_fallback(None)
    assert get_json_fallback() is None


@pytest.mark.asyncio
async def test_get_db_connection_stable(tmp_path):
    from bot import database as db_mod

    db_path = str(tmp_path / "test.db")
    old_path = db_mod.DB_PATH
    old_conn = db_mod._db_conn
    old_lock = db_mod._db_lock

    db_mod.DB_PATH = db_path
    db_mod._db_conn = None
    db_mod._db_lock = None

    db = await db_mod.init_db(db_path)
    cursor = await db.execute("SELECT 1 AS val")
    row = await cursor.fetchone()
    assert row["val"] == 1
    assert await integrity_check()
    assert wal_checkpoint is not None
    stats = sqlite_file_stats(db_path)
    assert stats["exists"]
    backup_path = str(tmp_path / "backup" / "test.db")
    assert await backup_sqlite(backup_path) == backup_path
    assert stats["db_size"] >= 0

    await db.close()
    db_mod.DB_PATH = old_path
    db_mod._db_conn = old_conn
    db_mod._db_lock = old_lock
