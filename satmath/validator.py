from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from satmath.config import CHOICES


class QuestionValidator:
    def __init__(self, questions: list[dict]):
        self.questions = questions

    def validate_all(self) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        stats = {
            'total': len(self.questions),
            'multiple_choice': 0,
            'grid_in': 0,
            'missing_fields': 0,
            'empty_questions': 0,
            'orphan_images': 0,
        }

        required = ['id', 'question_text', 'correct_answer', 'question_type', 'topic']

        for q in self.questions:
            qtype = q.get('question_type', '')
            stats[qtype] = stats.get(qtype, 0) + 1

            for field in required:
                if not q.get(field):
                    stats['missing_fields'] += 1
                    if len(errors) < 50:
                        errors.append(f"{q.get('id', '?')}: missing field '{field}'")

            text = q.get('question_text', '').strip()
            if len(text) < 10:
                stats['empty_questions'] += 1
                if len(warnings) < 50:
                    warnings.append(f"{q.get('id', '?')}: question_text too short ({len(text)} chars)")

            if qtype == 'multiple_choice':
                choices = q.get('choices', {})
                for c in CHOICES:
                    if c not in choices:
                        if len(errors) < 50:
                            errors.append(f"{q.get('id', '?')}: missing choice '{c}'")
                if q.get('correct_answer') not in CHOICES:
                    if len(errors) < 50:
                        errors.append(f"{q.get('id', '?')}: correct_answer '{q.get('correct_answer')}' not in A/B/C/D")

            if qtype == 'grid_in':
                correct = q.get('correct_answer', '')
                if correct in CHOICES:
                    if len(warnings) < 50:
                        warnings.append(f"{q.get('id', '?')}: grid_in has letter answer '{correct}'")

            if q.get('image_required') and not q.get('page'):
                stats['orphan_images'] += 1

        domains = [q.get('sat_domain', '') for q in self.questions if q.get('sat_domain')]
        if not domains:
            warnings.append('No questions have sat_domain classified')

        duplicates = self._find_duplicates()
        if duplicates:
            warnings.append(f'Found {len(duplicates)} duplicate question texts')

        return {
            'passed': len(errors) == 0,
            'stats': stats,
            'errors': errors[:20],
            'warnings': warnings[:20],
            'duplicate_texts': duplicates[:10],
            'summary': f"{'PASS' if len(errors) == 0 else 'FAIL'}: {stats['total']} questions, "
                       f"{len(errors)} errors, {len(warnings)} warnings",
        }

    def _find_duplicates(self) -> list[str]:
        seen = {}
        dups = []
        for q in self.questions:
            text = q.get('question_text', '')[:80]
            if text in seen:
                dups.append(f"'{text}...' by {seen[text]} and {q.get('id', '?')}")
            seen[text] = q.get('id', '?')
        return dups

    def validate_output_files(self, output_dir: Path) -> dict[str, Any]:
        expected = ['questions.json', 'mock_tests.json', 'manifest.json', 'answer_keys.json']
        result = {}
        for fname in expected:
            path = output_dir / fname
            exists = path.exists()
            size = path.stat().st_size if exists else 0
            result[fname] = {'exists': exists, 'size': size}
        return result
