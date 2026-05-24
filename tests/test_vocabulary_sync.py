import json

import aiosqlite
import pytest

from bot.utils import db_helpers


@pytest.mark.asyncio
async def test_load_vocabulary_updates_existing_primary_words(tmp_path, monkeypatch):
    vocab_path = tmp_path / "vocabulary.json"
    vocab_path.write_text(
        json.dumps([
            {
                "english": "positive",
                "uzbek": "musbat",
                "category": "Number Types",
                "source": "User SAT Core",
                "difficulty": "easy",
            }
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(db_helpers, "VOCABULARY_PATH", str(vocab_path))

    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute(
        "CREATE TABLE vocabulary ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, english TEXT, uzbek TEXT, "
        "category TEXT, source TEXT, difficulty TEXT)"
    )
    await db.execute(
        "INSERT INTO vocabulary (english, uzbek, category, source, difficulty) VALUES (?,?,?,?,?)",
        ("positive", "old", "General", "Old", "hard"),
    )
    await db.commit()

    rows = await db_helpers.load_vocabulary(db)

    assert len(rows) == 1
    assert rows[0]["uzbek"] == "musbat"
    assert rows[0]["category"] == "Number Types"
    assert rows[0]["source"] == "User SAT Core"
    assert rows[0]["difficulty"] == "easy"
    await db.close()
