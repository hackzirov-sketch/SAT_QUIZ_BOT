from bot.config import LEVEL_NAMES, CATEGORY_ALL
from bot.quiz_engine import level_name

MODE_LABELS = {'eng_uzb': 'ENG → UZB', 'uzb_eng': 'UZB → ENG'}
DIFFICULTY_LABELS = {'easy': '🟢 Oson', 'hard': '🔴 Qiyin'}

def mode_label(m: str) -> str: return MODE_LABELS.get(m, m)
def difficulty_label(d: str) -> str: return DIFFICULTY_LABELS.get(d, d)

def format_seconds(secs: int) -> str:
    s = max(0, int(secs))
    return f"{s // 60:02d}:{s % 60:02d}"

def esc(val) -> str:
    return str(val).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def question_text(question: dict, index: int, total: int, remaining: int, mode: str, minimal: bool = False) -> str:
    prompt = esc(question['prompt'])
    remaining_s = format_seconds(remaining)
    if mode == 'eng_uzb':
        ask = f'"<b>{prompt[0].upper() + prompt[1:] if prompt else prompt}</b>" so‘zining ma’nosini toping:'
    else:
        ask = f'"<b>{prompt[0].upper() + prompt[1:] if prompt else prompt}</b>" so‘zining inglizcha ma’nosini toping:'
    if minimal:
        return f"⏳ {remaining_s}\n📘 {index + 1}/{total}\n\n{ask}"
    return f"⏳ <b>Qolgan vaqt:</b> {remaining_s}\n\n📘 <b>Savol {index + 1}/{total}</b>\n\n{ask}"

def answer_feedback(is_correct: bool, correct_answer: str) -> str:
    if is_correct:
        return '✅ To‘g‘ri!'
    return f'❌ Noto‘g‘ri!\n✅ To‘g‘ri javob: <b>{esc(correct_answer)}</b>'

def format_wrong_answers(questions: list, answers: list) -> str:
    wrong = [a for a in answers if not a['is_correct']]
    if not wrong:
        return "Barcha savollarga to'g'ri javob berdingiz! ✅"
    lines = ["❌ <b>Xatolar:</b>\n"]
    for a in wrong[:10]:
        q = questions[a['question_index']] if a['question_index'] < len(questions) else {}
        prompt = esc(q.get('prompt', ''))
        lines.append(f"{a['question_index'] + 1}. {prompt}")
        lines.append(f"   Siz: {esc(a['selected_answer'])}")
        lines.append(f"   To'g'ri: <b>{esc(a['correct_answer'])}</b>\n")
    if len(wrong) > 10:
        lines.append(f"... va yana {len(wrong) - 10} ta xato")
    return '\n'.join(lines)

def final_result_text(attempt: dict, achievements: list = None, xp: int = 0, level_up: str = None) -> str:
    if achievements is None: achievements = []
    score = attempt.get('score', 0)
    total = attempt.get('total_questions', 50)
    correct = attempt.get('correct_count', 0)
    wrong = attempt.get('wrong_count', 0)
    completion = attempt.get('completion_seconds', 0)
    title = '⏰ Vaqt tugadi!' if attempt.get('status') == 'timed_out' else '✅ Test yakunlandi!'
    diff = attempt.get('difficulty', '')
    diff_str = f" {difficulty_label(diff)}" if diff else ''
    cat = attempt.get('category', '')
    cat_str = f" | {cat}" if cat and cat != CATEGORY_ALL else ''

    lines = [
        title, '',
        f"📘 <b>Rejim:</b> {mode_label(attempt.get('mode', ''))}{diff_str}{cat_str}",
        f"🎯 <b>Ball:</b> {score}/100",
        f"✅ <b>To'g'ri:</b> {correct}/{total}",
        f"❌ <b>Noto'g'ri:</b> {wrong}/{total}",
        f"⏱ <b>Vaqt:</b> {format_seconds(completion)}",
    ]
    if xp:
        lines.append(f'\n⭐ <b>+{xp} XP</b>')
    if level_up:
        lines.append(f'🎉 <b>{level_up}</b> — yangi daraja!')
    if achievements:
        lines.append('', '🏅 <b>Yangi yutuqlar:</b>')
        for a in achievements:
            lines.append(f'• {esc(a["title"])}')
    lines.append('', '🏆 Reytingni ko\'rish uchun "🏆 Reyting" tugmasini bosing.')
    return '\n'.join(lines)

def weakness_text(weakness_data: list) -> str:
    if not weakness_data:
        return 'Hali test ishlamagansiz.'
    cat_stats = {}
    for a in weakness_data:
        cat = a['category']
        if cat not in cat_stats:
            cat_stats[cat] = {'correct': 0, 'wrong': 0}
        if a['is_correct']:
            cat_stats[cat]['correct'] += 1
        else:
            cat_stats[cat]['wrong'] += 1
    lines = ['📊 <b>Zaif va kuchli tomonlar tahlili</b>\n']
    strong, weak = [], []
    for cat, st in cat_stats.items():
        total = st['correct'] + st['wrong']
        if total < 3: continue
        pct = round(st['correct'] / total * 100)
        if pct >= 70: strong.append(f"{cat} ({pct}%)")
        elif pct < 50: weak.append(f"{cat} ({pct}%)")
    if strong: lines.append(f'✅ <b>Kuchli:</b> {", ".join(strong)}')
    if weak: lines.append(f'❌ <b>Zaif:</b> {", ".join(weak)}')
    if len(lines) == 1:
        lines.append('Tahlil uchun yetarli ma\'lumot yo\'q.')
    if weak:
        cats = ', '.join(w.split(' (')[0] for w in weak)
        lines.append('', f'🎯 <b>Tavsiya:</b> "{cats}" mavzusida mashq qiling.')
    return '\n'.join(lines)
