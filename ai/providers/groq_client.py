from __future__ import annotations

import json
import logging
import os
import asyncio
from typing import Any

logger = logging.getLogger('ai.groq')

MENTOR_SYSTEM_PROMPT = (
    'Sen SAT Math mentorisan. Faqat berilgan savol bo\'yicha qisqa, aniq, '
    'o\'zbekcha tushuntir. Keraksiz gap yozma. '
    'Agar desmos kerak bo\'lsa, Desmosda yechishni ko\'rsat. '
    'Javobni <b>✅ Javob:</b> bilan tugat. 200 so\'zdan oshma.'
)

MISTAKE_SYSTEM_PROMPT = (
    'Sen SAT Math mentorisan. Talaba xatosini tahlil qil. '
    'Nima xato, qanday qilib to\'g\'rilash mumkin? '
    'Faqat o\'zbekcha, qisqa va aniq. 100 so\'zdan oshma.'
)


class GroqClient:
    MODEL = 'llama-3.3-70b-versatile'
    MAX_RETRIES = 3
    BASE_DELAY = 1.0
    TIMEOUT = 30

    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv('GROQ_API_KEY', '')
        if not key:
            raise ValueError('GROQ_API_KEY not set. Add to .env or pass api_key.')
        self.api_key = key
        self._client = None

    def _lazy_init(self):
        if self._client is not None:
            return
        try:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        except ImportError:
            raise RuntimeError('groq not installed. Run: pip install groq')

    def explain_question(self, question_text: str, correct_answer: str,
                         choices: dict[str, str] | None = None,
                         desmos_needed: bool = False) -> str:
        self._lazy_init()
        desmos_hint = '\nDesmos yechimini ham ko\'rsat.' if desmos_needed else ''
        prompt = (
            f'Savol: {question_text[:1000]}\n'
            f'To\'g\'ri javob: {correct_answer}\n'
        )
        if choices:
            prompt += f'Variantlar: {json.dumps(choices, ensure_ascii=False)[:500]}\n'
        prompt += (
            f'O\'zbekcha tushuntir. 200 so\'zdan oshma.{desmos_hint}'
        )
        return self._chat_safe(MENTOR_SYSTEM_PROMPT, prompt, max_tokens=512)

    def analyze_mistake(self, question_text: str, user_answer: str,
                        correct_answer: str, choices: dict[str, str] | None = None) -> str:
        self._lazy_init()
        prompt = (
            f'Savol: {question_text[:500]}\n'
            f'Sizning javobingiz: {user_answer}\n'
            f'To\'g\'ri javob: {correct_answer}\n'
        )
        if choices:
            prompt += f'Variantlar: {json.dumps(choices, ensure_ascii=False)[:300]}\n'
        prompt += 'Nima xato? Qanday qilib to\'g\'rilash mumkin?'
        return self._chat_safe(MISTAKE_SYSTEM_PROMPT, prompt, max_tokens=384)

    def short_feedback(self, question_text: str, is_correct: bool,
                       correct_answer: str) -> str:
        self._lazy_init()
        if is_correct:
            prompt = (
                f'Savol: {question_text[:300]}\n'
                f'To\'g\'ri javob: {correct_answer}\n'
                'Talaba to\'g\'ri javob berdi. Qisqa tabrik va mustahkamlash. '
                '2-3 ta gap o\'zbekcha.'
            )
        else:
            prompt = (
                f'Savol: {question_text[:300]}\n'
                f'To\'g\'ri javob: {correct_answer}\n'
                'Talaba xato qildi. Qisqa, o\'zbekcha 2-3 gapda '
                'motivatsiya bering va keyingi safar e\'tiborli bo\'lishni eslating.'
            )
        return self._chat_safe(MENTOR_SYSTEM_PROMPT, prompt, max_tokens=192)

    def desmos_solution(self, question_text: str, correct_answer: str) -> str:
        self._lazy_init()
        prompt = (
            f'Savol: {question_text[:800]}\n'
            f'To\'g\'ri javob: {correct_answer}\n\n'
            'Bu savolni Desmos grafik kalkulyatorida qanday yechish mumkin? '
            'Qisqa qadamlarni o\'zbekcha yoz. 150 so\'zdan oshma.'
        )
        return self._chat_safe(MENTOR_SYSTEM_PROMPT, prompt, max_tokens=384)

    def _chat_safe(self, system_prompt: str, user_prompt: str,
                   max_tokens: int = 512) -> str:
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = self._client.chat.completions.create(
                    model=self.MODEL,
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3,
                    timeout=self.TIMEOUT,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                logger.warning('Groq call attempt %d failed: %s', attempt + 1, e)
        return ''

    async def _chat_safe_async(self, system_prompt: str, user_prompt: str,
                               max_tokens: int = 512) -> str:
        for attempt in range(self.MAX_RETRIES):
            try:
                return await asyncio.to_thread(self._chat_safe, system_prompt, user_prompt, max_tokens)
            except Exception as e:
                logger.warning('Groq async call attempt %d failed: %s', attempt + 1, e)
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.BASE_DELAY * (2 ** attempt))
        return ''
