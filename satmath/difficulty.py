from __future__ import annotations

import re
from typing import Any


class DifficultyLabeler:
    def __init__(self, questions: list[dict]):
        self.questions = questions

    def label_all(self) -> list[dict]:
        for q in self.questions:
            q['difficulty'] = self._estimate_difficulty(q)
            q['estimated_time_seconds'] = self._estimate_time(q)
            q['trap_level'] = self._detect_trap_level(q)
        return self.questions

    def _estimate_difficulty(self, q: dict) -> str:
        text = q.get('question_text', '').lower()
        choices = ' '.join(q.get('choices', {}).values()).lower()
        full = text + ' ' + choices

        hard_indicators = [
            r'\bsystem\b', r'\bquadratic\b', r'\bsimultaneous\b',
            r'\bexponential\b', r'\blogarithm\b', r'\btrigonometric\b',
            r'\bvolume\b', r'\bsurface area\b', r'\bcomposite\b',
            r'\bvertex\b', r'\bmaximum\b', r'\bminimum\b', r'\bdomain\b',
            r'\brange\b', r'\basymptote\b', r'\bscatterplot\b',
            r'\bmargin of error\b', r'\boutlier\b', r'\bprobability\b',
            r'\binference\b', r'\bcircle\b.*\bequation\b',
            r'\bcomplex\b', r'\bimaginary\b', r'\bradical\b',
            r'\brate\b.*\bchange\b', r'\btangent\b', r'\barc\b',
        ]
        medium_indicators = [
            r'\blinear\b', r'\bfunction\b', r'\bgraph\b',
            r'\bplot\b', r'\btable\b', r'\bequation\b',
            r'\bexpression\b', r'\bfactor\b', r'\bexpand\b',
            r'\binequality\b', r'\bslope\b', r'\bintercept\b',
            r'\bpercent\b', r'\bratio\b', r'\bproportion\b',
            r'\baverage\b', r'\bmean\b', r'\bmedian\b',
            r'\bangle\b', r'\btriangle\b', r'\bcircle\b',
            r'\baren\b', r'\bperimeter\b', r'\barea\b',
            r'\bvolume\b', r'\bunit\b', r'\bconvert\b',
        ]

        hard_score = sum(1 for p in hard_indicators if re.search(p, full))
        medium_score = sum(1 for p in medium_indicators if re.search(p, full))

        if hard_score >= 3 or (hard_score >= 2 and medium_score >= 3):
            return 'hard'
        elif hard_score >= 1 or medium_score >= 2:
            return 'medium'
        return 'easy'

    def _estimate_time(self, q: dict) -> int:
        text = q.get('question_text', '')
        word_count = len(text.split())
        difficulty = q.get('difficulty', 'easy')
        base = 45
        if difficulty == 'medium':
            base = 75
        elif difficulty == 'hard':
            base = 120
        if word_count > 50:
            base += 30
        if q.get('image_required'):
            base += 15
        return min(base, 180)

    def _detect_trap_level(self, q: dict) -> str:
        text = q.get('question_text', '') + ' ' + ' '.join(q.get('choices', {}).values())
        trap_keywords = [
            'not', 'except', 'least', 'greatest', 'always', 'never',
            'must be', 'could be', 'cannot be', 'in terms of',
            'percent increase', 'percent decrease', 'percent more',
            'percent less', 'ratio', 'proportion',
        ]
        count = sum(1 for kw in trap_keywords if kw in text.lower())
        if count >= 3:
            return 'high'
        elif count >= 1:
            return 'medium'
        return 'low'

    def distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for q in self.questions:
            d = q.get('difficulty', 'easy')
            dist[d] = dist.get(d, 0) + 1
        return dist
