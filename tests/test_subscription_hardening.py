import time

import pytest

from bot.services import subscription_service


class _Member:
    status = "member"


class _Bot:
    def __init__(self):
        self.calls = 0

    async def get_chat_member(self, _chat_id, _user_id):
        self.calls += 1
        return _Member()


@pytest.mark.asyncio
async def test_subscription_periodic_recheck(monkeypatch):
    bot = _Bot()
    req = {"chat_id": "@test"}
    subscription_service.invalidate_cache(123)
    assert await subscription_service.is_subscribed(bot, 123, req)
    assert bot.calls == 1
    key = (123, "@test")
    subscription_service._last_successful_check[key] = time.monotonic() - (
        subscription_service.RECHECK_INTERVAL_SECONDS + 1
    )
    assert await subscription_service.is_subscribed(bot, 123, req)
    assert bot.calls == 2
