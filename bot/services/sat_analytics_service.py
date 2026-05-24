from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from bot.database import now_iso


def _question_topic(question: dict[str, Any]) -> str:
    return str(question.get('topic') or question.get('category') or 'Unknown')


def _question_difficulty(question: dict[str, Any]) -> str:
    return str(question.get('difficulty') or 'mixed')


def _estimate_score(accuracy: float, hard_ratio: float, timing_penalty: float) -> int:
    raw = 200 + (accuracy * 520) + (hard_ratio * 80) - timing_penalty
    return max(200, min(800, int(round(raw / 10) * 10)))


async def record_sat_answer(
    db,
    *,
    user_id: int,
    attempt_id: int,
    question: dict[str, Any],
    user_answer: str,
    correct_answer: str,
    is_correct: bool,
    seconds_spent: int = 0,
) -> None:
    topic = _question_topic(question)
    subtopic = str(question.get('subtopic') or question.get('skill') or '')
    difficulty = _question_difficulty(question)
    now = now_iso()
    slow = 1 if seconds_spent >= int(question.get('estimated_time_seconds') or 90) else 0
    await db.execute(
        '''
        INSERT INTO sat_topic_stats
            (user_id, topic, subtopic, difficulty, attempts, correct, wrong, slow, total_seconds, updated_at)
        VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, topic, subtopic, difficulty) DO UPDATE SET
            attempts = attempts + 1,
            correct = correct + excluded.correct,
            wrong = wrong + excluded.wrong,
            slow = slow + excluded.slow,
            total_seconds = total_seconds + excluded.total_seconds,
            updated_at = excluded.updated_at
        ''',
        (user_id, topic, subtopic, difficulty, 1 if is_correct else 0, 0 if is_correct else 1, slow, max(seconds_spent, 0), now),
    )
    if not is_correct:
        reason = 'wrong_answer'
        await db.execute(
            '''
            INSERT INTO sat_mistake_notebook
                (user_id, attempt_id, question_id, user_answer, correct_answer, topic, subtopic, difficulty, mistake_reason, retry_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            ''',
            (
                user_id,
                attempt_id,
                str(question.get('id') or question.get('question_id') or ''),
                user_answer,
                correct_answer,
                topic,
                subtopic,
                difficulty,
                reason,
                now,
                now,
            ),
        )


async def learning_profile(db, user_id: int) -> dict[str, Any]:
    rows = await (await db.execute(
        'SELECT * FROM sat_topic_stats WHERE user_id = ? ORDER BY updated_at DESC',
        (user_id,),
    )).fetchall()
    by_topic: dict[str, dict[str, Any]] = defaultdict(lambda: {'attempts': 0, 'correct': 0, 'wrong': 0, 'slow': 0})
    hard_attempts = 0
    total_attempts = 0
    total_correct = 0
    for row in rows:
        topic = row['topic']
        by_topic[topic]['attempts'] += row['attempts']
        by_topic[topic]['correct'] += row['correct']
        by_topic[topic]['wrong'] += row['wrong']
        by_topic[topic]['slow'] += row['slow']
        total_attempts += row['attempts']
        total_correct += row['correct']
        if row['difficulty'] == 'hard':
            hard_attempts += row['attempts']

    weak_topics = []
    strong_topics = []
    recommended = []
    for topic, data in by_topic.items():
        attempts = max(data['attempts'], 1)
        accuracy = data['correct'] / attempts
        slow_rate = data['slow'] / attempts
        if attempts >= 2 and (accuracy < 0.65 or slow_rate > 0.35):
            weak_topics.append(topic)
            recommended.append(f"{topic} bo'yicha practice tavsiya qilinadi.")
        elif attempts >= 2 and accuracy >= 0.8:
            strong_topics.append(topic)

    accuracy = total_correct / total_attempts if total_attempts else 0.0
    hard_ratio = hard_attempts / total_attempts if total_attempts else 0.0
    timing_penalty = 30 if any(by_topic[t]['slow'] > 0 for t in by_topic) else 0
    score = _estimate_score(accuracy, hard_ratio, timing_penalty) if total_attempts else 200
    level = 'Boshlangich' if score < 450 else 'O\'rta' if score < 650 else 'Kuchli'
    return {
        'weak_topics': sorted(set(weak_topics)),
        'strong_topics': sorted(set(strong_topics)),
        'recommended_practice': recommended,
        'estimated_skill_level': level,
        'estimated_sat_math_score': score,
    }


def profile_to_json(profile: dict[str, Any]) -> str:
    return json.dumps(profile, ensure_ascii=False, separators=(',', ':'))
