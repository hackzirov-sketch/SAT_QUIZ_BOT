import logging
import time
from typing import Any

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError

from bot.config import REQUIRED_SUBSCRIPTIONS, SUBSCRIPTION_CACHE_TTL, SUBSCRIPTION_STRICT

logger = logging.getLogger(__name__)

_subscription_cache: dict[tuple[int, str], tuple[bool, float]] = {}


def _cache_key(user_id: int, chat_id: Any) -> tuple[int, str]:
    return user_id, str(chat_id)


async def is_subscribed(bot: Bot, user_id: int, req: dict[str, Any], *, force_refresh: bool = False) -> bool:
    chat_id = req.get('chat_id')
    if not chat_id:
        return True

    key = _cache_key(user_id, chat_id)
    cached = _subscription_cache.get(key)
    now = time.monotonic()
    if not force_refresh and cached and cached[1] > now:
        return cached[0]

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        ok = member.status not in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED)
    except TelegramAPIError as exc:
        logger.warning("subscription_check_failed chat_id=%s user_id=%s error=%s", chat_id, user_id, exc)
        ok = not SUBSCRIPTION_STRICT

    ttl = SUBSCRIPTION_CACHE_TTL if ok else min(SUBSCRIPTION_CACHE_TTL, 60)
    if ttl > 0:
        _subscription_cache[key] = (ok, now + ttl)
    return ok


async def missing_subscriptions(bot: Bot, user_id: int, *, force_refresh: bool = False) -> list[dict[str, Any]]:
    missing = []
    for req in REQUIRED_SUBSCRIPTIONS:
        if not await is_subscribed(bot, user_id, req, force_refresh=force_refresh):
            missing.append(req)
    return missing


def invalidate_cache(user_id: int):
    keys = [k for k in _subscription_cache if k[0] == user_id]
    for k in keys:
        _subscription_cache.pop(k, None)
