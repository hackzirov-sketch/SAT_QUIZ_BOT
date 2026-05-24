import pathlib
import os
import re
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(dotenv_path=pathlib.Path(__file__).parent / '.env')

ROOT = pathlib.Path(__file__).parent
DATA_DIR = ROOT / 'data'
MOCK_TESTS_DIR = DATA_DIR / 'mock_tests'
MOCK_IMAGES_DIR = DATA_DIR / 'mock_images'
PDF_RESULTS_DIR = DATA_DIR / 'pdf_results'
RENDERED_IMAGES_DIR = DATA_DIR / 'rendered_images'

def _env_str(name: str, default: str = '') -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int, minimum: int | None = None) -> int:
    raw = _env_str(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f'{name} must be an integer') from exc
    if minimum is not None and value < minimum:
        raise SystemExit(f'{name} must be >= {minimum}')
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env_str(name, '1' if default else '0').lower()
    return raw in {'1', 'true', 'yes', 'on'}


def _resolve_path(raw: str, default: str) -> str:
    path = pathlib.Path(raw or default)
    if not path.is_absolute():
        path = ROOT / path
    return str(path)


BOT_TOKEN = _env_str('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in re.findall(r'\d+', _env_str('ADMIN_IDS'))]
DATABASE_PATH = _resolve_path(_env_str('DATABASE_PATH'), 'data/quiz_bot.db')
VOCABULARY_PATH = _resolve_path(_env_str('VOCABULARY_PATH'), 'data/vocabulary.json')
PORT = _env_int('PORT', 5000, minimum=1)
TZ = _env_str('TZ', _env_str('BOT_TIMEZONE', 'Asia/Tashkent'))
LOG_LEVEL = _env_str('LOG_LEVEL', 'INFO').upper()

WEBHOOK_URL = _env_str('WEBHOOK_URL').rstrip('/')
WEBHOOK_SECRET = _env_str('WEBHOOK_SECRET')
WEBHOOK_SETUP_TOKEN = _env_str('WEBHOOK_SETUP_TOKEN')

DB_BUSY_TIMEOUT_MS = _env_int('DB_BUSY_TIMEOUT_MS', 5000, minimum=1000)
SUBSCRIPTION_CACHE_TTL = _env_int('SUBSCRIPTION_CACHE_TTL', 600, minimum=0)
SUBSCRIPTION_STRICT = _env_bool('SUBSCRIPTION_STRICT', True)
ALLOW_EPHEMERAL_SQLITE_FALLBACK = _env_bool('ALLOW_EPHEMERAL_SQLITE_FALLBACK', False)
SESSION_SWEEP_INTERVAL = _env_int('SESSION_SWEEP_INTERVAL', 10, minimum=2)
BOT_POLLING_ENABLED = _env_bool('BOT_POLLING_ENABLED', True)
WEEKLY_REPORT_ENABLED = _env_bool('WEEKLY_REPORT_ENABLED', True)
WEEKLY_REPORT_WEEKDAY = _env_int('WEEKLY_REPORT_WEEKDAY', 0, minimum=0)
WEEKLY_REPORT_HOUR = _env_int('WEEKLY_REPORT_HOUR', 9, minimum=0)
WEEKLY_REPORT_MINUTE = _env_int('WEEKLY_REPORT_MINUTE', 0, minimum=0)
AI_MENTOR_ENABLED = _env_bool('AI_MENTOR_ENABLED', False)
AI_DAILY_LIMIT_USD = float(_env_str('AI_DAILY_LIMIT_USD', '0.50'))
AI_USER_COOLDOWN_SECONDS = _env_int('AI_USER_COOLDOWN_SECONDS', 20, minimum=0)

if (
    os.environ.get('RENDER')
    and DATABASE_PATH.startswith('/data/')
    and not pathlib.Path('/data').is_dir()
    and ALLOW_EPHEMERAL_SQLITE_FALLBACK
):
    DATABASE_PATH = _resolve_path('data/quiz_bot.db', 'data/quiz_bot.db')

if WEEKLY_REPORT_WEEKDAY > 6:
    raise SystemExit('WEEKLY_REPORT_WEEKDAY must be between 0 and 6')
if WEEKLY_REPORT_HOUR > 23:
    raise SystemExit('WEEKLY_REPORT_HOUR must be between 0 and 23')
if WEEKLY_REPORT_MINUTE > 59:
    raise SystemExit('WEEKLY_REPORT_MINUTE must be between 0 and 59')

QUIZ_QUESTION_COUNT = 50
QUIZ_DURATION = 900
POINTS_PER_CORRECT = 2
WIN_SCORE_THRESHOLD = 80

XP_BASE = 10
XP_STREAK_BONUS = 3
XP_TIME_BONUS_MAX = 5
XP_WIN_BONUS = 5

LEVEL_THRESHOLDS = [0, 200, 800, 2500, 6000]
LEVEL_NAMES = ['', '🌱 Beginner', '🌿 Intermediate', '🔥 Advanced', '🏆 SAT Master', '👑 Ivy League']

CATEGORY_ALL = 'all'
CATEGORY_OTHER = 'other'
SMALL_CATEGORIES = {'Arithmetic', 'Functions', 'Probability', 'Number Types', 'Coordinate Geometry', 'Basic Operations'}

GROUP_ID = _env_str('GROUP_ID')
CHANNEL_ID = _env_str('CHANNEL_ID')

_REQUIRED_SUBSCRIPTIONS = [
    {'chat_id': CHANNEL_ID or '@mathacademy01', 'title': 'Kanalimiz', 'link': 'https://t.me/mathacademy01'},
    {'chat_id': GROUP_ID, 'title': 'Guruximiz', 'link': 'https://t.me/+xN0rLsUBkGY2NjZi'},
]
REQUIRED_SUBSCRIPTIONS = [req for req in _REQUIRED_SUBSCRIPTIONS if req['chat_id']]

if not BOT_TOKEN:
    raise SystemExit('BOT_TOKEN is required')

if ':' not in BOT_TOKEN:
    raise SystemExit('BOT_TOKEN format is invalid')

if WEBHOOK_URL:
    parsed_webhook = urlparse(WEBHOOK_URL)
    if parsed_webhook.scheme != 'https' or not parsed_webhook.netloc:
        raise SystemExit('WEBHOOK_URL must be a full https URL')
    if len(WEBHOOK_SECRET) < 24:
        raise SystemExit('WEBHOOK_SECRET must be at least 24 characters when WEBHOOK_URL is set')


def is_admin_id(user_id: int | str | None) -> bool:
    try:
        return int(user_id) in ADMIN_IDS
    except (TypeError, ValueError):
        return False
