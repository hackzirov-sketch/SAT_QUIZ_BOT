from __future__ import annotations

import math
from typing import Any


class ScoringEngine:
    def __init__(self):
        self.scale_easy = self._build_scale(0.6, 200, 800)
        self.scale_hard = self._build_scale(0.45, 200, 800)

    def score_test(self, answers: dict[str, str], test: dict[str, Any]) -> dict[str, Any]:
        modules = test.get('modules', [])
        correct_by_module = {1: 0, 2: 0}
        total_by_module = {1: 0, 2: 0}
        details_by_module = {1: [], 2: []}

        for module in modules:
            mnum = module.get('module_number', 1)
            for q in module.get('questions', []):
                qid = q.get('id', '')
                total_by_module[mnum] += 1
                user_ans = answers.get(qid, '')
                correct_ans = q.get('correct_answer', '')
                is_correct = user_ans == correct_ans
                if is_correct:
                    correct_by_module[mnum] += 1
                details_by_module[mnum].append({
                    'id': qid,
                    'user_answer': user_ans,
                    'correct_answer': correct_ans,
                    'is_correct': is_correct,
                    'difficulty': q.get('difficulty', 'easy'),
                })

        m1_raw = correct_by_module[1]
        m1_total = total_by_module[1]
        m2_raw = correct_by_module[2]
        m2_total = total_by_module[2] or m1_total

        m1_pct = m1_raw / m1_total if m1_total else 0
        m2_pct = m2_raw / m2_total if m2_total else 0

        if m1_pct >= 0.7:
            scale = self.scale_hard
            adaptive = 'harder_module_2'
        else:
            scale = self.scale_easy
            adaptive = 'easier_module_2'

        total_raw = correct_by_module[1] + correct_by_module[2]
        total_max = total_by_module[1] + total_by_module[2]
        total_pct = total_raw / total_max if total_max else 0

        scaled = self._raw_to_scaled(scale, total_pct)
        m1_scaled = self._raw_to_scaled(self.scale_easy, m1_pct)
        m2_scaled = self._raw_to_scaled(scale, m2_pct)

        return {
            'total_score': scaled,
            'module_1': {
                'raw': m1_raw,
                'total': m1_total,
                'percentage': round(m1_pct * 100, 1),
                'scaled_approx': m1_scaled,
            },
            'module_2': {
                'raw': m2_raw,
                'total': m2_total,
                'percentage': round(m2_pct * 100, 1),
                'scaled_approx': m2_scaled,
                'adaptive_level': adaptive,
            },
            'total_raw': total_raw,
            'total_max': total_max,
            'overall_percentage': round(total_pct * 100, 1),
            'details_by_module': details_by_module,
            'adaptive_level': adaptive,
        }

    def estimate_section_score(self, correct: int, total: int,
                                section: str = 'module_1') -> int:
        pct = correct / total if total else 0
        scale = self.scale_easy
        if section == 'module_2' and pct >= 0.7:
            scale = self.scale_hard
        return self._raw_to_scaled(scale, pct)

    def _build_scale(self, midpoint_pct: float, min_score: int, max_score: int) -> list[dict]:
        points = []
        for pct_int in range(0, 101):
            pct = pct_int / 100.0
            diff = pct - midpoint_pct
            scaled = int(round(max_score / (1 + math.exp(-6 * diff))))
            scaled = max(min_score, min(max_score, scaled))
            points.append({'percentage': pct_int, 'scaled': scaled})
        return points

    def _raw_to_scaled(self, scale: list[dict], pct: float) -> int:
        pct_int = min(100, max(0, round(pct * 100)))
        entry = scale[pct_int]
        return entry['scaled']

    def score_breakdown(self, results: dict[str, Any]) -> str:
        lines = [
            f"<b>SAT Math — Natijalar</b>\n",
            f"Module 1: {results['module_1']['raw']}/{results['module_1']['total']} ({results['module_1']['percentage']}%)",
            f"Module 2: {results['module_2']['raw']}/{results['module_2']['total']} ({results['module_2']['percentage']}%)",
            f"Jami: {results['total_raw']}/{results['total_max']} ({results['overall_percentage']}%)",
            f"",
            f"<b>Umumiy ball: {results['total_score']}/800</b>",
            f"",
            f"Adaptiv rejim: {'Harder Module 2' if 'harder' in results.get('adaptive_level', '') else 'Easier Module 2'}",
        ]
        return '\n'.join(lines)
