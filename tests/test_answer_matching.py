import json
from bot.quiz_engine import QuizEngine
from bot.answer_validator import validate_question_answer_consistency, validate_answer_mapping, verify_answer_key_consistency
from bot.mock_tests import load_mock_bank, validate_mock_question
from bot.formatting import answer_feedback

SAMPLE_VOCAB = [
    {"id": i, "english": f"word_{i}", "uzbek": f"tarjima_{i}",
     "category": "Algebra", "source": "Test", "difficulty": "easy"}
    for i in range(1, 60)
]


def _make_mock_question(qid: str, correct: str) -> dict:
    choices = {"A": "opt_a", "B": "opt_b", "C": "opt_c", "D": "opt_d"}
    choices[correct] = "correct_value"
    return {
        "id": qid,
        "topic": "Algebra",
        "difficulty": "mixed",
        "question": f"Test question {qid}",
        "choices": choices,
        "correct_choice": correct,
        "explanation": "",
        "source_page": 1,
    }


def test_quiz_engine_generates_correct_answer_in_options():
    engine = QuizEngine(None, SAMPLE_VOCAB)
    result = engine.generate_questions(1, "eng_uzb", count=10, difficulty="easy", category="Algebra")
    for q in result["questions"]:
        assert q["correct_answer"] in q["options"], f"correct_answer {q['correct_answer']} not in options for question {q['id']}"


def test_quiz_engine_options_have_four_distinct():
    engine = QuizEngine(None, SAMPLE_VOCAB)
    result = engine.generate_questions(1, "eng_uzb", count=10, difficulty="easy", category="Algebra")
    for q in result["questions"]:
        assert len(q["options"]) == 4, f"question {q['id']} has {len(q['options'])} options"
        assert len(set(o.lower() for o in q["options"])) == 4, f"question {q['id']} has duplicate options"


def test_quiz_engine_answer_via_letter_matches_value():
    engine = QuizEngine(None, SAMPLE_VOCAB)
    result = engine.generate_questions(1, "eng_uzb", count=10, difficulty="easy", category="Algebra")
    letters = ["A", "B", "C", "D"]
    for q in result["questions"]:
        correct_idx = q["options"].index(q["correct_answer"])
        correct_letter = letters[correct_idx]
        selected_value = q["options"][letters.index(correct_letter)]
        assert selected_value == q["correct_answer"], (
            f"letter->value mismatch: letter={correct_letter} "
            f"selected={selected_value} correct={q['correct_answer']}"
        )


def test_quiz_engine_all_modes_generate_valid():
    engine = QuizEngine(None, SAMPLE_VOCAB)
    for mode in ("eng_uzb", "uzb_eng"):
        result = engine.generate_questions(1, mode, count=10, difficulty="easy", category="Algebra")
        issues = validate_question_answer_consistency(result["questions"])
        assert not issues, f"mode={mode} issues={issues}"


def test_mock_bank_questions_all_valid():
    bank = load_mock_bank()
    assert len(bank) >= 44, f"bank too small: {len(bank)}"
    for q in bank:
        assert validate_mock_question(q), f"invalid question: {q.get('id')}"
        assert q["correct_choice"] in q["choices"], f"correct_choice {q['correct_choice']} not in choices for {q['id']}"
        assert all(k in q["choices"] for k in ("A", "B", "C", "D")), f"missing choices for {q['id']}"


def test_mock_bank_correct_choice_matches_letter():
    bank = load_mock_bank()
    for q in bank:
        cc = q["correct_choice"]
        assert cc in ("A", "B", "C", "D"), f"invalid correct_choice {cc} for {q['id']}"


def test_answer_feedback_shows_correct():
    fb = answer_feedback(True, "test_value")
    assert "To‘g‘ri" in fb
    fb_wrong = answer_feedback(False, "test_value")
    assert "Noto‘g‘ri" in fb_wrong
    assert "test_value" in fb_wrong


def test_validate_answer_mapping_empty():
    issues = validate_answer_mapping({}, [], [])
    assert issues == []


def test_verify_answer_key_consistency():
    questions = [
        {"id": 1, "correct_answer": "tarjima_1", "options": ["tarjima_1", "x", "y", "z"]},
        {"id": 2, "correct_choice": "A", "choices": {"A": "val_a", "B": "val_b", "C": "val_c", "D": "val_d"}},
    ]
    assert verify_answer_key_consistency(questions)

    bad_q = [{"id": 3, "correct_answer": "not_in_options", "options": ["a", "b", "c", "d"]}]
    assert not verify_answer_key_consistency(bad_q)


def test_shuffled_options_still_match_correct_answer():
    engine = QuizEngine(None, SAMPLE_VOCAB)
    import random
    random.seed(42)
    result1 = engine.generate_questions(1, "eng_uzb", count=10, difficulty="easy", category="Algebra")
    random.seed(42)
    result2 = engine.generate_questions(1, "eng_uzb", count=10, difficulty="easy", category="Algebra")

    for q1, q2 in zip(result1["questions"], result2["questions"]):
        assert q1["correct_answer"] == q2["correct_answer"]
        assert q1["correct_answer"] in q2["options"]
    for q in result1["questions"]:
        assert q["correct_answer"] in q["options"]


def test_mock_question_option_order_stable():
    bank = load_mock_bank()
    import random
    random.seed(42)
    from bot.mock_tests import select_mock_questions
    sel1 = select_mock_questions(bank, seed=42)
    sel2 = select_mock_questions(bank, seed=42)
    for q1, q2 in zip(sel1, sel2):
        assert q1["id"] == q2["id"]
        assert q1["correct_choice"] == q2["correct_choice"]
        for letter in ("A", "B", "C", "D"):
            assert q1["choices"][letter] == q2["choices"][letter], f"option order changed for {q1['id']}"


def test_quiz_engine_adaptive_select_valid():
    engine = QuizEngine(None, SAMPLE_VOCAB)
    result = engine.adaptive_select(1, "eng_uzb", count=10, difficulty="hard", category="Algebra")
    issues = validate_question_answer_consistency(result["questions"])
    assert not issues, f"adaptive_select issues: {issues}"
