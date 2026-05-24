from __future__ import annotations

from collections import defaultdict
from typing import Any

from satmath.config import SAT_TOPIC_ALIASES, CHOICES


class AnswerMatcher:
    def __init__(self, questions: list[dict], answer_sections: list[dict]):
        self.questions = questions
        self.answer_sections = answer_sections
        self.report: dict[str, Any] = {}

    def validate_all(self) -> dict[str, Any]:
        mc_questions = [q for q in self.questions if q['question_type'] == 'multiple_choice']
        grid_questions = [q for q in self.questions if q['question_type'] == 'grid_in']
        all_questions = mc_questions + grid_questions

        matched = 0
        missing = []
        duplicates = self._find_duplicate_ids()
        mismatches = []

        for q in all_questions:
            correct = q.get('correct_answer', '')
            qtype = q.get('question_type', 'multiple_choice')

            if qtype == 'multiple_choice':
                if correct not in CHOICES:
                    mismatches.append({
                        'id': q['id'],
                        'issue': f'correct_answer {correct} not in A/B/C/D',
                    })
                    continue
                if correct not in q.get('choices', {}):
                    mismatches.append({
                        'id': q['id'],
                        'issue': f'correct_answer {correct} not found in choices keys',
                    })
                    continue
                if q['choices'].get(correct) != q['choices'].get(correct):
                    pass
                matched += 1
            elif qtype == 'grid_in':
                if not correct:
                    mismatches.append({
                        'id': q['id'],
                        'issue': 'grid_in question has empty correct_answer',
                    })
                    continue
                matched += 1

            answer_key_val = self._lookup_answer_key(q)
            if answer_key_val and answer_key_val != correct:
                mismatches.append({
                    'id': q['id'],
                    'issue': f'bank answer "{correct}" differs from answer key "{answer_key_val}"',
                })

        for section in self.answer_sections:
            for num, ans in section['answers'].items():
                found = any(
                    q['question_number_original'] == num and
                    SAT_TOPIC_ALIASES.get(q['topic'], q['topic']) == section['topic']
                    for q in all_questions
                )
                if not found:
                    missing.append({
                        'topic': section['topic'],
                        'number': num,
                        'answer': ans,
                    })

        self.report = {
            'total_questions': len(all_questions),
            'multiple_choice': len(mc_questions),
            'grid_in': len(grid_questions),
            'matched_answers': matched,
            'missing_answers': missing[:20],
            'total_missing': len(missing),
            'duplicate_ids': duplicates,
            'suspicious_matches': mismatches,
            'all_ok': len(mismatches) == 0 and len(duplicates) == 0,
        }
        return self.report

    def _find_duplicate_ids(self) -> list[str]:
        ids = [q['id'] for q in self.questions]
        seen = {}
        dups = []
        for i, qid in enumerate(ids):
            if qid in seen:
                dups.append(f'{qid} at indices {seen[qid]}, {i}')
            seen[qid] = i
        return dups

    def _lookup_answer_key(self, question: dict) -> str | None:
        topic = SAT_TOPIC_ALIASES.get(question.get('topic', ''), question.get('topic', ''))
        number = question.get('question_number_original')
        for section in self.answer_sections:
            if section['topic'] == topic:
                return section['answers'].get(number)
        return None
