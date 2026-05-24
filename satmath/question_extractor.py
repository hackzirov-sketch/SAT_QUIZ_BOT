from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from satmath.config import SATMathConfig, CHOICES, SAT_TOPIC_ALIASES


class QuestionExtractor:
    def __init__(self, extracted_text: str):
        self.text = extracted_text
        self.questions: list[dict[str, Any]] = []
        self.grid_in_questions: list[dict[str, Any]] = []

    @classmethod
    def from_file(cls, path: Path | str = SATMathConfig.EXTRACTED_TEXT) -> QuestionExtractor:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f'Extracted text not found: {p}')
        return cls(p.read_text(encoding='utf-8'))

    def extract_all(self) -> list[dict[str, Any]]:
        self.questions = []
        self.grid_in_questions = []
        for answer_match in re.finditer(r'(?m)^Answers:\s*(.+?)\s*$', self.text):
            topic_label = answer_match.group(1).strip()
            self._extract_topic_questions(topic_label, answer_match)
        self._deduplicate()
        return self.questions + self.grid_in_questions

    def _extract_topic_questions(self, topic_label: str, answer_match: re.Match):
        topic = SAT_TOPIC_ALIASES.get(topic_label, topic_label)
        answer_start = answer_match.start()
        answer_text = self.text[answer_start:answer_start + 3000]
        answers = self._parse_answers(answer_text)

        headings = self._find_topic_headings(topic_label, answer_start)
        if not headings:
            return
        topic_start = headings[-1].end()
        question_area = self.text[topic_start:answer_start]

        for q_match in re.finditer(r'(?m)^(\d+)\.\s+\[([^\]]+)\]\s*', question_area):
            number = int(q_match.group(1))
            month = q_match.group(2)
            q_start = q_match.end()
            q_end_matches = list(re.finditer(r'(?m)^(\d+)\.\s+\[', question_area[q_start:]))
            q_end = q_start + q_end_matches[0].start() if q_end_matches else len(question_area)
            block = question_area[q_start:q_end].strip()

            correct = answers.get(number)
            if not correct:
                continue

            mc = self._parse_multiple_choice(block)
            if mc and correct in CHOICES:
                question_text, choices = mc
                abs_pos = topic_start + q_match.start()
                self.questions.append(self._make_question(
                    topic, number, month, question_text, choices, correct,
                    self._source_page_for(abs_pos), 'multiple_choice',
                ))
            elif correct not in CHOICES:
                abs_pos = topic_start + q_match.start()
                self.grid_in_questions.append(self._make_grid_in(
                    topic, number, month, block, correct,
                    self._source_page_for(abs_pos),
                ))

    def _parse_answers(self, answer_text: str) -> dict[int, str]:
        answers = {}
        after_header = answer_text.split('\n', 1)[1] if '\n' in answer_text else answer_text
        for match in re.finditer(r'(\d+)\s+([ABCD]|[-\d/.,]+)', after_header):
            num = int(match.group(1))
            val = match.group(2).strip()
            if val and num > 0:
                answers[num] = val
        return answers

    def _find_topic_headings(self, topic_label: str, before_pos: int) -> list[re.Match]:
        patterns = [topic_label]
        for alias, canonical in SAT_TOPIC_ALIASES.items():
            if canonical == SAT_TOPIC_ALIASES.get(topic_label, topic_label):
                patterns.append(alias)
        patterns = list(set(patterns))
        headings = []
        for pat in patterns:
            headings.extend(list(re.finditer(r'(?m)^' + re.escape(pat) + r'\s*$', self.text[:before_pos])))
        if not headings:
            loose = list(re.finditer(r'(?mi)^' + re.escape(topic_label)[:10] + r'.*$', self.text[:before_pos]))
            if loose:
                headings.append(loose[-1])
        return sorted(headings, key=lambda m: m.start())

    def _parse_multiple_choice(self, block: str) -> tuple[str, dict[str, str]] | None:
        markers = list(re.finditer(r'(?m)^([ABCD])\)\s*', block))
        if len(markers) != 4:
            alt = list(re.finditer(r'(?m)^([ABCD])\.\s+', block))
            if len(alt) == 4:
                markers = alt
            else:
                return None
        if tuple(m.group(1) for m in markers) != ('A', 'B', 'C', 'D'):
            return None
        question_text = block[:markers[0].start()].strip()
        choices = {}
        for idx, marker in enumerate(markers):
            end = markers[idx + 1].start() if idx + 1 < len(markers) else len(block)
            choices[marker.group(1)] = self._clean(block[marker.end():end])
        if not question_text or not all(choices[c] for c in CHOICES):
            return None
        return question_text, choices

    def _clean(self, text: str) -> str:
        text = text.replace('\u2019', "'").replace('\u2018', "'")
        text = text.replace('\u201c', '"').replace('\u201d', '"')
        text = re.sub(r'-\n(?=[a-z])', '', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _source_page_for(self, position: int) -> int | None:
        page = None
        for match in re.finditer(r'--- PAGE (\d+) ---', self.text[:position]):
            page = int(match.group(1))
        return page

    def _slug(self, topic: str) -> str:
        return re.sub(r'[^a-z0-9]+', '-', topic.lower()).strip('-')

    def _make_question(self, topic: str, number: int, month: str,
                       question_text: str, choices: dict, correct: str,
                       page: int | None, qtype: str) -> dict:
        return {
            'id': f'{self._slug(topic)}-{number}',
            'source_pdf': 'Mathbook 3.0',
            'page': page,
            'topic': topic,
            'month': month,
            'question_number_original': number,
            'question_type': qtype,
            'difficulty': 'mixed',
            'sat_domain': '',
            'skill': '',
            'calculator_allowed': True,
            'desmos_recommended': False,
            'image_required': False,
            'question_text': self._clean(question_text),
            'choices': {k: self._clean(v) for k, v in choices.items()} if qtype == 'multiple_choice' else {},
            'correct_answer': correct,
            'manual_solution_uz': '',
            'desmos_solution_uz': '',
            'shortcut_uz': '',
            'common_trap_uz': '',
            'tags': [],
            'needs_manual_review': False,
        }

    def _make_grid_in(self, topic: str, number: int, month: str,
                      question_text: str, correct: str,
                      page: int | None) -> dict:
        return {
            'id': f'{self._slug(topic)}-{number}-grid',
            'source_pdf': 'Mathbook 3.0',
            'page': page,
            'topic': topic,
            'month': month,
            'question_number_original': number,
            'question_type': 'grid_in',
            'difficulty': 'mixed',
            'sat_domain': '',
            'skill': '',
            'calculator_allowed': True,
            'desmos_recommended': False,
            'image_required': False,
            'question_text': self._clean(question_text),
            'choices': {},
            'correct_answer': correct,
            'manual_solution_uz': '',
            'desmos_solution_uz': '',
            'shortcut_uz': '',
            'common_trap_uz': '',
            'tags': [],
            'needs_manual_review': False,
        }

    def _deduplicate(self):
        seen = set()
        unique = []
        for q in self.questions + self.grid_in_questions:
            if q['id'] in seen:
                continue
            seen.add(q['id'])
            unique.append(q)
        self.questions = [q for q in unique if q['question_type'] == 'multiple_choice']
        self.grid_in_questions = [q for q in unique if q['question_type'] == 'grid_in']
