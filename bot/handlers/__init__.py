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

error_router = Router()

@error_router.errors()
async def global_error_handler(event: ErrorEvent):
    logging.error(f"Handler error: {event.exception}", exc_info=event.exception)
    try:
        if event.update.message:
            await event.update.message.answer("❌ Xatolik yuz berdi. Iltimos qayta urinib ko'ring.")
        elif event.update.callback_query:
            await event.update.callback_query.answer("❌ Xatolik yuz berdi.")
    except:
        pass

routers = [
    error_router,
    start_router, quiz_router, daily_router, admin_router,
    chill_router, mistakes_router, duel_router, stats_router, settings_router,
]
