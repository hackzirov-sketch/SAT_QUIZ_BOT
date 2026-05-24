from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

from ai.ai_router import AIRouter
from bot.config import AI_DAILY_LIMIT_USD, AI_MENTOR_ENABLED, AI_USER_COOLDOWN_SECONDS

logger = logging.getLogger(__name__)

_router: AIRouter | None = None
_router_error: str = ''
_last_user_call: dict[int, float] = {}


def ai_available() -> bool:
    return AI_MENTOR_ENABLED and bool(os.getenv('GROQ_API_KEY', '').strip())


def _get_router() -> AIRouter | None:
    global _router, _router_error
    if not ai_available():
        return None
    if _router is None:
        try:
            _router = AIRouter(
                gemini_key=os.getenv('GEMINI_API_KEY', '').strip() or None,
                groq_key=os.getenv('GROQ_API_KEY', '').strip() or None,
                daily_limit=AI_DAILY_LIMIT_USD,
            )
            _router_error = ''
        except Exception as exc:
            _router_error = type(exc).__name__
            logger.warning("ai_router_init_failed error_type=%s", _router_error)
            return None
    return _router


def cooldown_remaining(user_id: int) -> int:
    if AI_USER_COOLDOWN_SECONDS <= 0:
        return 0
    elapsed = time.monotonic() - _last_user_call.get(user_id, 0)
    return max(0, int(AI_USER_COOLDOWN_SECONDS - elapsed))


def mark_ai_call(user_id: int) -> None:
    _last_user_call[user_id] = time.monotonic()


def _choices_from_question(question: dict[str, Any]) -> dict[str, str] | None:
    if isinstance(question.get('choices'), dict):
        return {str(k): str(v) for k, v in question['choices'].items()}
    options = question.get('options')
    if isinstance(options, list):
        letters = ['A', 'B', 'C', 'D', 'E']
        return {letters[i]: str(value) for i, value in enumerate(options[:len(letters)])}
    return None


def normalize_question(question: dict[str, Any]) -> dict[str, Any]:
    text = (
        question.get('question_text')
        or question.get('text')
        or question.get('english')
        or question.get('prompt')
        or ''
    )
    correct = question.get('correct_answer') or question.get('answer') or question.get('uzbek') or ''
    return {
        'id': str(question.get('id') or question.get('question_id') or hash(json.dumps(question, sort_keys=True, default=str))),
        'question_text': str(text)[:1200],
        'correct_answer': str(correct)[:500],
        'choices': _choices_from_question(question),
        'topic': question.get('topic') or question.get('category') or '',
        'subtopic': question.get('subtopic') or '',
        'difficulty': question.get('difficulty') or '',
        'desmos_recommended': bool(question.get('desmos_recommended') or question.get('desmos_needed')),
        'desmos_solution_uz': question.get('desmos_solution_uz') or '',
        'manual_solution_uz': question.get('manual_solution_uz') or question.get('explanation_uz') or question.get('explanation') or '',
    }


async def explain_question(user_id: int, question: dict[str, Any]) -> str:
    router = _get_router()
    if router is None:
        return "AI Mentor hozircha yoqilmagan. Render'da AI_MENTOR_ENABLED=1 va GROQ_API_KEY qo'shing."
    mark_ai_call(user_id)
    normalized = normalize_question(question)
    return await asyncio.to_thread(router.explain, normalized)


async def analyze_mistake(user_id: int, question: dict[str, Any], user_answer: str) -> str:
    router = _get_router()
    if router is None:
        return "AI Mentor hozircha yoqilmagan. Render'da AI_MENTOR_ENABLED=1 va GROQ_API_KEY qo'shing."
    mark_ai_call(user_id)
    normalized = normalize_question(question)
    return await asyncio.to_thread(router.analyze_mistake, normalized, user_answer)


async def desmos_solution(user_id: int, question: dict[str, Any]) -> str:
    router = _get_router()
    if router is None:
        return "AI Mentor hozircha yoqilmagan. Render'da AI_MENTOR_ENABLED=1 va GROQ_API_KEY qo'shing."
    mark_ai_call(user_id)
    normalized = normalize_question(question)
    return await asyncio.to_thread(router.desmos_solution, normalized)


def ai_summary() -> dict[str, Any]:
    router = _get_router()
    if router is None:
        return {'enabled': AI_MENTOR_ENABLED, 'available': False, 'last_error': _router_error}
    summary = router.summary()
    summary.update({'enabled': AI_MENTOR_ENABLED, 'available': True})
    return summary
