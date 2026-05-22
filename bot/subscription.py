import logging
from aiogram import Router, BaseMiddleware, F
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ChatMemberStatus
from bot.config import REQUIRED_SUBSCRIPTIONS
from bot.database import get_db, now_iso

router = Router()

@router.my_chat_member()
async def bot_added_to_chat(event: ChatMemberUpdated):
    chat = event.chat
    if chat.type in ('group', 'supergroup'):
        db = await get_db()
        try:
            await db.execute(
                "INSERT INTO channel_config (chat_id, chat_type, chat_title, enabled) VALUES (?,?,?,1) ON CONFLICT(chat_id) DO UPDATE SET chat_title=excluded.chat_title",
                (chat.id, chat.type, chat.title or 'Group'))
            await db.commit()
            logging.info(f"Bot added to group: {chat.id} ({chat.title})")
        except:
            pass

@router.callback_query(F.data == 'check_sub')
async def check_sub_callback(callback: CallbackQuery):
    bot = callback.bot
    user = callback.from_user
    missing = []
    for req in REQUIRED_SUBSCRIPTIONS:
        chat_id = req.get('chat_id')
        if not chat_id:
            missing.append(req)
            continue
        try:
            member = await bot.get_chat_member(chat_id, user.id)
            if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
                missing.append(req)
        except:
            missing.append(req)
    if not missing:
        await callback.message.edit_text("✅ <b>Barcha kanal/guruhlarga a'zosiz! Botdan foydalanishingiz mumkin.</b>\n\n/start")
        await callback.answer()
        return
    lines = ["⚠️ <b>Hali quyidagilarga a'zo emassiz:</b>\n"]
    kb_buttons = []
    for req in REQUIRED_SUBSCRIPTIONS:
        lines.append(f"🔹 {req['title']}")
        kb_buttons.append([InlineKeyboardButton(text=f"📢 {req['title']}", url=req['link'])])
    kb_buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data='check_sub')])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await callback.message.edit_text('\n'.join(lines), reply_markup=kb)
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

        text = ''
        if isinstance(event, Message):
            text = event.text or ''
        elif isinstance(event, CallbackQuery):
            text = event.data or ''

        if text.startswith('/start') or text == 'check_sub':
            return await handler(event, data)

        bot = data.get('bot')
        if not bot or not REQUIRED_SUBSCRIPTIONS:
            return await handler(event, data)

        missing = []
        for req in REQUIRED_SUBSCRIPTIONS:
            chat_id = req.get('chat_id')
            if not chat_id:
                missing.append(req)
                continue
            try:
                member = await bot.get_chat_member(chat_id, user.id)
                if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
                    missing.append(req)
            except:
                missing.append(req)

        if not missing:
            return await handler(event, data)

        lines = ["⚠️ <b>Botdan foydalanish uchun quyidagi kanal/guruhlarga a'zo bo'ling:</b>\n"]
        kb_buttons = []
        for req in REQUIRED_SUBSCRIPTIONS:
            lines.append(f"🔹 {req['title']}")
            kb_buttons.append([InlineKeyboardButton(text=f"📢 {req['title']}", url=req['link'])])
        kb_buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data='check_sub')])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

        if isinstance(event, Message):
            await event.answer('\n'.join(lines), reply_markup=kb)
        elif isinstance(event, CallbackQuery):
            await event.message.edit_text('\n'.join(lines), reply_markup=kb)
            await event.answer()
        return