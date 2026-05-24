import json
from pathlib import Path

from bot.quiz_engine import PRIMARY_SOURCE


def test_user_sat_core_vocabulary_is_present():
    items = json.loads(Path("bot/data/vocabulary.json").read_text(encoding="utf-8"))
    core = {item["english"]: item for item in items if item.get("source") == PRIMARY_SOURCE}

    assert len(core) >= 65
    assert core["positive"]["uzbek"] == "musbat"
    assert core["constant"]["uzbek"] == "oʻzgarmas"
    assert core["line segment"]["uzbek"] == "kesma"
