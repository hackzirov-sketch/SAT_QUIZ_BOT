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

class QuizEngine:
    def __init__(self, db_pool, vocabulary: list):
        self.db = db_pool
        self.vocabulary = [dict(item) for item in vocabulary]
        self._pool_cache: dict[tuple[str, str, int], list[dict]] = {}

    def _pool(self, difficulty: str = '', category: str = '', minimum: int = QUIZ_QUESTION_COUNT) -> list[dict]:
        key = (difficulty or '', category or '', minimum)
        cached = self._pool_cache.get(key)
        if cached is not None:
            return cached

        pool = self.vocabulary
        if difficulty:
            pool = [e for e in pool if e.get('difficulty') == difficulty]
        if category and category != CATEGORY_ALL:
            if category == CATEGORY_OTHER:
                pool = [e for e in pool if e.get('category') in SMALL_CATEGORIES]
            else:
                pool = [e for e in pool if e.get('category') == category]

        if len(pool) < minimum:
            return self.vocabulary
        self._pool_cache[key] = pool
        return pool

    def _distractor_score(self, entry: dict, cand: dict, target_field: str) -> int:
        score = 0
        if cand.get('category') == entry.get('category'):
            score += 100
        if cand.get('difficulty') == entry.get('difficulty'):
            score += 20
        if cand.get('source') == entry.get('source'):
            score += 10

        # Cheap lexical closeness keeps options plausible without O(n*m) Levenshtein DP per candidate.
        correct = str(entry[target_field]).lower()
        value = str(cand[target_field]).lower()
        score += max(0, 12 - abs(len(correct) - len(value)))
        if correct[:1] and correct[:1] == value[:1]:
            score += 4
        return score + random.randint(0, 5)

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
            candidates.append({'value': value, 'score': self._distractor_score(entry, cand, target_field)})
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
        pool = list(self._pool(difficulty, category, count))
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
