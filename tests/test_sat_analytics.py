import pytest

from bot.database import init_db
from bot.services.sat_analytics_service import learning_profile, record_sat_answer


@pytest.mark.asyncio
async def test_sat_analytics_weak_topic_detection(tmp_path):
    db = await init_db(str(tmp_path / "analytics.db"))
    await db.execute(
        "INSERT INTO users (id, telegram_id, created_at, updated_at) VALUES (1, 1, 'n', 'n')"
    )
    question = {"id": "q1", "topic": "Quadratics", "difficulty": "hard"}
    await record_sat_answer(
        db,
        user_id=1,
        attempt_id=None,
        question=question,
        user_answer="A",
        correct_answer="B",
        is_correct=False,
    )
    await record_sat_answer(
        db,
        user_id=1,
        attempt_id=None,
        question=question,
        user_answer="C",
        correct_answer="B",
        is_correct=False,
    )
    await db.commit()
    profile = await learning_profile(db, 1)
    assert "Quadratics" in profile["weak_topics"]
    assert 200 <= profile["estimated_sat_math_score"] <= 800
    await db.close()
