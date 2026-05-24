import json
from collections import Counter

BANK_PATH = r'C:\Users\hackz\Desktop\SATQUIZ bot\bot\data\mock_tests\math_mock_bank.json'

with open(BANK_PATH, 'r', encoding='utf-8') as f:
    questions = json.loads(f.read())

topics = Counter(q['topic'] for q in questions)
for t, c in topics.most_common():
    print(f'{t}: {c} questions')
print(f'\nTotal: {len(questions)} questions, {len(topics)} topics')
