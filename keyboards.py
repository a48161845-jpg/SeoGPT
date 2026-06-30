"""
Инлайн-клавиатуры и текстовые константы, которые показываются пользователю.
Здесь нет бизнес-логики — только разметка интерфейса.
"""
import urllib.parse
from typing import List

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import SUPPORT_USERNAME, CRYPTO_DONATE_URL, BOT_SHARE_URL, STARS_MIN, STARS_MAX
from helpers import html_escape, code

# ================== STATS / TOP KEYBOARDS ==================
def stats_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 День", callback_data="ad:stats:d"),
                InlineKeyboardButton(text="🗓 Неделя", callback_data="ad:stats:n"),
                InlineKeyboardButton(text="🗓 Месяц", callback_data="ad:stats:m"),
            ],
            [
                InlineKeyboardButton(text="📆 Год", callback_data="ad:stats:y"),
                InlineKeyboardButton(text="📊 Всё время", callback_data="ad:stats:all"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ad:back"),
                InlineKeyboardButton(text="❌ Закрыть", callback_data="ad:close"),
            ],
        ]
    )

def top_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 День", callback_data="ad:top:d"),
                InlineKeyboardButton(text="🗓 Неделя", callback_data="ad:top:n"),
                InlineKeyboardButton(text="🗓 Месяц", callback_data="ad:top:m"),
            ],
            [
                InlineKeyboardButton(text="📆 Год", callback_data="ad:top:y"),
                InlineKeyboardButton(text="📊 Всё время", callback_data="ad:top:all"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ad:back"),
                InlineKeyboardButton(text="❌ Закрыть", callback_data="ad:close"),
            ],
        ]
    )

# ================== START ==================
START_TEXT = (
    "👋 Добро пожаловать в TIKSAVES!\n\n"
    "📥 Скачивай контент из TikTok быстро и без лишних действий.\n\n"
    "Доступно:\n"
    "🎬 Видео без водяного знака\n"
    "🖼️ Фото и слайд-шоу\n"
    "🎵 Музыка из видео\n\n"
    "📎 Просто отправь ссылку на TikTok — всё остальное бот сделает сам.\n\n"
    "━━━━━━━━━━━━━━━\n\n"
    "🧾 Помощь — /help\n"
    "📊 Моя статистика — /stats\n"
    "💛 Поддержать проект — /donate\n"
    "🆘 Поддержка — /support\n\n"
    "💛 Спасибо, что пользуешься TIKSAVES!"
)

# ================== DONATE ==================
def donate_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Донат звёздами", callback_data="donate:stars")],
            [InlineKeyboardButton(text="💲 Донат криптой", url=CRYPTO_DONATE_URL)],
            [InlineKeyboardButton(text="🆘 Поддержка", callback_data="donate:support")],
        ]
    )

def stars_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ 10", callback_data="stars:10"),
                InlineKeyboardButton(text="⭐ 50", callback_data="stars:50"),
                InlineKeyboardButton(text="⭐ 100", callback_data="stars:100"),
            ],
            [
                InlineKeyboardButton(text="⭐ 250", callback_data="stars:250"),
                InlineKeyboardButton(text="⭐ 500", callback_data="stars:500"),
                InlineKeyboardButton(text="⭐ 1000", callback_data="stars:1000"),
            ],
            [InlineKeyboardButton(text="✍️ Другая сумма", callback_data="stars:custom")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="donate:back")],
        ]
    )

DONATE_TEXT = (
    "💛 <b>Поддержать TIKSAVES</b>\n\n"
    "Спасибо, что пользуешься ботом!\n\n"
    "Каждый донат помогает оплачивать:\n\n"
    "☁️ Хостинг 24/7\n"
    "⚡ Быстрые серверы\n"
    "🌍 Прокси и API\n"
    "🛠 Разработку новых функций\n\n"
    "Выберите удобный способ поддержки 👇"
)
STARS_MENU_TEXT = (
    "⭐ <b>Telegram Stars</b>\n\n"
    "Поддержать проект можно прямо в Telegram.\n\n"
    f"Выберите количество Stars\nили укажите своё значение.\n\n"
    f"⭐ От {STARS_MIN} до {STARS_MAX} Stars\n\n"
    "Спасибо за поддержку! 💛"
)
SUPPORT_TEXT = (
    "🆘 <b>Поддержка</b>\n\n"
    "Возникла проблема?\n\n"
    "Перед сообщением желательно указать:\n\n"
    "• ссылку на TikTok;\n"
    "• что именно произошло;\n"
    "• скриншот ошибки (если есть).\n\n"
    f"📨 {html_escape(SUPPORT_USERNAME)}"
)
SHARE_TEXT = "Нашел топового бота для скачивания видео и фото из TikTok. Переходи ☝️"

# ================== HELP ==================
HELP_TEXT = (
    "🧾 <b>Помощь</b>\n\n"
    "Добро пожаловать в справочный центр TIKSAVES.\n\n"
    "Выберите нужный раздел с помощью кнопок ниже 👇"
)

def help_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 Скачать видео", callback_data="help:video"),
                InlineKeyboardButton(text="🖼 Скачать фото", callback_data="help:photo"),
            ],
            [
                InlineKeyboardButton(text="🎵 Скачать музыку", callback_data="help:music"),
            ],
            [
                InlineKeyboardButton(text="⚠️ Ограничения", callback_data="help:limits"),
            ],
            [
                InlineKeyboardButton(text="💛 Донат", callback_data="help:donate"),
                InlineKeyboardButton(text="🆘 Поддержка", callback_data="help:support"),
            ],
            [
                InlineKeyboardButton(text="❌ Закрыть", callback_data="help:close"),
            ],
        ]
    )

def help_section_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="help:back"),
                InlineKeyboardButton(text="❌ Закрыть", callback_data="help:close"),
            ]
        ]
    )

HELP_SECTIONS = {
    "video": (
        "🎬 <b>Скачать видео</b>\n\n"
        "1️⃣ Отправьте ссылку на TikTok.\n\n"
        "2️⃣ Нажмите «🎬 Скачать видео».\n\n"
        "3️⃣ Через несколько секунд бот отправит видео без водяного знака (если доступно)."
    ),
    "photo": (
        "🖼 <b>Скачать фото</b>\n\n"
        "1️⃣ Отправьте ссылку на публикацию с фотографиями.\n\n"
        "2️⃣ Выберите нужные номера или нажмите «📥 Скачать всё».\n\n"
        "3️⃣ Получите выбранные изображения в хорошем качестве."
    ),
    "music": (
        "🎵 <b>Скачать музыку</b>\n\n"
        "После обработки ссылки нажмите «🎵 Музыка».\n\n"
        "Бот отправит оригинальную аудиодорожку из публикации."
    ),
    "limits": (
        "⚠️ <b>Ограничения</b>\n\n"
        "Для стабильной работы действует защита от спама.\n\n"
        "• Между запросами есть небольшая задержка.\n"
        "• При большом количестве запросов возможна временная блокировка.\n"
        "• Некоторые публикации могут быть недоступны из-за ограничений TikTok.\n\n"
        "Спасибо за понимание 💛"
    ),
    "donate": (
        "💛 <b>Донат</b>\n\n"
        "Поддержка проекта через Stars или крипту. Спасибо!"
    ),
    "support": (
        "🆘 <b>Поддержка</b>\n\n"
        f"Пиши: {html_escape(SUPPORT_USERNAME)}\n"
        "Укажи ссылку и что не работает."
    ),
}

# ================== POST-DOWNLOAD / VIDEO KEYBOARDS ==================
def _share_url() -> str:
    """Ссылка «Поделиться»: в шаре подставляется url, текст — про бота (ссылка вставляется сама)."""
    share_url = urllib.parse.quote_plus(BOT_SHARE_URL)
    share_text = urllib.parse.quote_plus(SHARE_TEXT)
    return f"https://t.me/share/url?url={share_url}&text={share_text}"

def post_download_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💛 Донат", callback_data="donate:open"),
                InlineKeyboardButton(text="🔗 Поделиться", url=_share_url()),
            ]
        ]
    )

def under_video_kb(has_music: bool = False, has_desc: bool = False) -> InlineKeyboardMarkup:
    """Кнопки под скачанным видео: Описание, Музыка (если есть), Донат, Поделиться."""
    rows: List[List[InlineKeyboardButton]] = []
    extra_row: List[InlineKeyboardButton] = []
    if has_desc:
        extra_row.append(InlineKeyboardButton(text="📑 Описание", callback_data="dl:desc"))
    if has_music:
        extra_row.append(InlineKeyboardButton(text="🎵 Музыка", callback_data="dl:audio"))
    if extra_row:
        rows.append(extra_row)
    rows.append([
        InlineKeyboardButton(text="💛 Донат", callback_data="donate:open"),
        InlineKeyboardButton(text="🔗 Поделиться", url=_share_url()),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def video_choice_kb() -> InlineKeyboardMarkup:
    """Только «Скачать видео» и «Отмена» — кнопка музыки перенесена под видео."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎬 Скачать видео", callback_data="vd:video")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="vd:cancel")],
        ]
    )

# ================== ADMIN UI ==================
def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="ad:stats"),
                InlineKeyboardButton(text="🏆 Топ", callback_data="ad:top"),
            ],
            [
                InlineKeyboardButton(text="🚫 Бан-лист", callback_data="ad:banlist"),
                InlineKeyboardButton(text="🗄 Дамп БД", callback_data="ad:dbfile"),
            ],
            [
                InlineKeyboardButton(text="📌 Напоминание", callback_data="ad:reminder"),
                InlineKeyboardButton(text="📢 Реклама", callback_data="ad:advert"),
            ],
            [
                InlineKeyboardButton(text="👑 Администраторы", callback_data="ad:adminlist"),
            ],
            [
                InlineKeyboardButton(text="🧾 Команды", callback_data="ad:help"),
                InlineKeyboardButton(text="❌ Закрыть", callback_data="ad:close"),
            ],
        ]
    )

def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="ad:back"),
                InlineKeyboardButton(text="❌ Закрыть", callback_data="ad:close"),
            ]
        ]
    )

ADMIN_MENU_TEXT = (
    "🛠 <b>Админ-панель</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "📊 <b>Статистика</b> — выбор периода\n"
    "🏆 <b>Топ</b> — лидеры по периоду\n"
    "🚫 <b>Бан-лист</b> — активные баны\n"
    "🗄 <b>Дамп БД</b> — скачать базу данных\n"
    "👑 <b>Администраторы</b> — список и управление\n"
    "📌 <b>Напоминание</b> / 📢 <b>Реклама</b> — рассылки\n"
    "🧾 <b>Команды</b> — полный список\n"
)

ADMIN_HELP_TEXT = (
    "🧾 <b>Команды администратора</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"

    "📊 <b>Статистика</b>\n"
    f"├ {code('/stats d')} — день\n"
    f"├ {code('/stats n')} — неделя\n"
    f"├ {code('/stats m')} — месяц\n"
    f"├ {code('/stats y')} — год\n"
    f"├ {code('/stats all')} — всё время\n"
    f"└ {code('/stats 2026-02-01 2026-02-07')} — диапазон\n\n"

    "🏆 <b>Топ пользователей</b>\n"
    f"├ {code('/top d')} {code('/top n')} {code('/top m')} {code('/top y')} {code('/top all')}\n"
    f"└ {code('/top 2026-02-01 2026-02-07')} — диапазон\n\n"

    "🚫 <b>Баны</b>\n"
    f"├ {code('/ban ID 2h причина')} — забанить\n"
    f"├ {code('/unban ID')} — разбанить\n"
    f"├ {code('/banlist')} — список банов\n"
    f"└ {code('/baninfo ID')} — информация о бане\n\n"

    "👑 <b>Администраторы</b>\n"
    f"├ {code('/adminlist')} — список всех админов\n"
    f"├ {code('/adminadd ID')} — добавить (только суперадмин)\n"
    f"└ {code('/admindel ID')} — удалить (только суперадмин)\n\n"

    "👤 <b>Пользователь</b>\n"
    f"└ {code('/info ID')} — информация о пользователе\n\n"

    "🗄 <b>База данных</b>\n"
    f"├ {code('/dbfile')} — дамп БД файлом\n"
    f"└ {code('/dblog')} — отчёт в лог-канал\n\n"

    "📣 <b>Рассылка</b>\n"
    f"├ {code('/broadcast')} — пошаговая рассылка (текст → фото → закреп → предпросмотр)\n"
    f"├ {code('/reminder_message')} — напоминание\n"
    f"├ {code('/advertisement_message')} — реклама\n"
    f"└ {code('/undo_broadcast')} — удалить последнюю рассылку\n"
)

def admin_broadcast_confirm_kb(kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отправить", callback_data=f"ad:send:{kind}"),
            ],
            [
                InlineKeyboardButton(text="❌ Закрыть", callback_data="ad:close"),
            ],
        ]
    )

def broadcast_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⛔ Остановить рассылку", callback_data="ad:bcancel")],
        ]
    )

# ================== BROADCAST WIZARD ==================
def bcw_skip_photo_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Пропустить (без фото)", callback_data="bcw:skip_photo")],
            [InlineKeyboardButton(text="❌ Отменить рассылку", callback_data="bcw:abort")],
        ]
    )

def bcw_pin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="bcw:pin_yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="bcw:pin_no"),
            ],
            [InlineKeyboardButton(text="❌ Отменить рассылку", callback_data="bcw:abort")],
        ]
    )

def bcw_preview_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🚀 Разослать", callback_data="bcw:send"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="bcw:abort"),
            ],
        ]
    )
