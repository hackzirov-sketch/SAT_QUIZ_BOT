import logging
import time
from typing import Any

from aiogram import BaseMiddleware, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, ChatMemberUpdated, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import REQUIRED_SUBSCRIPTIONS, SUBSCRIPTION_CACHE_TTL, is_admin_id
from bot.database import get_db

router = Router()
logger = logging.getLogger(__name__)

_subscription_cache: dict[tuple[int, str], tuple[bool, float]] = {}


def _cache_key(user_id: int, chat_id: Any) -> tuple[int, str]:
    return user_id, str(chat_id)


def _subscription_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for req in REQUIRED_SUBSCRIPTIONS:
        link = req.get('link')
        if link:
            buttons.append([InlineKeyboardButton(text=f"📢 {req['title']}", url=link)])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data='check_sub')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _subscription_text(missing: list[dict[str, Any]]) -> str:
    lines = ["⚠️ <b>Botdan foydalanish uchun quyidagilarga a'zo bo'ling:</b>", ""]
    for req in missing:
        lines.append(f"• {req['title']}")
    return '\n'.join(lines)


async def _is_subscribed(bot, user_id: int, req: dict[str, Any], *, force_refresh: bool = False) -> bool:
    chat_id = req.get('chat_id')
    if not chat_id:
        return True

    key = _cache_key(user_id, chat_id)
    cached = _subscription_cache.get(key)
    now = time.monotonic()
    if not force_refresh and cached and cached[1] > now:
        return cached[0]

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        ok = member.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)
    except TelegramAPIError as exc:
        logger.warning("subscription_check_failed chat_id=%s user_id=%s error=%s", chat_id, user_id, exc)
        ok = False

    ttl = SUBSCRIPTION_CACHE_TTL if ok else min(SUBSCRIPTION_CACHE_TTL, 60)
    if ttl > 0:
        _subscription_cache[key] = (ok, now + ttl)
    return ok


async def _missing_subscriptions(bot, user_id: int, *, force_refresh: bool = False) -> list[dict[str, Any]]:
    missing = []
    for req in REQUIRED_SUBSCRIPTIONS:
        if not await _is_subscribed(bot, user_id, req, force_refresh=force_refresh):
            missing.append(req)
    return missing


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
        await callback.message.edit_text("✅ <b>Admin sifatida barcha imkoniyatlar ochiq!</b>\n\n/start")
        await callback.answer()
        return

    missing = await _missing_subscriptions(callback.bot, user.id, force_refresh=True)
    if not missing:
        await callback.message.edit_text("✅ <b>Barcha kanal/guruhlarga a'zosiz! Botdan foydalanishingiz mumkin.</b>\n\n/start")
        await callback.answer()
        return

    await callback.message.edit_text(_subscription_text(missing), reply_markup=_subscription_keyboard())
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
            text = event.text or ''
        else:
            text = event.data or ''
        if text.startswith('/start') or text == 'check_sub':
            return await handler(event, data)

        if is_admin_id(user.id):
            return await handler(event, data)

        bot = data.get('bot')
        if not bot or not REQUIRED_SUBSCRIPTIONS:
            return await handler(event, data)

        missing = await _missing_subscriptions(bot, user.id)
        if not missing:
            return await handler(event, data)

        text = _subscription_text(missing)
        keyboard = _subscription_keyboard()
        if isinstance(event, Message):
            await event.answer(text, reply_markup=keyboard)
        elif isinstance(event, CallbackQuery):
            if event.message:
                await event.message.edit_text(text, reply_markup=keyboard)
            await event.answer()
        return
