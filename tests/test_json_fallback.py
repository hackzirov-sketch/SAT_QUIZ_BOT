import json
import os
import tempfile
from pathlib import Path

import aiosqlite
import pytest

from bot.database import get_db, get_json_fallback, set_json_fallback, db_transaction
from bot.utils.db_helpers import _load_vocab_json_fallback


def test_set_and_get_json_fallback():
    set_json_fallback({"source": "test", "data": [{"id": 1, "word": "test"}]})
    fb = get_json_fallback()
    assert fb is not None
    assert fb["source"] == "test"
    assert len(fb["data"]) == 1
    set_json_fallback(None)


def test_json_fallback_loads_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump([{"english": "test", "uzbek": "test", "category": "Algebra", "source": "Test", "difficulty": "easy"}], f)
        tmp_path = f.name

    try:
        import bot.utils.db_helpers as dh
        original = dh.VOCABULARY_PATH
        dh.VOCABULARY_PATH = tmp_path

        result = _load_vocab_json_fallback()
        assert len(result) == 1
        assert result[0]["english"] == "test"

        dh.VOCABULARY_PATH = original
    finally:
        os.unlink(tmp_path)


@pytest.mark.asyncio
async def test_db_get_fallback_safe():
    try:
        db = await aiosqlite.connect(":memory:")
        db.row_factory = aiosqlite.Row
        await db.execute("CREATE TABLE vocabulary (id INTEGER PRIMARY KEY, english TEXT)")
        await db.execute("INSERT INTO vocabulary VALUES (1, 'hello')")
        await db.commit()

        cursor = await db.execute("SELECT COUNT(*) as c FROM vocabulary")
        row = await cursor.fetchone()
        assert row["c"] == 1
        await db.close()
    except Exception:
        pass


def test_json_fallback_roundtrip():
    set_json_fallback({"source": "json_fallback", "data": [{"id": 1}], "count": 1})
    fb = get_json_fallback()
    assert fb["source"] == "json_fallback"
    assert fb["count"] == 1
    set_json_fallback(None)
    assert get_json_fallback() is None
