"""
Рассылки: ручная (через /broadcast или admin UI) и автоматическая по расписанию
(напоминание/реклама каждые 4 дня), плюс готовые тексты-шаблоны.
"""
import asyncio
from datetime import timedelta
from typing import Dict, Optional

from aiogram import Bot
from aiogram.types import Message, LinkPreviewOptions
from aiogram.exceptions import TelegramBadRequest

from config import BROADCAST_MAX_USERS, BROADCAST_DELAY_SEC, log
from helpers import html_escape, msk_now, to_html_simple, pe
from storage import store
from admin_log_file import log_admin
from logging_channel import log_event, format_user_for_log
from logger import logger, Event
from keyboards import broadcast_cancel_kb

# ================== STATE ==================
pending_admin_broadcast: Dict[int, str] = {}
pending_admin_broadcast_text: Dict[int, str] = {}
pending_admin_broadcast_source: Dict[int, str] = {}
pending_admin_broadcast_cancel: Dict[int, bool] = {}

# ================== WIZARD STATE (/broadcast text -> photo -> pin -> preview) ==================
# wizard[admin_id] = {"step": "text"|"photo"|"pin"|"preview", "text": str, "photo": str|None, "pin": bool}
broadcast_wizard: Dict[int, Dict] = {}

# ================== LAST BROADCAST (для удаления) ==================
# last_broadcast[admin_id] = {"chat_message_ids": [(chat_id, message_id), ...], "pinned": [(chat_id, message_id), ...]}
last_broadcast: Dict[int, Dict] = {}

# ================== PRESET TEXTS ==================
REMINDER_MSG = (
    "🆘 Нужна помощь?\n\n"
    "Если возник вопрос или что-то не работает, воспользуйтесь командой /support.\n"
    "Или напишите напрямую: 📩 @tiksavesbotsupport\n\n"
    "━━━━━━━━━━━━━━━\n\n"
    "💛 Поддержать проект\n\n"
    "Если бот оказался полезным, вы можете помочь его развитию.\n\n"
    "Доступные способы:\n"
    "⭐ Telegram Stars\n"
    "💎 Криптовалюта\n"
    "Команда: /donate\n\n"
    "Спасибо, что пользуетесь TIKSAVES! 💛"
)

ADVERTISEMENT_MSG = (
    "💛 Спасибо, что пользуетесь TIKSAVES!\n\n"
    "Если бот оказался полезным, поделитесь им с друзьями.\n\n"
    "Это занимает всего пару секунд, но очень помогает развитию проекта.\n\n"
    "Спасибо за вашу поддержку! 🙌\n\n"
    "🤖 @tiksavesbot"
)


async def do_broadcast(
    message: Message,
    admin_id: int,
    admin_label: str,
    raw_text: str,
    *,
    already_html: bool = False,
    photo: Optional[str] = None,
    pin: bool = False,
) -> None:
    users = list(store.data.get("users", []))
    if not users:
        await message.answer(pe("Пока нет пользователей для рассылки."), parse_mode="HTML")
        return
    if len(users) > BROADCAST_MAX_USERS:
        await message.answer(pe(f"⚠️ Слишком много пользователей ({len(users)}). Лимит: {BROADCAST_MAX_USERS}."), parse_mode="HTML")
        return

    # Без конвертации Markdown-подобной разметки — текст уходит как есть,
    # просто экранируем спецсимволы HTML, чтобы Telegram его не сломал.
    html = raw_text if already_html else html_escape(raw_text)

    log_admin(admin_id, "broadcast", f"len={len(raw_text)} users={len(users)} photo={bool(photo)} pin={pin}")
    logger.log(
        Event.BROADCAST,
        "Рассылка запущена",
        status="PENDING",
        user={"id": admin_id},
        extra={
            "Кто": format_user_for_log(admin_label, admin_id),
            "Получателей": len(users),
            "Фото": "да" if photo else "нет",
            "Закреп": "да" if pin else "нет",
        },
        force_telegram=True,
    )

    pending_admin_broadcast_cancel[admin_id] = False
    status = await message.answer(
        pe(f"📣 Запускаю рассылку…\nПолучателей: {len(users)}"),
        parse_mode="HTML",
        reply_markup=broadcast_cancel_kb(),
    )
    sent = 0
    sent_messages: list = []
    pinned_messages: list = []

    # Telegram caption limit для фото — 1024 символа. Если текст длиннее,
    # отправляем фото без подписи и текст отдельным сообщением сразу следом,
    # иначе send_photo упадёт с ошибкой у ВСЕХ получателей.
    caption_too_long = bool(photo) and len(html) > 1024

    for u in users:
        if pending_admin_broadcast_cancel.get(admin_id):
            break
        try:
            if photo:
                if caption_too_long:
                    msg = await message.bot.send_photo(u, photo)
                    await message.bot.send_message(u, html, parse_mode="HTML", link_preview_options=LinkPreviewOptions(is_disabled=True))
                else:
                    msg = await message.bot.send_photo(u, photo, caption=html, parse_mode="HTML")
            else:
                msg = await message.bot.send_message(u, html, parse_mode="HTML", link_preview_options=LinkPreviewOptions(is_disabled=True))
            sent += 1
            sent_messages.append((u, msg.message_id))
            if pin:
                try:
                    await message.bot.pin_chat_message(u, msg.message_id, disable_notification=True)
                    pinned_messages.append((u, msg.message_id))
                except Exception:
                    pass
        except Exception:
            pass
        await asyncio.sleep(BROADCAST_DELAY_SEC)

    last_broadcast[admin_id] = {
        "chat_message_ids": sent_messages,
        "pinned": pinned_messages,
    }

    if pending_admin_broadcast_cancel.get(admin_id):
        await status.edit_text(pe(f"⛔ Рассылка остановлена: {sent}/{len(users)}"), parse_mode="HTML")
        logger.log(
            Event.BROADCAST,
            "Рассылка остановлена",
            status="WARNING",
            user={"id": admin_id},
            extra={
                "Кто": format_user_for_log(admin_label, admin_id),
                "Отправлено": f"{sent}/{len(users)}",
            },
            force_telegram=True,
        )
        pending_admin_broadcast_cancel.pop(admin_id, None)
        return

    await status.edit_text(
        pe(
            f"✅ Рассылка завершена: {sent}/{len(users)}\n\n"
            f"Удалить рассылку: /undo_broadcast"
        ),
        parse_mode="HTML",
    )
    logger.log(
        Event.BROADCAST,
        "Рассылка завершена",
        status="SUCCESS",
        user={"id": admin_id},
        extra={
            "Кто": format_user_for_log(admin_label, admin_id),
            "Отправлено": f"{sent}/{len(users)}",
            "Закреплено": len(pinned_messages),
        },
        force_telegram=True,
    )
    pending_admin_broadcast_cancel.pop(admin_id, None)


async def undo_last_broadcast(admin_id: int, bot: Bot) -> int:
    """Удаляет последнюю рассылку у всех получателей. Возвращает кол-во удалённых сообщений."""
    data = last_broadcast.get(admin_id)
    if not data:
        return -1
    removed = 0
    for chat_id, message_id in data.get("chat_message_ids", []):
        try:
            await bot.delete_message(chat_id, message_id)
            removed += 1
        except TelegramBadRequest:
            pass
        except Exception:
            pass
        await asyncio.sleep(0.05)
    last_broadcast.pop(admin_id, None)
    return removed


async def do_broadcast_system(bot: Bot, kind: str, raw_text: str) -> None:
    users = list(store.data.get("users", []))
    if not users:
        logger.log(Event.BROADCAST, f"Авто-рассылка ({kind}): нет пользователей", status="SKIPPED", force_telegram=True)
        return
    if len(users) > BROADCAST_MAX_USERS:
        logger.log(Event.BROADCAST, f"Авто-рассылка ({kind}): слишком много пользователей", status="WARNING",
                   extra={"Пользователей": len(users)}, force_telegram=True)
        return

    html = to_html_simple(raw_text)
    logger.log(Event.BROADCAST, f"Авто-рассылка ({kind}) запущена", status="PENDING",
               extra={"Получателей": len(users)}, force_telegram=True)

    sent = 0
    for u in users:
        try:
            await bot.send_message(u, html, parse_mode="HTML", link_preview_options=LinkPreviewOptions(is_disabled=True))
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(BROADCAST_DELAY_SEC)

    logger.log(Event.BROADCAST, f"Авто-рассылка ({kind}) завершена", status="SUCCESS",
               extra={"Отправлено": f"{sent}/{len(users)}"}, force_telegram=True)


def _broadcast_state() -> Dict[str, str]:
    store.data.setdefault("broadcast_state", {})
    return store.data["broadcast_state"]


async def broadcast_schedule_loop(bot: Bot) -> None:
    # Рассылки раз в 4 дня: напоминание в 15:00, реклама бота в 20:00
    while True:
        try:
            now = msk_now()
            today_str = now.strftime("%Y-%m-%d")
            day_mod = now.date().toordinal() % 4
            state = _broadcast_state()

            if now.hour == 15 and now.minute == 0 and day_mod == 0:
                if state.get("last_reminder") != today_str:
                    await do_broadcast_system(bot, "reminder", REMINDER_MSG)
                    state["last_reminder"] = today_str
                    store._mark_dirty()
                    log.info("broadcast: reminder sent at 15:00 (4-day cycle)")

            if now.hour == 20 and now.minute == 0 and day_mod == 0:
                if state.get("last_advert") != today_str:
                    await do_broadcast_system(bot, "advert", ADVERTISEMENT_MSG)
                    state["last_advert"] = today_str
                    store._mark_dirty()
                    log.info("broadcast: advert sent at 20:00 (4-day cycle)")

            # Спим до следующей минуты, чтобы не пропустить 15:00 / 20:00
            next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
            wait_sec = (next_minute - now).total_seconds()
            await asyncio.sleep(max(1, min(60, wait_sec)))
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.exception("broadcast_schedule_loop: %s", e)
            await asyncio.sleep(60)
