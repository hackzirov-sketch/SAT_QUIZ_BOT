from pathlib import Path


def test_ai_providers_do_not_use_time_sleep():
    for path in (Path("ai/providers/groq_client.py"), Path("ai/providers/gemini_client.py")):
        assert "time.sleep" not in path.read_text(encoding="utf-8")
