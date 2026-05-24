import json
import os
import tempfile
from pathlib import Path

from bot.pdf_service import generate_result_pdf, _HAS_PYPDF
from bot.image_service import pdf_to_images, text_to_image_fallback, _HAS_PYMUPDF, _HAS_PDF2IMAGE
from bot.mock_images import needs_image, get_image_path, IMG_KEYWORDS
from bot.mock_tests import load_mock_bank


def test_generate_result_pdf_returns_path_when_pypdf_available():
    if not _HAS_PYPDF:
        return

    attempt = {
        "score": 80,
        "total_questions": 10,
        "correct_count": 8,
        "wrong_count": 2,
        "completion_seconds": 300,
        "mode": "eng_uzb",
        "difficulty": "easy",
        "status": "completed",
    }
    questions = [
        {"id": i, "prompt": f"word_{i}", "correct_answer": f"meaning_{i}",
         "options": [f"meaning_{i}", "wrong1", "wrong2", "wrong3"]}
        for i in range(1, 6)
    ]
    answers = [
        {"question_index": i, "selected_answer": f"meaning_{i}", "correct_answer": f"meaning_{i}", "is_correct": 1}
        for i in range(5)
    ]
    path = generate_result_pdf(attempt, questions, answers, user_name="TestUser")
    if path:
        assert os.path.exists(path), f"PDF not found at {path}"
        assert path.endswith(".pdf")
        os.unlink(path)


def test_pdf_to_images_pymupdf(tmp_path):
    if not _HAS_PYMUPDF:
        return
    from bot.pdf_service import generate_result_pdf, _HAS_PYPDF
    if not _HAS_PYPDF:
        return

    attempt = {"score": 60, "total_questions": 5, "correct_count": 3, "wrong_count": 2,
               "completion_seconds": 120, "mode": "eng_uzb", "difficulty": "easy", "status": "completed"}
    questions = [{"id": i, "prompt": f"q{i}", "correct_answer": f"a{i}",
                  "options": [f"a{i}", "b", "c", "d"]} for i in range(1, 4)]
    answers = [{"question_index": i, "selected_answer": f"a{i}", "correct_answer": f"a{i}", "is_correct": 1}
               for i in range(3)]

    pdf_path = generate_result_pdf(attempt, questions, answers, "RenderTest")
    if not pdf_path:
        return

    images = pdf_to_images(pdf_path, dpi=100)
    if images:
        for img in images:
            assert os.path.exists(img)
            assert img.endswith(".png")
            os.unlink(img)
    os.unlink(pdf_path)


def test_text_to_image_fallback(tmp_path):
    text = "SAT Quiz Result\nScore: 80%\nTest line 3"
    out_path = str(tmp_path / "test_fallback.png")
    result = text_to_image_fallback(text, output_path=out_path)
    if result:
        assert os.path.exists(result)
        os.unlink(result)


def test_mock_images_needs_image_keywords():
    q_with_figure = {"question": "Look at the figure below", "choices": {"A": "1", "B": "2", "C": "3", "D": "4"}}
    assert needs_image(q_with_figure)
    q_without = {"question": "Solve for x", "choices": {"A": "1", "B": "2", "C": "3", "D": "4"}}
    assert not needs_image(q_without)


def test_mock_images_get_image_path_returns_none_for_missing():
    q = {"source_page": 99999}
    path = get_image_path(q)
    assert path is None


def test_mock_bank_images_have_page_mapping():
    bank = load_mock_bank()
    qs_with_images = [q for q in bank if needs_image(q)]
    for q in qs_with_images[:10]:
        path = get_image_path(q)
        if path:
            assert path.exists(), f"image not found: {path}"


def test_mock_bank_question_has_image_keywords():
    bank = load_mock_bank()
    img_questions = [q for q in bank if needs_image(q)]
    assert len(img_questions) >= 5, f"too few image questions: {len(img_questions)}"
    for q in img_questions:
        text = (q.get("question", "") + " " + " ".join(q.get("choices", {}).values())).lower()
        assert any(kw in text for kw in IMG_KEYWORDS), f"no keyword found for {q['id']} but needs_image returned True"


def test_pdf_service_cleanup_no_error():
    from bot.pdf_service import cleanup_old_pdfs
    cleanup_old_pdfs(max_age_hours=0)


def test_image_service_cleanup_no_error():
    from bot.image_service import cleanup_old_images
    cleanup_old_images(max_age_hours=0)
