from __future__ import annotations

from typing import Any

from bot.constants import ANSWER_LETTERS


def validate_question_answer_consistency(questions: list[dict]) -> list[str]:
    issues = []

    for idx, q in enumerate(questions):
        qid = q.get('id', idx)

        correct = q.get('correct_answer')
        options = q.get('options', [])
        choices = q.get('choices')

        if correct is None and choices:
            correct_choice = q.get('correct_choice')
            if correct_choice and correct_choice in choices:
                correct = choices[correct_choice]

        if correct is None:
            issues.append(f'question_{qid}_index_{idx}_no_correct_answer')
            continue

        if options:
            if len(options) < 2:
                issues.append(f'question_{qid}_index_{idx}_too_few_options_count={len(options)}')
            if correct not in options:
                issues.append(f'question_{qid}_index_{idx}_correct_answer_not_in_options')
            if len(set(str(o).lower() for o in options)) != len(options):
                issues.append(f'question_{qid}_index_{idx}_duplicate_options')

        if choices:
            if len(choices) < 2:
                issues.append(f'question_{qid}_index_{idx}_too_few_choices_count={len(choices)}')
            correct_choice = q.get('correct_choice')
            if correct_choice and correct_choice not in choices:
                issues.append(f'question_{qid}_index_{idx}_correct_choice_not_in_choices')
            if correct_choice and correct_choice not in ANSWER_LETTERS:
                issues.append(f'question_{qid}_index_{idx}_invalid_correct_choice_letter={correct_choice}')

    return issues


def validate_answer_mapping(
    attempt: dict[str, Any],
    questions: list[dict[str, Any]],
    answers: list[dict[str, Any]],
) -> list[str]:
    issues = []
    answer_map = {}
    for a in answers:
        idx = a.get('question_index')
        if idx is not None:
            answer_map[idx] = a

    for idx, q in enumerate(questions):
        a = answer_map.get(idx)
        if not a:
            continue

        selected = a.get('selected_answer', '')
        correct_stored = a.get('correct_answer', '')
        is_correct_stored = bool(a.get('is_correct'))

        correct_value = q.get('correct_answer')
        choices = q.get('choices')
        correct_choice = q.get('correct_choice')

        if choices and correct_choice:
            if selected in ANSWER_LETTERS:
                expected_correct = selected == correct_choice
                if expected_correct != is_correct_stored:
                    issues.append(
                        f'question_{idx}_letter_mismatch '
                        f'selected={selected} correct_choice={correct_choice} '
                        f'is_correct_stored={is_correct_stored}'
                    )
            else:
                issues.append(f'question_{idx}_selected_not_a_letter selected={selected}')
        elif correct_value:
            options = q.get('options', [])
            if selected in ANSWER_LETTERS:
                opt_idx = ANSWER_LETTERS.index(selected)
                if opt_idx < len(options):
                    selected_value = options[opt_idx]
                    expected_correct = selected_value == correct_value
                    if expected_correct != is_correct_stored:
                        issues.append(
                            f'question_{idx}_value_mismatch '
                            f'selected_letter={selected} selected_value={selected_value} '
                            f'correct_value={correct_value} is_correct_stored={is_correct_stored}'
                        )
                else:
                    issues.append(f'question_{idx}_option_index_oob idx={opt_idx} len_options={len(options)}')

    return issues


def verify_answer_key_consistency(questions: list[dict]) -> bool:
    for idx, q in enumerate(questions):
        correct = q.get('correct_answer')
        correct_choice = q.get('correct_choice')
        choices = q.get('choices')
        options = q.get('options')

        if correct and options:
            if correct not in options:
                return False

        if correct_choice and choices:
            if correct_choice not in choices:
                return False

        if correct_choice and correct:
            if choices and correct_choice in choices:
                if choices[correct_choice] != correct:
                    return False

    return True
