from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


import tempfile


def _q(overrides: dict | None = None) -> dict:
    base = {
        'id': 'test-001',
        'question_text': 'What is 2 + 2?',
        'correct_answer': 'B',
        'choices': {'A': '3', 'B': '4', 'C': '5', 'D': '6'},
        'question_type': 'multiple_choice',
        'topic': 'Linear Equations',
        'desmos_recommended': False,
    }
    if overrides:
        base.update(overrides)
    return base


class TestAIRouterFallback:
    @pytest.fixture
    def router(self):
        with (
            patch('ai.ai_router.GeminiClient') as mock_gc,
            patch('ai.ai_router.GroqClient') as mock_gr,
            tempfile.TemporaryDirectory() as tmp,
        ):
            from ai.ai_router import AIRouter
            r = AIRouter(gemini_key='test-gemini', groq_key='test-groq',
                         daily_limit=10.0)
            r.gemini = mock_gc.return_value
            r.groq = mock_gr.return_value
            r.cache = __import__('ai').cache.AICache(cache_dir=tmp)
            yield r

    def test_explain_uses_groq(self, router):
        q = _q({'id': 'explain-ok'})
        router.groq.explain_question.return_value = 'Groq explanation'
        result = router.explain(q)
        assert result == 'Groq explanation'
        router.groq.explain_question.assert_called_once()

    def test_explain_fallback_on_groq_failure(self, router):
        q = _q({'id': 'explain-fail'})
        router.groq.explain_question.side_effect = Exception('API down')
        result = router.explain(q)
        assert 'Yechim' in result or 'javob' in result

    def test_explain_fallback_on_empty_groq(self, router):
        q = _q({'id': 'explain-empty'})
        router.groq.explain_question.return_value = ''
        result = router.explain(q)
        assert 'Yechim' in result or 'javob' in result

    def test_explain_empty_on_missing(self, router):
        router.groq.explain_question.return_value = ''
        with patch('ai.ai_router.ExplanationGenerator') as mock_gen:
            mock_gen.return_value.generate_all.side_effect = Exception('no gen')
            result = router.explain({'id': 'x-missing', 'question_text': 'test', 'correct_answer': 'A'})
            assert 'Yechim mavjud emas' in result

    def test_analyze_mistake_uses_groq(self, router):
        q = _q({'id': 'mist-ok'})
        router.groq.analyze_mistake.return_value = 'Xato tahlili'
        result = router.analyze_mistake(q, 'A')
        assert result == 'Xato tahlili'

    def test_analyze_mistake_fallback(self, router):
        q = _q({'id': 'mist-fail'})
        router.groq.analyze_mistake.side_effect = Exception('fail')
        result = router.analyze_mistake(q, 'A')
        assert 'Xato' in result or 'javob' in result or 'To\'g\'ri' in result

    def test_short_feedback_uses_groq(self, router):
        q = _q({'id': 'fb-ok'})
        router.groq.short_feedback.return_value = 'Barakalla!'
        result = router.short_feedback(q, True)
        assert result == 'Barakalla!'

    def test_short_feedback_fallback(self, router):
        q = _q({'id': 'fb-fail'})
        router.groq.short_feedback.side_effect = Exception('fail')
        result = router.short_feedback(q, True)
        assert 'Barakalla' in result

    def test_desmos_solution_uses_groq(self, router):
        q = _q({'id': 'desmos-ok'})
        router.groq.desmos_solution.return_value = 'Desmos yechimi'
        result = router.desmos_solution(q)
        assert result == 'Desmos yechimi'

    def test_desmos_solution_fallback_no_cache(self, router):
        q = _q({'id': 'desmos-fail', 'desmos_solution_uz': ''})
        router.groq.desmos_solution.side_effect = Exception('fail')
        result = router.desmos_solution(q)
        assert result == 'Desmos yechimi mavjud emas.'

    def test_classify_uses_gemini(self, router):
        router.gemini.classify_question.return_value = {'topic': 'Algebra'}
        result = router.classify_question('test question')
        assert result == {'topic': 'Algebra'}

    def test_classify_fallback(self, router):
        router.gemini.classify_question.side_effect = Exception('fail')
        result = router.classify_question('test question')
        assert result == {}

    def test_extract_pdf_uses_gemini(self, router):
        router.gemini.extract_questions_from_pdf.return_value = [{'number': 1}]
        result = router.extract_questions_from_pdf('/fake/path.pdf', (0, 1))
        assert result == [{'number': 1}]

    def test_extract_pdf_fallback(self, router):
        router.gemini.extract_questions_from_pdf.side_effect = Exception('fail')
        result = router.extract_questions_from_pdf('/fake/path.pdf', (0, 1))
        assert result == []

    def test_describe_image_uses_gemini(self, router):
        router.gemini.describe_image.return_value = 'A line graph'
        result = router.describe_image(b'fake_image_data')
        assert result == 'A line graph'

    def test_describe_image_fallback(self, router):
        router.gemini.describe_image.side_effect = Exception('fail')
        result = router.describe_image(b'fake_image_data')
        assert result == ''

    def test_cache_hits_prevent_groq_call(self, router):
        q = _q({'id': 'cache-test'})
        router.cache.set('cached_explain', 'explanation', q['id'])
        router.groq.explain_question.return_value = 'should not be called'
        result = router.explain(q)
        assert result == 'cached_explain'
        router.groq.explain_question.assert_not_called()

    def test_summary(self, router):
        s = router.summary()
        assert 'budget' in s
        assert 'cache' in s
