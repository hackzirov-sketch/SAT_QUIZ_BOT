from bot.mock_tests import (
    MOCK_MODULE_SIZE,
    MOCK_TOTAL_QUESTIONS,
    load_mock_bank,
    mock_result_text,
    mock_topic_counts,
    select_mock_questions,
    validate_mock_question,
)
from bot.keyboards import mock_answer_kb


def _question(index: int, topic: str) -> dict:
    return {
        'id': f'{topic}-{index}',
        'topic': topic,
        'module_hint': None,
        'difficulty': 'mixed',
        'question': f'Question {index}',
        'choices': {'A': 'one', 'B': 'two', 'C': 'three', 'D': 'four'},
        'correct_choice': 'A',
        'explanation': '',
        'source_page': 1,
    }


def test_mock_bank_json_is_valid_and_large_enough():
    bank = load_mock_bank()

    assert len(bank) >= MOCK_TOTAL_QUESTIONS
    assert all(validate_mock_question(question) for question in bank)
    assert len(mock_topic_counts(bank)) >= 10


def test_select_mock_questions_splits_modules_and_avoids_duplicates():
    bank = [_question(index, f'Topic {index % 25}') for index in range(100)]

    selected = select_mock_questions(bank, seed=123)

    assert len(selected) == MOCK_TOTAL_QUESTIONS
    assert len({question['id'] for question in selected}) == MOCK_TOTAL_QUESTIONS
    assert [question['module'] for question in selected[:MOCK_MODULE_SIZE]] == [1] * MOCK_MODULE_SIZE
    assert [question['module'] for question in selected[MOCK_MODULE_SIZE:]] == [2] * MOCK_MODULE_SIZE
    assert selected[0]['module_index'] == 1
    assert selected[MOCK_MODULE_SIZE]['module_index'] == 1


def test_select_mock_questions_balances_topics_first():
    bank = [_question(index, f'Topic {index % 25}') for index in range(100)]

    selected = select_mock_questions(bank, seed=456)

    assert len({question['topic'] for question in selected}) == 25


def test_select_mock_questions_does_not_mutate_source_bank():
    bank = [_question(index, f'Topic {index % 25}') for index in range(100)]

    select_mock_questions(bank, seed=789)

    assert all('module' not in question and 'module_index' not in question for question in bank)


def test_mock_answer_keyboard_uses_separate_namespace_and_truncates_labels():
    markup = mock_answer_kb(
        12,
        3,
        {'A': 'x' * 120, 'B': 'two', 'C': 'three', 'D': 'four'},
    )

    buttons = [button for row in markup.inline_keyboard for button in row]

    assert buttons[0].callback_data == 'mock_ans:12:3:A'
    assert buttons[0].text.startswith('A) ')
    assert len(buttons[0].text) < 70


def test_mock_result_text_shows_module_and_topic_breakdown():
    questions = [_question(index, 'Algebra') for index in range(4)]
    for index, question in enumerate(questions):
        question['module'] = 1 if index < 2 else 2
    answers = [
        {'question_index': 0, 'is_correct': 1},
        {'question_index': 1, 'is_correct': 0},
        {'question_index': 2, 'is_correct': 1},
        {'question_index': 3, 'is_correct': 1},
    ]

    text = mock_result_text({'completion_seconds': 90}, questions, answers)

    assert '3/4 (75%)' in text
    assert 'Module 1: 1/2' in text
    assert 'Module 2: 2/2' in text
    assert 'Algebra: 3/4' in text
