"""
Бизнес-логика донатов: проверка суммы звёзд, отправка инвойса Stars,
безопасное редактирование сообщений (с подавлением ошибок Telegram API).
"""
from typing import Dict

from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, LabeledPrice, LinkPreviewOptions

from config import STARS_MIN, STARS_MAX, log

def stars_valid(x: int) -> bool:
    return STARS_MIN <= x <= STARS_MAX


async def safe_edit(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> None:
    try:
        if call.message:
            await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb, link_preview_options=LinkPreviewOptions(is_disabled=True))
    except Exception as e:
        log.debug("safe_edit: %s", e)


async def send_stars_invoice(bot: Bot, user_id: int, stars: int) -> None:
    await bot.send_invoice(
        chat_id=user_id,
        title="💖 Поддержка разработчика",
        description="Донат на развитие бота",
        payload=f"donate_stars_{stars}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Чаевые", amount=stars)],
    )


waiting_stars_amount: Dict[int, float] = {}
