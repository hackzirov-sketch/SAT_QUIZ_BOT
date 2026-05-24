from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from satmath.config import SATMathConfig, SAT_TOPIC_ALIASES


class PDFAnalyzer:
    def __init__(self, extracted_text: str | None = None):
        self.text = extracted_text
        self.page_map: dict[int, dict[str, Any]] = {}
        self.topic_sections: list[dict[str, Any]] = []
        self.answer_sections: list[dict[str, Any]] = []

    @classmethod
    def from_file(cls, path: Path | str = SATMathConfig.EXTRACTED_TEXT) -> PDFAnalyzer:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f'Extracted text not found: {p}')
        return cls(p.read_text(encoding='utf-8'))

    def analyze(self) -> dict[str, Any]:
        self._detect_pages()
        self._detect_topic_sections()
        self._detect_answer_sections()
        return {
            'total_pages': len(self.page_map),
            'topic_sections': len(self.topic_sections),
            'answer_sections': len(self.answer_sections),
            'topics': [s['topic'] for s in self.topic_sections],
            'missing_topics': self._find_missing_topics(),
            'page_map': self.page_map,
        }

    def _detect_pages(self):
        for match in re.finditer(r'--- PAGE (\d+) ---', self.text):
            page_num = int(match.group(1))
            start = match.end()
            end_match = re.search(r'--- PAGE \d+ ---', self.text[start:])
            end = start + end_match.start() if end_match else len(self.text)
            content = self.text[start:end].strip()
            self.page_map[page_num] = {
                'number': page_num,
                'content_preview': content[:200],
                'has_heading': bool(re.search(r'^[A-Z][A-Za-z\s,;&()]+$', content[:80], re.MULTILINE)),
                'has_answer_key': 'Answers:' in content[:500],
                'has_questions': bool(re.search(r'^\d+\.\s+\[', content[:2000], re.MULTILINE)),
                'has_diagram_keywords': self._has_diagram(content),
                'length': len(content),
            }

    def _has_diagram(self, text: str) -> bool:
        keywords = ['figure', 'graph', 'scatterplot', 'diagram', 'chart',
                     'note:', 'not drawn', 'triangle', 'circle', 'line',
                     'xy-plane', 'coordinate', 'plot', 'table']
        return any(kw in text.lower() for kw in keywords)

    def _detect_topic_sections(self):
        answer_positions = [(m.start(), m.group(1)) for m in re.finditer(r'(?m)^Answers:\s*(.+?)\s*$', self.text)]
        for ans_start, topic_label in answer_positions:
            canonical = SAT_TOPIC_ALIASES.get(topic_label.strip(), topic_label.strip())
            heading_pattern = r'(?m)^' + re.escape(topic_label.strip()) + r'\s*$'
            headings = list(re.finditer(heading_pattern, self.text[:ans_start]))
            for alias, canonical_name in SAT_TOPIC_ALIASES.items():
                if alias != topic_label.strip():
                    alt_pattern = r'(?m)^' + re.escape(alias) + r'\s*$'
                    alt_headings = list(re.finditer(alt_pattern, self.text[:ans_start]))
                    headings.extend(alt_headings)
            if not headings:
                for alias, canonical_name in SAT_TOPIC_ALIASES.items():
                    if canonical_name == canonical and alias != topic_label.strip():
                        alt_pattern = r'(?m)^' + re.escape(alias) + r'\s*$'
                        alt_headings = list(re.finditer(alt_pattern, self.text[:ans_start]))
                        headings.extend(alt_headings)
            if not headings:
                headings = list(re.finditer(heading_pattern, self.text[:ans_start]))
            topic_start = headings[-1].end() if headings else ans_start
            answer_text = self.text[ans_start:ans_start + 3000]
            answer_end_match = re.search(r'--- PAGE', answer_text)
            answer_end = ans_start + answer_end_match.start() if answer_end_match else ans_start + 3000
            self.topic_sections.append({
                'topic': canonical,
                'original_label': topic_label.strip(),
                'topic_start': topic_start,
                'answer_start': ans_start,
                'answer_end': min(answer_end, len(self.text)),
            })

    def _detect_answer_sections(self):
        for section in self.topic_sections:
            answer_text = self.text[section['answer_start']:section['answer_end']]
            answers = {}
            for match in re.finditer(r'(\d+)\s+([ABCD]|[\d/.,]+)', answer_text):
                num = int(match.group(1))
                val = match.group(2).strip()
                answers[num] = val
            self.answer_sections.append({
                'topic': section['topic'],
                'answer_start': section['answer_start'],
                'answers': answers,
            })

    def _find_missing_topics(self) -> list[str]:
        found = {s['topic'] for s in self.topic_sections}
        all_topics = set(SAT_TOPIC_ALIASES.values()) | {
            'Expressions', 'Linear Equations', 'Linear System of Equations',
            'Linear Functions', 'Linear Inequalities',
            'Polynomials', 'Exponents&Radicals', 'Functions&Function Notation',
            'Exponential Functions', 'Quadratics',
            'Percent; Ratio&Proportion', 'Unit Conversion',
            'Probability', 'Mean, Median, Mode, Range',
            'Scatterplots', 'Research Organizing',
            'Lines and Angles', 'Triangles', 'Trigonometry',
            'Circles', 'Area and Volume',
        }
        canonical_found = {SAT_TOPIC_ALIASES.get(t, t) for t in found}
        canonical_all = {SAT_TOPIC_ALIASES.get(t, t) for t in all_topics}
        return sorted(canonical_all - canonical_found)

    def get_page_summary(self) -> dict[str, list[int]]:
        result: dict[str, list[int]] = defaultdict(list)
        for page_num, info in sorted(self.page_map.items()):
            if info['has_answer_key']:
                result['answer_key_pages'].append(page_num)
            if info['has_questions']:
                result['question_pages'].append(page_num)
            if info['has_diagram_keywords']:
                result['image_heavy_pages'].append(page_num)
        return dict(result)

    def get_answer_for_question(self, topic: str, number: int) -> str | None:
        for section in self.answer_sections:
            if section['topic'] == SAT_TOPIC_ALIASES.get(topic, topic):
                return section['answers'].get(number)
        return None
