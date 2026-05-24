import json
import logging
import random
import string

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.database import db_transaction, get_db, now_iso
from bot.formatting import question_text
from bot.handlers.quiz import question_payload, send_current_question
from bot.keyboards import answer_kb, duel_difficulty_kb, duel_menu_kb
from bot.quiz_engine import QuizEngine
from bot.utils.db_helpers import upsert_user

router = Router()
engine: QuizEngine = None
bot_instance = None
logger = logging.getLogger(__name__)


def set_quiz_engine(e: QuizEngine):
    global engine
    engine = e


def set_bot(b):
    global bot_instance
    bot_instance = b


@router.message(F.text.in_({'Duel', '⚔️ Duel', '🔥 Duel'}))
@router.message(Command('duel'))
async def duel_menu(message: Message):
    await message.answer(
        "<b>Duel rejimi</b>\n\n"
        "2 foydalanuvchi bir-biri bilan bellashadi. Kim tez va to'g'ri javob bersa, o'sha yutadi!",
        reply_markup=duel_menu_kb(),
    )


@router.callback_query(F.data == 'duel:find')
async def duel_find(callback: CallbackQuery):
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    active = await (await db.execute(
        "SELECT * FROM duel_matches WHERE (player1_id = ? OR player2_id = ?) "
        "AND status IN ('waiting','active') ORDER BY created_at DESC LIMIT 1",
        (user['id'], user['id']),
    )).fetchone()
    if active:
        await callback.answer('Sizda faol duel bor.')
        return
    await callback.message.edit_text('Qiyinlik tanlang:', reply_markup=duel_difficulty_kb())
    await callback.answer()


@router.callback_query(F.data == 'duel:join')
async def duel_join_prompt(callback: CallbackQuery):
    await callback.answer('Kodni /duel_join <kod> deb yuboring')


@router.callback_query(F.data == 'duel:stats')
async def duel_stats(callback: CallbackQuery):
    db = await get_db()
    duels = await (await db.execute(
        'SELECT d.*, u1.username AS p1name, u1.first_name AS p1first, '
        'u2.username AS p2name, u2.first_name AS p2first '
        'FROM duel_matches d '
        'LEFT JOIN users u1 ON u1.id = d.player1_id '
        'LEFT JOIN users u2 ON u2.id = d.player2_id '
        'WHERE d.status = ? ORDER BY d.finished_at DESC LIMIT 10',
        ('finished',),
    )).fetchall()
    if not duels:
        await callback.answer("Hali duel o'tkazilmagan.")
        return
    lines = ["<b>So'nggi duellar</b>\n"]
    for duel in duels:
        p1 = duel['p1name'] or duel['p1first'] or 'P1'
        p2 = duel['p2name'] or duel['p2first'] or 'P2'
        winner = duel['winner_id']
        w_name = p1 if winner == duel['player1_id'] else (p2 if winner == duel['player2_id'] else 'Durang')
        lines.append(f"- {p1} ({duel['player1_score']}) vs {p2} ({duel['player2_score']}) -> {w_name}")
    await callback.message.edit_text('\n'.join(lines))
    await callback.answer()


@router.callback_query(F.data.startswith('duel:find:'))
async def duel_find_opponent(callback: CallbackQuery):
    parts = callback.data.split(':')
    difficulty = parts[2]
    mode = parts[3] if len(parts) > 3 else 'eng_uzb'
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    opponent = await (await db.execute(
        'SELECT * FROM duel_queue WHERE user_id != ? AND mode = ? AND difficulty = ? '
        'ORDER BY created_at ASC LIMIT 1',
        (user['id'], mode, difficulty),
    )).fetchone()

    if opponent:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        res = engine.generate_questions(user['id'], mode, 10, difficulty if difficulty != 'mixed' else '', '')
        questions = res['questions']
        qjson = question_payload(questions)
        now = now_iso()
        attempts_map = {}

        async with db_transaction() as tx:
            await tx.execute('DELETE FROM duel_queue WHERE user_id = ?', (opponent['user_id'],))
            cursor = await tx.execute(
                "INSERT INTO duel_matches "
                "(code, player1_id, player2_id, questions_json, status, created_at) "
                "VALUES (?,?,?,?,'active',?)",
                (code, opponent['user_id'], user['id'], qjson, now),
            )
            match_id = cursor.lastrowid

            for pid in (opponent['user_id'], user['id']):
                cursor = await tx.execute(
                    'INSERT INTO attempts '
                    '(user_id, mode, difficulty, category, total_questions, question_order_json, '
                    'order_hash, started_at, status, quiz_mode) '
                    'VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (pid, mode, difficulty, '', 10, qjson, '', now, 'active', 'duel'),
                )
                aid = cursor.lastrowid
                chat = opponent['chat_id'] if pid == opponent['user_id'] else callback.message.chat.id
                await tx.execute(
                    'INSERT INTO active_sessions '
                    '(attempt_id, user_id, chat_id, expires_at, status, created_at, updated_at) '
                    'VALUES (?,?,?,?,?,?,?)',
                    (aid, pid, chat, 0, 'active', now, now),
                )
                await tx.execute(
                    "INSERT INTO user_state (user_id, key, value, updated_at) VALUES (?,?,?,?) "
                    "ON CONFLICT(user_id,key) DO UPDATE SET "
                    "value=excluded.value, updated_at=excluded.updated_at",
                    (pid, f'duel_attempt_{match_id}', str(aid), now),
                )
                attempts_map[pid] = {'aid': aid, 'chat': chat}

        await callback.message.edit_text(
            f"<b>Duel topildi!</b>\n\n"
            f"Raqib bilan bellashuv boshlandi!\nKod: <b>{code}</b>\n\n"
            "10 ta savol, kim tez va to'g'ri javob bersa yutadi!"
        )

        for pid, info in attempts_map.items():
            attempt = {'id': info['aid'], 'user_id': pid, 'current_index': 0, 'total_questions': 10, 'mode': mode, 'quiz_mode': 'duel'}
            session = {'attempt_id': info['aid'], 'expires_at': 0}
            if pid == user['id']:
                await callback.message.answer('Duel boshlandi! Savollar kelmoqda...')
                await send_current_question(callback.message, attempt, session, questions)
            else:
                try:
                    await bot_instance.send_message(info['chat'], '<b>Duel topildi!</b>\n\nRaqib bilan bellashuv boshlandi!')
                    question = questions[0]
                    text = question_text(question, 0, 10, 0, mode, False)
                    await bot_instance.send_message(info['chat'], text, reply_markup=answer_kb(info['aid'], 0, question['options']))
                except Exception:
                    logger.exception("failed_to_send_duel_to_opponent user_id=%s chat_id=%s", pid, info['chat'])
        await callback.answer()
        return

    await db.execute(
        "INSERT INTO duel_queue (user_id, mode, difficulty, chat_id, created_at) VALUES (?,?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET "
        "mode=excluded.mode, difficulty=excluded.difficulty, chat_id=excluded.chat_id, created_at=excluded.created_at",
        (user['id'], mode, difficulty, callback.message.chat.id, now_iso()),
    )
    await db.commit()
    await callback.message.edit_text("Raqib qidirilmoqda... Birozdan so'ng qayta urinib ko'ring.", reply_markup=duel_menu_kb())
    await callback.answer("Navbatga qo'shildingiz.")


@router.message(Command('duel_join'))
async def duel_join_code(message: Message):
    text = message.text or ''
    parts = text.split()
    if len(parts) < 2:
        await message.answer('Kodni kiriting: /duel_join ABC123')
        return
    code = parts[1].strip().upper()
    db = await get_db()
    match = await (await db.execute('SELECT * FROM duel_matches WHERE code = ?', (code,))).fetchone()
    if not match:
        await message.answer('Bunday duel topilmadi.')
        return
    if match['status'] != 'waiting':
        await message.answer('Bu duel allaqachon boshlangan.')
        return
    user = await upsert_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
    if match['player1_id'] == user['id']:
        await message.answer('Bu sizning duelingiz.')
        return

    questions = json.loads(match['questions_json'])
    mode = 'eng_uzb'
    difficulty = 'easy'
    now = now_iso()
    qjson = match['questions_json']

    async with db_transaction() as tx:
        await tx.execute("UPDATE duel_matches SET player2_id = ?, status = ? WHERE id = ?", (user['id'], 'active', match['id']))
        cursor = await tx.execute(
            'INSERT INTO attempts '
            '(user_id, mode, difficulty, category, total_questions, question_order_json, '
            'order_hash, started_at, status, quiz_mode) '
            'VALUES (?,?,?,?,?,?,?,?,?,?)',
            (user['id'], mode, difficulty, '', 10, qjson, '', now, 'active', 'duel'),
        )
        aid = cursor.lastrowid
        await tx.execute(
            'INSERT INTO active_sessions '
            '(attempt_id, user_id, chat_id, expires_at, status, created_at, updated_at) '
            'VALUES (?,?,?,?,?,?,?)',
            (aid, user['id'], message.chat.id, 0, 'active', now, now),
        )
        await tx.execute(
            "INSERT INTO user_state (user_id, key, value, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (user['id'], f'duel_attempt_{match["id"]}', str(aid), now),
        )

    await message.answer("Duelga qo'shildingiz! Test boshlandi.")
    attempt = {'id': aid, 'user_id': user['id'], 'current_index': 0, 'total_questions': 10, 'mode': mode, 'quiz_mode': 'duel'}
    session = {'attempt_id': aid, 'expires_at': 0}
    await send_current_question(message, attempt, session, questions)
