from __future__ import annotations

import random
from typing import Any

from satmath.config import SATMathConfig, SAT_TOPIC_ALIASES


class TopicPracticeGenerator:
    def __init__(self, questions: list[dict]):
        self.questions = questions

    def generate_practice_set(self, topic: str, count: int = 10,
                               seed: int | None = None) -> dict[str, Any]:
        rng = random.Random(seed)
        topic_key = SAT_TOPIC_ALIASES.get(topic, topic)
        pool = [q for q in self.questions if q.get('topic', '') == topic_key]
        if not pool:
            pool = [q for q in self.questions
                    if SAT_TOPIC_ALIASES.get(q.get('topic', ''), '') == topic_key]

        if not pool:
            return {'error': f'Topic "{topic}" not found in question bank', 'questions': []}

        count = min(count, len(pool))
        selected = rng.sample(pool, count)
        rng.shuffle(selected)

        mc = [q for q in selected if q['question_type'] == 'multiple_choice']
        grid = [q for q in selected if q['question_type'] == 'grid_in']

        return {
            'type': 'topic_practice',
            'topic': topic_key,
            'label': f'{topic_key} — Amaliyot ({count} ta)',
            'total_questions': count,
            'multiple_choice': len(mc),
            'grid_in': len(grid),
            'estimated_time_minutes': max(5, count * 2),
            'questions': [{
                'order': i + 1,
                'id': q['id'],
                'question_type': q['question_type'],
                'difficulty': q.get('difficulty', 'easy'),
                'question_text': q.get('question_text', ''),
                'choices': q.get('choices', {}),
                'correct_answer': q['correct_answer'],
                'explanation_uz': q.get('manual_solution_uz', ''),
                'desmos_solution_uz': q.get('desmos_solution_uz', ''),
                'shortcut_uz': q.get('shortcut_uz', ''),
                'image_required': q.get('image_required', False),
                'page': q.get('page'),
            } for i, q in enumerate(selected)],
            'scoring': {
                'scale': 'percentage',
                'max_score': count,
            },
        }

    def list_topics_with_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for q in self.questions:
            t = q.get('topic', 'Unknown')
            counts[t] = counts.get(t, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def generate_weakness_workout(self, wrong_topics: dict[str, int],
                                   total: int = 15) -> dict[str, Any]:
        prioritized = sorted(wrong_topics.items(), key=lambda x: -x[1])
        selected = []
        remaining = total

        for topic, _ in prioritized:
            if remaining <= 0:
                break
            topic_key = SAT_TOPIC_ALIASES.get(topic, topic)
            pool = [q for q in self.questions if q.get('topic', '') == topic_key]
            if not pool:
                pool = [q for q in self.questions
                        if SAT_TOPIC_ALIASES.get(q.get('topic', ''), '') == topic_key]
            n = min(max(3, remaining // max(len(prioritized), 1)), len(pool))
            rng = random.Random()
            chosen = rng.sample(pool, n)
            selected.extend(chosen)
            remaining -= n

        if remaining > 0:
            filler = [q for q in self.questions if q not in selected]
            rng = random.Random()
            rng.shuffle(filler)
            selected.extend(filler[:remaining])

        return self.generate_practice_set(
            topic='custom_weakness',
            count=len(selected),
            seed=42,
        )
