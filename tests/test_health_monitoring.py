import pytest

from bot.runtime_state import runtime_state
from bot.services.health_service import health_snapshot


@pytest.mark.asyncio
async def test_health_snapshot_contains_operational_fields():
    runtime_state.vocabulary_count = 1
    snapshot = await health_snapshot()
    assert "flask_alive" in snapshot
    assert "polling_alive" in snapshot
    assert "db_alive" in snapshot
    assert "wal_size" in snapshot
    assert "uptime_seconds" in snapshot


def test_teacher_health_returns_json():
    from teacher_site.app import app

    client = app.test_client()
    response = client.get("/health")
    assert response.is_json
    assert "flask_alive" in response.get_json()
