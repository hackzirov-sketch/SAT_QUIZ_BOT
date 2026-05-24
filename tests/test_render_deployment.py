import os
import sys
from pathlib import Path

from bot.config import ROOT, DATABASE_PATH, PORT, BOT_TOKEN


def test_render_start_exists():
    assert os.path.exists("render_start.py"), "render_start.py not found"


def test_render_yaml_exists():
    assert os.path.exists("render.yaml"), "render.yaml not found"


def test_requirements_txt_exists():
    assert os.path.exists("requirements.txt"), "requirements.txt not found"


def test_database_path_is_relative():
    assert DATABASE_PATH.endswith("quiz_bot.db"), f"unexpected DATABASE_PATH: {DATABASE_PATH}"


def test_render_yaml_uses_persistent_sqlite_path():
    content = Path("render.yaml").read_text(encoding="utf-8")
    assert "mountPath: /data" in content
    assert "value: /data/quiz_bot.db" in content


def test_port_is_valid():
    assert 1 <= PORT <= 65535, f"PORT {PORT} out of range"


def test_bot_token_format():
    assert ":" in BOT_TOKEN, "BOT_TOKEN should contain ':' separator"


def test_data_directory_exists():
    data_dir = ROOT / "data"
    assert data_dir.exists(), f"data directory not found at {data_dir}"


def test_vocabulary_json_exists():
    vocab = ROOT / "data" / "vocabulary.json"
    assert vocab.exists(), f"vocabulary.json not found at {vocab}"


def test_mock_bank_exists():
    bank = ROOT / "data" / "mock_tests" / "math_mock_bank.json"
    assert bank.exists(), f"math_mock_bank.json not found at {bank}"


def test_mock_images_dir_exists():
    img_dir = ROOT / "data" / "mock_images"
    assert img_dir.exists(), f"mock_images dir not found at {img_dir}"


def test_teacher_site_app_exists():
    assert os.path.exists("teacher_site/app.py"), "teacher_site/app.py not found"


def test_python_version_compatible():
    v = sys.version_info
    assert v.major == 3 and v.minor >= 10, f"Python {v.major}.{v.minor} too old"


def test_no_duplicate_main_entry():
    content = Path("render_start.py").read_text(encoding="utf-8")
    assert content.count("dp.start_polling") <= 1, "duplicate start_polling in render_start.py"
    call_count = content.count("await run_telegram_bot()")
    assert call_count == 1, f"expected exactly 1 run_telegram_bot call, found {call_count}"


def test_no_hardcoded_secrets():
    files_to_check = ["render_start.py", "render.yaml"]
    secrets = ["BOT_TOKEN=", "API_KEY=", "TELEGRAM_TOKEN="]
    for fname in files_to_check:
        if not os.path.exists(fname):
            continue
        content = Path(fname).read_text(encoding="utf-8")
        for secret in secrets:
            # Check that if a value is set after =, it's not a hardcoded token
            for line in content.split("\n"):
                if secret in line and "sync: false" not in line and "value:" not in line:
                    val = line.split("=", 1)[1].strip().strip("'\"")
                    if val and len(val) > 10:
                        assert False, f"possible hardcoded secret in {fname}: {line.strip()}"
