from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.database import get_db, now_iso
from bot.utils.db_helpers import upsert_user
from bot.keyboards import chill_kb
from bot.quiz_engine import QuizEngine
from bot.handlers.quiz import question_payload, send_current_question

router = Router()
engine: QuizEngine = None

def set_quiz_engine(e: QuizEngine):
    global engine
    engine = e

@router.callback_query(F.data == 'chill')
async def chill_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        '🧘 <b>Cheksiz rejim</b>\n\nTimer yo\'q, o\'z vaqtingizda. Qiyinlikni tanlang:',
        reply_markup=chill_kb())
    await callback.answer()

@router.callback_query(F.data.startswith('chill:'))
async def chill_start(callback: CallbackQuery):
    diff = callback.data.split(':')[1]
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    mode = 'eng_uzb'
    cat = 'all'
    qty = 30
    res = engine.generate_questions(user['id'], mode, qty, diff if diff != 'mixed' else '', cat)
    questions = res['questions']
    now = now_iso()
    await db.execute(
        'INSERT INTO attempts (user_id, mode, difficulty, category, total_questions, question_order_json, order_hash, started_at, status, quiz_mode) VALUES (?,?,?,?,?,?,?,?,?,?)',
        (user['id'], mode, diff, cat, qty, question_payload(questions), res['order_hash'], now, 'active', 'chill'))
    await db.commit()
    cursor = await db.execute('SELECT last_insert_rowid() AS id')
    attempt_id = (await cursor.fetchone())['id']
    await db.execute(
        'INSERT INTO active_sessions (attempt_id, user_id, chat_id, expires_at, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)',
        (attempt_id, user['id'], callback.message.chat.id, 0, 'active', now, now))
    await db.commit()
    attempt = {'id': attempt_id, 'user_id': user['id'], 'current_index': 0, 'total_questions': qty, 'mode': mode, 'quiz_mode': 'chill'}
    session = {'attempt_id': attempt_id, 'expires_at': 0}
    await callback.message.edit_text('🧘 Cheksiz rejim. 30 ta savol, vaqt cheklovi yo\'q!')
    await send_current_question(callback.message, attempt, session, questions)
    await callback.answer()
