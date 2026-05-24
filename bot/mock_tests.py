from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from bot.config import ROOT

MOCK_BANK_PATH = ROOT / 'data' / 'mock_tests' / 'math_mock_bank.json'
MOCK_TOTAL_QUESTIONS = 44
MOCK_MODULE_SIZE = 22
MOCK_MODULE_SECONDS = 35 * 60
MOCK_CHOICES = ('A', 'B', 'C', 'D')


class MockBankError(RuntimeError):
    pass


def load_mock_bank(path: str | Path = MOCK_BANK_PATH) -> list[dict[str, Any]]:
    bank_path = Path(path)
    if not bank_path.exists():
        return []
    with bank_path.open('r', encoding='utf-8') as f:
        raw = json.load(f)
    return [q for q in raw if validate_mock_question(q)]


def validate_mock_question(question: dict[str, Any]) -> bool:
    choices = question.get('choices')
    return (
        isinstance(question.get('id'), str)
        and isinstance(question.get('topic'), str)
        and isinstance(question.get('question'), str)
        and isinstance(choices, dict)
        and all(choice in choices and str(choices[choice]).strip() for choice in MOCK_CHOICES)
        and question.get('correct_choice') in MOCK_CHOICES
    )


def select_mock_questions(bank: list[dict[str, Any]], *, seed: int | None = None) -> list[dict[str, Any]]:
    if len(bank) < MOCK_TOTAL_QUESTIONS:
        raise MockBankError('Mock test hali tayyor emas.')

    rng = random.Random(seed)
    by_topic: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for question in bank:
        by_topic[question['topic']].append(question)
    for questions in by_topic.values():
        rng.shuffle(questions)

    selected: list[dict[str, Any]] = []
    topic_names = list(by_topic)
    rng.shuffle(topic_names)

    for topic in topic_names:
        if len(selected) >= MOCK_TOTAL_QUESTIONS:
            break
        selected.append(by_topic[topic].pop())

    topic_index = 0
    while len(selected) < MOCK_TOTAL_QUESTIONS:
        available = [topic for topic in topic_names if by_topic[topic]]
        if not available:
            break
        topic = available[topic_index % len(available)]
        selected.append(by_topic[topic].pop())
        topic_index += 1

    if len(selected) < MOCK_TOTAL_QUESTIONS:
        raise MockBankError('Mock test hali tayyor emas.')

    rng.shuffle(selected)
    selected = [dict(question) for question in selected]
    module_1 = selected[:MOCK_MODULE_SIZE]
    module_2 = selected[MOCK_MODULE_SIZE:MOCK_TOTAL_QUESTIONS]
    for index, question in enumerate(module_1, start=1):
        question['module'] = 1
        question['module_index'] = index
    for index, question in enumerate(module_2, start=1):
        question['module'] = 2
        question['module_index'] = index
    return module_1 + module_2


def mock_question_text(question: dict[str, Any], index: int, total: int, remaining: int) -> str:
    from bot.formatting import esc, format_seconds

    module = question.get('module', 1)
    module_index = question.get('module_index', index + 1)
    topic = esc(question.get('topic', 'Math'))
    prompt = esc(question['question'])
    remaining_s = format_seconds(remaining)
    return (
        f"⏳ <b>Qolgan vaqt:</b> {remaining_s}\n"
        f"📝 <b>Mock Math | Module {module}</b>\n"
        f"📘 <b>Savol {module_index}/{MOCK_MODULE_SIZE}</b> | {topic}\n\n"
        f"{prompt}"
    )


def mock_result_text(attempt: dict[str, Any], questions: list[dict[str, Any]], answers: list[dict[str, Any]]) -> str:
    from bot.formatting import esc, format_seconds

    total = len(questions)
    correct = sum(1 for answer in answers if answer.get('is_correct'))
    percent = round((correct / total) * 100) if total else 0
    module_stats = {1: [0, 0], 2: [0, 0]}
    topic_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    for answer in answers:
        idx = answer['question_index']
        if idx >= len(questions):
            continue
        question = questions[idx]
        module = int(question.get('module', 1))
        topic = question.get('topic', 'Math')
        module_stats[module][1] += 1
        topic_stats[topic][1] += 1
        if answer.get('is_correct'):
            module_stats[module][0] += 1
            topic_stats[topic][0] += 1

    lines = [
        "✅ <b>Mock test yakunlandi!</b>",
        "",
        f"🎯 <b>Natija:</b> {correct}/{total} ({percent}%)",
        f"⏱ <b>Vaqt:</b> {format_seconds(attempt.get('completion_seconds', 0))}",
        "",
        "<b>Modullar:</b>",
        f"Module 1: {module_stats[1][0]}/{module_stats[1][1]}",
        f"Module 2: {module_stats[2][0]}/{module_stats[2][1]}",
        "",
        "<b>Mavzular:</b>",
    ]
    for topic, (topic_correct, topic_total) in sorted(topic_stats.items()):
        lines.append(f"- {esc(topic)}: {topic_correct}/{topic_total}")
    return '\n'.join(lines)


def mock_topic_counts(bank: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(q['topic'] for q in bank))
