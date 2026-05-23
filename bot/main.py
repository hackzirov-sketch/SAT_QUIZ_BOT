import asyncio
import logging
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import BOT_TOKEN, DATABASE_PATH, LOG_LEVEL, PORT, WEBHOOK_SECRET, WEBHOOK_URL
from bot.database import init_db
from bot.handlers import routers
from bot.handlers.admin import set_bot as set_admin_bot
from bot.handlers.chill import set_quiz_engine as set_chill_qe
from bot.handlers.daily import set_quiz_engine as set_daily_qe
from bot.handlers.duel import set_bot as set_duel_bot
from bot.handlers.duel import set_quiz_engine as set_duel_qe
from bot.handlers.mistakes import set_quiz_engine as set_mistakes_qe
from bot.handlers.quiz import set_quiz_engine as set_qe
from bot.quiz_engine import QuizEngine
from bot.services.session_sweeper import run_session_sweeper
from bot.services.weekly_report_service import run_weekly_report_scheduler
from bot.subscription import SubscriptionMiddleware
from bot.utils.db_helpers import load_vocabulary

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        stream=sys.stdout,
    )


async def health(_request: web.Request) -> web.Response:
    return web.Response(text='OK')


def setup_dispatcher(engine: QuizEngine, bot: Bot) -> Dispatcher:
    set_qe(engine)
    set_chill_qe(engine)
    set_daily_qe(engine)
    set_mistakes_qe(engine)
    set_duel_qe(engine)
    set_admin_bot(bot)
    set_duel_bot(bot)

    dp = Dispatcher()
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())
    for router in routers:
        dp.include_router(router)
    return dp


async def start_health_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info("health_server_started port=%s", PORT)
    return runner


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    app = web.Application()
    app.router.add_get('/', health)
    app.router.add_get('/health', health)
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET).register(app, path='/webhook')
    setup_application(app, dp, bot=bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook", secret_token=WEBHOOK_SECRET)
    logger.info("webhook_started port=%s url=%s/webhook", PORT, WEBHOOK_URL)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def main():
    configure_logging()
    db = await init_db(DATABASE_PATH)
    vocab_data = await load_vocabulary(db)
    if not vocab_data:
        raise RuntimeError('Vocabulary is empty')

    engine = QuizEngine(None, vocab_data)
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = setup_dispatcher(engine, bot)
    sweeper_task = asyncio.create_task(run_session_sweeper(), name='session-sweeper')
    weekly_task = asyncio.create_task(run_weekly_report_scheduler(bot), name='weekly-report')
    health_runner = None
    try:
        if WEBHOOK_URL:
            await run_webhook(bot, dp)
        else:
            health_runner = await start_health_server()
            logger.info("polling_started")
            await dp.start_polling(bot)
    finally:
        for task in (sweeper_task, weekly_task):
            task.cancel()
        await asyncio.gather(sweeper_task, weekly_task, return_exceptions=True)
        if health_runner:
            await health_runner.cleanup()
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
