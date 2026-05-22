import os
from dotenv import load_dotenv
import pathlib

load_dotenv(dotenv_path=pathlib.Path(__file__).parent / '.env')

ROOT = pathlib.Path(__file__).parent

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip().isdigit()]
DATABASE_PATH = str(ROOT / os.getenv('DATABASE_PATH', 'data/quiz_bot.db'))
VOCABULARY_PATH = str(ROOT / os.getenv('VOCABULARY_PATH', 'data/vocabulary.json'))
PORT = int(os.getenv('PORT', '5000'))
TZ = os.getenv('TZ', 'Asia/Tashkent')

WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '')
WEBHOOK_SETUP_TOKEN = os.getenv('WEBHOOK_SETUP_TOKEN', '')

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

REQUIRED_SUBSCRIPTIONS = [
    {'chat_id': '@mathacademy01', 'title': 'Math Academy', 'link': 'https://t.me/mathacademy01'},
    {'chat_id': None, 'title': 'SAT Quiz Bot Group', 'link': 'https://t.me/+xN0rLsUBkGY2NjZi'},
]

if not BOT_TOKEN:
    raise SystemExit('BOT_TOKEN is required')
