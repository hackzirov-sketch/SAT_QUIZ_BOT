import json
import hashlib
import random
from datetime import datetime, timezone

from bot.config import (
    QUIZ_QUESTION_COUNT, QUIZ_DURATION, POINTS_PER_CORRECT, CATEGORY_ALL, CATEGORY_OTHER,
    SMALL_CATEGORIES, XP_BASE, XP_STREAK_BONUS, XP_TIME_BONUS_MAX, XP_WIN_BONUS,
    LEVEL_THRESHOLDS, LEVEL_NAMES,
)

def level_name(lv: int) -> str:
    return LEVEL_NAMES[lv] if 0 <= lv < len(LEVEL_NAMES) else LEVEL_NAMES[1]

def calc_level(xp: int) -> int:
    for i in range(len(LEVEL_THRESHOLDS) - 1, -1, -1):
        if xp >= LEVEL_THRESHOLDS[i]:
            return i
    return 1

def shuffle(arr: list) -> list:
    a = list(arr)
    random.shuffle(a)
    return a

def levenshtein(a: str, b: str) -> int:
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1): dp[i][0] = i
    for j in range(n + 1): dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            dp[i][j] = dp[i - 1][j - 1] if a[i - 1] == b[j - 1] else min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]) + 1
    return dp[m][n]

class QuizEngine:
    def __init__(self, db_pool, vocabulary: list):
        self.db = db_pool
        self.vocabulary = vocabulary

    def _build_distractors(self, entry: dict, target_field: str, protected: set, used: set) -> list:
        correct_value = str(entry[target_field])
        correct_key = correct_value.lower()
        candidates = []
        for cand in self.vocabulary:
            if cand['id'] == entry['id']:
                continue
            value = str(cand[target_field])
            key = value.lower()
            if key == correct_key or key in used or key in protected:
                continue
            score = 0
            if cand.get('category') == entry.get('category'):
                score += 80
            if cand.get('source') == entry.get('source'):
                score += 15
            eng_dist = levenshtein(entry['english'].lower(), cand['english'].lower())
            uzb_dist = levenshtein(entry['uzbek'].lower(), cand['uzbek'].lower())
            score += max(0, 50 - eng_dist * 5)
            score += max(0, 50 - uzb_dist * 5)
            if cand.get('difficulty'):
                score += 10 if cand['difficulty'] == 'hard' else 5
            candidates.append({'value': value, 'score': score})
        candidates.sort(key=lambda c: -c['score'])
        return [c['value'] for c in candidates[:3]]

    def _build_questions(self, selected: list, mode: str) -> list:
        target_field = 'uzbek' if mode == 'eng_uzb' else 'english'
        prompt_field = 'english' if mode == 'eng_uzb' else 'uzbek'
        protected = {str(e[target_field]).lower() for e in selected}
        used = set()
        questions = []
        for entry in selected:
            correct = str(entry[target_field])
            dist = self._build_distractors(entry, target_field, protected, used)
            options = shuffle([correct] + dist[:3])
            for o in options:
                used.add(o.lower())
            questions.append({
                'id': entry['id'],
                'english': entry['english'],
                'uzbek': entry['uzbek'],
                'category': entry.get('category', ''),
                'difficulty': entry.get('difficulty', 'easy'),
                'prompt': entry[prompt_field],
                'correct_answer': correct,
                'options': options,
            })
        return questions

    def generate_questions(self, user_id: int, mode: str, count: int = QUIZ_QUESTION_COUNT,
                           difficulty: str = '', category: str = '', for_daily: bool = False) -> dict:
        pool = list(self.vocabulary)
        if difficulty:
            pool = [e for e in pool if e.get('difficulty') == difficulty]
        if category and category != CATEGORY_ALL:
            if category == CATEGORY_OTHER:
                pool = [e for e in pool if e.get('category') in SMALL_CATEGORIES]
            else:
                pool = [e for e in pool if e.get('category') == category]
        if len(pool) < count:
            pool = list(self.vocabulary)
        if len(pool) < count:
            raise ValueError(f"Vocabulary has only {len(pool)} entries, but {count} are required")

        if for_daily:
            today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            seed = sum(ord(c) for c in today)
            seeded = sorted(pool, key=lambda e: (e['id'] * 31 + seed) % 10007)
            selected = seeded[:count]
            ids = ','.join(str(e['id']) for e in selected)
            order_hash = hashlib.sha256(f"daily:{today}:{ids}".encode()).hexdigest()
            return {'questions': self._build_questions(selected, mode), 'order_hash': order_hash, 'selected': selected}

        selected = shuffle(pool)[:count]
        ids = ','.join(str(e['id']) for e in selected)
        order_hash = hashlib.sha256(f"{mode}:{ids}".encode()).hexdigest()
        return {'questions': self._build_questions(selected, mode), 'order_hash': order_hash, 'selected': selected}

    def adaptive_select(self, user_id: int, mode: str, count: int, difficulty: str, category: str) -> dict:
        pool = list(self.vocabulary)
        easy_pool = [e for e in pool if e.get('difficulty') != 'hard']
        hard_pool = [e for e in pool if e.get('difficulty') == 'hard']
        if category and category != CATEGORY_ALL:
            filt = (lambda e: e.get('category') in SMALL_CATEGORIES) if category == CATEGORY_OTHER else (lambda e: e.get('category') == category)
            easy_pool = [e for e in easy_pool if filt(e)]
            hard_pool = [e for e in hard_pool if filt(e)]
        if len(easy_pool) < 5: easy_pool = pool
        if len(hard_pool) < 5: hard_pool = pool
        # Default ratio
        hard_count = max(1, count // 5)
        easy_count = count - hard_count
        selected = shuffle(easy_pool)[:easy_count] + shuffle(hard_pool)[:hard_count]
        selected = shuffle(selected)[:count]
        ids = ','.join(str(e['id']) for e in selected)
        order_hash = hashlib.sha256(f"adaptive:{user_id}:{ids}".encode()).hexdigest()
        return {'questions': self._build_questions(selected, mode), 'order_hash': order_hash}

    def calc_xp(self, score: int, correct: int, total: int, seconds: int) -> int:
        accuracy = correct / total if total > 0 else 0
        xp = XP_BASE + round(accuracy * XP_STREAK_BONUS * 3)
        if seconds > 0 and seconds < QUIZ_DURATION * 0.5:
            xp += XP_TIME_BONUS_MAX
        if score >= 80:
            xp += XP_WIN_BONUS
        return xp
