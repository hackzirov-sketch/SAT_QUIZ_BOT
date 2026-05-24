from __future__ import annotations

import asyncio
import logging
import os
import signal
import tempfile
import threading
import time

try:
    import fcntl
    _HAVE_FCNTL = True
except ImportError:
    _HAVE_FCNTL = False

try:
    import msvcrt
    _HAVE_MSVCRT = True
except ImportError:
    _HAVE_MSVCRT = False

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from waitress import serve

from bot.config import BOT_POLLING_ENABLED, BOT_TOKEN, DATABASE_PATH, PORT
from bot.database import db_transaction, get_db, init_db, integrity_check, wal_checkpoint
from bot.handlers.admin import set_bot as set_admin_bot
from bot.handlers.duel import set_bot as set_duel_bot
from bot.main import configure_logging, setup_dispatcher
from bot.quiz_engine import QuizEngine
from bot.services.session_sweeper import run_session_sweeper
from bot.services.weekly_report_service import run_weekly_report_scheduler
from bot.utils.db_helpers import load_vocabulary
from bot.runtime_state import runtime_state
from teacher_site.app import app as flask_app


logger = logging.getLogger(__name__)
_shutdown_event = asyncio.Event()
_polling_started = False
_polling_lock_fd: int | None = None
_POLLING_LOCK_PATH = os.path.join(tempfile.gettempdir(), 'quiz_bot_polling.lock')
_DB_MAINT_INTERVAL = 14_400  # 4 hours between incremental_vacuum


def validate_render_sqlite_path() -> None:
    if os.name != 'posix':
        return
    if not os.environ.get('RENDER'):
        return
    if not DATABASE_PATH.startswith('/data/'):
        raise RuntimeError('DATABASE_PATH must be under /data on Render when using SQLite')
    if not os.path.isdir('/data'):
        raise RuntimeError('/data persistent disk is not mounted')
    probe_path = os.path.join('/data', '.quiz_bot_write_probe')
    try:
        with open(probe_path, 'w', encoding='utf-8') as probe:
            probe.write(str(os.getpid()))
        os.remove(probe_path)
    except OSError as exc:
        raise RuntimeError('/data persistent disk is not writable') from exc


def _acquire_polling_lock() -> bool:
    global _polling_lock_fd
    if _polling_lock_fd is not None:
        return True
    try:
        fd = os.open(_POLLING_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
        if _HAVE_FCNTL:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        elif _HAVE_MSVCRT:
            if os.path.getsize(_POLLING_LOCK_PATH) == 0:
                os.write(fd, b' ')
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            logger.warning("file_lock_unavailable_lockfile_skipped")
            os.close(fd)
            return True
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        _polling_lock_fd = fd
        logger.info("polling_lock_acquired pid=%s path=%s", os.getpid(), _POLLING_LOCK_PATH)
        return True
    except (IOError, OSError) as exc:
        logger.critical("polling_lock_failed pid=%s error=%s is_another_instance_running?", os.getpid(), exc)
        return False


def _release_polling_lock() -> None:
    global _polling_lock_fd
    if _polling_lock_fd is None:
        return
    try:
        if _HAVE_FCNTL:
            fcntl.flock(_polling_lock_fd, fcntl.LOCK_UN)
        elif _HAVE_MSVCRT:
            os.lseek(_polling_lock_fd, 0, os.SEEK_SET)
            msvcrt.locking(_polling_lock_fd, msvcrt.LK_UNLCK, 1)
        os.close(_polling_lock_fd)
        logger.info("polling_lock_released pid=%s", os.getpid())
    except OSError:
        logger.exception("polling_lock_release_failed")
    finally:
        _polling_lock_fd = None


async def _wait_for_polling_lock(retry_seconds: int = 10) -> bool:
    while not _shutdown_event.is_set():
        if _acquire_polling_lock():
            return True
        logger.warning("polling_lock_busy_retrying seconds=%s", retry_seconds)
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=retry_seconds)
        except asyncio.TimeoutError:
            continue
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
            await wal_checkpoint('TRUNCATE')
            ok = await integrity_check()
            runtime_state.last_db_check_ok = ok
            runtime_state.last_db_check_at = time.time()
            runtime_state.scheduler_alive['db-maintenance'] = True
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

    if not await _wait_for_polling_lock():
        logger.info("polling_lock_wait_cancelled")
        return

    db = await init_db(DATABASE_PATH)
    vocab_data = await load_vocabulary(db)
    if not vocab_data:
        raise RuntimeError('Vocabulary is empty')
    runtime_state.vocabulary_count = len(vocab_data)

    engine = QuizEngine(None, vocab_data)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = setup_dispatcher(engine, bot)
    set_admin_bot(bot)
    set_duel_bot(bot)

    sweeper_task = asyncio.create_task(run_session_sweeper(_shutdown_event), name='session-sweeper')
    weekly_task = asyncio.create_task(run_weekly_report_scheduler(bot, _shutdown_event), name='weekly-report')
    maint_task = asyncio.create_task(run_db_maintenance(), name='db-maintenance')
    polling_task = None
    shutdown_task = None
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        polling_task = asyncio.create_task(dp.start_polling(bot), name='polling')
        shutdown_task = asyncio.create_task(_shutdown_event.wait(), name='shutdown-wait')
        runtime_state.polling_started = True
        runtime_state.polling_alive = True
        runtime_state.scheduler_alive.update({
            'session-sweeper': True,
            'weekly-report': True,
            'db-maintenance': True,
        })
        logger.info("telegram_polling_started pid=%s polling_task=%s", os.getpid(), id(polling_task))
        done, pending = await asyncio.wait(
            [polling_task, shutdown_task],
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
        tasks = [task for task in (sweeper_task, weekly_task, maint_task, polling_task, shutdown_task) if task]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            db = await get_db()
            await wal_checkpoint('TRUNCATE')
            logger.info("wal_checkpoint_completed")
        except Exception:
            pass
        await bot.session.close()
        runtime_state.polling_alive = False
        _release_polling_lock()
        logger.info("telegram_polling_stopped")


def run_flask_with_health() -> None:
    site_thread = threading.Thread(target=_run_flask_site, name='flask-site', daemon=True)
    site_thread.start()


def _run_flask_site() -> None:
    threads = int(os.environ.get('WEB_THREADS', '8'))
    runtime_state.flask_alive = True
    logger.info("flask_site_started host=0.0.0.0 port=%s threads=%s", PORT, threads)
    serve(flask_app, host='0.0.0.0', port=PORT, threads=threads)


async def main() -> None:
    configure_logging()
    logger.info("render_start_main pid=%s polling=%s", os.getpid(), BOT_POLLING_ENABLED)
    _data_disk = os.path.isdir('/data') if os.name == 'posix' else None
    runtime_state.render_disk_mounted = _data_disk
    logger.info("db_path=%s render_disk_mounted=%s", DATABASE_PATH, _data_disk)
    validate_render_sqlite_path()
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
