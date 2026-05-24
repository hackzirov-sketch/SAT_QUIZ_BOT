from __future__ import annotations


def test_normalize_question_supports_vocab_shape():
    from bot.services.ai_mentor_service import normalize_question

    q = normalize_question({
        'id': 12,
        'english': 'slope',
        'uzbek': 'qiyalik',
        'options': ['qiyalik', 'kesma'],
        'category': 'Algebra',
    })

    assert q['id'] == '12'
    assert q['question_text'] == 'slope'
    assert q['correct_answer'] == 'qiyalik'
    assert q['choices']['A'] == 'qiyalik'
    assert q['topic'] == 'Algebra'


def test_normalize_question_supports_mock_shape():
    from bot.services.ai_mentor_service import normalize_question

    q = normalize_question({
        'question_id': 'm1',
        'question_text': 'What is x?',
        'correct_answer': 'B',
        'choices': {'A': '1', 'B': '2'},
        'desmos_recommended': True,
    })

    assert q['id'] == 'm1'
    assert q['question_text'] == 'What is x?'
    assert q['choices']['B'] == '2'
    assert q['desmos_recommended'] is True


def test_ai_available_requires_enabled_and_groq_key(monkeypatch):
    import bot.services.ai_mentor_service as service

    monkeypatch.setattr(service, 'AI_MENTOR_ENABLED', True)
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    assert service.ai_available() is False

    monkeypatch.setenv('GROQ_API_KEY', 'test-key')
    assert service.ai_available() is True
