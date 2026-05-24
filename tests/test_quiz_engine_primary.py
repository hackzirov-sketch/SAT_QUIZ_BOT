from bot.quiz_engine import PRIMARY_SOURCE, QuizEngine


def test_generate_questions_prefers_user_sat_core_words():
    primary = [
        {
            'id': i,
            'english': f'primary-{i}',
            'uzbek': f'asosiy-{i}',
            'category': 'Algebra',
            'source': PRIMARY_SOURCE,
            'difficulty': 'easy',
        }
        for i in range(1, 6)
    ]
    rest = [
        {
            'id': i,
            'english': f'other-{i}',
            'uzbek': f'boshqa-{i}',
            'category': 'Algebra',
            'source': 'Other',
            'difficulty': 'easy',
        }
        for i in range(6, 16)
    ]
    engine = QuizEngine(None, primary + rest)

    result = engine.generate_questions(1, 'eng_uzb', count=5, difficulty='easy', category='Algebra')

    assert {item['source'] for item in result['selected']} == {PRIMARY_SOURCE}
