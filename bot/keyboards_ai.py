from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def ai_answer_kb(attempt_id: int, question_index: int, is_correct: bool, desmos: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text='AI izoh', callback_data=f'ai:explain:{attempt_id}:{question_index}')]]
    if not is_correct:
        rows.append([InlineKeyboardButton(text='Xatoni AI tahlil qilsin', callback_data=f'ai:mistake:{attempt_id}:{question_index}')])
    if desmos:
        rows.append([InlineKeyboardButton(text='Desmos yechim', callback_data=f'ai:desmos:{attempt_id}:{question_index}')])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ai_mentor_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Oxirgi xatoni tahlil qilish', callback_data='ai:last_mistake')],
        [InlineKeyboardButton(text='Asosiy menyu', callback_data='back_main')],
    ])
