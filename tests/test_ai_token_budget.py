from __future__ import annotations

import pytest

from ai.token_budget import TokenBudget


class TestTokenBudget:
    @pytest.fixture
    def budget(self):
        return TokenBudget(daily_limit_usd=1.0)

    def test_initial_state(self, budget: TokenBudget):
        s = budget.summary()
        assert s['call_count'] == 0
        assert s['total_cost_usd'] == 0.0
        assert s['remaining_budget'] == 1.0

    def test_track_call(self, budget: TokenBudget):
        budget.track_call('groq', 'llama-3.3-70b-versatile', 'explain',
                          tokens_in=200, tokens_out=100)
        s = budget.summary()
        assert s['call_count'] == 1
        assert s['by_provider']['groq'] == 1
        assert s['total_prompt_tokens'] == 200
        assert s['total_completion_tokens'] == 100
        assert s['total_cost_usd'] > 0

    def test_multiple_calls(self, budget: TokenBudget):
        budget.track_call('groq', 'llama-3.3-70b-versatile', 'explain',
                          tokens_in=100, tokens_out=50)
        budget.track_call('gemini', 'gemini-2.0-flash', 'classify',
                          tokens_in=80, tokens_out=20)
        s = budget.summary()
        assert s['call_count'] == 2
        assert s['by_provider']['groq'] == 1
        assert s['by_provider']['gemini'] == 1
        assert s['by_model']['llama-3.3-70b-versatile'] == 1
        assert s['by_model']['gemini-2.0-flash'] == 1

    def test_estimated_tokens(self, budget: TokenBudget):
        est = budget.estimated_tokens('explain', text_length=400)
        assert est['prompt_est'] > 0
        assert est['max_tokens'] == 512
        assert est['total_est'] > est['max_tokens']

    def test_estimated_cost(self, budget: TokenBudget):
        cost = budget.estimated_cost('explain', 'llama-3.3-70b-versatile')
        assert cost > 0
        assert cost < 0.01

    def test_within_daily_limit_true(self, budget: TokenBudget):
        assert budget.within_daily_limit('llama-3.3-70b-versatile', 'explain')

    def test_within_daily_limit_false(self, budget: TokenBudget):
        budget.daily_limit = 0.0
        assert not budget.within_daily_limit('llama-3.3-70b-versatile', 'explain')

    def test_can_make_call(self, budget: TokenBudget):
        assert budget.can_make_call('llama-3.3-70b-versatile', 'explain')

    def test_cannot_make_call_exceeded(self, budget: TokenBudget):
        budget.track_call('groq', 'llama-3.3-70b-versatile', 'explain',
                          tokens_in=2000000, tokens_out=2000000)
        budget.daily_limit = 0.01
        assert budget.can_make_call('llama-3.3-70b-versatile', 'explain') is False

    def test_reset(self, budget: TokenBudget):
        budget.track_call('groq', 'llama-3.3-70b-versatile', 'explain',
                          tokens_in=100, tokens_out=50)
        budget.session.reset()
        s = budget.summary()
        assert s['call_count'] == 0
        assert s['total_cost_usd'] == 0.0

    def test_summary_keys(self, budget: TokenBudget):
        s = budget.summary()
        assert 'total_prompt_tokens' in s
        assert 'total_completion_tokens' in s
        assert 'total_cost_usd' in s
        assert 'call_count' in s
        assert 'by_provider' in s
        assert 'by_model' in s
        assert 'daily_limit_usd' in s
        assert 'remaining_budget' in s
