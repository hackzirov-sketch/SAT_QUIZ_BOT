from __future__ import annotations

import re
from typing import Any

from satmath.config import CHOICES


class MistakeAnalyzer:
    def __init__(self, questions: list[dict]):
        self.questions = questions

    def analyze_all(self) -> dict[str, Any]:
        mc = [q for q in self.questions if q['question_type'] == 'multiple_choice']
        grid = [q for q in self.questions if q['question_type'] == 'grid_in']

        return {
            'total_analyzed': len(self.questions),
            'pattern_breakdown': self._pattern_breakdown(),
            'high_value_questions': self._high_value_questions(),
            'topic_weakness_map': self._topic_weakness_map(mc),
            'recommendations': self._recommendations(),
        }

    def _pattern_breakdown(self) -> dict[str, int]:
        patterns = {
            'careless_error_traps': 0,
            'multi_step_requires_planning': 0,
            'concept_boundary': 0,
            'time_pressure_shortcuts': 0,
            'desmos_opportunity': 0,
        }
        for q in self.questions:
            text = q.get('question_text', '') + ' '.join(q.get('choices', {}).values())
            t = q.get('trap_level', 'low')
            if t == 'high':
                patterns['careless_error_traps'] += 1
            if q.get('difficulty') == 'hard':
                patterns['multi_step_requires_planning'] += 1
            if q.get('desmos_recommended'):
                patterns['desmos_opportunity'] += 1
            if t == 'medium':
                patterns['concept_boundary'] += 1

        patterns['time_pressure_shortcuts'] = sum(
            1 for q in self.questions
            if q.get('difficulty') == 'medium' and q.get('estimated_time_seconds', 60) > 90
        )
        return patterns

    def _high_value_questions(self) -> list[dict]:
        scored = []
        for q in self.questions:
            score = 0
            if q.get('difficulty') == 'hard':
                score += 3
            if q.get('trap_level') == 'high':
                score += 2
            if q.get('desmos_recommended'):
                score += 1
            if q.get('question_type') == 'grid_in':
                score += 1
            if score >= 3:
                scored.append({'id': q['id'], 'value_score': score, 'topic': q.get('topic', '')})
        return sorted(scored, key=lambda x: -x['value_score'])[:30]

    def _topic_weakness_map(self, mc_questions: list[dict]) -> dict[str, dict[str, Any]]:
        topics: dict[str, dict] = {}
        for q in mc_questions:
            topic = q.get('topic', 'Unknown')
            if topic not in topics:
                topics[topic] = {'total': 0, 'hard': 0, 'traps': 0, 'desmos': 0}
            topics[topic]['total'] += 1
            if q.get('difficulty') == 'hard':
                topics[topic]['hard'] += 1
            if q.get('trap_level') == 'high':
                topics[topic]['traps'] += 1
            if q.get('desmos_recommended'):
                topics[topic]['desmos'] += 1
        return dict(sorted(topics.items(), key=lambda x: (-x[1]['hard'], -x[1]['traps'])))

    def _recommendations(self) -> list[str]:
        return [
            'Hard va trap savollarga ustuvorlik bering (yuqori value_score).',
            'Desmos yechimlari bor savollarni Desmos bilan ishlashga o\'rgating.',
            'Grid-in savollar (student-produced response) ko\'proq amaliyot talab qiladi.',
            'Ko\'p qadamli savollarni bosqichma-bosqich yechishni o\'rgating.',
            'Vaqt bosimi ostida noto\'g\'ri variantlarni chiqarib tashlash strategiyasini qo\'llang.',
        ]

    def mistake_report(self, user_answers: dict[str, str]) -> dict[str, Any]:
        wrong = []
        for q in self.questions:
            qid = q['id']
            if qid in user_answers and user_answers[qid] != q.get('correct_answer', ''):
                wrong.append({
                    'id': qid,
                    'topic': q.get('topic', ''),
                    'difficulty': q.get('difficulty', ''),
                    'user_answer': user_answers[qid],
                    'correct_answer': q['correct_answer'],
                    'trap_level': q.get('trap_level', 'low'),
                    'explanation_uz': q.get('manual_solution_uz', '')[:200],
                    'shortcut_uz': q.get('shortcut_uz', ''),
                })

        topic_errors: dict[str, int] = {}
        for w in wrong:
            t = w['topic']
            topic_errors[t] = topic_errors.get(t, 0) + 1

        return {
            'total_wrong': len(wrong),
            'accuracy': round((len(self.questions) - len(wrong)) / len(self.questions) * 100, 1) if self.questions else 0,
            'topic_errors': dict(sorted(topic_errors.items(), key=lambda x: -x[1])),
            'wrong_questions': wrong,
            'recommendations': self._personalized_recs(topic_errors),
        }

    def _personalized_recs(self, topic_errors: dict[str, int]) -> list[str]:
        recs = []
        if topic_errors:
            worst = max(topic_errors, key=topic_errors.get)
            recs.append(f'Eng ko\'p xato qilgan mavzu: {worst} ({topic_errors[worst]} ta). Shu mavzuga ko\'proq e\'tibor bering.')
        if sum(1 for w in self._high_value_questions() if any(topic_errors.get(q.get('topic', ''), 0) > 0 for q in self._high_value_questions())):
            recs.append('High-value savollarda xato qilgansiz — ularni qayta ishlash tavsiya etiladi.')
        recs.append('Har bir xatoni tahlil qiling: nega bu javobni tanladingiz? Qanday qilib to\'g\'ri topish mumkin edi?')
        return recs
