import json
import time
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from bot.database import get_db, now_iso
from bot.utils.db_helpers import upsert_user, add_xp, record_mistake, clear_mistake
from bot.quiz_engine import QuizEngine, level_name, calc_level
from bot.formatting import question_text, answer_feedback, final_result_text, format_wrong_answers, format_seconds
from bot.keyboards import answer_kb, active_quiz_kb, review_kb, main_menu_kb, start_kb, category_kb

router = Router()
engine: QuizEngine = None

def set_quiz_engine(e: QuizEngine):
    global engine
    engine = e

async def send_current_question(message_or_callback, attempt: dict, session: dict, questions: list = None):
    db = await get_db()
    if questions is None:
        cursor = await db.execute('SELECT question_order_json FROM attempts WHERE id = ?', (attempt['id'],))
        row = await cursor.fetchone()
        questions = json.loads(row['question_order_json']) if row else []
    cursor = await db.execute('SELECT * FROM settings WHERE user_id = ?', (attempt['user_id'],))
    s = await cursor.fetchone()
    index = attempt['current_index']
    if index >= len(questions):
        return
    q = questions[index]
    remaining = max(0, session['expires_at'] - int(time.time())) if session.get('expires_at') else 0
    minimal = bool(s and s.get('minimal_mode')) if s else False
    text = question_text(q, index, attempt['total_questions'], remaining, attempt['mode'], minimal)
    await message_or_callback.answer(text, reply_markup=answer_kb(attempt['id'], index, q['options']))

@router.callback_query(F.data.startswith('start:'))
async def start_callback(callback: CallbackQuery):
    parts = callback.data.split(':')
    mode = parts[1]
    difficulty = parts[2]
    if mode not in ('eng_uzb', 'uzb_eng') or difficulty not in ('easy', 'hard'):
        await callback.answer('Noto\'g\'ri parametr.')
        return
    if len(parts) == 3:
        await callback.message.edit_text('Kategoriyani tanlang:', reply_markup=category_kb(mode, difficulty))
        await callback.answer()
        return
    if len(parts) >= 4:
        category = parts[3]
        if category not in ('all', 'Algebra', 'Geometry', 'Statistics', 'other'):
            await callback.answer('Noto\'g\'ri kategoriya.')
            return
        db = await get_db()
        user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        cursor = await db.execute(
            'SELECT s.* FROM active_sessions s JOIN attempts a ON a.id = s.attempt_id WHERE s.user_id = ? AND s.status = ? AND a.status = ?',
            (user['id'], 'active', 'active'))
        if await cursor.fetchone():
            await callback.answer('Sizda faol test bor.')
            return
        qty = 50
        expires = 900
        res = engine.generate_questions(user['id'], mode, qty, difficulty, category)
        questions = res['questions']
        now = now_iso()
        await db.execute(
            'INSERT INTO attempts (user_id, mode, difficulty, category, total_questions, question_order_json, order_hash, started_at, status) VALUES (?,?,?,?,?,?,?,?,?)',
            (user['id'], mode, difficulty, category, qty, json.dumps([{k: q[k] for k in ('id','english','uzbek','category','difficulty','prompt','correct_answer','options')} for q in questions]), res['order_hash'], now, 'active'))
        await db.commit()
        cursor = await db.execute('SELECT last_insert_rowid() AS id')
        attempt_id = (await cursor.fetchone())['id']
        expires_at = int(time.time()) + expires
        await db.execute(
            'INSERT INTO active_sessions (attempt_id, user_id, chat_id, expires_at, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)',
            (attempt_id, user['id'], callback.message.chat.id, expires_at, 'active', now, now))
        await db.commit()
        attempt = {'id': attempt_id, 'user_id': user['id'], 'current_index': 0, 'total_questions': qty, 'mode': mode}
        session = {'attempt_id': attempt_id, 'expires_at': expires_at}
        await callback.answer('Test boshlandi!')
        await callback.message.edit_text('⏱ Timer boshlandi: 15:00')
        await send_current_question(callback.message, attempt, session, questions)

@router.callback_query(F.data.startswith('active:'))
async def active_quiz_callback(callback: CallbackQuery):
    parts = callback.data.split(':')
    action = parts[1]
    attempt_id = int(parts[2])
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    attempt = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
    if not attempt or attempt['user_id'] != user['id']:
        await callback.answer('Test topilmadi.')
        return
    if action == 'continue':
        session = await (await db.execute('SELECT * FROM active_sessions WHERE attempt_id = ? AND status = ?', (attempt_id, 'active'))).fetchone()
        if not session:
            await callback.answer('Sessiya topilmadi.')
            return
        if session['expires_at'] and int(time.time()) > session['expires_at']:
            await _finish_attempt(db, attempt_id, 'timed_out')
            await callback.answer('Vaqt tugadi.')
            ta = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
            if ta:
                await callback.message.edit_reply_markup(reply_markup=None)
                rt = final_result_text(dict(ta))
                await callback.message.answer(rt)
            return
        await callback.answer()
        await send_current_question(callback.message, attempt, session)
    elif action == 'restart':
        await db.execute('UPDATE attempts SET status = ? WHERE id = ?', ('cancelled', attempt_id))
        await db.execute('UPDATE active_sessions SET status = ? WHERE attempt_id = ?', ('cancelled', attempt_id))
        await db.commit()
        await callback.answer('Faol test bekor qilindi.')
        s = await (await db.execute('SELECT * FROM settings WHERE user_id = ?', (user['id'],))).fetchone()
        pref_mode = s['preferred_mode'] if s else 'eng_uzb'
        pref_diff = s['preferred_difficulty'] if s else 'easy'
        await callback.message.edit_text('📘 <b>Test sozlamalari</b>', reply_markup=start_kb(pref_mode, pref_diff))

@router.callback_query(F.data.startswith('ans:'))
async def answer_callback(callback: CallbackQuery):
    parts = callback.data.split(':')
    attempt_id = int(parts[1])
    question_index = int(parts[2])
    selected_letter = parts[3]

    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    attempt = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
    if not attempt or attempt['user_id'] != user['id']:
        await callback.answer('Bu test sizniki emas.')
        return
    if attempt['status'] != 'active':
        await callback.answer('Test allaqachon yakunlangan.')
        return
    if attempt['current_index'] != question_index:
        await callback.answer('Eski tugma.')
        return

        session = await (await db.execute('SELECT * FROM active_sessions WHERE attempt_id = ? AND status = ?', (attempt_id, 'active'))).fetchone()
        if not session:
            await callback.answer('Sessiya topilmadi.')
            return
        if session['expires_at'] and int(time.time()) > session['expires_at']:
            await _finish_attempt(db, attempt_id, 'timed_out')
            await callback.answer('Vaqt tugadi.')
            await callback.message.edit_reply_markup(reply_markup=None)
            ta = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
            if ta:
                rt = final_result_text(dict(ta))
                await callback.message.answer(rt)
            return

        questions = json.loads(attempt['question_order_json'])
        q = questions[question_index]
        letters = ['A', 'B', 'C', 'D']
        selected_answer = q['options'][letters.index(selected_letter)] if selected_letter in letters else ''
        is_correct = selected_answer == q['correct_answer']

        # Check duplicate
        existing = await (await db.execute('SELECT id FROM answers WHERE attempt_id = ? AND question_index = ?', (attempt_id, question_index))).fetchone()
        if existing:
            await callback.answer('Bu savolga javob berilgan.')
            return

        now = now_iso()
        await db.execute(
            'INSERT INTO answers (attempt_id, question_id, question_index, selected_answer, correct_answer, is_correct, answered_at) VALUES (?,?,?,?,?,?,?)',
            (attempt_id, q['id'], question_index, selected_answer, q['correct_answer'], 1 if is_correct else 0, now))
        points = 2 if is_correct else 0
        await db.execute(
            'UPDATE attempts SET score = score + ?, current_index = current_index + 1, correct_count = correct_count + ?, wrong_count = wrong_count + ? WHERE id = ? AND status = ? AND current_index = ?',
            (points, 1 if is_correct else 0, 0 if is_correct else 1, attempt_id, 'active', question_index))
        await db.commit()

        # Record mistake
        if not is_correct:
            await record_mistake(db, user['id'], q['id'], q['english'], q['uzbek'], q.get('category', ''))
        elif attempt['quiz_mode'] == 'mistakes':
            await clear_mistake(db, user['id'], q['id'])

        # Update attempt
        attempt = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
        finished = attempt['current_index'] >= attempt['total_questions']

        await callback.message.edit_reply_markup(reply_markup=None)
        fb = answer_feedback(is_correct, q['correct_answer'])
        await callback.message.answer(fb)
        await callback.answer('✅' if is_correct else '❌')

        if finished:
            await _finish_attempt(db, attempt_id, 'completed')
            attempt_after = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
            xp_data = await add_xp(db, user['id'], engine.calc_xp(attempt_after['score'], attempt_after['correct_count'], attempt_after['total_questions'], attempt_after['completion_seconds'] or 0))
            result_text = final_result_text(dict(attempt_after), xp=xp_data['xp'], level_up=xp_data['level_name'] if xp_data['leveled_up'] else None)
            await callback.message.answer(result_text, reply_markup=main_menu_kb())

            # Daily challenge submit
            if attempt['quiz_mode'] == 'daily':
                today = now_iso()[:10]
                challenge = await (await db.execute('SELECT * FROM daily_challenge WHERE date = ?', (today,))).fetchone()
                if challenge:
                    await db.execute(
                        "INSERT INTO daily_leaderboard (challenge_id, user_id, score, total_questions, completion_seconds, finished_at) VALUES (?,?,?,?,?,?) ON CONFLICT(challenge_id, user_id) DO UPDATE SET score=excluded.score, completion_seconds=excluded.completion_seconds, finished_at=excluded.finished_at",
                        (challenge['id'], user['id'], attempt_after['score'] or 0, attempt_after['total_questions'] or 10, attempt_after['completion_seconds'] or 0, now))
                    # Update daily streak
                    srow = await (await db.execute('SELECT last_quiz_date, daily_streak FROM statistics WHERE user_id = ?', (user['id'],))).fetchone()
                    if srow:
                        last = srow['last_quiz_date'] or ''
                        streak = srow['daily_streak'] or 0
                        from datetime import datetime, timezone, timedelta
                        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
                        if last == yesterday:
                            streak += 1
                        elif last != today:
                            streak = 1
                        await db.execute('UPDATE statistics SET daily_streak = ?, last_quiz_date = ? WHERE user_id = ?', (streak, today, user['id']))
                    else:
                        await db.execute('UPDATE statistics SET daily_streak = 1, last_quiz_date = ? WHERE user_id = ?', (today, user['id']))
                    await db.commit()
                    dlb = await (await db.execute(
                        'SELECT d.*, u.username, u.first_name FROM daily_leaderboard d JOIN users u ON u.id = d.user_id WHERE d.challenge_id = ? ORDER BY d.score DESC, d.completion_seconds ASC LIMIT 10',
                        (challenge['id'],))).fetchall()
                    lines = ['🗓 <b>Daily Challenge — Bugungi reyting</b>\n']
                    for i, r in enumerate(dlb):
                        name = f"@{r['username']}" if r['username'] else (r['first_name'] or 'User')
                        lines.append(f"{i+1}. {name} — {r['score']}/{r['total_questions']}")
                    await callback.message.answer('\n'.join(lines))

            # Duel finish
            if attempt['quiz_mode'] == 'duel':
                un = now_iso()
                kv = await (await db.execute(
                    "SELECT key FROM user_state WHERE user_id = ? AND key LIKE 'duel_attempt_%'", (user['id'],))).fetchone()
                if kv and kv['key']:
                    parts = kv['key'].split('_')
                    if len(parts) >= 3:
                        match_id = int(parts[2])
                        match = await (await db.execute('SELECT * FROM duel_matches WHERE id = ?', (match_id,))).fetchone()
                        if match:
                            side = 'player1' if match['player1_id'] == user['id'] else 'player2'
                            sc = attempt_after['score'] or 0
                            tm = attempt_after['completion_seconds'] or 0
                            if side == 'player1':
                                await db.execute('UPDATE duel_matches SET player1_score = ?, player1_time = ? WHERE id = ?', (sc, tm, match_id))
                            else:
                                await db.execute('UPDATE duel_matches SET player2_score = ?, player2_time = ? WHERE id = ?', (sc, tm, match_id))
                            await db.commit()
                            match = await (await db.execute('SELECT * FROM duel_matches WHERE id = ?', (match_id,))).fetchone()
                            if match['player1_time'] > 0 and match['player2_time'] > 0:
                                if match['player1_score'] > match['player2_score']:
                                    match['winner_id'] = match['player1_id']
                                elif match['player2_score'] > match['player1_score']:
                                    match['winner_id'] = match['player2_id']
                                else:
                                    match['winner_id'] = match['player1_id'] if match['player1_time'] <= match['player2_time'] else match['player2_id']
                                await db.execute(
                                    "UPDATE duel_matches SET status = 'finished', winner_id = ?, finished_at = ? WHERE id = ?",
                                    (match['winner_id'], un, match_id))
                                await db.commit()
                                w = await (await db.execute('SELECT * FROM users WHERE id = ?', (match['winner_id'],))).fetchone()
                                wname = f"@{w['username']}" if w and w['username'] else (w['first_name'] or 'Player')
                                await callback.message.answer(
                                    f"🏆 <b>Duel yakunlandi!</b>\n\n"
                                    f"Player 1: {match['player1_score']} ball\n"
                                    f"Player 2: {match['player2_score']} ball\n"
                                    f"G'olib: <b>{wname}</b>! 🎉")

            # Update leaderboard
            if attempt_after['status'] in ('completed', 'timed_out'):
                await db.execute(
                    "INSERT INTO leaderboard (attempt_id, user_id, score, completion_seconds, mode, finished_at) VALUES (?,?,?,?,?,?) ON CONFLICT(attempt_id) DO UPDATE SET score=excluded.score, completion_seconds=excluded.completion_seconds, mode=excluded.mode, finished_at=excluded.finished_at",
                    (attempt_after['id'], user['id'], attempt_after['score'] or 0, attempt_after['completion_seconds'] or 0, attempt_after['mode'], attempt_after['finished_at'] or now))
                await db.commit()
            return

        # Next question
        attempt_updated = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
        session_updated = await (await db.execute('SELECT * FROM active_sessions WHERE attempt_id = ? AND status = ?', (attempt_id, 'active'))).fetchone()
        await send_current_question(callback.message, attempt_updated, session_updated)

@router.callback_query(F.data.startswith('review:'))
async def review_callback(callback: CallbackQuery):
    attempt_id = int(callback.data.split(':')[1])
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    attempt = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
    if not attempt or attempt['user_id'] != user['id']:
        await callback.answer('Bu test sizniki emas.')
        return
    answers = await (await db.execute('SELECT * FROM answers WHERE attempt_id = ? ORDER BY question_index', (attempt_id,))).fetchall()
    questions = json.loads(attempt['question_order_json'])
    await callback.answer()
    await callback.message.answer(format_wrong_answers(questions, [dict(a) for a in answers]))

async def _finish_attempt(db, attempt_id: int, status: str):
    now = now_iso()
    attempt = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
    if not attempt:
        return None
    start = attempt['started_at']
    try:
        start_dt = datetime.fromisoformat(start)
        end_dt = datetime.fromisoformat(now)
        secs = int((end_dt - start_dt).total_seconds())
    except:
        secs = 0
    await db.execute(
        'UPDATE attempts SET status = ?, finished_at = ?, completion_seconds = ? WHERE id = ? AND status = ?',
        (status, now, secs, attempt_id, 'active'))
    await db.execute(
        'UPDATE active_sessions SET status = ?, updated_at = ? WHERE attempt_id = ? AND status = ?',
        (status, now, attempt_id, 'active'))
    await db.commit()
    return secs
