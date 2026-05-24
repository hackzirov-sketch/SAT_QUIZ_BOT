import logging
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, ChatMemberUpdated, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import REQUIRED_SUBSCRIPTIONS, is_admin_id
from bot.database import get_db
from bot.services.subscription_service import invalidate_cache, missing_subscriptions

router = Router()
logger = logging.getLogger(__name__)


def subscription_keyboard(missing: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    for req in missing:
        link = req.get('link')
        if link:
            buttons.append([InlineKeyboardButton(text=f"📢 {req['title']}", url=link)])
    buttons.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data='check_sub')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subscription_text(missing: list[dict[str, Any]]) -> str:
    lines = [
        "🚫 <b>Botdan foydalanish cheklangan</b>",
        "",
        "Botdan foydalanish uchun quyidagi manbalarga obuna bo'ling:",
        "",
    ]
    for req in missing:
        lines.append(f"🔹 {req['title']}")
    lines.extend([
        "",
        "Obuna bo'lganingizdan keyin <b>✅ Obunani tekshirish</b> tugmasini bosing.",
        "Adminlar uchun cheklov mavjud emas.",
    ])
    return '\n'.join(lines)


_sub_required_cache: dict[int, tuple[bool, float]] = {}
_SUB_CACHE_TTL = 60.0


async def is_subscription_required(user_id: int) -> bool:
    import time

    now = time.monotonic()
    cached = _sub_required_cache.get(user_id)
    if cached and cached[1] > now:
        return cached[0]
    try:
        db = await get_db()
        cursor = await db.execute('SELECT subscription_required FROM users WHERE telegram_id = ?', (user_id,))
        row = await cursor.fetchone()
        result = bool(row['subscription_required']) if row is not None else True
    except Exception:
        result = True
    _sub_required_cache[user_id] = (result, now + _SUB_CACHE_TTL)
    return result


async def mark_subscription_ok(user_id: int):
    db = await get_db()
    await db.execute('UPDATE users SET subscription_required = 0 WHERE telegram_id = ?', (user_id,))
    await db.commit()
    invalidate_cache(user_id)


@router.my_chat_member()
async def bot_added_to_chat(event: ChatMemberUpdated):
    chat = event.chat
    if chat.type not in ('group', 'supergroup'):
        return
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO channel_config (chat_id, chat_type, chat_title, enabled) VALUES (?,?,?,1) "
            "ON CONFLICT(chat_id) DO UPDATE SET chat_title=excluded.chat_title",
            (chat.id, chat.type, chat.title or 'Group'),
        )
        await db.commit()
        logger.info("bot_added_to_chat chat_id=%s title=%s", chat.id, chat.title)
    except Exception:
        logger.exception("failed_to_save_channel_config chat_id=%s", chat.id)


@router.callback_query(F.data == 'check_sub')
async def check_sub_callback(callback: CallbackQuery):
    user = callback.from_user
    if is_admin_id(user.id):
        await mark_subscription_ok(user.id)
        await callback.message.edit_text("✅ <b>Admin sifatida barcha imkoniyatlar ochiq!</b>\n\n/start")
        await callback.answer()
        return

    missing = await missing_subscriptions(callback.bot, user.id, force_refresh=True)
    if not missing:
        await mark_subscription_ok(user.id)
        await callback.message.edit_text(
            "✅ <b>Barcha kanal va guruhlarga a'zosiz!</b>\n\n"
            "Endi botdan to'liq foydalanishingiz mumkin.\n\n/start"
        )
        await callback.answer()
        return

    await callback.message.edit_text(subscription_text(missing), reply_markup=subscription_keyboard(missing))
    await callback.answer()


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        if user is None:
            return await handler(event, data)

        if isinstance(event, Message):
            event_text = event.text or ''
        else:
            event_text = event.data or ''
        if event_text == 'check_sub':
            return await handler(event, data)

        if is_admin_id(user.id):
            return await handler(event, data)

        bot = data.get('bot')
        if not bot or not REQUIRED_SUBSCRIPTIONS:
            return await handler(event, data)

        missing = await missing_subscriptions(bot, user.id)
        if not missing:
            await mark_subscription_ok(user.id)
            return await handler(event, data)

        text = subscription_text(missing)
        keyboard = subscription_keyboard(missing)
        logger.info(
            "subscription_gate_shown user_id=%s missing_count=%s event_prefix=%s event_len=%s",
            user.id,
            len(missing),
            event_text.split(':', 1)[0][:32],
            len(event_text),
        )
        if isinstance(event, Message):
            await event.answer(text, reply_markup=keyboard)
        elif isinstance(event, CallbackQuery):
            if event.message:
                await event.message.edit_text(text, reply_markup=keyboard)
            await event.answer()
        return
