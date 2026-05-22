import json
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from bot.database import get_db
from bot.utils.db_helpers import upsert_user, weakness_data
from bot.quiz_engine import level_name
from bot.formatting import mode_label, format_seconds, weakness_text
from bot.keyboards import main_menu_kb

router = Router()

@router.message(F.text == '📚 Statistika')
@router.message(Command('stats'))
async def statistika(message: Message):
    async with await get_db() as db:
        user = await upsert_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
        cursor = await db.execute('SELECT * FROM statistics WHERE user_id = ?', (user['id'],))
        stats = await cursor.fetchone()
        analysis = await weakness_data(db, user['id'])

    if not stats:
        await message.answer('Hali test ishlamagansiz.', reply_markup=main_menu_kb())
        return

    lines = [
        '📊 <b>Statistika</b>\n',
        f"⭐ <b>XP:</b> {stats['xp']} ({level_name(stats['level'])})",
        f"🧠 Testlar: {stats['attempts_count']}",
        f"✅ To'g'ri: {stats['correct_answers']}",
        f"❌ Xato: {stats['wrong_answers']}",
        f"🎯 Eng yaxshi: {stats['best_score']}/100",
        f"🏅 Seriya: {stats['current_win_streak']} (eng: {stats['best_win_streak']})",
        f"🗓 Daily seriya: {stats['daily_streak']}",
    ]
    if stats['best_time']:
        lines.append(f"⏱ Eng yaxshi vaqt: {format_seconds(stats['best_time'])}")
    await message.answer('\n'.join(lines), reply_markup=main_menu_kb())

    # weakness analysis
    if analysis:
        await message.answer(weakness_text([dict(a) for a in analysis]))

@router.message(F.text == '📊 Natijalarim')
@router.message(Command('result'))
async def natijalarim(message: Message):
    async with await get_db() as db:
        user = await upsert_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
        cursor = await db.execute(
            "SELECT * FROM attempts WHERE user_id = ? AND status IN ('completed','timed_out') ORDER BY finished_at DESC LIMIT 1",
            (user['id'],))
        latest = await cursor.fetchone()
        cursor = await db.execute(
            "SELECT * FROM attempts WHERE user_id = ? AND status IN ('completed','timed_out') ORDER BY score DESC, completion_seconds ASC LIMIT 1",
            (user['id'],))
        best = await cursor.fetchone()
    if not latest:
        await message.answer('📊 Hali test yo\'q.', reply_markup=main_menu_kb())
        return
    def line(title, a):
        if not a:
            return f'{title}: —'
        return f'{title}: <b>{a["score"]}/100</b> — {mode_label(a["mode"])} — {format_seconds(a["completion_seconds"] or 0)}'
    await message.answer(f'📊 <b>Mening natijalarim</b>\n\n{line("So\'nggi", latest)}\n{line("Eng yaxshi", best)}')

@router.message(F.text == '🏆 Reyting')
@router.message(Command('rating'))
async def reyting(message: Message):
    async with await get_db() as db:
        user = await upsert_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
        cursor = await db.execute(
            'SELECT l.*, u.username, u.first_name FROM leaderboard l JOIN users u ON u.id = l.user_id ORDER BY l.score DESC, l.completion_seconds ASC, l.finished_at ASC LIMIT 10')
        lb = await cursor.fetchall()
        cursor = await db.execute(
            'SELECT s.xp, s.level, u.telegram_id, u.username, u.first_name FROM statistics s JOIN users u ON u.id = s.user_id WHERE s.xp > 0 ORDER BY s.xp DESC LIMIT 10')
        xp_lb = await cursor.fetchall()
    lines = ['🏆 <b>Reyting</b>\n']
    for i, r in enumerate(lb):
        name = f"@{r['username']}" if r['username'] else (r['first_name'] or 'User')
        lines.append(f"{i+1}. {name} — {r['score']}/100")
    await message.answer('\n'.join(lines))
    if xp_lb:
        xlines = ['⭐ <b>XP Reytingi</b>\n']
        for i, r in enumerate(xp_lb):
            name = f"@{r['username']}" if r['username'] else (r['first_name'] or 'User')
            xlines.append(f"{i+1}. {name} — {r['xp']} XP ({level_name(r['level'])})")
        await message.answer('\n'.join(xlines))
