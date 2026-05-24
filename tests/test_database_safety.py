import pytest

from bot.database import _column_exists, db_transaction


class DummyDb:
    async def execute(self, _sql):
        raise AssertionError("unsafe SQL should be rejected before execution")


@pytest.mark.asyncio
async def test_column_exists_rejects_unknown_table():
    with pytest.raises(ValueError):
        await _column_exists(DummyDb(), "users; DROP TABLE users", "id")


@pytest.mark.asyncio
async def test_db_transaction_rejects_unknown_mode():
    with pytest.raises(ValueError):
        async with db_transaction("IMMEDIATE; DROP TABLE users"):
            pass
