import time
from collections import OrderedDict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, min_interval: float = 0.25, max_users: int = 5000):
        self.min_interval = min_interval
        self.max_users = max_users
        self._last_seen: OrderedDict[tuple[int, str], float] = OrderedDict()

    async def __call__(self, handler, event, data):
        user = getattr(event, 'from_user', None)
        if user is None:
            return await handler(event, data)

        now = time.monotonic()
        event_key = getattr(event, 'data', None) or getattr(event, 'text', '') or ''
        key = (user.id, event_key)
        last = self._last_seen.get(key, 0.0)
        self._last_seen[key] = now
        self._last_seen.move_to_end(key)
        if len(self._last_seen) > self.max_users:
            self._last_seen.popitem(last=False)

        if now - last < self.min_interval:
            if hasattr(event, 'answer') and getattr(event, 'data', None) is not None:
                await event.answer('Sekinroq bosing.')
            return None
        return await handler(event, data)
