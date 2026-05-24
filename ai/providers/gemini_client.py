from __future__ import annotations

import base64
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger('ai.gemini')


class GeminiClient:
    MODEL = 'gemini-2.0-flash'
    MAX_RETRIES = 3
    BASE_DELAY = 2.0
    TIMEOUT = 60

    def __init__(self, api_key: str | None = None):
        key = api_key or os.getenv('GEMINI_API_KEY', '')
        if not key:
            raise ValueError('GEMINI_API_KEY not set. Add to .env or pass api_key.')
        self.api_key = key
        self._client = None

    def _lazy_init(self):
        if self._client is not None:
            return
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._client = genai
        except ImportError:
            raise RuntimeError(
                'google-generativeai not installed. Run: pip install google-generativeai'
            )

    def extract_questions_from_pdf_page(self, page_text: str, page_num: int) -> list[dict]:
        self._lazy_init()
        prompt = (
            'Extract SAT Math questions from this page text. '
            'Return ONLY valid JSON array. Each object: {"number": int, "question_text": str, '
            '"choices": {"A":"...","B":"...","C":"...","D":"..."} or {}, '
            '"question_type": "multiple_choice" or "grid_in"}. '
            'If no questions, return []. No markdown, no extra text.\n\n'
            f'--- PAGE {page_num} ---\n{page_text[:4000]}'
        )
        result = self._call_safe(prompt, max_tokens=2048)
        return self._parse_json_list(result, page_num)

    def extract_questions_from_pdf(self, pdf_path: str | Path,
                                   page_range: tuple[int, int] | None = None) -> list[dict]:
        self._lazy_init()
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.error('PDF not found: %s', pdf_path)
            return []

        try:
            import fitz
        except ImportError:
            logger.error('PyMuPDF required for PDF parsing')
            return []

        doc = fitz.open(str(pdf_path))
        total = len(doc)
        start, end = page_range or (0, total)
        start = max(0, start)
        end = min(total, end)

        all_questions = []
        for i in range(start, end):
            page = doc[i]
            page_text = page.get_text().strip()
            if not page_text:
                continue
            questions = self.extract_questions_from_pdf_page(page_text, i + 1)
            for q in questions:
                q['source_page'] = i + 1
                q['source_pdf'] = pdf_path.name
            all_questions.extend(questions)
        doc.close()
        return all_questions

    def describe_image(self, image_data: bytes, detail: str = 'diagram') -> str:
        self._lazy_init()
        model = self._client.GenerativeModel(self.MODEL)

        prompt = (
            f'Describe this {detail} for an SAT Math problem. '
            'Include all numbers, labels, relationships. '
            'Be concise. Use English. Max 100 words.'
        )

        for attempt in range(self.MAX_RETRIES):
            try:
                resp = model.generate_content(
                    [prompt, {'mime_type': 'image/png', 'data': base64.b64encode(image_data).decode()}],
                    generation_config=self._gc(max_tokens=256),
                    request_options={'timeout': self.TIMEOUT},
                )
                return resp.text.strip() if resp.text else ''
            except Exception as e:
                logger.warning('image describe attempt %d failed: %s', attempt + 1, e)
        return ''

    def classify_question(self, question_text: str, choices: dict | None = None) -> dict:
        self._lazy_init()
        prompt = (
            'Classify this SAT Math question. Return JSON: '
            '{"topic": str, "domain": "Algebra"|"Advanced Math"|"Problem Solving and Data Analysis"|"Geometry and Trigonometry", '
            '"difficulty": "easy"|"medium"|"hard", "skill": str}. '
            'No markdown.\n\n'
            f'Question: {question_text[:1500]}'
        )
        if choices:
            prompt += f'\nChoices: {json.dumps(choices, ensure_ascii=False)[:500]}'
        result = self._call_safe(prompt, max_tokens=256)
        return self._parse_json_dict(result)

    def _call_safe(self, prompt: str, max_tokens: int = 1024) -> str:
        model = self._client.GenerativeModel(self.MODEL)
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = model.generate_content(
                    prompt,
                    generation_config=self._gc(max_tokens=max_tokens),
                    request_options={'timeout': self.TIMEOUT},
                )
                return resp.text.strip() if resp.text else ''
            except Exception as e:
                logger.warning('Gemini call attempt %d failed: %s', attempt + 1, e)
        return ''

    async def _call_safe_async(self, prompt: str, max_tokens: int = 1024) -> str:
        for attempt in range(self.MAX_RETRIES):
            try:
                return await asyncio.to_thread(self._call_safe, prompt, max_tokens)
            except Exception as e:
                logger.warning('Gemini async call attempt %d failed: %s', attempt + 1, e)
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(self.BASE_DELAY * (2 ** attempt))
        return ''

    def _gc(self, max_tokens: int):
        try:
            from google.generativeai import types
            return types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.1,
                top_p=0.95,
            )
        except ImportError:
            return {'max_output_tokens': max_tokens, 'temperature': 0.1, 'top_p': 0.95}

    def _parse_json_list(self, text: str, page_num: int) -> list[dict]:
        text = text.strip()
        if not text:
            return []
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end > start:
            text = text[start:end + 1]
        try:
            data = json.loads(text)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            logger.warning('Gemini returned invalid JSON on page %d', page_num)
            return []

    def _parse_json_dict(self, text: str) -> dict:
        text = text.strip()
        if not text:
            return {}
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            text = text[start:end + 1]
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
