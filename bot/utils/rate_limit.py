import time
from collections import OrderedDict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, min_interval: float = 0.25, max_users: int = 5000):
        self.min_interval = min_interval
        self.max_users = max_users
        self._last_seen: OrderedDict[int, float] = OrderedDict()

    async def __call__(self, handler, event, data):
        user = event.from_user if isinstance(event, (Message, CallbackQuery)) else None
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        last = self._last_seen.get(user.id, 0.0)
        self._last_seen[user.id] = now
        self._last_seen.move_to_end(user.id)
        if len(self._last_seen) > self.max_users:
            self._last_seen.popitem(last=False)

        if now - last < self.min_interval:
            if isinstance(event, CallbackQuery):
                await event.answer('Sekinroq bosing.')
            return None
        return await handler(event, data)
