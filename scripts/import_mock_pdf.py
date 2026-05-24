from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pypdf import PdfReader

CHOICES = ('A', 'B', 'C', 'D')


def extract_pdf_text(pdf_path: Path, extracted_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    parts = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ''
        parts.append(f'\n\n--- PAGE {page_num} ---\n{text}')
    extracted = '\n'.join(parts)
    extracted_path.parent.mkdir(parents=True, exist_ok=True)
    extracted_path.write_text(extracted, encoding='utf-8')
    return extracted


def clean_text(text: str) -> str:
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = re.sub(r'-\n(?=[a-z])', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text


def parse_answer_section(section: str) -> dict[int, str]:
    answers = {}
    for number, answer in re.findall(r'\b(\d+)\s+([ABCD])\b', section):
        answers[int(number)] = answer
    return answers


def source_page_for(text: str, position: int) -> int | None:
    page = None
    for match in re.finditer(r'--- PAGE (\d+) ---', text[:position]):
        page = int(match.group(1))
    return page


def split_choice_question(block: str) -> tuple[str, dict[str, str]] | None:
    markers = list(re.finditer(r'(?m)^([ABCD])\)\s*', block))
    if len(markers) != 4 or tuple(marker.group(1) for marker in markers) != CHOICES:
        return None
    question_text = block[:markers[0].start()].strip()
    choices = {}
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(block)
        choices[marker.group(1)] = block[marker.end():end].strip()
    if not question_text or any(not choices[choice] for choice in CHOICES):
        return None
    return question_text, choices


def parse_questions_for_topic(full_text: str, topic: str, answer_match: re.Match[str]) -> list[dict]:
    answer_start = answer_match.start()
    heading_matches = list(re.finditer(rf'(?m)^{re.escape(topic)}\s*$', full_text[:answer_start]))
    if not heading_matches:
        return []
    topic_start = heading_matches[-1].end()
    question_area = full_text[topic_start:answer_start]
    next_page = full_text.find('--- PAGE', answer_start + 1)
    answer_end = next_page if next_page != -1 else len(full_text)
    answers = parse_answer_section(full_text[answer_start:answer_end])
    questions = []
    starts = list(re.finditer(r'(?m)^(\d+)\.\s+\[[^\]]+\]', question_area))
    for index, start in enumerate(starts):
        number = int(start.group(1))
        correct = answers.get(number)
        if correct not in CHOICES:
            continue
        end = starts[index + 1].start() if index + 1 < len(starts) else len(question_area)
        block = question_area[start.end():end].strip()
        parsed = split_choice_question(block)
        if not parsed:
            continue
        question_text, choices = parsed
        absolute_pos = topic_start + start.start()
        questions.append({
            'id': f'{slug(topic)}-{number}',
            'topic': topic,
            'module_hint': None,
            'difficulty': 'mixed',
            'question': clean_text(question_text),
            'choices': {key: clean_text(value) for key, value in choices.items()},
            'correct_choice': correct,
            'explanation': '',
            'source_page': source_page_for(full_text, absolute_pos),
        })
    return questions


def slug(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')


def build_bank(extracted_text: str) -> list[dict]:
    bank = []
    for answer_match in re.finditer(r'(?m)^Answers:\s*(.+?)\s*$', extracted_text):
        topic = answer_match.group(1).strip()
        bank.extend(parse_questions_for_topic(extracted_text, topic, answer_match))
    seen = set()
    unique = []
    for question in bank:
        if question['id'] in seen:
            continue
        seen.add(question['id'])
        unique.append(question)
    return unique


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', default='bot/data/mock_pdfs/Mathbook 3.0.pdf')
    parser.add_argument('--out', default='bot/data/mock_tests/math_mock_bank.json')
    parser.add_argument('--text-out', default='bot/data/mock_tests/extracted/Mathbook 3.0.txt')
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    extracted_path = Path(args.text_out)
    out_path = Path(args.out)
    extracted = extract_pdf_text(pdf_path, extracted_path)
    bank = build_bank(extracted)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    topics = sorted({q['topic'] for q in bank})
    print(f'extracted_questions={len(bank)} topics={len(topics)}')
    for topic in topics:
        print(f'{topic}: {sum(1 for q in bank if q["topic"] == topic)}')


if __name__ == '__main__':
    main()
