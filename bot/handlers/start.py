import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from bot.database import get_db
from bot.utils.db_helpers import upsert_user
from bot.keyboards import active_quiz_kb, future_plan_kb, main_menu_kb, start_kb
from bot.services.active_session_service import get_resumable_attempt
from bot.services.attempt_service import finish_attempt

router = Router()
logger = logging.getLogger(__name__)


async def send_start_menu(message: Message):
    db = await get_db()
    await upsert_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
    logger.info("start_menu_sent user_id=%s username=%s", message.from_user.id, message.from_user.username)
    await message.answer(
        "🧠 <b>SAT LUĠĞAT QUIZ BOT</b>\n\nSAT Matematika terminlariga ixtisoslashgan lug'at testi.\n\n"
        "🏆 <b>Yangi:</b> XP & Level, Daily Challenge, Duel, Cheksiz rejim!\n\n"
        "Boshlash uchun <b>🧠 Test boshlash</b> tugmasini bosing.",
        reply_markup=main_menu_kb(),
    )


@router.message(CommandStart())
@router.message(F.text.regexp(r'^/start(?:@\w+)?(?:\s+.*)?$'))
async def cmd_start(message: Message):
    await send_start_menu(message)

@router.message(F.text == '🧠 Test boshlash')
@router.message(Command('quiz'))
async def test_boshlash(message: Message):
    db = await get_db()
    user = await upsert_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
    attempt, _session = await get_resumable_attempt(db, user['id'])
    if attempt:
        await message.answer(
            'Sizda faol test bor. Davom ettirasizmi yoki yangidan boshlaysizmi?',
            reply_markup=active_quiz_kb(attempt['id']),
        )
        return
    cursor = await db.execute('SELECT preferred_mode, preferred_difficulty FROM settings WHERE user_id = ?', (user['id'],))
    s = await cursor.fetchone()
    pref_mode = s['preferred_mode'] if s else 'eng_uzb'
    pref_diff = s['preferred_difficulty'] if s else 'easy'
    await message.answer(
        '📘 <b>Test sozlamalari</b>\n\nRejim va qiyinlik darajasini tanlang:',
        reply_markup=start_kb(pref_mode, pref_diff),
    )

@router.message(F.text == '🚀 Kelajak uchun rejalar')
async def future_plans(message: Message):
    await message.answer(
        "🚀 <b>Kelajak uchun rejalar</b>\n\n"
        "Tez orada botimizga yangi imkoniyatlar qo'shiladi:\n\n"
        "🤖 <b>AI Mentor</b>\n"
        "— Savollaringizga tushunarli izoh beradi va o'rganishingizga yordam beradi.\n\n"
        "📝 <b>Mock test</b>\n"
        "— SAT uslubidagi to'liq sinov testlari va natijalar tahlili.\n\n"
        "📖 <b>Reading so'zlari</b>\n"
        "— Reading bo'limi uchun eng kerakli akademik so'zlar.\n\n"
        "⚔️ <b>Duel</b>\n"
        "— Do'stlaringiz bilan bilim bo'yicha bellashish imkoniyati.\n\n"
        "🚀 <b>Rivojlantirishlar</b>\n"
        "— Reyting, yutuqlar, streak, statistika va boshqa foydali funksiyalar.\n\n"
        "Hozircha asosiy testlardan foydalanishda davom etishingiz mumkin ✅",
        reply_markup=future_plan_kb(),
    )


@router.message(F.text == 'ℹ️ Yordam')
@router.message(Command('help'))
async def yordam(message: Message):
    await message.answer(
        "ℹ️ <b>Yordam</b>\n\n"
        "🧠 Test boshlash — standart 50 savol\n"
        "📝 Mock test — SAT Math 2 modul\n"
        "🗓 Daily Challenge — kungi 10 savol\n"
        "🏆 Reyting — eng yaxshi 10\n"
        "📊 Natijalarim — oxirgi va eng yaxshi\n"
        "📚 Statistika — XP, level, tahlil\n"
        "⚙️ Sozlamalar — rejim va qiyinlik\n\n"
        "Buyruqlar: /quiz /mock /daily /rating /result /stats /settings /cancel",
        reply_markup=main_menu_kb(),
    )

@router.callback_query(F.data == 'back_main')
async def back_main(callback: CallbackQuery):
    try:
        await callback.message.edit_text('🧠 <b>Asosiy menyu</b>')
    except Exception:
        logger.exception("back_main_edit_failed user_id=%s", callback.from_user.id)
    await callback.answer()

@router.message(Command('cancel'))
async def cancel(message: Message):
    db = await get_db()
    user = await upsert_user(db, message.from_user.id, message.from_user.username, message.from_user.first_name)
    cursor = await db.execute(
        'SELECT s.* FROM active_sessions s JOIN attempts a ON a.id = s.attempt_id '
        'WHERE s.user_id = ? AND s.status = ? AND a.status = ?', (user['id'], 'active', 'active'))
    active = await cursor.fetchone()
    if active:
        await finish_attempt(db, active['attempt_id'], 'cancelled')
    await message.answer('🛑 Faol test bekor qilindi.', reply_markup=main_menu_kb())
