from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

from satmath.config import SATMathConfig, DOMAIN_MAP, SAT_TOPIC_ALIASES


class MockGenerator:
    def __init__(self, questions: list[dict]):
        self.questions = questions
        self.history: list[str] = []
        self._load_history()

    def _load_history(self):
        if SATMathConfig.MOCK_HISTORY.exists():
            self.history = json.loads(SATMathConfig.MOCK_HISTORY.read_text(encoding='utf-8'))

    def _save_history(self):
        SATMathConfig.MOCK_HISTORY.parent.mkdir(parents=True, exist_ok=True)
        SATMathConfig.MOCK_HISTORY.write_text(
            json.dumps(self.history, ensure_ascii=False, indent=2), encoding='utf-8'
        )

    def generate_full_test(self, seed: int | None = None) -> dict[str, Any]:
        rng = random.Random(seed)
        topic_questions = self._group_by_topic()

        module_1 = self._select_questions(topic_questions, 22, rng)
        module_2 = self._select_questions(
            topic_questions, 22, rng,
            difficulty_distribution={'easy': 0.2, 'medium': 0.4, 'hard': 0.4},
        )

        test_id = self._test_id(module_1, module_2)
        test = {
            'test_id': test_id,
            'type': 'full_mock',
            'label': f'SAT Math Mock Test {len(self.history) + 1}',
            'modules': [self._make_module(module_1, 1, rng), self._make_module(module_2, 2, rng)],
            'scoring': {
                'module_1_type': 'full_range',
                'module_2_type': 'adaptive_harder',
                'question_types': {'multiple_choice': 40, 'grid_in': 4},
            },
            'metadata': {
                'generated_at': '',
                'seed': seed,
                'source': 'Mathbook 3.0',
                'version': SATMathConfig.VERSION,
            },
        }

        self.history.append(test_id)
        self._save_history()
        return test

    def generate_module_practice(self, module_num: int = 1, count: int = 22,
                                  seed: int | None = None) -> dict[str, Any]:
        rng = random.Random(seed)
        topic_questions = self._group_by_topic()
        selected = self._select_questions(topic_questions, count, rng)
        return {
            'test_id': f'module-{module_num}-{self._hash(str(seed or 0)[:8])}',
            'type': 'module_practice',
            'label': f'Module {module_num} Practice',
            'modules': [self._make_module(selected, module_num, rng)],
            'scoring': {},
            'metadata': {'generated_at': '', 'seed': seed},
        }

    def _group_by_topic(self) -> dict[str, list[dict]]:
        groups: dict[str, list] = {}
        for q in self.questions:
            t = q.get('topic', 'Unknown')
            groups.setdefault(t, []).append(q)
        return groups

    def _select_questions(self, topic_questions: dict, count: int,
                          rng: random.Random,
                          difficulty_distribution: dict[str, float] | None = None) -> list[dict]:
        if not difficulty_distribution:
            difficulty_distribution = {'easy': 0.4, 'medium': 0.4, 'hard': 0.2}

        total_needed = count
        selected = []
        topic_list = sorted(topic_questions.keys())

        target_each = total_needed // max(len(topic_list), 1)
        remainder = total_needed % max(len(topic_list), 1)

        for i, topic in enumerate(topic_list):
            pool = topic_questions[topic]
            n = target_each + (1 if i < remainder else 0)
            n = min(n, len(pool))
            chosen = rng.sample(pool, n) if n > 0 else []
            selected.extend(chosen)

        if len(selected) < total_needed:
            filler = [q for q in self.questions if q not in selected]
            rng.shuffle(filler)
            selected.extend(filler[:total_needed - len(selected)])

        if len(selected) > total_needed:
            rng.shuffle(selected)
            selected = selected[:total_needed]

        rng.shuffle(selected)

        mc_count = sum(1 for q in selected if q['question_type'] == 'multiple_choice')
        grid_count = sum(1 for q in selected if q['question_type'] == 'grid_in')
        if grid_count < 2:
            grid_pool = [q for q in self.questions if q['question_type'] == 'grid_in' and q not in selected]
            rng.shuffle(grid_pool)
            needed = min(2 - grid_count, len(grid_pool))
            if needed:
                for _ in range(needed):
                    g = grid_pool.pop()
                    if len(selected) > 0:
                        idx = rng.randint(0, len(selected) - 1)
                        selected[idx] = g
                    else:
                        selected.append(g)
                    grid_count += 1

        if len(selected) > 0:
            while selected[-1].get('question_type') == 'grid_in' and mc_count > (total_needed - 5):
                rng.shuffle(selected)

        return selected

    def _make_module(self, questions: list[dict], module_num: int,
                     rng: random.Random) -> dict[str, Any]:
        mc = [q for q in questions if q['question_type'] == 'multiple_choice']
        grid = [q for q in questions if q['question_type'] == 'grid_in']

        module_questions = []
        last_mc_index = 0
        last_grid_index = 0

        for i, q in enumerate(questions):
            order_num = i + 1
            is_grid = q['question_type'] == 'grid_in'
            base = {
                'order': order_num,
                'id': q['id'],
                'question_type': q['question_type'],
                'topic': q.get('topic', ''),
                'difficulty': q.get('difficulty', 'easy'),
                'sat_domain': q.get('sat_domain', ''),
                'question_text': q.get('question_text', ''),
                'choices': q.get('choices', {}),
                'correct_answer': q['correct_answer'],
                'image_required': q.get('image_required', False),
                'page': q.get('page'),
                'estimated_time_seconds': q.get('estimated_time_seconds', 60),
            }
            module_questions.append(base)

        return {
            'module_number': module_num,
            'total_questions': len(module_questions),
            'multiple_choice': len(mc),
            'grid_in': len(grid),
            'time_limit_minutes': 35,
            'questions': module_questions,
        }

    def _test_id(self, m1: list, m2: list) -> str:
        raw = str([q['id'] for q in m1]) + str([q['id'] for q in m2])
        return self._hash(raw)

    def _hash(self, s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()[:12]
