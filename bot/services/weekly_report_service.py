import asyncio
import logging
from datetime import datetime, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram.exceptions import TelegramAPIError

from bot.config import (
    TZ,
    WEEKLY_REPORT_ENABLED,
    WEEKLY_REPORT_HOUR,
    WEEKLY_REPORT_MINUTE,
    WEEKLY_REPORT_WEEKDAY,
)
from bot.database import get_db
from bot.formatting import format_seconds

logger = logging.getLogger(__name__)


def _tzinfo() -> ZoneInfo:
    try:
        return ZoneInfo(TZ)
    except ZoneInfoNotFoundError:
        logger.warning("timezone_not_found tz=%s fallback=UTC", TZ)
        return ZoneInfo("UTC")


def _name(row) -> str:
    username = row['username'] if 'username' in row.keys() else None
    first_name = row['first_name'] if 'first_name' in row.keys() else None
    if username:
        return escape(f"@{username}")
    return escape(first_name or 'User')


async def build_weekly_report_text(db) -> str:
    tz = _tzinfo()
    now = datetime.now(tz)
    since_local = now - timedelta(days=7)
    since_utc = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    counts = await (await db.execute(
        '''
        SELECT
          (SELECT COUNT(*) FROM users WHERE created_at >= ?) AS new_users,
          (SELECT COUNT(*) FROM attempts WHERE started_at >= ?) AS attempts,
          (SELECT COUNT(*) FROM attempts WHERE status IN ('completed','timed_out') AND finished_at >= ?) AS finished_attempts,
          (SELECT COUNT(*) FROM answers WHERE answered_at >= ?) AS answers,
          (SELECT COUNT(*) FROM duel_matches WHERE status = 'finished' AND finished_at >= ?) AS finished_duels
        ''',
        (since_utc, since_utc, since_utc, since_utc, since_utc),
    )).fetchone()
    leaderboard = await (await db.execute(
        '''
        WITH ranked AS (
            SELECT
                l.*,
                ROW_NUMBER() OVER (
                    PARTITION BY l.user_id
                    ORDER BY l.score DESC, l.completion_seconds ASC, l.finished_at ASC
                ) AS rn
            FROM leaderboard l
            WHERE l.finished_at >= ?
        )
        SELECT ranked.*, u.username, u.first_name
        FROM ranked
        JOIN users u ON u.id = ranked.user_id
        WHERE ranked.rn = 1
        ORDER BY ranked.score DESC, ranked.completion_seconds ASC, ranked.finished_at ASC
        LIMIT 10
        ''',
        (since_utc,),
    )).fetchall()
    xp_leaderboard = await (await db.execute(
        '''
        SELECT s.xp, s.level, u.username, u.first_name
        FROM statistics s
        JOIN users u ON u.id = s.user_id
        WHERE s.xp > 0
        ORDER BY s.xp DESC, s.level DESC
        LIMIT 10
        '''
    )).fetchall()
    duels = await (await db.execute(
        '''
        SELECT d.*, u1.username AS p1name, u1.first_name AS p1first,
               u2.username AS p2name, u2.first_name AS p2first,
               uw.username AS winner_name, uw.first_name AS winner_first
        FROM duel_matches d
        LEFT JOIN users u1 ON u1.id = d.player1_id
        LEFT JOIN users u2 ON u2.id = d.player2_id
        LEFT JOIN users uw ON uw.id = d.winner_id
        WHERE d.status = 'finished' AND d.finished_at >= ?
        ORDER BY d.finished_at DESC
        LIMIT 10
        ''',
        (since_utc,),
    )).fetchall()

    lines = [
        "📊 <b>Haftalik SAT Quiz hisoboti</b>",
        f"Davr: {since_local.strftime('%Y-%m-%d')} — {now.strftime('%Y-%m-%d')}",
        "",
        f"👥 Yangi foydalanuvchilar: <b>{counts['new_users']}</b>",
        f"🧠 Boshlangan testlar: <b>{counts['attempts']}</b>",
        f"✅ Tugagan testlar: <b>{counts['finished_attempts']}</b>",
        f"✍️ Javoblar: <b>{counts['answers']}</b>",
        f"🔥 Tugagan duellar: <b>{counts['finished_duels']}</b>",
        "",
        "🏆 <b>Reyting TOP 10</b>",
    ]
    if leaderboard:
        for index, row in enumerate(leaderboard, start=1):
            lines.append(
                f"{index}. {_name(row)} — <b>{row['score']}/100</b> — {format_seconds(row['completion_seconds'] or 0)}"
            )
    else:
        lines.append("Bu haftada reyting natijalari yo‘q.")

    lines.extend(["", "⭐ <b>Umumiy XP TOP 10</b>"])
    if xp_leaderboard:
        for index, row in enumerate(xp_leaderboard, start=1):
            lines.append(f"{index}. {_name(row)} — <b>{row['xp']} XP</b>")
    else:
        lines.append("Hali XP reytingi yo‘q.")

    lines.extend(["", "🔥 <b>So‘nggi duellar</b>"])
    if duels:
        for row in duels:
            p1 = escape(row['p1name'] or row['p1first'] or 'Player 1')
            p2 = escape(row['p2name'] or row['p2first'] or 'Player 2')
            winner = escape(row['winner_name'] or row['winner_first'] or 'G‘olib aniqlanmagan')
            lines.append(
                f"• {p1} {row['player1_score']} - {row['player2_score']} {p2} → 🏆 {winner}"
            )
    else:
        lines.append("Bu haftada duel natijalari yo‘q.")

    return '\n'.join(lines)


async def send_weekly_report(db, bot) -> str:
    chats = await (await db.execute(
        'SELECT * FROM channel_config WHERE enabled = 1 AND weekly_report = 1'
    )).fetchall()
    if not chats:
        return 'Haftalik hisobot uchun guruh sozlanmagan. Guruhda /admin weekly_on yuboring.'

    text = await build_weekly_report_text(db)
    sent = 0
    for chat in chats:
        try:
            await bot.send_message(chat['chat_id'], text, parse_mode='HTML')
            sent += 1
        except TelegramAPIError as exc:
            logger.warning("weekly_report_send_failed chat_id=%s error=%s", chat['chat_id'], exc)
    return f"✅ Haftalik hisobot {sent}/{len(chats)} ta guruhga yuborildi."


def _next_run(now: datetime) -> datetime:
    target = now.replace(
        hour=WEEKLY_REPORT_HOUR,
        minute=WEEKLY_REPORT_MINUTE,
        second=0,
        microsecond=0,
    )
    days_ahead = (WEEKLY_REPORT_WEEKDAY - now.weekday()) % 7
    target = target + timedelta(days=days_ahead)
    if target <= now:
        target = target + timedelta(days=7)
    return target


async def run_weekly_report_scheduler(bot) -> None:
    if not WEEKLY_REPORT_ENABLED:
        logger.info("weekly_report_scheduler_disabled")
        return

    tz = _tzinfo()
    logger.info(
        "weekly_report_scheduler_started weekday=%s time=%02d:%02d tz=%s",
        WEEKLY_REPORT_WEEKDAY,
        WEEKLY_REPORT_HOUR,
        WEEKLY_REPORT_MINUTE,
        tz.key,
    )
    while True:
        try:
            now = datetime.now(tz)
            target = _next_run(now)
            await asyncio.sleep(max(1, (target - now).total_seconds()))
            db = await get_db()
            result = await send_weekly_report(db, bot)
            logger.info("weekly_report_sent result=%s", result)
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("weekly_report_scheduler_failed")
            await asyncio.sleep(300)
