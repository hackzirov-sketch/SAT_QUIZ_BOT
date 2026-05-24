from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.database import get_db
from bot.keyboards import DICTIONARY_PAGE_SIZE, clamp_dictionary_page, dictionary_kb, future_plan_kb

router = Router()


def _parse_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def dictionary_translation_text(word) -> str:
    text = f"{word['english']} — {word['uzbek']}"
    category = word['category'] if 'category' in word.keys() else ''
    if category:
        text = f"{text}\nKategoriya: {category}"
    return text


async def _dictionary_count(db) -> int:
    row = await (await db.execute('SELECT COUNT(*) AS c FROM vocabulary')).fetchone()
    return row['c'] if row else 0


async def _dictionary_words(db, page: int, total_items: int) -> tuple[list, int]:
    page = clamp_dictionary_page(page, total_items)
    offset = page * DICTIONARY_PAGE_SIZE
    rows = await (await db.execute(
        '''
        SELECT id, english, uzbek, category
        FROM vocabulary
        ORDER BY LOWER(english), id
        LIMIT ? OFFSET ?
        ''',
        (DICTIONARY_PAGE_SIZE, offset),
    )).fetchall()
    return rows, page


async def _send_dictionary(message: Message, page: int = 0) -> None:
    db = await get_db()
    total_items = await _dictionary_count(db)
    if total_items <= 0:
        await message.answer("Lug‘at hozircha bo‘sh.", reply_markup=future_plan_kb())
        return
    words, page = await _dictionary_words(db, page, total_items)
    total_pages = (total_items + DICTIONARY_PAGE_SIZE - 1) // DICTIONARY_PAGE_SIZE
    await message.answer(
        f"📖 <b>Lug‘at</b>\n\nSahifa: <b>{page + 1}/{total_pages}</b>\nSo‘z tanlang:",
        reply_markup=dictionary_kb(words, page, total_items),
    )


async def _edit_dictionary(callback: CallbackQuery, page: int = 0) -> None:
    db = await get_db()
    total_items = await _dictionary_count(db)
    if total_items <= 0:
        await callback.message.edit_text("Lug‘at hozircha bo‘sh.", reply_markup=future_plan_kb())
        await callback.answer()
        return
    words, page = await _dictionary_words(db, page, total_items)
    total_pages = (total_items + DICTIONARY_PAGE_SIZE - 1) // DICTIONARY_PAGE_SIZE
    await callback.message.edit_text(
        f"📖 <b>Lug‘at</b>\n\nSahifa: <b>{page + 1}/{total_pages}</b>\nSo‘z tanlang:",
        reply_markup=dictionary_kb(words, page, total_items),
    )
    await callback.answer()


@router.message(F.text.in_({'📖 Lug‘at', 'Lug‘at', 'Lugat'}))
@router.message(Command('lugat'))
async def dictionary_message(message: Message):
    await _send_dictionary(message)


@router.callback_query(F.data.startswith('dict:p:'))
async def dictionary_page_callback(callback: CallbackQuery):
    page = _parse_int((callback.data or '').split(':', 2)[2])
    await _edit_dictionary(callback, page)


@router.callback_query(F.data.startswith('dict:w:'))
async def dictionary_word_callback(callback: CallbackQuery):
    parts = (callback.data or '').split(':')
    if len(parts) != 4:
        await callback.answer("Tugma eskirgan. /start ni bosing.")
        return
    word_id = _parse_int(parts[2], default=-1)
    db = await get_db()
    word = await (await db.execute(
        'SELECT id, english, uzbek, category FROM vocabulary WHERE id = ?',
        (word_id,),
    )).fetchone()
    if not word:
        await callback.answer("So‘z topilmadi.", show_alert=True)
        return
    await callback.answer(dictionary_translation_text(word), show_alert=True)
