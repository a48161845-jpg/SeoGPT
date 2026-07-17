"""
Административные команды: баны, информация о пользователе, рассылки.
"""
import time
from typing import Optional

from aiogram.filters import Command
from aiogram.types import Message

from globals_state import dp
from helpers import html_escape, code, is_admin, parse_duration, format_msk
from storage import store
from user_label import resolve_user_label
from gates import gate_message
from logging_channel import format_user_for_log
from logger import logger, Event
from admin_log_file import log_admin
from keyboards import admin_broadcast_confirm_kb
from broadcast import (
    pending_admin_broadcast,
    pending_admin_broadcast_text,
    pending_admin_broadcast_source,
)


@dp.message(Command("ban"))
async def ban_cmd(message: Message):
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 4 or not parts[1].isdigit():
        await message.answer(
            pe(
                "❌ Формат:\n"
                f"{code('/ban 123 2h причина')}\n"
                "Длительность: 30m, 6h, 2d, 1d12h, 3h30m"
            ),
            parse_mode="HTML",
        )
        return

    uid = int(parts[1])
    dur_raw = parts[2]
    reason = parts[3].strip()

    # Нельзя банить админов
    if is_admin(uid):
        await message.answer(pe("❌ Нельзя банить администратора."), parse_mode="HTML")
        return

    existing = store.get_ban(uid)
    if existing:
        until_existing = int(existing.get("until", 0))
        reason_existing = html_escape(str(existing.get("reason", "Не указана")))
        who_label = await resolve_user_label(message.bot, uid)
        store.set_user_label(uid, who_label)
        await message.answer(
            pe(
                "ℹ️ Пользователь уже в бане.\n\n"
                f"👤 Кого: <b>{format_user_for_log(who_label, uid)}</b>\n"
                f"⏳ До: <b>{format_msk(until_existing)} МСК</b>\n"
                f"📌 Причина: <b>{reason_existing}</b>"
            ),
            parse_mode="HTML",
        )
        return

    try:
        seconds = parse_duration(dur_raw)
    except ValueError:
        await message.answer(pe("❌ Неверное время. Пример: 2h, 30m, 1d12h"), parse_mode="HTML")
        return

    until = int(time.time()) + seconds
    target_label = await resolve_user_label(message.bot, uid)
    store.set_user_label(uid, target_label)

    store.set_ban(uid, until=until, reason=reason, by=admin_id)
    store.inc_ban()
    log_admin(admin_id, "ban", f"target={uid} until={until} reason={reason}")

    logger.log(
        Event.SECURITY, "Ручной бан",
        status="FAIL",
        user={"id": uid, "username": target_label if target_label.startswith("@") else None},
        extra={
            "Кто": format_user_for_log(admin_label, admin_id),
            "До": format_msk(until) + " МСК",
            "Причина": reason,
        },
        force_telegram=True,
    )

    await message.answer(
        pe(
            "🛑 Пользователь забанен.\n\n"
            f"👤 Кого: <b>{format_user_for_log(target_label, uid)}</b>\n"
            f"⏳ До: <b>{format_msk(until)} МСК</b>\n"
            f"📌 Причина: <b>{html_escape(reason)}</b>"
        ),
        parse_mode="HTML",
    )


@dp.message(Command("unban"))
async def unban_cmd(message: Message):
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(pe(f"Использование: {code('/unban 123')}"), parse_mode="HTML")
        return

    uid = int(parts[1])
    existed = store.unban(uid)

    target_label = await resolve_user_label(message.bot, uid)
    store.set_user_label(uid, target_label)

    log_admin(admin_id, "unban", f"target={uid} existed={existed}")

    logger.log(
        Event.SECURITY, "Разбан",
        status="SUCCESS",
        user={"id": uid, "username": target_label if target_label.startswith("@") else None},
        extra={
            "Кто": format_user_for_log(admin_label, admin_id),
            "Был в бане": "да" if existed else "нет",
        },
        force_telegram=True,
    )
    if existed:
        await message.answer(pe(f"✅ Разбан: <b>{format_user_for_log(target_label, uid)}</b>"), parse_mode="HTML")
    else:
        await message.answer(pe(f"ℹ️ Пользователь не в бане: <b>{format_user_for_log(target_label, uid)}</b>"), parse_mode="HTML")


@dp.message(Command("banlist"))
async def banlist_cmd(message: Message):
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    bans = store.list_bans()
    log_admin(admin_id, "banlist", f"count={len(bans)}")
    logger.log(
        Event.ADMIN, "Просмотр бан-листа",
        status="SUCCESS",
        user={"id": admin_id},
        force_telegram=True,
    )

    if not bans:
        await message.answer(pe("✅ Активных банов нет."), parse_mode="HTML")
        return

    lines = ["🚫 <b>Активные баны</b>\n\n"]
    for uid2, until, reason, _by in bans[:100]:
        who_label = store.get_user_label(uid2)
        lines.append(
            f"• <b>{format_user_for_log(who_label, uid2)}</b> - до <b>{format_msk(until)} МСК</b>\n"
            f"  Причина: <i>{html_escape(reason)}</i>\n\n"
        )
    await message.answer(pe("".join(lines)), parse_mode="HTML")


@dp.message(Command("baninfo"))
async def baninfo_cmd(message: Message):
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer(pe(f"Использование: {code('/baninfo 123')}"), parse_mode="HTML")
        return

    uid = int(parts[1])
    ban = store.get_ban(uid)
    who_label = await resolve_user_label(message.bot, uid)
    store.set_user_label(uid, who_label)

    log_admin(admin_id, "baninfo", f"target={uid} banned={'yes' if ban else 'no'}")
    logger.log(
        Event.ADMIN, "Просмотр бана",
        status="SUCCESS",
        user={"id": admin_id},
        force_telegram=True,
    )

    if not ban:
        await message.answer(pe(f"ℹ️ Не в бане: <b>{format_user_for_log(who_label, uid)}</b>"), parse_mode="HTML")
        return

    until = int(ban.get("until", 0))
    reason = html_escape(str(ban.get("reason", "Не указана")))
    by = int(ban.get("by", 0))
    by_label = store.get_user_label(by)

    await message.answer(
        pe(
            "🚫 <b>Информация о бане</b>\n\n"
            f"👤 Пользователь: <b>{format_user_for_log(who_label, uid)}</b>\n"
            f"⏳ До: <b>{format_msk(until)} МСК</b>\n"
            f"📌 Причина: <b>{reason}</b>\n"
            f"👑 Кто выдал: <b>{format_user_for_log(by_label, by)}</b>"
        ),
        parse_mode="HTML",
    )


@dp.message(Command("info"))
async def info_cmd(message: Message):
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer(pe(f"Использование: {code('/info 123')} или {code('/info @username')}"), parse_mode="HTML")
        return

    raw = parts[1].strip()
    uid: Optional[int] = None
    if raw.isdigit():
        uid = int(raw)
    else:
        username = raw[1:] if raw.startswith("@") else raw
        try:
            chat = await message.bot.get_chat(username)
            uid = int(chat.id)
        except Exception:
            # fallback to stored usernames
            found_uid: Optional[int] = None
            for uid_str, label in (store.data.get("users_map", {}) or {}).items():
                if f"@{username}".lower() in str(label).lower():
                    found_uid = int(uid_str)
                    break
            if found_uid is None:
                await message.answer(pe("❌ Пользователь не найден. Проверь ID или username."), parse_mode="HTML")
                return
            uid = found_uid
    who_label = await resolve_user_label(message.bot, uid)
    store.set_user_label(uid, who_label)

    first_seen_ts = int((store.data.get("first_seen", {}) or {}).get(str(uid), 0))
    last_seen_ts = int((store.data.get("last_seen", {}) or {}).get(str(uid), 0))
    joined = format_msk(first_seen_ts) if first_seen_ts > 0 else "неизвестно"
    last_seen = format_msk(last_seen_ts) if last_seen_ts > 0 else "неизвестно"

    us_dl = (store.data.get("user_stats", {}) or {}).get("downloads", {}) or {}
    rec = us_dl.get(str(uid), {}) or {}
    v_sent = int(rec.get("video_sent", 0))
    p_sent = int(rec.get("photos_sent", 0))
    a_sent = int(rec.get("audio_sent", 0))

    stars_by_user = (store.data.get("user_stats", {}) or {}).get("stars", {}) or {}
    stars = int(stars_by_user.get(str(uid), 0))

    ban = store.get_ban(uid)
    if ban:
        status_text = f"🚫 Заблокирован до <b>{format_msk(int(ban.get('until', 0)))} МСК</b>"
    else:
        status_text = "Не заблокирован ✅"

    info_user = (store.data.get("users_info", {}) or {}).get(str(uid), {})
    username = info_user.get("username")
    username_line = f"👤 Username: @{html_escape(username)}\n" if username else ""

    await message.answer(
        pe(
            "👤 <b>Информация о пользователе</b>\n\n"
            f"🆔 ID: <b>{uid}</b>\n"
            f"{username_line}"
            f"<a href=\"tg://user?id={uid}\">Открыть профиль</a>\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"🗓 Первый визит\n└ {joined}\n\n"
            f"🕒 Последняя активность\n└ {last_seen}\n\n"
            f"🚫 Статус\n└ {status_text}\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            "📥 <b>Статистика</b>\n\n"
            f"🎬 Видео: {v_sent}\n"
            f"🖼 Фото: {p_sent}\n"
            f"🎵 Музыка: {a_sent}\n\n"
            f"⭐ Пожертвовано:\n{stars} Stars\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            "🤖 TIKSAVES"
        ),
        parse_mode="HTML",
    )


@dp.message(Command("broadcast"))
async def broadcast_cmd(message: Message):
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    from broadcast import broadcast_wizard
    broadcast_wizard[admin_id] = {"step": "text", "text": None, "photo": None, "pin": False}
    log_admin(admin_id, "broadcast_wizard_start")
    await message.answer(
        pe(
            "📣 <b>Новая рассылка</b>\n\n"
            "Шаг 1/3: пришлите текст рассылки."
        ),
        parse_mode="HTML",
    )


@dp.message(Command("undo_broadcast"))
async def undo_broadcast_cmd(message: Message):
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    from broadcast import undo_last_broadcast
    status = await message.answer(pe("⏳ Удаляю последнюю рассылку…"), parse_mode="HTML")
    removed = await undo_last_broadcast(admin_id, message.bot)
    if removed == -1:
        await status.edit_text(pe("❌ Нет данных о последней рассылке (или бот был перезапущен)."), parse_mode="HTML")
        return
    log_admin(admin_id, "undo_broadcast", f"removed={removed}")
    logger.log(
        Event.ADMIN, "Удалена рассылка",
        status="SUCCESS",
        user={"id": admin_id},
        force_telegram=True,
    )
    await status.edit_text(pe(f"✅ Рассылка удалена у {removed} пользователей."), parse_mode="HTML")


@dp.message(Command("reminder_message"))
async def reminder_message_cmd(message: Message):
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    pending_admin_broadcast[admin_id] = "reminder"
    pending_admin_broadcast_text.pop(admin_id, None)
    pending_admin_broadcast_source[admin_id] = "cmd"
    users_cnt = len(store.data.get("users", []))
    await message.answer(
        pe(
            "📣 <b>Подтверждение рассылки</b>\n\n"
            "Тип: <b>Напоминание</b>\n"
            f"Получателей: <b>{users_cnt}</b>\n\n"
            "Отправить?"
        ),
        parse_mode="HTML",
        reply_markup=admin_broadcast_confirm_kb("reminder"),
    )


@dp.message(Command("advertisement_message"))
async def advertisement_message_cmd(message: Message):
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    pending_admin_broadcast[admin_id] = "advert"
    pending_admin_broadcast_text.pop(admin_id, None)
    pending_admin_broadcast_source[admin_id] = "cmd"
    users_cnt = len(store.data.get("users", []))
    await message.answer(
        pe(
            "📣 <b>Подтверждение рассылки</b>\n\n"
            "Тип: <b>Реклама</b>\n"
            f"Получателей: <b>{users_cnt}</b>\n\n"
            "Отправить?"
        ),
        parse_mode="HTML",
        reply_markup=admin_broadcast_confirm_kb("advert"),
    )


@dp.message(Command("dblog"))
async def dblog_cmd(message: Message):
    """Отправить текстовый отчёт по БД в лог-канал (файлом .txt)."""
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    from db_report import send_db_report
    log_admin(admin_id, "dblog", "manual db report requested")
    await message.answer(pe("📊 Генерирую отчёт…"), parse_mode="HTML")
    await send_db_report(message.bot, title="Отчёт БД (ручной запрос)")
    await message.answer(pe("✅ Отчёт-файл отправлен в лог-канал."), parse_mode="HTML")


@dp.message(Command("dbfile"))
async def dbfile_cmd(message: Message):
    """Отправить полный JSON-дамп базы данных прямо в этот чат."""
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    from db_report import send_db_json
    log_admin(admin_id, "dbfile", "manual db dump requested")
    logger.log(
        Event.ADMIN, "Запрошен дамп БД",
        status="SUCCESS",
        user={"id": admin_id},
        force_telegram=True,
    )
    await message.answer(pe("🗄 Формирую дамп БД…"), parse_mode="HTML")
    await send_db_json(message.bot, admin_id)
    await message.answer(pe("✅ Файл отправлен."), parse_mode="HTML")


@dp.message(Command("adminadd"))
async def adminadd_cmd(message: Message):
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    from config import ADMINS
    if admin_id not in ADMINS:
        await message.answer("❌ Только владелец (суперадмин) может добавлять администраторов.", parse_mode="HTML")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip().isdigit():
        await message.answer(pe(f"Использование: {code('/adminadd 123456789')}"), parse_mode="HTML")
        return

    uid = int(parts[1].strip())
    target_label = await resolve_user_label(message.bot, uid)
    store.set_user_label(uid, target_label)

    added = store.add_extra_admin(uid)
    log_admin(admin_id, "adminadd", f"target={uid} success={added}")

    if added:
        logger.log(
        Event.ADMIN, "Добавление администратора",
        status="SUCCESS",
        user={"id": admin_id},
        force_telegram=True,
    )
        await message.answer(
            pe(f"✅ Администратор добавлен: <b>{format_user_for_log(target_label, uid)}</b>"),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            pe(f"ℹ️ Уже является администратором: <b>{format_user_for_log(target_label, uid)}</b>"),
            parse_mode="HTML",
        )


@dp.message(Command("admindel"))
async def admindel_cmd(message: Message):
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    from config import ADMINS
    if admin_id not in ADMINS:
        await message.answer("❌ Только владелец (суперадмин) может удалять администраторов.", parse_mode="HTML")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip().isdigit():
        await message.answer(pe(f"Использование: {code('/admindel 123456789')}"), parse_mode="HTML")
        return

    uid = int(parts[1].strip())
    if uid in ADMINS:
        await message.answer(pe("❌ Нельзя удалить суперадмина (прописан в config)."), parse_mode="HTML")
        return

    target_label = store.get_user_label(uid)
    removed = store.del_extra_admin(uid)
    log_admin(admin_id, "admindel", f"target={uid} success={removed}")

    if removed:
        logger.log(
        Event.ADMIN, "Удаление администратора",
        status="SUCCESS",
        user={"id": admin_id},
        force_telegram=True,
    )
        await message.answer(
            pe(f"✅ Администратор удалён: <b>{format_user_for_log(target_label, uid)}</b>"),
            parse_mode="HTML",
        )
    else:
        await message.answer(
            pe(f"ℹ️ Не является дополнительным администратором: <b>{format_user_for_log(target_label, uid)}</b>"),
            parse_mode="HTML",
        )


@dp.message(Command("adminlist"))
async def adminlist_cmd(message: Message):
    admin_id = message.from_user.id
    admin_label = await resolve_user_label(message.bot, admin_id)
    store.set_user_label(admin_id, admin_label)

    if not is_admin(admin_id):
        return
    if not await gate_message(message, admin_label):
        return

    from config import ADMINS
    # Пункт 11: [5807868868886009920] для заголовка, [5778570255555105942] для суперадминов, [6039496266180726678] для дополнительных
    lines = [
        '<tg-emoji emoji-id="5807868868886009920">🔌</tg-emoji> <b>Администраторы</b>',
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        '<tg-emoji emoji-id="5778570255555105942">🔒</tg-emoji> <b>Суперадмины:</b>',
    ]
    for uid2 in sorted(ADMINS):
        lbl = store.get_user_label(uid2)
        lines.append(f"  └ {format_user_for_log(lbl, uid2)}")

    extra = store.get_extra_admins()
    lines.append("")
    lines.append(f'<tg-emoji emoji-id="6039496266180726678">➕</tg-emoji> <b>Дополнительные ({len(extra)}):</b>')
    if extra:
        for uid2 in sorted(extra):
            lbl = store.get_user_label(uid2)
            lines.append(f"  └ {format_user_for_log(lbl, uid2)}")
    else:
        lines.append("  <i>нет</i>")

    lines.append("")
    lines.append(f"Управление: {code('/adminadd ID')} · {code('/admindel ID')}")

    log_admin(admin_id, "adminlist", f"extra_count={len(extra)}")
    logger.log(
        Event.ADMIN, "Просмотр списка администраторов",
        status="SUCCESS",
        user={"id": admin_id},
        force_telegram=True,
    )
    await message.answer("\n".join(lines), parse_mode="HTML")
