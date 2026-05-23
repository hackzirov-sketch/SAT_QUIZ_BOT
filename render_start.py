from __future__ import annotations

import asyncio
import logging
import os
import threading

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from waitress import serve

from bot.config import BOT_POLLING_ENABLED, BOT_TOKEN, DATABASE_PATH, PORT
from bot.database import init_db
from bot.handlers.admin import set_bot as set_admin_bot
from bot.handlers.duel import set_bot as set_duel_bot
from bot.main import configure_logging, setup_dispatcher
from bot.quiz_engine import QuizEngine
from bot.services.session_sweeper import run_session_sweeper
from bot.services.weekly_report_service import run_weekly_report_scheduler
from bot.utils.db_helpers import load_vocabulary
from teacher_site.app import app as flask_app


logger = logging.getLogger(__name__)


def run_flask_site() -> None:
    threads = int(os.environ.get('WEB_THREADS', '8'))
    logger.info("flask_site_started host=0.0.0.0 port=%s threads=%s", PORT, threads)
    serve(flask_app, host='0.0.0.0', port=PORT, threads=threads)


async def run_telegram_bot() -> None:
    db = await init_db(DATABASE_PATH)
    vocab_data = await load_vocabulary(db)
    if not vocab_data:
        raise RuntimeError('Vocabulary is empty')

    engine = QuizEngine(None, vocab_data)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = setup_dispatcher(engine, bot)
    set_admin_bot(bot)
    set_duel_bot(bot)

    sweeper_task = asyncio.create_task(run_session_sweeper(), name='session-sweeper')
    weekly_task = asyncio.create_task(run_weekly_report_scheduler(bot), name='weekly-report')
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("telegram_polling_started")
        await dp.start_polling(bot)
    finally:
        for task in (sweeper_task, weekly_task):
            task.cancel()
        await asyncio.gather(sweeper_task, weekly_task, return_exceptions=True)
        await bot.session.close()


async def main() -> None:
    configure_logging()
    site_thread = threading.Thread(target=run_flask_site, name='flask-site', daemon=True)
    site_thread.start()
    if BOT_POLLING_ENABLED:
        await run_telegram_bot()
    else:
        logger.info("telegram_polling_disabled")
        await asyncio.Event().wait()


if __name__ == '__main__':
    asyncio.run(main())
