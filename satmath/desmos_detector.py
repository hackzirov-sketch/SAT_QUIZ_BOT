from __future__ import annotations

import re
from typing import Any


class DesmosDetector:
    def __init__(self, questions: list[dict]):
        self.questions = questions

    def detect_all(self) -> list[dict]:
        for q in self.questions:
            result = self._analyze(q)
            q['desmos_recommended'] = result['recommended']
            q['desmos_solution_uz'] = result['solution_uz']
            q['calculator_allowed'] = True
        return self.questions

    def _analyze(self, q: dict) -> dict:
        text = q.get('question_text', '').lower()
        choices_text = ' '.join(q.get('choices', {}).values()).lower()
        full = text + ' ' + choices_text
        topic = q.get('topic', '')
        qtype = q.get('question_type', 'multiple_choice')

        desmos_useful_patterns = [
            r'\bgraph\b', r'\bplot\b', r'\bintersect\b',
            r'\bvertex\b', r'\bmaximum\b', r'\bminimum\b',
            r'\bparabola\b', r'\bquadratic\b', r'\bexponential\b',
            r'\bsystem\b', r'\bsolution\b', r'\broot\b',
            r'\bzero\b', r'\bx-intercept\b', r'\by-intercept\b',
            r'\bslope\b', r'\bline\b.*\bpasses\b', r'\bregression\b',
            r'\bline of best fit\b', r'\bcorrelation\b',
            r'\btable\b', r'\bequation\b',
            r'\bscatterplot\b', r'\bdata\b',
        ]

        score = sum(1 for p in desmos_useful_patterns if re.search(p, full))

        if score >= 3:
            recommended = True
            solution = self._generate_desmos_solution(q, 'high')
        elif score >= 1:
            recommended = True
            solution = self._generate_desmos_solution(q, 'medium')
        else:
            recommended = False
            solution = (
                'Desmos shart emas. Mental/algebraik yechim tezroq.\n\n'
                'Maslahat: Agar tenglama yoki ifoda soddaroq bo\'lsa, '
                'qog\'ozda yechish Desmosdan tezroq ketadi.'
            )

        return {'recommended': recommended, 'solution_uz': solution}

    def _generate_desmos_solution(self, q: dict, level: str) -> str:
        text = q.get('question_text', '')
        lines = ['<b>Desmos yechimi:</b>\n']

        has_graph = any(kw in text.lower() for kw in ['graph', 'plot', 'figure'])
        has_equation = any(kw in text.lower() for kw in ['equation', '=', 'function'])
        has_system = any(kw in text.lower() for kw in ['system', 'simultaneous'])
        has_table = any(kw in text.lower() for kw in ['table', 'data'])
        has_scatter = any(kw in text.lower() for kw in ['scatterplot', 'scatter plot'])

        if has_system:
            lines.append('1. Desmosga birinchi tenglamani kiriting.')
            lines.append('2. Ikkinchi tenglamani kiriting.')
            lines.append('3. Kesishgan nuqtani toping.')
            lines.append('4. Koordinatalarni tekshirib, mos javobni tanlang.')
        elif has_graph or has_equation:
            lines.append('1. Desmosga funksiya/ifodani kiriting.')
            if has_scatter:
                lines.append('2. Nuqtalarni Desmosga kiriting (table mode).')
                lines.append('3. Regression chiziqni toping.')
            else:
                lines.append('2. Grafikni kuzating.')
                lines.append('3. So\'ralgan qiymatni toping (kesishish, maksimum, minimum).')
            lines.append('4. Grafikdagi qiymatni javob bilan solishtiring.')
        elif has_table:
            lines.append('1. Desmosda table mode-ni oching.')
            lines.append('2. Ma\'lumotlarni jadvalga kiriting.')
            lines.append('3. Regression tenglamani toping.')
            lines.append('4. So\'ralgan qiymatni hisoblang.')
        else:
            lines.append('1. Ifodani Desmosga kiriting.')
            lines.append('2. Qiymatlarni tekshiring.')
            lines.append('3. Javobni variantlar bilan solishtiring.')

        lines.append('')
        lines.append('💡 <b>Maslahat:</b> Desmosda har bir variantni tekshirish mumkin.')
        lines.append('Variantlarni birma-bir kiritib, qaysi biri shartni qanoatlantirishini toping.')

        return '\n'.join(lines)

    def distribution(self) -> dict[str, int]:
        return {
            'desmos_recommended': sum(1 for q in self.questions if q.get('desmos_recommended')),
            'desmos_not_needed': sum(1 for q in self.questions if not q.get('desmos_recommended')),
        }
