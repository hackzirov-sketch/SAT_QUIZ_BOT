from __future__ import annotations

from typing import Any

from satmath.config import DOMAIN_MAP, SAT_MATH_DOMAINS, SAT_TOPIC_ALIASES


class SATClassifier:
    def __init__(self, questions: list[dict]):
        self.questions = questions

    def classify_all(self) -> list[dict]:
        for q in self.questions:
            topic = SAT_TOPIC_ALIASES.get(q.get('topic', ''), q.get('topic', ''))
            q['sat_domain'] = DOMAIN_MAP.get(topic, 'Algebra')
            q['skill'] = self._detect_skill(q)
        return self.questions

    def _detect_skill(self, q: dict) -> str:
        text = (q.get('question_text', '') + ' ' + ' '.join(q.get('choices', {}).values())).lower()
        topic = q.get('topic', '')
        skill_map: dict[str, list[str]] = {
            'Expressions': ['Equivalent expressions', 'Algebraic manipulation'],
            'Linear Equations': ['Solving linear equations', 'Linear equation word problems'],
            'Systems of Equations': ['Solving systems', 'System word problems'],
            'Linear Functions': ['Linear function interpretation', 'Function graphs'],
            'Linear Inequalities': ['Linear inequalities', 'Inequality word problems'],
            'Polynomials': ['Polynomial operations', 'Polynomial factorization'],
            'Exponents & Radicals': ['Exponent rules', 'Radical expressions'],
            'Function Notation': ['Function evaluation', 'Composite functions'],
            'Exponential Functions': ['Exponential growth/decay', 'Exponential equations'],
            'Quadratics': ['Quadratic equations', 'Quadratic graphs', 'Vertex form'],
            'Percent / Ratio / Proportion': ['Percent change', 'Ratios', 'Proportions'],
            'Unit Conversion': ['Unit conversion', 'Dimensional analysis'],
            'Probability': ['Probability', 'Relative frequency'],
            'Mean / Median / Mode / Range': ['Central tendency', 'Data spread'],
            'Scatterplots': ['Scatterplot interpretation', 'Line of best fit'],
            'Margin of Error / Outliers': ['Margin of error', 'Outlier detection'],
            'Lines and Angles': ['Angle relationships', 'Parallel lines'],
            'Triangles': ['Triangle properties', 'Right triangles', 'Similar triangles'],
            'Trigonometry': ['Sine/cosine/tangent', 'Trig ratios'],
            'Circles': ['Circle equations', 'Circle geometry', 'Arc length'],
            'Area and Volume': ['Area formulas', 'Volume formulas', 'Surface area'],
        }
        skills = skill_map.get(topic, ['General'])
        for sk in skills:
            for kw in sk.lower().split():
                if kw in text:
                    return sk
        return skills[0]

    def domain_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for q in self.questions:
            d = q.get('sat_domain', 'Algebra')
            dist[d] = dist.get(d, 0) + 1
        return dist

    def topic_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for q in self.questions:
            t = q.get('topic', 'Unknown')
            dist[t] = dist.get(t, 0) + 1
        return dist
