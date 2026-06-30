"""
Конфигурация бота: переменные окружения, константы, логгер.
"""
import os
import re
import logging
from pathlib import Path
from datetime import timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# ================== CONFIG ==================
ENV_PATH = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=ENV_PATH, override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не найден. Добавь BOT_TOKEN в .env рядом с bot.py")
if not re.match(r"^\d+:[A-Za-z0-9_-]{30,}$", BOT_TOKEN):
    raise RuntimeError("❌ BOT_TOKEN имеет неверный формат. Проверь токен в .env")

# База данных (PostgreSQL на Render)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
# Render даёт postgres://, asyncpg требует postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

# Путь к JSON для первичной миграции данных (если файл существует — мигрируем)
DATA_FILE = Path("data.json")

API_URL = "https://tikwm.com/api/"
ADMINS = {7233257134}  # <-- твой Telegram ID

ADMIN_LOG_FILE = Path("admin.log")

SUPPORT_USERNAME = "@tiksavesbotsupport"
try:
    MSK_TZ = ZoneInfo("Europe/Moscow")
except Exception:
    MSK_TZ = timezone.utc

# Канал для логов (бот должен быть админом канала)
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "-1003763229922"))

TIKTOK_RE = re.compile(r"(https?://)?(www\.)?(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)/", re.I)

MEDIA_GROUP_LIMIT = 10
PAGE_SIZE = 10
PENDING_TTL_SEC = 300

# ========= DONATE =========
CRYPTO_DONATE_URL = os.getenv("CRYPTO_DONATE_URL", "").strip() or "https://t.me/send?start=IVba6SXTH9iy"
BOT_SHARE_URL = os.getenv("BOT_SHARE_URL", "").strip() or "https://t.me/tiksavesbot"
STARS_MIN = int(os.getenv("STARS_MIN", "1"))
STARS_MAX = int(os.getenv("STARS_MAX", "1000"))
WAITING_STARS_TTL_SEC = 120

# ========= GLOBAL LIMITS =========
GLOBAL_CONCURRENCY = 8  # одновременных скачиваний на весь бот — не блокирует других пользователей очередью

# ========= SPAM LIMIT (тихий cooldown, без страйков) =========
EVENT_WINDOW_SEC = 15
EVENT_MAX = 8
SPAM_COOLDOWN_SEC = 60

# ========= DOWNLOAD LIMIT =========
DL_WINDOW_SEC = 60
DL_MAX_ACTIONS = 6

# ========= PHOTO VOLUME LIMIT =========
PHOTO_WINDOW_SEC = 60
PHOTO_LIMIT_PER_MIN = 120

# ========= AUTOSAVE =========
AUTO_SAVE_INTERVAL_SEC = 5  # автосинхронизация раз в N сек

# ========= VIDEO/AUDIO FALLBACK DOWNLOAD =========
MAX_VIDEO_MB = int(os.getenv("MAX_VIDEO_MB", "60"))
MAX_VIDEO_BYTES = MAX_VIDEO_MB * 1024 * 1024
MAX_AUDIO_MB = int(os.getenv("MAX_AUDIO_MB", "25"))
MAX_AUDIO_BYTES = MAX_AUDIO_MB * 1024 * 1024

# ========= API FALLBACK / HEALTH =========
API_ERROR_WINDOW_SEC = 120
API_ERROR_THRESHOLD = 6
API_FALLBACK_COOLDOWN_SEC = 180

# Варианты fallback: "none" | "apify"
ALT_PROVIDER = os.getenv("ALT_PROVIDER", "none").strip().lower()
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "").strip()
APIFY_ACTOR = os.getenv("APIFY_ACTOR", "apilabs/tiktok-downloader").strip()

BAN_DURATION_SEC = int(os.getenv("BAN_DURATION_SEC", str(24 * 3600)))  # 24 часа по умолчанию
BAN_REASON_SPAM = "Авто-бан: спам/флуд"
BAN_REASON_DL = "Лимит скачиваний"
BAN_REASON_PHOTO = "Лимит фото"

# Подпись с указанием бота
CAPTION_PHOTO = '<tg-emoji emoji-id="5774022692642492953">✅</tg-emoji> <b>Готово!</b> <tg-emoji emoji-id="6030466823290360017">🖼️</tg-emoji>\nПриятного просмотра 😎\n\n<tg-emoji emoji-id="6039420807900303010">📥</tg-emoji> Скачано в боте @tiksavesbot'
CAPTION_VIDEO = '<tg-emoji emoji-id="5774022692642492953">✅</tg-emoji> <b>Готово!</b> <tg-emoji emoji-id="5937999673510858217">🎬</tg-emoji>\nПриятного просмотра 😎\n\n<tg-emoji emoji-id="6039420807900303010">📥</tg-emoji> Скачано в боте @tiksavesbot'
CAPTION_AUDIO = '<tg-emoji emoji-id="5938473438468378529">🎵</tg-emoji> <b>Звук из TikTok</b>\n\n<tg-emoji emoji-id="6039420807900303010">📥</tg-emoji> Скачано в боте @tiksavesbot'

ALBUM_PAUSE_MIN = 0.4
ALBUM_PAUSE_MAX = 0.8

BROADCAST_DELAY_SEC = 0.35
BROADCAST_MAX_USERS = 5000

MSG_SPAM = "🛡 Флуд. Подожди ~{n} сек."
MSG_DL = '<tg-emoji emoji-id="5891211339170326418">⏳</tg-emoji> Лимит скачиваний. Подожди ~{n} сек.'
MSG_PHOTO = "📸 Лимит фото. Подожди ~{n} сек."

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("tiktok_bot")
