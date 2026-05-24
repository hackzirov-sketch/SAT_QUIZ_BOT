from __future__ import annotations

import os

import pytest


SAMPLE_QUESTION = {
    'id': 'test-001',
    'question_text': 'What is 2 + 2?',
    'correct_answer': 'B',
    'choices': {'A': '3', 'B': '4', 'C': '5', 'D': '6'},
}


class TestGroqClientInit:
    def test_init_with_key(self):
        from ai.providers.groq_client import GroqClient
        c = GroqClient(api_key='test-key')
        assert c.api_key == 'test-key'

    def test_init_raises_without_key(self):
        from ai.providers.groq_client import GroqClient
        key = os.environ.pop('GROQ_API_KEY', None)
        try:
            with pytest.raises(ValueError, match='GROQ_API_KEY'):
                GroqClient()
        finally:
            if key:
                os.environ['GROQ_API_KEY'] = key

    def test_init_from_env(self, monkeypatch):
        monkeypatch.setenv('GROQ_API_KEY', 'env-key')
        from ai.providers.groq_client import GroqClient
        c = GroqClient()
        assert c.api_key == 'env-key'

    def test_missing_import_raises_runtime_error(self, monkeypatch):
        from ai.providers.groq_client import GroqClient
        c = GroqClient(api_key='test')
        import builtins

        real_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name == 'groq':
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, '__import__', blocked_import)
        with monkeypatch.context():
            with pytest.raises(RuntimeError, match='groq'):
                c._lazy_init()

    def test_mentor_system_prompt_exists(self):
        from ai.providers.groq_client import MENTOR_SYSTEM_PROMPT
        assert 'SAT Math mentorisan' in MENTOR_SYSTEM_PROMPT
        assert 'o\'zbekcha' in MENTOR_SYSTEM_PROMPT

    def test_mistake_system_prompt_exists(self):
        from ai.providers.groq_client import MISTAKE_SYSTEM_PROMPT
        assert 'xatosini tahlil qil' in MISTAKE_SYSTEM_PROMPT
        assert 'o\'zbekcha' in MISTAKE_SYSTEM_PROMPT
