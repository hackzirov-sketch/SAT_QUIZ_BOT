from __future__ import annotations

def test_polling_lock_acquire_release(tmp_path, monkeypatch):
    import render_start

    monkeypatch.setattr(render_start, "_POLLING_LOCK_PATH", str(tmp_path / "bot.lock"))
    monkeypatch.setattr(render_start, "_polling_lock_fd", None)

    assert render_start._acquire_polling_lock() is True
    assert render_start._polling_lock_fd is not None

    render_start._release_polling_lock()
    assert render_start._polling_lock_fd is None


def test_answer_save_flow_guards_duplicate_callbacks():
    from pathlib import Path

    source = Path("bot/handlers/quiz.py").read_text(encoding="utf-8")

    assert "INSERT INTO answers" in source
    assert "except aiosqlite.IntegrityError" in source
    assert "AND current_index = ?" in source
    assert "attempt_index_changed" in source
