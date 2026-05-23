import pytest
from bot.utils.db_helpers import row_get


class DictRow(dict):
    def keys(self):
        return super().keys()


class MockRow:
    def __init__(self, data):
        self._data = data
    def keys(self):
        return self._data.keys()
    def __getitem__(self, key):
        return self._data[key]


class TestRowGet:
    def test_none_row(self):
        assert row_get(None, 'anything') is None
        assert row_get(None, 'anything', 42) == 42

    def test_dict_row(self):
        d = DictRow({'a': 1, 'b': 2})
        assert row_get(d, 'a') == 1
        assert row_get(d, 'c') is None
        assert row_get(d, 'c', 99) == 99

    def test_mock_row(self):
        r = MockRow({'minimal_mode': 1, 'preferred_mode': 'eng_uzb'})
        assert row_get(r, 'minimal_mode') == 1
        assert row_get(r, 'preferred_mode') == 'eng_uzb'
        assert row_get(r, 'nonexistent') is None
        assert row_get(r, 'nonexistent', 'default') == 'default'

    def test_minimal_mode_logic(self):
        cases = [
            (MockRow({'minimal_mode': 0}), False),
            (MockRow({'minimal_mode': 1}), True),
            (MockRow({'minimal_mode': 99}), True),
            (None, False),
        ]
        for s, expected in cases:
            result = bool(s and row_get(s, 'minimal_mode', 0)) if s else False
            assert result == expected, f"Failed for {s} expected {expected}"
