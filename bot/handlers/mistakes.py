import json
from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.database import get_db, now_iso
from bot.utils.db_helpers import upsert_user, get_mistakes, mistake_count, clear_mistake
from bot.keyboards import mistakes_kb
from bot.quiz_engine import QuizEngine
from bot.handlers.quiz import send_current_question

router = Router()
engine: QuizEngine = None

def set_quiz_engine(e: QuizEngine):
    global engine
    engine = e

@router.callback_query(F.data == 'mistakes')
async def mistakes_menu(callback: CallbackQuery):
    async with await get_db() as db:
        user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        cnt = await mistake_count(db, user['id'])
    if cnt == 0:
        await callback.answer("Xato qilgan so'zlaringiz yo'q! 🎉")
        return
    await callback.message.edit_text(
        f"📚 <b>Xato qilgan so'zlarim</b>\n\nSizda {cnt} ta xato qilingan so'z bor. Qayta ishlash uchun rejim tanlang:",
        reply_markup=mistakes_kb())
    await callback.answer()

@router.callback_query(F.data.startswith('mistakes:'))
async def mistakes_start(callback: CallbackQuery):
    mode = callback.data.split(':', 1)[1]
    async with await get_db() as db:
        user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
        mistakes = await get_mistakes(db, user['id'])
        if not mistakes:
            await callback.answer("Xato qilgan so'z topilmadi.")
            return

        target_field = 'uzbek' if mode == 'eng_uzb' else 'english'
        prompt_field = 'english' if mode == 'eng_uzb' else 'uzbek'
        questions = []
        for m in mistakes:
            correct = m[target_field]
            entry = {'id': m['vocab_id'], 'english': m['english'], 'uzbek': m['uzbek'], 'category': m.get('category', ''), 'difficulty': ''}
            distractors = await _build_mistake_distractors(db, entry, target_field, {correct.lower()})
            options = list(dict.fromkeys([correct] + distractors[:3]))
            while len(options) < 4:
                options.append('—')
            questions.append({
                'id': entry['id'], 'english': entry['english'], 'uzbek': entry['uzbek'],
                'category': entry.get('category', ''), 'difficulty': '',
                'prompt': entry[prompt_field], 'correct_answer': correct,
                'options': options[:4],
            })

        qty = len(questions)
        now = now_iso()
        await db.execute(
            'INSERT INTO attempts (user_id, mode, difficulty, category, total_questions, question_order_json, order_hash, started_at, status, quiz_mode) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (user['id'], mode, '', '', qty, json.dumps(questions), '', now, 'active', 'mistakes'))
        await db.commit()
        cursor = await db.execute('SELECT last_insert_rowid() AS id')
        attempt_id = (await cursor.fetchone())['id']
        await db.execute(
            'INSERT INTO active_sessions (attempt_id, user_id, chat_id, expires_at, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)',
            (attempt_id, user['id'], callback.message.chat.id, 0, 'active', now, now))
        await db.commit()
        attempt = {'id': attempt_id, 'user_id': user['id'], 'current_index': 0, 'total_questions': qty, 'mode': mode, 'quiz_mode': 'mistakes'}
        session = {'attempt_id': attempt_id, 'expires_at': 0}

    await callback.message.edit_text('📚 Xato qilgan so\'zlar bo\'yicha test boshlandi! To\'g\'ri javob bersangiz, xato ro\'yxatidan o\'chiriladi.')
    await send_current_question(callback.message, attempt, session, questions)
    await callback.answer()

async def _build_mistake_distractors(db, entry, target_field, protected):
    cursor = await db.execute('SELECT id, english, uzbek FROM vocabulary ORDER BY RANDOM() LIMIT 20')
    candidates = await cursor.fetchall()
    result = []
    for c in candidates:
        val = str(c[target_field])
        if c['id'] == entry['id'] or val.lower() in protected:
            continue
        result.append(val)
        if len(result) >= 3:
            break
    return result
