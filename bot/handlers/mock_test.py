from __future__ import annotations

import json
import time

import aiosqlite
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.constants import ANSWER_LETTERS
from bot.database import db_transaction, get_db, now_iso
from bot.keyboards import (
    active_quiz_kb, main_menu_kb, mock_answer_kb, mock_feedback_kb,
    mock_menu_kb, mock_module_break_kb, mock_topics_kb,
)
from bot.keyboards_ai import ai_answer_kb
from bot.mock_images import get_image_path
from bot.mock_tests import (
    MOCK_MODULE_SECONDS,
    MockBankError,
    get_mock_topics,
    load_mock_bank,
    mock_module_size,
    mock_question_text,
    mock_result_text,
    select_mock_questions,
)
from bot.services.active_session_service import get_resumable_attempt
from bot.services.attempt_service import finish_attempt
from bot.services.quiz_service import create_attempt_with_session
from bot.services.sat_analytics_service import record_sat_answer
from bot.utils.db_helpers import upsert_user

router = Router()


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def mock_question_payload(questions: list[dict]) -> str:
    return json.dumps(questions, ensure_ascii=False, separators=(',', ':'))


async def send_mock_question(message_or_callback, attempt: dict, session: dict, questions: list[dict] | None = None, *, edit_msg: Message | None = None):
    db = await get_db()
    if questions is None:
        row = await (await db.execute('SELECT question_order_json FROM attempts WHERE id = ?', (attempt['id'],))).fetchone()
        questions = json.loads(row['question_order_json']) if row else []
    index = attempt['current_index']
    if index >= len(questions):
        return
    question = questions[index]
    remaining = max(0, session['expires_at'] - int(time.time())) if session['expires_at'] else 0
    text = mock_question_text(question, index, len(questions), remaining)
    kb = mock_answer_kb(attempt['id'], index, question['choices'])
    img_path = get_image_path(question)
    target = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
    if edit_msg:
        if img_path:
            try:
                await edit_msg.delete()
            except Exception:
                pass
            await target.answer_photo(FSInputFile(str(img_path)), caption=text, reply_markup=kb)
        else:
            try:
                await edit_msg.edit_text(text, reply_markup=kb)
            except Exception:
                try:
                    await edit_msg.delete()
                except Exception:
                    pass
                await target.answer(text, reply_markup=kb)
    elif img_path:
        await target.answer_photo(FSInputFile(str(img_path)), caption=text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


async def _mock_answers_for_result(db, attempt: dict) -> str:
    questions = json.loads(attempt['question_order_json'])
    answers = await (await db.execute(
        'SELECT * FROM answers WHERE attempt_id = ? ORDER BY question_index',
        (attempt['id'],),
    )).fetchall()
    return mock_result_text(attempt, questions, [dict(answer) for answer in answers])


async def _start_mock(message: Message | CallbackQuery, user_id: int, chat_id: int, topic: str | None = None):
    db = await get_db()
    active_attempt, _session = await get_resumable_attempt(db, user_id)
    if active_attempt:
        target = message.message if isinstance(message, CallbackQuery) else message
        await target.answer(
            'Sizda faol test bor. Davom ettirasizmi yoki yangidan boshlaysizmi?',
            reply_markup=active_quiz_kb(active_attempt['id']),
        )
        return None

    bank = load_mock_bank()
    try:
        questions = select_mock_questions(bank, seed=int(time.time()), topic=topic)
    except MockBankError:
        target = message.message if isinstance(message, CallbackQuery) else message
        await target.answer('Bu mavzuda yetarli savol yo\'q.', reply_markup=main_menu_kb())
        return None

    total = len(questions)
    expires_at = int(time.time()) + MOCK_MODULE_SECONDS
    attempt_id = await create_attempt_with_session(
        user_id=user_id,
        chat_id=chat_id,
        mode='mock_math',
        difficulty='mixed',
        category=topic or 'SAT Math',
        total_questions=total,
        question_order_json=mock_question_payload(questions),
        order_hash='',
        expires_at=expires_at,
        quiz_mode='mock',
    )
    return (
        {'id': attempt_id, 'user_id': user_id, 'current_index': 0, 'total_questions': total, 'mode': 'mock_math', 'quiz_mode': 'mock'},
        {'attempt_id': attempt_id, 'expires_at': expires_at},
        questions,
    )


async def _show_mock_result(target_message: Message, attempt_id: int, db):
    finished = await finish_attempt(db, attempt_id, 'completed')
    attempt = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
    questions = json.loads(attempt['question_order_json'])
    answers = await (await db.execute('SELECT * FROM answers WHERE attempt_id = ? ORDER BY question_index', (attempt_id,))).fetchall()
    await target_message.answer(mock_result_text(finished or dict(attempt), questions, [dict(a) for a in answers]), reply_markup=main_menu_kb())


@router.message(F.text.in_({'📝 Mock test', 'Mock test'}))
@router.message(Command('mock'))
async def mock_menu(message: Message):
    await message.answer(
        '📝 <b>SAT Math Mock Test</b>\n\nMathbook 3.0 dan olingan savollar. Mavzu bo\'yicha yoki aralash rejimda ishlang.',
        reply_markup=mock_menu_kb(),
    )


@router.callback_query(F.data == 'mock:rules')
async def mock_rules(callback: CallbackQuery):
    await callback.message.edit_text(
        '📋 <b>Mock test qoidalari</b>\n\n'
        '- Savollar Mathbook topiclaridan tanlanadi\n'
        '- Har bir savoldan keyin to\'g\'ri javob ko\'rsatiladi\n'
        '- Test yakunida natijalar tahlili chiqariladi\n'
        '- Istalgan mavzuni tanlab ishlash mumkin',
        reply_markup=mock_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == 'mock:topics')
async def mock_topics(callback: CallbackQuery):
    bank = load_mock_bank()
    topics = get_mock_topics(bank)
    await callback.message.edit_text(
        '📚 <b>Mavzu tanlang</b>\n\nTest ishlamoqchi bo\'lgan mavzuni tanlang:',
        reply_markup=mock_topics_kb(topics),
    )
    await callback.answer()


@router.callback_query(F.data == 'mock:menu')
async def mock_back_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        '📝 <b>SAT Math Mock Test</b>\n\nMathbook 3.0 dan olingan savollar.',
        reply_markup=mock_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == 'mock:start')
async def mock_start_callback(callback: CallbackQuery):
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    started = await _start_mock(callback, user['id'], callback.message.chat.id, topic=None)
    if not started:
        await callback.answer()
        return
    attempt, session, questions = started
    await send_mock_question(callback.message, attempt, session, questions, edit_msg=callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith('mock:topic:'))
async def mock_start_topic(callback: CallbackQuery):
    topic = (callback.data or '').removeprefix('mock:topic:')
    if topic == 'all':
        topic = None
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    started = await _start_mock(callback, user['id'], callback.message.chat.id, topic=topic)
    if not started:
        await callback.answer()
        return
    attempt, session, questions = started
    await send_mock_question(callback.message, attempt, session, questions, edit_msg=callback.message)
    await callback.answer()


@router.message(Command('mock_start'))
async def mock_start_message(message: Message):
    db = await get_db()
    user = await upsert_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
    started = await _start_mock(message, user['id'], message.chat.id, topic=None)
    if not started:
        return
    attempt, session, questions = started
    await message.answer('📝 Mock test boshlandi.')
    await send_mock_question(message, attempt, session, questions)


@router.callback_query(F.data.startswith('mock:module2:'))
async def mock_module_two(callback: CallbackQuery):
    attempt_id = _parse_int((callback.data or '').split(':')[-1])
    if attempt_id is None:
        await callback.answer('Noto‘g‘ri tugma.', show_alert=True)
        return
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    attempt = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
    if not attempt or attempt['user_id'] != user['id'] or attempt['quiz_mode'] != 'mock':
        await callback.answer('Mock test topilmadi.', show_alert=True)
        return
    mod_size = mock_module_size(attempt['total_questions'])
    if attempt['current_index'] < mod_size:
        await callback.answer('Avval Module 1 ni yakunlang.', show_alert=True)
        return
    if attempt['current_index'] > mod_size:
        session = await (await db.execute(
            'SELECT * FROM active_sessions WHERE attempt_id = ? AND status = ?',
            (attempt_id, 'active'),
        )).fetchone()
        await callback.answer('Module 2 allaqachon boshlangan.')
        if session:
            await send_mock_question(callback.message, dict(attempt), dict(session), edit_msg=callback.message)
        return
    expires_at = int(time.time()) + MOCK_MODULE_SECONDS
    now = now_iso()
    async with db_transaction() as tx:
        await tx.execute(
            'UPDATE active_sessions SET expires_at = ?, updated_at = ? WHERE attempt_id = ? AND status = ?',
            (expires_at, now, attempt_id, 'active'),
        )
    session = {'attempt_id': attempt_id, 'expires_at': expires_at}
    await send_mock_question(callback.message, attempt, session, edit_msg=callback.message)
    await callback.answer()


@router.callback_query(F.data.startswith('mock_ans:'))
async def mock_answer_callback(callback: CallbackQuery):
    parts = (callback.data or '').split(':')
    if len(parts) != 4:
        await callback.answer('Noto‘g‘ri tugma.', show_alert=True)
        return
    attempt_id = _parse_int(parts[1])
    question_index = _parse_int(parts[2])
    selected_letter = parts[3]
    if attempt_id is None or question_index is None or selected_letter not in ANSWER_LETTERS:
        await callback.answer('Noto‘g‘ri tugma.', show_alert=True)
        return

    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    attempt = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
    if not attempt or attempt['user_id'] != user['id'] or attempt['quiz_mode'] != 'mock':
        await callback.answer('Bu mock test sizniki emas.', show_alert=True)
        return
    if attempt['status'] != 'active':
        await callback.answer('Mock test yakunlangan.')
        return
    if attempt['current_index'] != question_index:
        await callback.answer('Eski tugma.')
        return

    session = await (await db.execute(
        'SELECT * FROM active_sessions WHERE attempt_id = ? AND status = ?',
        (attempt_id, 'active'),
    )).fetchone()
    questions = json.loads(attempt['question_order_json'])
    if not session:
        await callback.answer('Sessiya topilmadi.', show_alert=True)
        return
    if session['expires_at'] and int(time.time()) > session['expires_at']:
        finished = await finish_attempt(db, attempt_id, 'timed_out')
        answers = await (await db.execute('SELECT * FROM answers WHERE attempt_id = ? ORDER BY question_index', (attempt_id,))).fetchall()
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(mock_result_text(finished or dict(attempt), questions, [dict(a) for a in answers]), reply_markup=main_menu_kb())
        await callback.answer('Vaqt tugadi.')
        return

    if question_index < 0 or question_index >= len(questions):
        await callback.answer('Eski tugma.')
        return
    question = questions[question_index]
    correct_letter = question['correct_choice']
    is_correct = selected_letter == correct_letter
    now = now_iso()
    real_question_id = _parse_int(str(question.get('id', '')).split('-')[-1]) or (question_index + 1)
    try:
        async with db_transaction() as tx:
            await tx.execute(
                'INSERT INTO answers (attempt_id, question_id, question_index, selected_answer, correct_answer, is_correct, answered_at) VALUES (?,?,?,?,?,?,?)',
                (attempt_id, real_question_id, question_index, selected_letter, correct_letter, 1 if is_correct else 0, now),
            )
            await record_sat_answer(
                tx,
                user_id=user['id'],
                attempt_id=attempt_id,
                question=question,
                user_answer=selected_letter,
                correct_answer=correct_letter,
                is_correct=is_correct,
            )
            cursor = await tx.execute(
                'UPDATE attempts SET score = score + ?, current_index = current_index + 1, correct_count = correct_count + ?, wrong_count = wrong_count + ? WHERE id = ? AND status = ? AND current_index = ?',
                (1 if is_correct else 0, 1 if is_correct else 0, 0 if is_correct else 1, attempt_id, 'active', question_index),
            )
            if cursor.rowcount != 1:
                raise RuntimeError('attempt_index_changed')
    except aiosqlite.IntegrityError:
        await callback.answer('Bu savolga javob berilgan.')
        return
    except RuntimeError:
        await callback.answer('Eski tugma.')
        return

    await callback.answer('✅' if is_correct else '❌')
    attempt = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
    total = attempt['total_questions']
    current = attempt['current_index']
    mod_size = mock_module_size(total)
    is_last = current >= total
    is_module_break = not is_last and current == mod_size and total > mod_size

    if is_module_break:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            'Module 1 yakunlandi. Tayyor bo‘lsangiz Module 2 ni boshlang.',
            reply_markup=mock_module_break_kb(attempt_id),
        )
        return

    if is_last:
        await _show_mock_result(callback.message, attempt_id, db)
        return

    fb_kb = mock_feedback_kb(attempt_id, question_index, question['choices'], correct_letter, selected_letter, is_last=is_last)
    try:
        await callback.message.edit_text(text=callback.message.html_text, reply_markup=fb_kb)
    except Exception:
        try:
            await callback.message.edit_caption(caption=callback.message.html_text or callback.message.caption, reply_markup=fb_kb)
        except Exception:
            await callback.message.edit_reply_markup(reply_markup=fb_kb)
    await callback.message.answer(
        'AI Mentor yordam kerakmi?',
        reply_markup=ai_answer_kb(
            attempt_id,
            question_index,
            is_correct,
            bool(question.get('desmos_recommended') or question.get('desmos_needed')),
        ),
    )


@router.callback_query(F.data.startswith('mock:next:'))
async def mock_next_callback(callback: CallbackQuery):
    parts = (callback.data or '').split(':')
    if len(parts) != 4:
        await callback.answer('Noto‘g‘ri tugma.', show_alert=True)
        return
    attempt_id = _parse_int(parts[2])
    question_index = _parse_int(parts[3])
    if attempt_id is None or question_index is None:
        await callback.answer('Noto‘g‘ri tugma.', show_alert=True)
        return

    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    attempt = await (await db.execute('SELECT * FROM attempts WHERE id = ?', (attempt_id,))).fetchone()
    if not attempt or attempt['user_id'] != user['id'] or attempt['quiz_mode'] != 'mock':
        await callback.answer('Bu mock test sizniki emas.', show_alert=True)
        return
    if attempt['status'] != 'active':
        await callback.answer('Mock test yakunlangan.')
        return
    if attempt['current_index'] != question_index + 1:
        await callback.answer('Eski tugma.')
        return

    session = await (await db.execute(
        'SELECT * FROM active_sessions WHERE attempt_id = ? AND status = ?',
        (attempt_id, 'active'),
    )).fetchone()
    if not session:
        await callback.answer('Sessiya topilmadi.', show_alert=True)
        return

    questions = json.loads(attempt['question_order_json'])
    await send_mock_question(callback.message, dict(attempt), dict(session), questions, edit_msg=callback.message)
    await callback.answer()
