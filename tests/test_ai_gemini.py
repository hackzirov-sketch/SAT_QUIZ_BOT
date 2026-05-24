from __future__ import annotations

import os

import pytest


class TestGeminiClientInit:
    def test_init_with_key(self):
        from ai.providers.gemini_client import GeminiClient
        c = GeminiClient(api_key='test-key')
        assert c.api_key == 'test-key'

    def test_init_raises_without_key(self):
        from ai.providers.gemini_client import GeminiClient
        key = os.environ.pop('GEMINI_API_KEY', None)
        try:
            with pytest.raises(ValueError, match='GEMINI_API_KEY'):
                GeminiClient()
        finally:
            if key:
                os.environ['GEMINI_API_KEY'] = key

    def test_init_from_env(self, monkeypatch):
        monkeypatch.setenv('GEMINI_API_KEY', 'env-key')
        from ai.providers.gemini_client import GeminiClient
        c = GeminiClient()
        assert c.api_key == 'env-key'

    def test_missing_import_raises_runtime_error(self, monkeypatch):
        from ai.providers.gemini_client import GeminiClient
        c = GeminiClient(api_key='test')
        import builtins

        real_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name == 'google.generativeai':
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, '__import__', blocked_import)
        with monkeypatch.context():
            with pytest.raises(RuntimeError, match='google-generativeai'):
                c._lazy_init()

    def test_parse_json_list_empty(self):
        from ai.providers.gemini_client import GeminiClient
        c = GeminiClient(api_key='test')
        assert c._parse_json_list('', 1) == []
        assert c._parse_json_list('no json here', 1) == []

    def test_parse_json_list_valid(self):
        from ai.providers.gemini_client import GeminiClient
        c = GeminiClient(api_key='test')
        result = c._parse_json_list('[{"number": 1, "question_text": "test"}]', 1)
        assert len(result) == 1
        assert result[0]['number'] == 1

    def test_parse_json_dict_empty(self):
        from ai.providers.gemini_client import GeminiClient
        c = GeminiClient(api_key='test')
        assert c._parse_json_dict('') == {}
        assert c._parse_json_dict('not json') == {}

    def test_parse_json_dict_valid(self):
        from ai.providers.gemini_client import GeminiClient
        c = GeminiClient(api_key='test')
        result = c._parse_json_dict('{"topic": "Algebra", "difficulty": "easy"}')
        assert result['topic'] == 'Algebra'
        assert result['difficulty'] == 'easy'
