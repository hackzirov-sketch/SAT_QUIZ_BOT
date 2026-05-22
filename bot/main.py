import asyncio
import logging
import sys
import threading
from flask import Flask
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from bot.config import BOT_TOKEN, DATABASE_PATH, VOCABULARY_PATH, WEBHOOK_URL, WEBHOOK_SECRET, PORT
from bot.database import init_db
from bot.utils.db_helpers import load_vocabulary
from bot.quiz_engine import QuizEngine
from bot.handlers import routers
from bot.handlers.quiz import set_quiz_engine as set_qe
from bot.handlers.chill import set_quiz_engine as set_chill_qe
from bot.handlers.daily import set_quiz_engine as set_daily_qe
from bot.handlers.mistakes import set_quiz_engine as set_mistakes_qe
from bot.handlers.duel import set_quiz_engine as set_duel_qe, set_bot as set_duel_bot
from bot.handlers.admin import set_bot as set_admin_bot

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

flask_app = Flask(__name__)


@flask_app.route('/health')
@flask_app.route('/')
def health():
    return 'OK'


def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)


async def main():
    db = await init_db(DATABASE_PATH)
    vocab_data = await load_vocabulary(db)

    engine = QuizEngine(None, vocab_data)
    set_qe(engine)
    set_chill_qe(engine)
    set_daily_qe(engine)
    set_mistakes_qe(engine)
    set_duel_qe(engine)

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    set_admin_bot(bot)
    set_duel_bot(bot)

    for router in routers:
        dp.include_router(router)

    if WEBHOOK_URL:
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        from aiohttp import web
        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET).register(app, path='/webhook')
        setup_application(app, dp, bot=bot)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', PORT)
        await site.start()
        logging.info(f"Webhook started on port {PORT}")
        await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook", secret_token=WEBHOOK_SECRET)
        await asyncio.Event().wait()
    else:
        threading.Thread(target=run_flask, daemon=True).start()
        logging.info(f"Health server started on port {PORT} (Flask), polling in parallel")
        await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
