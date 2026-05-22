import json
import logging
import time
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from bot.database import get_db, now_iso
from bot.config import ADMIN_IDS
from bot.keyboards import admin_kb
from bot.formatting import format_seconds

router = Router()
bot_instance = None

def set_bot(b):
    global bot_instance
    bot_instance = b

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

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
            "🛡 <b>Admin panel</b>\n\n/admin stats\n/admin active\n/admin clean [kun]\n/admin channels\n/admin weekly\n/admin duels",
            reply_markup=admin_kb())
        return

    await _handle_admin_action(message, action, payload)

@router.callback_query(F.data.startswith('admin:'))
async def admin_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer('Admin emas.')
        return
    action = callback.data.split(':', 1)[1]
    await callback.answer()
    await _handle_admin_action(callback.message, action, '')

async def _handle_admin_action(msg, action: str, payload: str = ''):
    db = await get_db()
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
            # Get DB size
            import os
            from bot.config import DATABASE_PATH
            size_kb = os.path.getsize(DATABASE_PATH) / 1024 if os.path.exists(DATABASE_PATH) else 0
            await msg.reply(f"🧹 Tozalandi! {total_del} ta o'chirildi. DB: {size_kb:.1f} KB")

        elif action == 'channels':
            channels = await (await db.execute('SELECT * FROM channel_config WHERE enabled = 1')).fetchall()
            lines = ['📢 <b>Kanal/Group sozlamalari</b>\n\n/admin add_chat <chat_id> <type> <title>\n/admin remove_chat <chat_id>\n']
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
            chat_id = int(parts[0])
            chat_type = parts[1]
            title = ' '.join(parts[2:]) if len(parts) > 2 else None
            await db.execute(
                "INSERT INTO channel_config (chat_id, chat_type, chat_title, enabled, weekly_report) VALUES (?,?,?,1,0) ON CONFLICT(chat_id) DO UPDATE SET chat_type=excluded.chat_type, chat_title=excluded.chat_title",
                (chat_id, chat_type, title))
            await db.commit()
            await msg.reply(f'✅ Kanal qo\'shildi: {chat_id}')

        elif action == 'remove_chat':
            chat_id = payload.strip()
            if not chat_id.isdigit():
                await msg.reply('ID kiriting.')
                return
            await db.execute('DELETE FROM channel_config WHERE chat_id = ?', (int(chat_id),))
            await db.commit()
            await msg.reply(f'✅ O\'chirildi: {chat_id}')

        elif action == 'weekly':
            if not bot_instance:
                await msg.reply('Bot ishga tushmagan.')
                return
            result = await _send_weekly_report(db)
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
    from datetime import datetime, timezone, timedelta
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

async def _send_weekly_report(db):
    channels = await (await db.execute('SELECT * FROM channel_config WHERE enabled = 1 AND weekly_report = 1')).fetchall()
    if not channels:
        return 'Haftalik hisobot uchun kanal sozlanmagan.'
    lb = await (await db.execute(
        'SELECT l.*, u.username, u.first_name FROM leaderboard l JOIN users u ON u.id = l.user_id ORDER BY l.score DESC, l.completion_seconds ASC LIMIT 20'
    )).fetchall()
    xp_lb = await (await db.execute(
        'SELECT s.xp, s.level, u.telegram_id, u.username, u.first_name FROM statistics s JOIN users u ON u.id = s.user_id WHERE s.xp > 0 ORDER BY s.xp DESC LIMIT 20'
    )).fetchall()
    duels = await (await db.execute(
        'SELECT d.*, u1.username AS p1name, u1.first_name AS p1first, u2.username AS p2name, u2.first_name AS p2first '
        'FROM duel_matches d LEFT JOIN users u1 ON u1.id = d.player1_id LEFT JOIN users u2 ON u2.id = d.player2_id '
        'WHERE d.status = ? ORDER BY d.finished_at DESC LIMIT 5', ('finished',))).fetchall()
    c = await _admin_counts(db)

    lines = [
        '📊 <b>Haftalik hisobot</b> 📊\n',
        f'👥 Jami foydalanuvchilar: {c["users"]}',
        f'🧠 Jami testlar: {c["attempts"]}',
        f'✅ Tugagan: {c["finished_attempts"]}',
        '',
        '🏆 <b>TOP 20</b>',
    ]
    for i, r in enumerate(lb):
        name = f"@{r['username']}" if r['username'] else (r['first_name'] or 'User')
        lines.append(f"{i+1}. {name} — {r['score']}/100")
    lines.extend(['', '⭐ <b>XP TOP 20</b>'])
    for i, r in enumerate(xp_lb):
        name = f"@{r['username']}" if r['username'] else (r['first_name'] or 'User')
        lines.append(f"{i+1}. {name} — {r['xp']} XP")
    if duels:
        lines.extend(['', '🔥 <b>Duellar</b>'])
        for d in duels:
            p1 = d['p1name'] or d['p1first'] or 'P1'
            p2 = d['p2name'] or d['p2first'] or 'P2'
            lines.append(f"• {p1} {d['player1_score']} - {d['player2_score']} {p2}")
    text = '\n'.join(lines)
    sent = 0
    for ch in channels:
        try:
            await bot_instance.send_message(ch['chat_id'], text, parse_mode='HTML')
            sent += 1
        except Exception as e:
            logging.error(f"Failed to send weekly to {ch['chat_id']}: {e}")
    return f"✅ Hisobot {sent}/{len(channels)} kanalga yuborildi."
