from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger('ai.token_budget')


@dataclass
class BudgetSnapshot:
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    call_count: int = 0
    by_provider: dict[str, int] = field(default_factory=lambda: {'gemini': 0, 'groq': 0})
    by_model: dict[str, int] = field(default_factory=dict)

    def reset(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost_usd = 0.0
        self.call_count = 0
        self.by_provider = {'gemini': 0, 'groq': 0}
        self.by_model = {}


TOKEN_LIMITS = {
    'gemini-2.0-flash': {
        'max_input': 1_000_000,
        'max_output': 8192,
        'cost_per_1k_input': 0.0001,
        'cost_per_1k_output': 0.0004,
    },
    'llama-3.3-70b-versatile': {
        'max_input': 128_000,
        'max_output': 32768,
        'cost_per_1k_input': 0.00059,
        'cost_per_1k_output': 0.00079,
    },
}

PROMPT_SIZES = {
    'explain': {'prompt_est': 200, 'max_tokens': 512},
    'mistake_analysis': {'prompt_est': 150, 'max_tokens': 384},
    'short_feedback': {'prompt_est': 100, 'max_tokens': 192},
    'desmos_solution': {'prompt_est': 150, 'max_tokens': 384},
    'classify': {'prompt_est': 100, 'max_tokens': 256},
    'extract_page': {'prompt_est': 300, 'max_tokens': 2048},
    'describe_image': {'prompt_est': 50, 'max_tokens': 256},
}


class TokenBudget:
    def __init__(self, daily_limit_usd: float = 0.50):
        self.daily_limit = daily_limit_usd
        self.session = BudgetSnapshot()
        self.daily_usage: dict[str, float] = {}

    def track_call(self, provider: str, model: str, task_type: str,
                   tokens_in: int = 0, tokens_out: int = 0):
        limits = TOKEN_LIMITS.get(model, {})
        cost_in = (tokens_in / 1000) * limits.get('cost_per_1k_input', 0)
        cost_out = (tokens_out / 1000) * limits.get('cost_per_1k_output', 0)
        cost = cost_in + cost_out

        self.session.total_prompt_tokens += tokens_in
        self.session.total_completion_tokens += tokens_out
        self.session.total_cost_usd += cost
        self.session.call_count += 1
        self.session.by_provider[provider] = self.session.by_provider.get(provider, 0) + 1
        self.session.by_model[model] = self.session.by_model.get(model, 0) + 1

        logger.debug(
            'AI call: %s/%s %s — in=%d out=%d cost=%.5f total=%.4f',
            provider, model, task_type, tokens_in, tokens_out, cost, self.session.total_cost_usd,
        )

    def estimated_tokens(self, task_type: str, text_length: int = 0) -> dict:
        base = PROMPT_SIZES.get(task_type, {'prompt_est': 100, 'max_tokens': 256})
        text_tokens = text_length // 4
        return {
            'prompt_est': base['prompt_est'] + text_tokens,
            'max_tokens': base['max_tokens'],
            'total_est': base['prompt_est'] + text_tokens + base['max_tokens'],
        }

    def within_daily_limit(self, model: str, task_type: str, text_length: int = 0) -> bool:
        if self.session.total_cost_usd >= self.daily_limit:
            logger.warning('Daily token budget exceeded ($%.4f >= $%.2f)',
                           self.session.total_cost_usd, self.daily_limit)
            return False
        est = self.estimated_tokens(task_type, text_length)
        limits = TOKEN_LIMITS.get(model, {})
        est_cost = (est['prompt_est'] / 1000) * limits.get('cost_per_1k_input', 0) + \
                   (est['max_tokens'] / 1000) * limits.get('cost_per_1k_output', 0)
        return (self.session.total_cost_usd + est_cost) < self.daily_limit

    def can_make_call(self, model: str, task_type: str, text_length: int = 0) -> bool:
        return self.within_daily_limit(model, task_type, text_length)

    def summary(self) -> dict[str, Any]:
        return {
            'total_prompt_tokens': self.session.total_prompt_tokens,
            'total_completion_tokens': self.session.total_completion_tokens,
            'total_cost_usd': round(self.session.total_cost_usd, 6),
            'call_count': self.session.call_count,
            'by_provider': dict(self.session.by_provider),
            'by_model': dict(self.session.by_model),
            'daily_limit_usd': self.daily_limit,
            'remaining_budget': round(max(0, self.daily_limit - self.session.total_cost_usd), 6),
        }

    def estimated_cost(self, task_type: str, model: str,
                       text_length: int = 0) -> float:
        est = self.estimated_tokens(task_type, text_length)
        limits = TOKEN_LIMITS.get(model, {})
        cost_in = (est['prompt_est'] / 1000) * limits.get('cost_per_1k_input', 0)
        cost_out = (est['max_tokens'] / 1000) * limits.get('cost_per_1k_output', 0)
        return round(cost_in + cost_out, 6)
