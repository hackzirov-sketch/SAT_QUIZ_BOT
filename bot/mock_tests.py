from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from bot.config import MOCK_TESTS_DIR

MOCK_BANK_PATH = MOCK_TESTS_DIR / 'math_mock_bank.json'
MOCK_TOTAL_QUESTIONS = 44
MOCK_MODULE_SIZE = 22
MOCK_MODULE_SECONDS = 35 * 60
MOCK_CHOICES = ('A', 'B', 'C', 'D')


def mock_module_size(total: int) -> int:
    return min(MOCK_MODULE_SIZE, (total + 1) // 2)


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


def select_mock_questions(bank: list[dict[str, Any]], *, seed: int | None = None, topic: str | None = None) -> list[dict[str, Any]]:
    filtered = [q for q in bank if topic is None or q['topic'] == topic]
    available = len(filtered)
    if available < 1:
        raise MockBankError('Bu mavzuda savol yo\'q.')

    total = min(MOCK_TOTAL_QUESTIONS, available)
    module_size = mock_module_size(total)

    rng = random.Random(seed)
    rng.shuffle(filtered)
    selected = [dict(q) for q in filtered[:total]]

    module_1 = selected[:module_size]
    module_2 = selected[module_size:total]
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


def get_mock_topics(bank: list[dict[str, Any]]) -> list[str]:
    return sorted(set(q['topic'] for q in bank))
