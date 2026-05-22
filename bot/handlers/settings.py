from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from bot.database import get_db, now_iso
from bot.utils.db_helpers import upsert_user
from bot.keyboards import settings_kb
from bot.formatting import mode_label, difficulty_label

router = Router()

def _settings_text(s: dict) -> str:
    mode = mode_label(s.get('preferred_mode', 'eng_uzb'))
    diff = difficulty_label(s.get('preferred_difficulty', 'easy'))
    sound = '✅ Yoqilgan' if s.get('sound_enabled') else '❌ O\'chirilgan'
    minimal = '✅ Yoqilgan' if s.get('minimal_mode') else '❌ O\'chirilgan'
    qty = s.get('question_count', 50)
    return (
        f"⚙️ <b>Sozlamalar</b>\n\n"
        f"📘 <b>Rejim:</b> {mode}\n"
        f"🎯 <b>Qiyinlik:</b> {diff}\n"
        f"📝 <b>Savollar:</b> {qty}\n"
        f"🔊 <b>Emoji:</b> {sound}\n"
        f"📏 <b>Minimal:</b> {minimal}"
    )

@router.message(F.text == '⚙️ Sozlamalar')
@router.message(Command('settings'))
async def settings_menu(message: Message):
    async with await get_db() as db:
        user = await upsert_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
        cursor = await db.execute('SELECT * FROM settings WHERE user_id = ?', (user['id'],))
        s = await cursor.fetchone()
    if not s:
        s = {'preferred_mode': 'eng_uzb', 'preferred_difficulty': 'easy', 'question_count': 50, 'sound_enabled': 1, 'minimal_mode': 0}
    await message.answer(_settings_text(dict(s)), reply_markup=settings_kb(dict(s)))

@router.callback_query(F.data.startswith('settings:'))
async def settings_callback(callback: CallbackQuery):
    data = callback.data
    async with await get_db() as db:
        user = await upsert_user(db, callback.from_user.id, callback.from_user.username, callback.from_user.first_name)

        if data == 'settings:mode':
            await callback.answer('Rejimni tanlang.')
            return
        elif data == 'settings:difficulty':
            await callback.answer('Qiyinlikni tanlang.')
            return
        elif data == 'settings:setmode:eng_uzb':
            await db.execute('UPDATE settings SET preferred_mode = ?, updated_at = ? WHERE user_id = ?', ('eng_uzb', now_iso(), user['id']))
            await db.commit()
            await callback.answer('Rejim yangilandi.')
        elif data == 'settings:setmode:uzb_eng':
            await db.execute('UPDATE settings SET preferred_mode = ?, updated_at = ? WHERE user_id = ?', ('uzb_eng', now_iso(), user['id']))
            await db.commit()
            await callback.answer('Rejim yangilandi.')
        elif data == 'settings:setdiff:easy':
            await db.execute('UPDATE settings SET preferred_difficulty = ?, updated_at = ? WHERE user_id = ?', ('easy', now_iso(), user['id']))
            await db.commit()
            await callback.answer('Oson.')
        elif data == 'settings:setdiff:hard':
            await db.execute('UPDATE settings SET preferred_difficulty = ?, updated_at = ? WHERE user_id = ?', ('hard', now_iso(), user['id']))
            await db.commit()
            await callback.answer('Qiyin.')
        elif data == 'settings:toggle_sound':
            cur = await (await db.execute('SELECT sound_enabled FROM settings WHERE user_id = ?', (user['id'],))).fetchone()
            await db.execute('UPDATE settings SET sound_enabled = ?, updated_at = ? WHERE user_id = ?', (0 if cur['sound_enabled'] else 1, now_iso(), user['id']))
            await db.commit()
            await callback.answer('Yangilandi.')
        elif data == 'settings:toggle_minimal':
            cur = await (await db.execute('SELECT minimal_mode FROM settings WHERE user_id = ?', (user['id'],))).fetchone()
            await db.execute('UPDATE settings SET minimal_mode = ?, updated_at = ? WHERE user_id = ?', (0 if cur['minimal_mode'] else 1, now_iso(), user['id']))
            await db.commit()
            await callback.answer('Yangilandi.')
        # Refresh
        cursor = await db.execute('SELECT * FROM settings WHERE user_id = ?', (user['id'],))
        s = await cursor.fetchone()
    if s:
        try:
            await callback.message.edit_text(_settings_text(dict(s)), reply_markup=settings_kb(dict(s)))
        except:
            pass
