from __future__ import annotations

import re
from typing import Any

from satmath.config import CHOICES


class ExplanationGenerator:
    def __init__(self, questions: list[dict]):
        self.questions = questions

    def generate_all(self) -> list[dict]:
        for q in self.questions:
            q['manual_solution_uz'] = self._manual_solution(q)
            if q.get('desmos_recommended') and not q.get('desmos_solution_uz'):
                q['desmos_solution_uz'] = self._desmos_solution(q)
            q['shortcut_uz'] = self._shortcut(q)
            q['common_trap_uz'] = self._common_trap(q)
        return self.questions

    def _manual_solution(self, q: dict) -> str:
        text = q.get('question_text', '')
        topic = q.get('topic', '')
        correct = q.get('correct_answer', '')
        choices = q.get('choices', {})
        correct_text = choices.get(correct, '')
        qtype = q.get('question_type', 'multiple_choice')

        parts = ['<b>Yechim:</b>\n']
        lines = [text.strip()]

        if qtype == 'grid_in':
            parts.append(f'Talab qilingan qiymat: {correct}')
            parts.append('')
            parts.append(self._grid_in_approach(q))
        else:
            parts.append(f'To\'g\'ri javob: {correct}) {correct_text}')
            parts.append('')

            wrong_elimination = self._elimination_approach(q)
            if wrong_elimination:
                parts.append(wrong_elimination)
                parts.append('')

            approach = self._topic_approach(q)
            if approach:
                parts.append(approach)
            else:
                parts.append('Berilgan shartlarni tenglama/ifoda ko\'rinishida yozing.')
                parts.append('Har bir variantni tekshirib, shartga mos keladiganini toping.')

        parts.append('')
        parts.append('<b>✅ Javob:</b> ' + (f'{correct}) {correct_text}' if qtype == 'multiple_choice' else str(correct)))
        return '\n'.join(parts)

    def _grid_in_approach(self, q: dict) -> str:
        text = q.get('question_text', '').lower()
        steps = ['1. Masala shartini tahlil qiling.', '2. O\'zgaruvchini belgilang.', '3. Tenglama tuzing.', '4. Tenglamani yeching.', '5. Javobni student-produced response formatida yozing (butun son, kasr, yoki o\'nli kasr).']
        if 'equation' in text or '=' in text:
            steps.insert(3, '   - Tenglamani bir o\'zgaruvchiga nisbatan yeching.')
        if 'percent' in text or 'ratio' in text or 'proportion' in text:
            steps.insert(3, '   - Proporsiyani tuzing va yeching.')
        if 'average' in text or 'mean' in text:
            steps.insert(3, '   - O\'rtacha qiymat formulasidan foydalaning.')
        return '\n'.join(steps)

    def _elimination_approach(self, q: dict) -> str:
        if q.get('question_type') != 'multiple_choice':
            return ''
        choices = q.get('choices', {})
        correct = q.get('correct_answer', '')
        wrong = [k for k in CHOICES if k != correct and k in choices]
        reasons = []
        for w in wrong[:2]:
            wtext = choices[w][:40]
            reasons.append(f'❌ {w}) {wtext}... — mos kelmaydi (shartni qanoatlantirmaydi)')
        if reasons:
            return 'Noto\'g\'ri variantlarni tekshirish:\n' + '\n'.join(reasons)
        return ''

    def _topic_approach(self, q: dict) -> str:
        topic = q.get('topic', '')
        text = q.get('question_text', '').lower()
        steps = {
            'Linear Equations': ['1. Tenglamani yozing.', '2. O\'zgaruvchini ajrating.', '3. Tenglamani yeching.', '4. Javobni tekshiring.'],
            'Linear Functions': ['1. Funksiya ko\'rinishini aniqlang (f(x) = mx + b).', '2. Berilgan nuqtalardan foydalanib m va b ni toping.', '3. So\'ralgan qiymatni hisoblang.'],
            'Systems of Equations': ['1. Ikkala tenglamani yozing.', '2. O\'rniga qo\'yish yoki qo\'shish usulidan foydalaning.', '3. x va y ni toping.', '4. Javobni tekshiring.'],
            'Quadratics': ['1. Kvadrat tenglamani yozing.', '2. Faktorlarga ajrating yoki kvadrat formula ishlating.', '3. Ildizlarni toping.', '4. Masala shartiga mos ildizni tanlang.'],
            'Exponents & Radicals': ['1. Daraja qoidalarini eslang.', '2. Ifodani soddalashtiring.', '3. Darajalarni bir xil asosga keltiring.', '4. Tenglamani yeching.'],
            'Probability': ['1. Qulay holatlar sonini aniqlang.', '2. Umumiy holatlar sonini aniqlang.', '3. Ehtimol = qulay/umumiy formulasini qo\'llang.', '4. Foiz yoki kasr ko\'rinishida ifodalang.'],
            'Triangles': ['1. Uchburchak turini aniqlang.', '2. Pifagor teoremasini yoki o\'xshashlikni qo\'llang.', '3. Trigonometrik nisbatlardan foydalaning (agar kerak).', '4. So\'ralgan tomon yoki burchakni toping.'],
            'Circles': ['1. Doira formulalarini eslang (aylana, yuz, yoy).', '2. Berilgan ma\'lumotlardan radius/diametrni toping.', '3. So\'ralgan qiymatni hisoblang.'],
            'Area and Volume': ['1. Shakl turini aniqlang.', '2. Tegishli formula tanlang.', '3. O\'lchamlarni formulaga qo\'ying.', '4. Hisoblang va birlikni ko\'rsating.'],
        }
        if topic in steps:
            return 'Qadamlar:\n' + '\n'.join(steps[topic])
        return ''

    def _desmos_solution(self, q: dict) -> str:
        text = q.get('question_text', '').lower()
        lines = ['<b>Desmos yechimi:</b>\n', '1. Desmos kalkulyatorni oching.', '2. Funksiya/tenglamani kiriting.']
        if 'system' in text or 'solution' in text:
            lines += ['3. Ikkala tenglamani kiriting.', '4. Kesishish nuqtasini toping.']
        elif 'graph' in text or 'plot' in text:
            lines += ['3. Grafikni tahlil qiling.', '4. So\'ralgan nuqta/qiymatni toping.']
        else:
            lines += ['3. Qiymatlarni tekshiring.', '4. Har bir variantni Desmosga kiriting.']
        lines.append('5. Javobni belgilang.')
        return '\n'.join(lines)

    def _shortcut(self, q: dict) -> str:
        text = q.get('question_text', '').lower()
        qtype = q.get('question_type', 'multiple_choice')
        shortcuts = {
            'backsolve': 'Javob variantlaridan foydalaning: har bir variantni shartga qo\'yib tekshiring. Bu ko\'pincha eng tez usul.',
            'plug_numbers': 'Murakkab ifodaga son qo\'yib tekshiring. Oson hisoblanadigan son tanlang (0, 1, -1).',
            'elimination': 'Avval aniq noto\'g\'ri variantlarni chiqarib tashlang. Qolganlarini tekshiring.',
            'unit_test': 'Birliklarni tekshiring: javob birligi masala birligiga mos kelishi kerak.',
            'sign_check': 'Ishorani tekshiring: musbat/manfiy javobni tezda aniqlang.',
            'estimation': 'Taxminiy hisob: javoblar orasidagi farq katta bo\'lsa, taxminiy hisob yetarli.',
        }
        if qtype == 'multiple_choice':
            key = 'backsolve'
            if any(kw in text for kw in ['equation', '=', 'function']):
                key = 'backsolve'
            elif any(kw in text for kw in ['graph', 'plot', 'figure']):
                key = 'elimination'
            elif any(kw in text for kw in ['percent', '%']):
                key = 'estimation'
            return shortcuts.get(key, shortcuts['backsolve'])
        else:
            return shortcuts['plug_numbers']

    def _common_trap(self, q: dict) -> str:
        text = q.get('question_text', '').lower()
        choices = q.get('choices', {})
        correct = q.get('correct_answer', '')
        traps = []

        if any(kw in text for kw in ['not', 'except']):
            traps.append('⚠️ "NOT" so\'ziga e\'tibor bering! So\'ralayotgan narsa mos kelmaydigan variant.')
        if any(kw in text for kw in ['percent increase', 'percent decrease', 'percent more', 'percent less']):
            traps.append('⚠️ Foiz o\'zgarishini hisoblashda asosiy qiymatni adashtirmang.')
        if q.get('question_type') == 'multiple_choice':
            wrong_texts = {k: v.lower() for k, v in choices.items() if k != correct}
            for k, v in wrong_texts.items():
                if 'negative' in v and 'negative' not in text:
                    traps.append(f'⚠️ {k}) variant manfiy ishorali — bu "trap" bo\'lishi mumkin.')
                if '0' in v and 'zero' not in text:
                    traps.append(f'⚠️ {k}) variant 0 — tenglamani to\'liq yechmasdan 0 ni tanlamang.')
        if not traps:
            traps.append('Masala shartini diqqat bilan o\'qing. Oshiqcha ma\'lumotlardan chalg\'imang.')
        return '\n'.join(traps[:3])
