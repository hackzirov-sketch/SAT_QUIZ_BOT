from __future__ import annotations

import logging
from typing import Any

from ai.cache import AICache
from ai.providers.gemini_client import GeminiClient
from ai.providers.groq_client import GroqClient
from ai.token_budget import TokenBudget

logger = logging.getLogger('ai.router')

from satmath.explanation_generator import ExplanationGenerator
from satmath.mistake_analysis import MistakeAnalyzer


class AIRouter:
    def __init__(self, gemini_key: str | None = None, groq_key: str | None = None,
                 daily_limit: float = 0.50):
        self.gemini = GeminiClient(api_key=gemini_key) if gemini_key else None
        self.groq = GroqClient(api_key=groq_key) if groq_key else None
        self.budget = TokenBudget(daily_limit_usd=daily_limit)
        self.cache = AICache()

    def explain(self, question: dict) -> str:
        qid = question.get('id', '')
        cached = self.cache.get('explanation', qid)
        if cached:
            return cached

        if not self.budget.can_make_call('llama-3.3-70b-versatile', 'explain',
                                          len(question.get('question_text', ''))):
            logger.info('budget exceeded for explain, using local fallback')
            return self._local_explain(question)
        if self.groq is None:
            return self._local_explain(question)

        try:
            result = self.groq.explain_question(
                question_text=question.get('question_text', ''),
                correct_answer=question.get('correct_answer', ''),
                choices=question.get('choices'),
                desmos_needed=question.get('desmos_recommended', False),
            )
            if result:
                self.budget.track_call('groq', 'llama-3.3-70b-versatile', 'explain',
                                       tokens_in=200, tokens_out=len(result) // 4)
                self.cache.set(result, 'explanation', qid)
                return result
        except Exception as e:
            logger.warning('Groq explain failed: %s', e)

        return self._local_explain(question)

    def analyze_mistake(self, question: dict, user_answer: str) -> str:
        qid = question.get('id', '')
        cache_key = f'{qid}:{user_answer}'
        cached = self.cache.get('mistake_analysis', cache_key)
        if cached:
            return cached

        if not self.budget.can_make_call('llama-3.3-70b-versatile', 'mistake_analysis',
                                          len(question.get('question_text', ''))):
            return self._local_mistake(question, user_answer)
        if self.groq is None:
            return self._local_mistake(question, user_answer)

        try:
            result = self.groq.analyze_mistake(
                question_text=question.get('question_text', ''),
                user_answer=user_answer,
                correct_answer=question.get('correct_answer', ''),
                choices=question.get('choices'),
            )
            if result:
                self.budget.track_call('groq', 'llama-3.3-70b-versatile', 'mistake_analysis',
                                       tokens_in=150, tokens_out=len(result) // 4)
                self.cache.set(result, 'mistake_analysis', cache_key)
                return result
        except Exception as e:
            logger.warning('Groq mistake analysis failed: %s', e)

        return self._local_mistake(question, user_answer)

    def short_feedback(self, question: dict, is_correct: bool) -> str:
        if not self.budget.can_make_call('llama-3.3-70b-versatile', 'short_feedback',
                                          len(question.get('question_text', ''))):
            return self._local_feedback(question, is_correct)
        if self.groq is None:
            return self._local_feedback(question, is_correct)
        try:
            result = self.groq.short_feedback(
                question_text=question.get('question_text', ''),
                is_correct=is_correct,
                correct_answer=question.get('correct_answer', ''),
            )
            if result:
                self.budget.track_call('groq', 'llama-3.3-70b-versatile', 'short_feedback',
                                       tokens_in=100, tokens_out=len(result) // 4)
                return result
        except Exception as e:
            logger.warning('Groq feedback failed: %s', e)
        return self._local_feedback(question, is_correct)

    def desmos_solution(self, question: dict) -> str:
        qid = question.get('id', '')
        cached = self.cache.get('desmos_solution', qid)
        if cached:
            return cached

        existing = question.get('desmos_solution_uz', '')
        if existing:
            return existing

        if not self.budget.can_make_call('llama-3.3-70b-versatile', 'desmos_solution',
                                          len(question.get('question_text', ''))):
            return existing or 'Desmos yechimi mavjud emas.'
        if self.groq is None:
            return existing or 'Desmos yechimi mavjud emas.'

        try:
            result = self.groq.desmos_solution(
                question_text=question.get('question_text', ''),
                correct_answer=question.get('correct_answer', ''),
            )
            if result:
                self.budget.track_call('groq', 'llama-3.3-70b-versatile', 'desmos_solution',
                                       tokens_in=150, tokens_out=len(result) // 4)
                self.cache.set(result, 'desmos_solution', qid)
                return result
        except Exception as e:
            logger.warning('Groq desmos solution failed: %s', e)
        return existing or 'Desmos yechimi mavjud emas.'

    def extract_questions_from_pdf(self, pdf_path: str,
                                   page_range: tuple[int, int] | None = None) -> list[dict]:
        cache_key = f'{pdf_path}:{page_range}'
        cached = self.cache.get_json('extracted_questions', cache_key)
        if cached is not None:
            return cached

        if not self.budget.can_make_call('gemini-2.0-flash', 'extract_page'):
            logger.warning('budget exceeded for pdf extraction')
            return []
        if self.gemini is None:
            return []

        try:
            questions = self.gemini.extract_questions_from_pdf(pdf_path, page_range)
            if questions:
                pages = page_range[1] - page_range[0] if page_range else 0
                self.budget.track_call('gemini', 'gemini-2.0-flash', 'extract_page',
                                       tokens_in=pages * 300, tokens_out=len(questions) * 200)
                self.cache.set_json(questions, 'extracted_questions', cache_key)
            return questions
        except Exception as e:
            logger.error('Gemini PDF extraction failed: %s', e)
            return []

    def classify_question(self, question_text: str) -> dict:
        h = str(hash(question_text[:200]))
        cached = self.cache.get_json('classify', h)
        if cached is not None:
            return cached

        if not self.budget.can_make_call('gemini-2.0-flash', 'classify', len(question_text)):
            return {}
        if self.gemini is None:
            return {}

        try:
            result = self.gemini.classify_question(question_text)
            if result:
                self.budget.track_call('gemini', 'gemini-2.0-flash', 'classify',
                                       tokens_in=100, tokens_out=50)
                self.cache.set_json(result, 'classify', h)
            return result
        except Exception as e:
            logger.warning('Gemini classify failed: %s', e)
            return {}

    def describe_image(self, image_data: bytes) -> str:
        h = str(hash(image_data))
        cached = self.cache.get('image_description', h)
        if cached:
            return cached

        if not self.budget.can_make_call('gemini-2.0-flash', 'describe_image'):
            return ''
        if self.gemini is None:
            return ''

        try:
            result = self.gemini.describe_image(image_data)
            if result:
                self.budget.track_call('gemini', 'gemini-2.0-flash', 'describe_image',
                                       tokens_in=50, tokens_out=len(result) // 4)
                self.cache.set(result, 'image_description', h)
            return result
        except Exception as e:
            logger.warning('Gemini image describe failed: %s', e)
            return ''

    def _local_explain(self, question: dict) -> str:
        try:
            gen = ExplanationGenerator([question])
            gen.generate_all()
            return question.get('manual_solution_uz', 'Yechim mavjud emas.')
        except Exception as e:
            logger.warning('local explain fallback failed: %s', e)
            return 'Yechim mavjud emas.'

    def _local_mistake(self, question: dict, user_answer: str) -> str:
        correct = question.get('correct_answer', '')
        return (
            f'❌ Sizning javobingiz: {user_answer}\n'
            f'✅ To\'g\'ri javob: {correct}\n\n'
            'Har bir xatoni tahlil qiling va shoshilmasdan yechimni qayta ko\'rib chiqing.'
        )

    def _local_feedback(self, question: dict, is_correct: bool) -> str:
        if is_correct:
            return '✅ To\'g\'ri! Barakalla.'
        return '❌ Xato. Keyingi safar diqqatliroq bo\'ling!'

    def summary(self) -> dict[str, Any]:
        return {
            'budget': self.budget.summary(),
            'cache': self.cache.stats(),
        }
