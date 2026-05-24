from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from ai.cache import AICache


class TestAICache:
    @pytest.fixture
    def cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield AICache(cache_dir=tmp)

    def test_set_and_get_string(self, cache: AICache):
        cache.set('hello world', 'test', 'greeting')
        assert cache.get('test', 'greeting') == 'hello world'

    def test_get_missing(self, cache: AICache):
        assert cache.get('nonexistent', 'key') is None

    def test_set_and_get_json(self, cache: AICache):
        data = {'a': 1, 'b': [2, 3]}
        cache.set_json(data, 'test_json', 'mykey')
        assert cache.get_json('test_json', 'mykey') == data

    def test_get_json_missing(self, cache: AICache):
        assert cache.get_json('nope', 'nothing') is None

    def test_ttl_expiry(self, cache: AICache):
        cache.set('value', 'test', 'expire')
        cache.ttl['test'] = -1
        cache._mem.clear()
        assert cache.get('test', 'expire') is None

    def test_clear_prefix(self, cache: AICache):
        cache.set('a', 'pref', 'x')
        cache.set('b', 'pref', 'y')
        cache.set('c', 'other', 'z')
        cache.clear_prefix('pref')
        assert cache.get('pref', 'x') is None
        assert cache.get('pref', 'y') is None
        assert cache.get('other', 'z') == 'c'

    def test_clear_all(self, cache: AICache):
        cache.set('a', 'p1', 'k1')
        cache.set('b', 'p2', 'k2')
        cache.clear_all()
        assert cache.get('p1', 'k1') is None
        assert cache.get('p2', 'k2') is None

    def test_stats(self, cache: AICache):
        cache.set('v1', 'grp', 'a')
        cache.set('v2', 'grp', 'b')
        s = cache.stats()
        assert s['total_entries'] == 2
        assert s['by_prefix']['grp'] == 2
        assert s['total_size_bytes'] > 0

    def test_memory_cache_hit(self, cache: AICache):
        cache.set('mem', 'test', 'hit')
        path = list(cache.cache_dir.glob('*.json'))[0]
        path.unlink()
        assert cache.get('test', 'hit') == 'mem'

    def test_set_overwrite(self, cache: AICache):
        cache.set('first', 't', 'k')
        cache.set('second', 't', 'k')
        assert cache.get('t', 'k') == 'second'
