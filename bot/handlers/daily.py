import json
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from bot.database import get_db, now_iso
from bot.utils.db_helpers import upsert_user
from bot.keyboards import main_menu_kb
from bot.quiz_engine import QuizEngine
from bot.handlers.quiz import send_current_question

router = Router()
engine: QuizEngine = None

def set_quiz_engine(e: QuizEngine):
    global engine
    engine = e

async def _start_daily(message_or_callback, user_id: int, chat_id: int):
    db = await get_db()
    today = now_iso()[:10]
    cursor = await db.execute('SELECT * FROM daily_challenge WHERE date = ?', (today,))
    challenge = await cursor.fetchone()
    if not challenge:
        res = engine.generate_questions(0, 'eng_uzb', 10, '', '', for_daily=True)
        questions = res['questions']
        await db.execute(
            'INSERT INTO daily_challenge (date, questions_json, created_at) VALUES (?,?,?)',
            (today, json.dumps(questions), now_iso()))
        await db.commit()
        cursor = await db.execute('SELECT last_insert_rowid() AS id')
        challenge = await cursor.fetchone()

    # Start attempt
    cursor = await db.execute('SELECT questions_json FROM daily_challenge WHERE id = ?', (challenge['id'],))
    row = await cursor.fetchone()
    questions = json.loads(row['questions_json'])
    now = now_iso()
    await db.execute(
        'INSERT INTO attempts (user_id, mode, difficulty, category, total_questions, question_order_json, order_hash, started_at, status, quiz_mode) VALUES (?,?,?,?,?,?,?,?,?,?)',
        (user_id, 'eng_uzb', 'mixed', 'all', len(questions), json.dumps([{k: q[k] for k in ('id','english','uzbek','category','difficulty','prompt','correct_answer','options')} for q in questions]), '', now, 'active', 'daily'))
    await db.commit()
    cursor = await db.execute('SELECT last_insert_rowid() AS id')
    attempt_id = (await cursor.fetchone())['id']
    await db.execute(
        'INSERT INTO active_sessions (attempt_id, user_id, chat_id, expires_at, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?)',
        (attempt_id, user_id, chat_id, 0, 'active', now, now))
    await db.commit()
    attempt = {'id': attempt_id, 'user_id': user_id, 'current_index': 0, 'total_questions': len(questions), 'mode': 'eng_uzb', 'quiz_mode': 'daily'}
    session = {'attempt_id': attempt_id, 'expires_at': 0}
    return attempt, session, questions

@router.message(F.text == '🗓 Daily Challenge')
@router.message(Command('daily'))
async def daily_challenge(message: Message):
    db = await get_db()
    user = await upsert_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
    attempt, session, questions = await _start_daily(message, user['id'], message.chat.id)
    await message.answer('🗓 <b>Daily SAT Challenge</b>\n\n10 ta savol, tezlik va aniqlik muhim!', reply_markup=main_menu_kb())
    await send_current_question(message, attempt, session, questions)

@router.callback_query(F.data == 'daily:start')
async def daily_callback(callback: CallbackQuery):
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    attempt, session, questions = await _start_daily(callback, user['id'], callback.message.chat.id)
    await callback.message.answer('🗓 Daily Challenge boshlandi!')
    await send_current_question(callback.message, attempt, session, questions)
    await callback.answer()
