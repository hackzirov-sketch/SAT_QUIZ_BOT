from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from bot.formatting import mode_label, difficulty_label

def main_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text='🧠 Test boshlash')
    builder.button(text='🗓 Daily Challenge')
    builder.button(text='🏆 Reyting')
    builder.button(text='📊 Natijalarim')
    builder.button(text='📚 Statistika')
    builder.button(text='ℹ️ Yordam')
    builder.button(text='⚙️ Sozlamalar')
    builder.button(text='🔥 Duel')
    builder.adjust(2, 2, 2, 2)
    return builder.as_markup(resize_keyboard=True)

def start_kb(preferred_mode: str = '', preferred_difficulty: str = '') -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for mode in ['eng_uzb', 'uzb_eng']:
        for diff in ['easy', 'hard']:
            badge = ' ✅' if (mode == preferred_mode and diff == preferred_difficulty) else ''
            builder.button(text=f"{mode_label(mode)} • {difficulty_label(diff)}{badge}",
                           callback_data=f"start:{mode}:{diff}")
    builder.button(text='🧘 Cheksiz rejim', callback_data='chill')
    builder.button(text='📚 Xato qilgan so\'zlarim', callback_data='mistakes')
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()

def chill_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='🟢 Oson', callback_data='chill:easy')
    builder.button(text='🔴 Qiyin', callback_data='chill:hard')
    builder.button(text='🔄 Aralash', callback_data='chill:mixed')
    builder.button(text='◀️ Orqaga', callback_data='back_main')
    builder.adjust(2, 1, 1)
    return builder.as_markup()

def mistakes_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='🇬🇧 ENG → 🇺🇿 UZB', callback_data='mistakes:eng_uzb')
    builder.button(text='🇺🇿 UZB → 🇬🇧 ENG', callback_data='mistakes:uzb_eng')
    builder.button(text='◀️ Orqaga', callback_data='back_main')
    builder.adjust(1, 1, 1)
    return builder.as_markup()

CATEGORY_LABELS = {'all': 'Hamma', 'Algebra': 'Algebra', 'Geometry': 'Geometry', 'Statistics': 'Statistics', 'other': 'Boshqa'}

def category_kb(mode: str, difficulty: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in ['all', 'Algebra', 'Geometry', 'Statistics', 'other']:
        builder.button(text=CATEGORY_LABELS.get(cat, cat), callback_data=f"start:{mode}:{difficulty}:{cat}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def review_kb(attempt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='❌ Xatolarni ko\'rish', callback_data=f'review:{attempt_id}')]
    ])

def active_quiz_kb(attempt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='▶️ Davom ettirish', callback_data=f'active:continue:{attempt_id}')],
        [InlineKeyboardButton(text='🛑 Bekor qilish', callback_data=f'active:restart:{attempt_id}')],
    ])

def answer_kb(attempt_id: int, question_index: int, options: list) -> InlineKeyboardMarkup:
    letters = ['A', 'B', 'C', 'D']
    builder = InlineKeyboardBuilder()
    for i, opt in enumerate(options):
        builder.button(text=f"{letters[i]}) {opt}", callback_data=f"ans:{attempt_id}:{question_index}:{letters[i]}")
    builder.adjust(1)
    return builder.as_markup()

def settings_kb(settings: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Rejim: {mode_label(settings.get('preferred_mode', 'eng_uzb'))}", callback_data='settings:mode')
    builder.button(text=f"Qiyinlik: {difficulty_label(settings.get('preferred_difficulty', 'easy'))}", callback_data='settings:difficulty')
    builder.button(text='🇬🇧 ENG → 🇺🇿 UZB', callback_data='settings:setmode:eng_uzb')
    builder.button(text='🇺🇿 UZB → 🇬🇧 ENG', callback_data='settings:setmode:uzb_eng')
    builder.button(text='🟢 Oson', callback_data='settings:setdiff:easy')
    builder.button(text='🔴 Qiyin', callback_data='settings:setdiff:hard')
    sound = 'yoqilgan ✅' if settings.get('sound_enabled') else 'o\'chirilgan ❌'
    minimal = 'yoqilgan ✅' if settings.get('minimal_mode') else 'o\'chirilgan ❌'
    builder.button(text=f"Emoji: {sound}", callback_data='settings:toggle_sound')
    builder.button(text=f"Minimal: {minimal}", callback_data='settings:toggle_minimal')
    builder.adjust(2, 2, 2, 2, 2)
    return builder.as_markup()

def admin_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='📊 Statistika', callback_data='admin:stats')
    builder.button(text='👥 Faol foydalanuvchilar', callback_data='admin:active')
    builder.button(text='🏆 Reyting eksport', callback_data='admin:export')
    builder.button(text='🧹 Tozalash', callback_data='admin:clean')
    builder.button(text='📢 Kanal/Group', callback_data='admin:channels')
    builder.button(text='✅ Weekly yoqish', callback_data='admin:weekly_on')
    builder.button(text='⛔ Weekly o\'chirish', callback_data='admin:weekly_off')
    builder.button(text='🗓 Haftalik hisobot', callback_data='admin:weekly')
    builder.button(text='🔥 Duel natijalari', callback_data='admin:duels')
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()

def duel_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='⚔️ Raqib qidirish', callback_data='duel:find')
    builder.button(text='🔗 Kod orqali ulanish', callback_data='duel:join')
    builder.button(text='📊 Duel statistikasi', callback_data='duel:stats')
    builder.button(text='◀️ Orqaga', callback_data='back_main')
    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()

def duel_difficulty_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text='🟢 Oson', callback_data='duel:find:easy')
    builder.button(text='🔴 Qiyin', callback_data='duel:find:hard')
    builder.button(text='🔄 Aralash', callback_data='duel:find:mixed')
    builder.button(text='◀️ Orqaga', callback_data='back_main')
    builder.adjust(2, 1, 1)
    return builder.as_markup()
