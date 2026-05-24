from __future__ import annotations

import json
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.database import get_db
from bot.keyboards import main_menu_kb
from bot.keyboards_ai import ai_mentor_kb
from bot.services.ai_mentor_service import (
    ai_summary,
    analyze_mistake,
    cooldown_remaining,
    desmos_solution,
    explain_question,
)
from bot.services.sat_analytics_service import learning_profile
from bot.utils.db_helpers import upsert_user

router = Router()
logger = logging.getLogger(__name__)


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _question_at(attempt, question_index: int) -> dict | None:
    try:
        questions = json.loads(attempt['question_order_json'])
    except (TypeError, json.JSONDecodeError):
        return None
    if question_index < 0 or question_index >= len(questions):
        return None
    question = questions[question_index]
    return question if isinstance(question, dict) else None


async def _load_attempt_question(db, user_id: int, attempt_id: int, question_index: int):
    attempt = await (await db.execute(
        'SELECT * FROM attempts WHERE id = ? AND user_id = ?',
        (attempt_id, user_id),
    )).fetchone()
    if not attempt:
        return None, None, None
    question = _question_at(attempt, question_index)
    answer = await (await db.execute(
        'SELECT * FROM answers WHERE attempt_id = ? AND question_index = ?',
        (attempt_id, question_index),
    )).fetchone()
    return attempt, question, answer


async def _send_ai_result(callback: CallbackQuery, text: str) -> None:
    await callback.message.answer(f'<b>AI Mentor</b>\n\n{text[:3500]}')


@router.message(Command('mentor'))
@router.message(F.text == 'AI Mentor')
async def mentor_home(message: Message):
    db = await get_db()
    user = await upsert_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
    profile = await learning_profile(db, user['id'])
    summary = ai_summary()
    status = 'yoqilgan' if summary.get('available') else 'sozlanmagan'
    weak = profile.get('weak_topics') or []
    strong = profile.get('strong_topics') or []
    recommended = profile.get('recommended_practice') or []
    lines = [
        '<b>AI Mentor</b>',
        f"Holat: <b>{status}</b>",
        f"Taxminiy SAT Math: <b>{profile.get('estimated_sat_math_score', 200)}</b>",
        f"Daraja: <b>{profile.get('estimated_skill_level', 'Boshlangich')}</b>",
    ]
    if weak:
        lines.append('Zaif mavzular: ' + ', '.join(weak[:5]))
    if strong:
        lines.append('Kuchli mavzular: ' + ', '.join(strong[:5]))
    if recommended:
        lines.append('Tavsiya: ' + '; '.join(recommended[:3]))
    lines.append("\nTestdan keyin 'AI izoh' yoki 'Xatoni AI tahlil qilsin' tugmalaridan foydalaning.")
    await message.answer('\n'.join(lines), reply_markup=ai_mentor_kb())


@router.callback_query(F.data.startswith('ai:explain:'))
async def ai_explain_callback(callback: CallbackQuery):
    parts = (callback.data or '').split(':')
    if len(parts) != 4:
        await callback.answer('Noto‘g‘ri tugma.', show_alert=True)
        return
    wait = cooldown_remaining(callback.from_user.id)
    if wait:
        await callback.answer(f'{wait}s kuting.', show_alert=True)
        return
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    attempt_id = _parse_int(parts[2])
    question_index = _parse_int(parts[3])
    if attempt_id is None or question_index is None:
        await callback.answer('Noto‘g‘ri tugma.', show_alert=True)
        return
    attempt, question, _answer = await _load_attempt_question(db, user['id'], attempt_id, question_index)
    if not attempt or not question:
        await callback.answer('Savol topilmadi.', show_alert=True)
        return
    await callback.answer('AI Mentor yozmoqda...')
    text = await explain_question(callback.from_user.id, question)
    await _send_ai_result(callback, text)


@router.callback_query(F.data.startswith('ai:mistake:'))
async def ai_mistake_callback(callback: CallbackQuery):
    parts = (callback.data or '').split(':')
    if len(parts) != 4:
        await callback.answer('Noto‘g‘ri tugma.', show_alert=True)
        return
    wait = cooldown_remaining(callback.from_user.id)
    if wait:
        await callback.answer(f'{wait}s kuting.', show_alert=True)
        return
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    attempt_id = _parse_int(parts[2])
    question_index = _parse_int(parts[3])
    if attempt_id is None or question_index is None:
        await callback.answer('Noto‘g‘ri tugma.', show_alert=True)
        return
    attempt, question, answer = await _load_attempt_question(db, user['id'], attempt_id, question_index)
    if not attempt or not question:
        await callback.answer('Savol topilmadi.', show_alert=True)
        return
    user_answer = answer['selected_answer'] if answer else ''
    await callback.answer('AI Mentor tahlil qilmoqda...')
    text = await analyze_mistake(callback.from_user.id, question, user_answer)
    await _send_ai_result(callback, text)


@router.callback_query(F.data.startswith('ai:desmos:'))
async def ai_desmos_callback(callback: CallbackQuery):
    parts = (callback.data or '').split(':')
    if len(parts) != 4:
        await callback.answer('Noto‘g‘ri tugma.', show_alert=True)
        return
    wait = cooldown_remaining(callback.from_user.id)
    if wait:
        await callback.answer(f'{wait}s kuting.', show_alert=True)
        return
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    attempt_id = _parse_int(parts[2])
    question_index = _parse_int(parts[3])
    if attempt_id is None or question_index is None:
        await callback.answer('Noto‘g‘ri tugma.', show_alert=True)
        return
    attempt, question, _answer = await _load_attempt_question(db, user['id'], attempt_id, question_index)
    if not attempt or not question:
        await callback.answer('Savol topilmadi.', show_alert=True)
        return
    await callback.answer('Desmos yechim tayyorlanmoqda...')
    text = await desmos_solution(callback.from_user.id, question)
    await _send_ai_result(callback, text)


@router.callback_query(F.data == 'ai:last_mistake')
async def ai_last_mistake_callback(callback: CallbackQuery):
    wait = cooldown_remaining(callback.from_user.id)
    if wait:
        await callback.answer(f'{wait}s kuting.', show_alert=True)
        return
    db = await get_db()
    user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    row = await (await db.execute(
        '''
        SELECT a.attempt_id, a.question_index, a.selected_answer
        FROM answers a
        JOIN attempts t ON t.id = a.attempt_id
        WHERE t.user_id = ? AND a.is_correct = 0
        ORDER BY a.answered_at DESC
        LIMIT 1
        ''',
        (user['id'],),
    )).fetchone()
    if not row:
        await callback.answer('Hali xato javob yo‘q.', show_alert=True)
        return
    attempt, question, _answer = await _load_attempt_question(db, user['id'], row['attempt_id'], row['question_index'])
    if not attempt or not question:
        await callback.answer('Savol topilmadi.', show_alert=True)
        return
    await callback.answer('AI Mentor tahlil qilmoqda...')
    text = await analyze_mistake(callback.from_user.id, question, row['selected_answer'])
    await _send_ai_result(callback, text)
