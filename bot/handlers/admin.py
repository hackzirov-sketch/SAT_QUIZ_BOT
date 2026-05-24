import os
import time
from datetime import datetime, timedelta, timezone
from html import escape

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from bot.database import get_db
from bot.config import DATABASE_PATH, is_admin_id
from bot.keyboards import admin_kb
from bot.formatting import format_seconds
from bot.services.health_service import admin_diagnostics
from bot.services.subscription_service import cache_stats as subscription_cache_stats
from bot.services.weekly_report_service import send_weekly_report

router = Router()
bot_instance = None
_admin_last_action: dict[int, float] = {}
_ADMIN_COOLDOWN_SECONDS = 1.0

def set_bot(b):
    global bot_instance
    bot_instance = b

def is_admin(user_id: int) -> bool:
    return is_admin_id(user_id)


def _admin_allowed(user_id: int) -> bool:
    now = time.monotonic()
    last = _admin_last_action.get(user_id, 0.0)
    if now - last < _ADMIN_COOLDOWN_SECONDS:
        return False
    _admin_last_action[user_id] = now
    return True


async def _audit_admin_action(db, actor_id: int | None, action: str, chat_id: int | None) -> None:
    await db.execute(
        'INSERT INTO admin_audit_log (actor_id, action, chat_id, created_at) VALUES (?,?,?,?)',
        (actor_id or 0, action[:64], chat_id or 0, datetime.now(timezone.utc).isoformat()),
    )
    await db.commit()


def _chat_type_value(msg) -> str:
    return getattr(msg.chat.type, 'value', str(msg.chat.type))


def _chat_title(msg) -> str:
    return (
        getattr(msg.chat, 'title', None)
        or getattr(msg.chat, 'username', None)
        or getattr(msg.chat, 'full_name', None)
        or str(msg.chat.id)
    )


async def _set_weekly_chat(db, msg, enabled: bool) -> str:
    chat_type = _chat_type_value(msg)
    if chat_type == 'private':
        return "Bu buyruq guruh ichida ishlaydi. Botni guruhga qo'shing va guruhda /admin weekly_on yuboring."

    title = _chat_title(msg)
    await db.execute(
        '''
        INSERT INTO channel_config (chat_id, chat_type, chat_title, enabled, weekly_report)
        VALUES (?, ?, ?, 1, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
          chat_type = excluded.chat_type,
          chat_title = excluded.chat_title,
          enabled = 1,
          weekly_report = excluded.weekly_report
        ''',
        (msg.chat.id, chat_type, title, 1 if enabled else 0),
    )
    await db.commit()

    if enabled:
        return (
            f"✅ Haftalik hisobot yoqildi: <b>{escape(title)}</b>\n"
            "Har dushanba 09:00 da reyting va duel natijalari shu guruhga yuboriladi.\n"
            "Tekshirish uchun: /admin weekly"
        )
    return f"⛔ Haftalik hisobot o'chirildi: <b>{escape(title)}</b>"

@router.message(Command('admin'))
async def admin_command(message: Message):
    if not is_admin(message.from_user.id):
        await message.reply('Admin emas.')
        return
    text = message.text or ''
    parts = text.split()
    action = parts[1] if len(parts) > 1 else ''
    payload = ' '.join(parts[2:]) if len(parts) > 2 else ''

    if not action:
        await message.reply(
            "🛡 <b>Admin panel</b>\n\n"
            "/admin stats\n"
            "/admin active\n"
            "/admin clean [kun]\n"
            "/admin channels\n"
            "/admin weekly_on\n"
            "/admin weekly_off\n"
            "/admin weekly\n"
            "/admin duels\n"
            "/admin diagnostics",
            reply_markup=admin_kb())
        return

    if not _admin_allowed(message.from_user.id):
        await message.reply('Juda tez. Bir soniyadan keyin urinib ko\'ring.')
        return
    await _handle_admin_action(message, action, payload, actor_id=message.from_user.id)

@router.callback_query(F.data.startswith('admin:'))
async def admin_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer('Admin emas.')
        return
    action = callback.data.split(':', 1)[1]
    if not _admin_allowed(callback.from_user.id):
        await callback.answer('Juda tez.')
        return
    await callback.answer()
    await _handle_admin_action(callback.message, action, '', actor_id=callback.from_user.id)

async def _handle_admin_action(msg, action: str, payload: str = '', actor_id: int | None = None):
    db = await get_db()
    await _audit_admin_action(db, actor_id, action, getattr(msg.chat, 'id', None) if msg else None)
    if action == 'stats':
        c = await _admin_counts(db)
        await msg.reply(
            f"📊 <b>Admin</b>\n\n"
            f"👥 Foydalanuvchilar: <b>{c['users']}</b>\n"
            f"🧠 Testlar: <b>{c['attempts']}</b>\n"
            f"✅ Tugagan: <b>{c['finished_attempts']}</b>\n"
            f"⏱ Faol: <b>{c['active_sessions']}</b>\n"
            f"📝 Javoblar: <b>{c['answers']}</b>\n"
            f"📚 Lug'at: <b>{c['vocab']}</b>")

    elif action == 'diagnostics':
        diag = await admin_diagnostics()
        cache = subscription_cache_stats()
        await msg.reply(
            "<b>Diagnostics</b>\n\n"
            f"DB: {'OK' if diag['db_alive'] else 'FAIL'}\n"
            f"Integrity: {'OK' if diag['db_integrity_ok'] else 'FAIL'}\n"
            f"Polling: {'OK' if diag['polling_alive'] else 'OFF'}\n"
            f"Vocab: {diag['vocabulary_count']}\n"
            f"DB size: {diag['db_size']} bytes\n"
            f"WAL size: {diag['wal_size']} bytes\n"
            f"Uptime: {diag['uptime_seconds']}s\n"
            f"Subscription cache: {cache['subscription_cache_entries']}"
        )

    elif action == 'active':
        rows = await (await db.execute(
            'SELECT s.*, u.telegram_id, u.username, u.first_name, a.current_index, a.total_questions, a.mode '
            'FROM active_sessions s JOIN users u ON u.id = s.user_id JOIN attempts a ON a.id = s.attempt_id '
            'WHERE s.status = ? AND a.status = ? ORDER BY s.expires_at ASC', ('active', 'active'))).fetchall()
        if not rows:
            await msg.reply('Faol testlar yo\'q.')
            return
        lines = ['👥 <b>Faol testlar</b>', '']
        for row in rows[:20]:
            remaining = max(0, row['expires_at'] - int(time.time())) if row['expires_at'] else 0
            name = f"@{row['username']}" if row['username'] else (row['first_name'] or 'Foydalanuvchi')
            lines.append(f"• {name} — {row['current_index']}/{row['total_questions']} — {row['mode']} — {format_seconds(remaining)}")
        await msg.reply('\n'.join(lines))

    elif action == 'clean':
        days = int(payload) if payload.isdigit() else 30
        res = await _clean_old_data(db, days)
        total_del = sum(res['deleted'].values())
        size_kb = os.path.getsize(DATABASE_PATH) / 1024 if os.path.exists(DATABASE_PATH) else 0
        await msg.reply(f"🧹 Tozalandi! {total_del} ta o'chirildi. DB: {size_kb:.1f} KB")

    elif action == 'channels':
        channels = await (await db.execute('SELECT * FROM channel_config WHERE enabled = 1')).fetchall()
        lines = [
            '📢 <b>Kanal/Group sozlamalari</b>\n',
            'Guruhda /admin weekly_on yuborsangiz haftalik hisobot yoqiladi.',
            'O\'chirish: /admin weekly_off',
            'Qo\'lda yuborish: /admin weekly',
            '',
            '/admin add_chat <chat_id> <type> <title>',
            '/admin remove_chat <chat_id>',
            '',
        ]
        if channels:
            lines.append('Faol kanallar:')
            for ch in channels:
                lines.append(f"• {ch['chat_title'] or 'N/A'} ({ch['chat_id']}) — {ch['chat_type']} — Weekly: {'✅' if ch['weekly_report'] else '❌'}")
        await msg.reply('\n'.join(lines))

    elif action == 'add_chat':
        parts = payload.split()
        if len(parts) < 2:
            await msg.reply('Format: /admin add_chat <id> <type> <title>')
            return
        try:
            chat_id = int(parts[0])
        except ValueError:
            await msg.reply('Chat ID raqam bo\'lishi kerak.')
            return
        chat_type = parts[1]
        title = ' '.join(parts[2:]) if len(parts) > 2 else None
        await db.execute(
            "INSERT INTO channel_config (chat_id, chat_type, chat_title, enabled, weekly_report) VALUES (?,?,?,1,0) ON CONFLICT(chat_id) DO UPDATE SET chat_type=excluded.chat_type, chat_title=excluded.chat_title",
            (chat_id, chat_type, title))
        await db.commit()
        await msg.reply(f'✅ Kanal qo\'shildi: {chat_id}')

    elif action == 'remove_chat':
        try:
            chat_id = int(payload.strip())
        except ValueError:
            await msg.reply('ID kiriting.')
            return
        await db.execute('DELETE FROM channel_config WHERE chat_id = ?', (chat_id,))
        await db.commit()
        await msg.reply(f'✅ O\'chirildi: {chat_id}')

    elif action == 'weekly':
        if not bot_instance:
            await msg.reply('Bot ishga tushmagan.')
            return
        result = await send_weekly_report(db, bot_instance)
        await msg.reply(result)

    elif action == 'weekly_on':
        result = await _set_weekly_chat(db, msg, True)
        await msg.reply(result)

    elif action == 'weekly_off':
        result = await _set_weekly_chat(db, msg, False)
        await msg.reply(result)

    elif action == 'duels':
        duels = await (await db.execute(
            'SELECT d.*, u1.username AS p1name, u1.first_name AS p1first, u2.username AS p2name, u2.first_name AS p2first '
            'FROM duel_matches d LEFT JOIN users u1 ON u1.id = d.player1_id LEFT JOIN users u2 ON u2.id = d.player2_id '
            'WHERE d.status = ? ORDER BY d.finished_at DESC LIMIT 20', ('finished',))).fetchall()
        if not duels:
            await msg.reply('Duel yo\'q.')
            return
        lines = ['🔥 <b>Duellar</b>\n']
        for d in duels:
            p1 = d['p1name'] or d['p1first'] or 'P1'
            p2 = d['p2name'] or d['p2first'] or 'P2'
            lines.append(f"• {p1} {d['player1_score']} - {d['player2_score']} {p2}")
        await msg.reply('\n'.join(lines))

    else:
        await msg.reply('Noma\'lum buyruq.')

async def _admin_counts(db):
    rows = await (await db.execute(
        "SELECT 'users' AS k, COUNT(*) AS v FROM users UNION ALL "
        "SELECT 'attempts', COUNT(*) FROM attempts UNION ALL "
        "SELECT 'finished_attempts', COUNT(*) FROM attempts WHERE status IN ('completed','timed_out') UNION ALL "
        "SELECT 'active_sessions', COUNT(*) FROM active_sessions WHERE status='active' UNION ALL "
        "SELECT 'answers', COUNT(*) FROM answers")).fetchall()
    result = {'vocab': 0}
    for r in rows:
        result[r['k']] = r['v']
    cursor = await db.execute('SELECT COUNT(*) AS c FROM vocabulary')
    row = await cursor.fetchone()
    if row:
        result['vocab'] = row['c']
    return result

async def _clean_old_data(db, days_old: int = 30):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
    old_ids = [r['id'] for r in await (await db.execute(
        "SELECT id FROM attempts WHERE status IN ('completed','timed_out','cancelled') AND finished_at < ?", (cutoff,))).fetchall()]
    result = {'answers': 0, 'question_history': 0, 'attempts': 0, 'active_sessions': 0}
    if old_ids:
        placeholders = ','.join('?' * len(old_ids))
        result['answers'] = (await (await db.execute(f'SELECT COUNT(*) AS c FROM answers WHERE attempt_id IN ({placeholders})', old_ids)).fetchone())['c']
        await db.execute(f'DELETE FROM answers WHERE attempt_id IN ({placeholders})', old_ids)
        result['active_sessions'] = (await (await db.execute(f'SELECT COUNT(*) AS c FROM active_sessions WHERE attempt_id IN ({placeholders})', old_ids)).fetchone())['c']
        await db.execute(f'DELETE FROM active_sessions WHERE attempt_id IN ({placeholders})', old_ids)
        result['attempts'] = len(old_ids)
        await db.execute(f'DELETE FROM attempts WHERE id IN ({placeholders})', old_ids)
        await db.commit()
    return {'deleted': result}
