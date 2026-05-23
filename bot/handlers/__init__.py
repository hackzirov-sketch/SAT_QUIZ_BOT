import logging
from aiogram import Router
from aiogram.types import ErrorEvent
from .start import router as start_router
from .quiz import router as quiz_router
from .daily import router as daily_router
from .admin import router as admin_router
from .chill import router as chill_router
from .mistakes import router as mistakes_router
from .duel import router as duel_router
from .stats import router as stats_router
from .settings import router as settings_router
from bot.subscription import router as subscription_router

error_router = Router()
logger = logging.getLogger(__name__)

@error_router.errors()
async def global_error_handler(event: ErrorEvent):
    exc = event.exception
    logger.error("handler_error", exc_info=(type(exc), exc, exc.__traceback__))
    try:
        if event.update.message:
            await event.update.message.answer("❌ Xatolik yuz berdi. Iltimos qayta urinib ko'ring.")
        elif event.update.callback_query:
            await event.update.callback_query.answer("❌ Xatolik yuz berdi.")
    except Exception:
        logger.exception("failed_to_notify_user_about_error")

routers = [
    error_router,
    subscription_router,
    start_router, quiz_router, daily_router, admin_router,
    chill_router, mistakes_router, duel_router, stats_router, settings_router,
]
