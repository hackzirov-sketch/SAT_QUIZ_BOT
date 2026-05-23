from __future__ import annotations

import asyncio
import logging
import os
import signal
import threading
import time

try:
    import fcntl
    _HAVE_FCNTL = True
except ImportError:
    _HAVE_FCNTL = False

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from waitress import serve

from bot.config import BOT_POLLING_ENABLED, BOT_TOKEN, DATABASE_PATH, PORT
from bot.database import db_transaction, get_db, init_db
from bot.handlers.admin import set_bot as set_admin_bot
from bot.handlers.duel import set_bot as set_duel_bot
from bot.main import configure_logging, setup_dispatcher
from bot.quiz_engine import QuizEngine
from bot.services.session_sweeper import run_session_sweeper
from bot.services.weekly_report_service import run_weekly_report_scheduler
from bot.utils.db_helpers import load_vocabulary
from teacher_site.app import app as flask_app


logger = logging.getLogger(__name__)
_shutdown_event = asyncio.Event()
_polling_started = False
_POLLING_LOCK_PATH = '/tmp/quiz_bot_polling.lock'
_DB_MAINT_INTERVAL = 14_400  # 4 hours between incremental_vacuum


def _acquire_polling_lock() -> bool:
    if not _HAVE_FCNTL:
        logger.warning("fcntl_unavailable_lockfile_skipped")
        return True
    try:
        fd = os.open(_POLLING_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.write(fd, str(os.getpid()).encode())
        logger.info("polling_lock_acquired pid=%s path=%s", os.getpid(), _POLLING_LOCK_PATH)
        return True
    except (IOError, OSError) as exc:
        logger.critical("polling_lock_failed pid=%s error=%s is_another_instance_running?", os.getpid(), exc)
        return False


def _signal_handler():
    logger.info("shutdown_signal_received")
    _shutdown_event.set()


async def run_db_maintenance() -> None:
    """Periodic DB maintenance to prevent file bloat on Render's disk."""
    while not _shutdown_event.is_set():
        try:
            await asyncio.sleep(_DB_MAINT_INTERVAL)
            db = await get_db()
            async with db_transaction():
                await db.execute('PRAGMA incremental_vacuum(500)')
            async with db_transaction():
                await db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            logger.info("db_maintenance_completed interval=%ss", _DB_MAINT_INTERVAL)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("db_maintenance_failed")


async def run_telegram_bot() -> None:
    global _polling_started
    if _polling_started:
        logger.warning("polling_already_started_skipping_duplicate")
        return
    _polling_started = True

    if not _acquire_polling_lock():
        logger.critical("another_polling_instance_active_aborting")
        return

    db = await init_db(DATABASE_PATH)
    vocab_data = await load_vocabulary(db)
    if not vocab_data:
        raise RuntimeError('Vocabulary is empty')

    engine = QuizEngine(None, vocab_data)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = setup_dispatcher(engine, bot)
    set_admin_bot(bot)
    set_duel_bot(bot)

    sweeper_task = asyncio.create_task(run_session_sweeper(_shutdown_event), name='session-sweeper')
    weekly_task = asyncio.create_task(run_weekly_report_scheduler(bot, _shutdown_event), name='weekly-report')
    maint_task = asyncio.create_task(run_db_maintenance(), name='db-maintenance')
    polling_task = asyncio.create_task(dp.start_polling(bot), name='polling')
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        logger.info("telegram_polling_started pid=%s polling_task=%s", os.getpid(), id(polling_task))
        done, pending = await asyncio.wait(
            [polling_task, asyncio.create_task(_shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    except asyncio.CancelledError:
        logger.info("telegram_polling_cancelled")
        raise
    except Exception:
        logger.exception("telegram_polling_failed")
        raise
    finally:
        for t in (sweeper_task, weekly_task, maint_task, polling_task):
            t.cancel()
        await asyncio.gather(sweeper_task, weekly_task, maint_task, polling_task, return_exceptions=True)
        try:
            db = await get_db()
            await db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            logger.info("wal_checkpoint_completed")
        except Exception:
            pass
        await bot.session.close()
        logger.info("telegram_polling_stopped")


async def run_flask_with_health() -> None:
    site_thread = threading.Thread(target=_run_flask_site, name='flask-site', daemon=True)
    site_thread.start()


def _run_flask_site() -> None:
    threads = int(os.environ.get('WEB_THREADS', '8'))
    logger.info("flask_site_started host=0.0.0.0 port=%s threads=%s", PORT, threads)
    serve(flask_app, host='0.0.0.0', port=PORT, threads=threads)


async def main() -> None:
    configure_logging()
    logger.info("render_start_main pid=%s polling=%s", os.getpid(), BOT_POLLING_ENABLED)
    _data_disk = os.path.isdir('/data') if os.name == 'posix' else None
    logger.info("db_path=%s render_disk_mounted=%s", DATABASE_PATH, _data_disk)
    loop = asyncio.get_event_loop()
    try:
        loop.add_signal_handler(signal.SIGTERM, _signal_handler)
        loop.add_signal_handler(signal.SIGINT, _signal_handler)
    except NotImplementedError:
        logger.warning("signal_handlers_not_supported_on_windows_fallback_keyboard_interrupt")
    run_flask_with_health()
    if BOT_POLLING_ENABLED:
        await run_telegram_bot()
    else:
        logger.info("telegram_polling_disabled")
        await _shutdown_event.wait()
    logger.info("render_start_shutdown_complete")


if __name__ == '__main__':
    asyncio.run(main())
