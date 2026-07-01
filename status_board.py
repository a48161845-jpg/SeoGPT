"""
Постоянное закреплённое статус-сообщение (обновляется каждые ~45 сек)
и периодические агрегированные сводки (почасовая / ежедневная) в Telegram.

Статус-сообщение редактируется на месте — НЕ создаёт новых сообщений каждый раз.
ID сообщения сохраняется в storage (bot_kv), чтобы переживать рестарт бота.
"""
import asyncio
import contextlib
from typing import Optional

from aiogram import Bot

from config import LOG_CHANNEL_ID, log as py_log
from helpers import html_escape, pe, now_msk_str
from storage import store, db_pool_available
from sys_metrics import system_snapshot
from logger import metrics

STATUS_UPDATE_INTERVAL_SEC = 45
HOURLY_SUMMARY_INTERVAL_SEC = 3600
DAILY_SUMMARY_INTERVAL_SEC = 86400

_status_message_id: Optional[int] = None
_status_task: Optional[asyncio.Task] = None
_hourly_task: Optional[asyncio.Task] = None
_daily_task: Optional[asyncio.Task] = None

# Внешняя ссылка на switcher для отображения состояния провайдеров (опционально)
_switcher_ref = None


def bind_switcher(switcher) -> None:
    global _switcher_ref
    _switcher_ref = switcher


def _provider_status_lines() -> list:
    if _switcher_ref is None:
        return ["└ нет данных"]
    try:
        import time as _time
        using_secondary = bool(
            getattr(_switcher_ref, "secondary", None)
            and _time.time() < getattr(_switcher_ref, "_use_secondary_until", 0)
        )
        primary_label = "⏸ резерв активен" if using_secondary else "✅ активен"
        lines = [f"├ Primary: {primary_label}"]
        if getattr(_switcher_ref, "secondary", None):
            secondary_label = "✅ активен" if using_secondary else "💤 ожидание"
            lines.append(f"└ Secondary: {secondary_label}")
        else:
            lines[-1] = lines[-1].replace("├", "└")
        return lines
    except Exception:
        return ["└ нет данных"]


async def _build_status_text() -> str:
    snap = system_snapshot()
    users_total = len(store.data.get("users", []))
    d = metrics.day

    ram = f"{snap['ram_mb']} MB" if snap["ram_mb"] is not None else "—"
    cpu = f"{snap['cpu_pct']}%" if snap["cpu_pct"] is not None else "—"
    db_status = "✅ подключена" if db_pool_available() else "❌ недоступна"
    avg_line = f"└ Среднее время: {d.avg_duration_ms()} ms" if d.duration_count else "└ Среднее время: —"

    lines = [
        "╭──────────── ⚙️ СТАТУС БОТА ────────────╮",
        "",
        "🟢 Бот работает",
        "",
        "👥 Пользователи",
        f"└ Всего: {users_total}",
        "",
        "📥 Скачивания сегодня",
        f"├ Всего: {d.downloads}",
        f"├ Ошибок: {d.errors}",
        avg_line,
        "",
        "💻 Ресурсы",
        f"├ RAM: {ram}",
        f"├ CPU: {cpu}",
        f"└ Аптайм: {snap['uptime']}",
        "",
        "🗄 База данных",
        f"└ {db_status}",
        "",
        "🔌 Провайдеры",
        *_provider_status_lines(),
        "",
        f"🕒 Обновлено: {now_msk_str()}",
        "",
        "╰──────────────────────────────────────╯",
    ]
    return pe("\n".join(lines))


async def ensure_status_message(bot: Bot) -> None:
    """Публикует статус-сообщение, если его ещё нет, и сохраняет его ID для последующего редактирования."""
    global _status_message_id
    saved_id = await _load_status_message_id()
    if saved_id:
        _status_message_id = saved_id
        return
    try:
        text = await _build_status_text()
        msg = await bot.send_message(LOG_CHANNEL_ID, text, parse_mode="HTML")
        _status_message_id = msg.message_id
        await _save_status_message_id(msg.message_id)
        with contextlib.suppress(Exception):
            await bot.pin_chat_message(LOG_CHANNEL_ID, msg.message_id, disable_notification=True)
    except Exception as e:
        py_log.warning("Could not create status message: %s", e)


async def _load_status_message_id() -> Optional[int]:
    try:
        from storage import _db_get
        val = await _db_get("status_message_id")
        return int(val) if val else None
    except Exception:
        return None


async def _save_status_message_id(message_id: int) -> None:
    try:
        from storage import _db_set
        await _db_set("status_message_id", message_id)
    except Exception:
        pass


async def _status_update_loop(bot: Bot) -> None:
    while True:
        await asyncio.sleep(STATUS_UPDATE_INTERVAL_SEC)
        if _status_message_id is None:
            continue
        try:
            text = await _build_status_text()
            await bot.edit_message_text(text, chat_id=LOG_CHANNEL_ID, message_id=_status_message_id, parse_mode="HTML")
        except Exception:
            pass  # сообщение могли удалить вручную / rate limit — просто пробуем на следующем цикле


async def _hourly_summary_loop(bot: Bot) -> None:
    while True:
        await asyncio.sleep(HOURLY_SUMMARY_INTERVAL_SEC)
        with contextlib.suppress(Exception):
            await _publish_hourly_summary(bot)
        metrics.reset_hour()


async def _daily_summary_loop(bot: Bot) -> None:
    while True:
        await asyncio.sleep(DAILY_SUMMARY_INTERVAL_SEC)
        with contextlib.suppress(Exception):
            await _publish_daily_summary(bot)
        metrics.reset_day()


def _provider_avg_lines(durations_map: dict) -> list:
    lines = []
    for prov, durs in durations_map.items():
        avg = int(sum(durs) / len(durs)) if durs else 0
        lines.append(f"├ {html_escape(prov)}: {avg} ms")
    if lines:
        lines[-1] = lines[-1].replace("├", "└")
    return lines


async def _publish_hourly_summary(bot: Bot) -> None:
    h = metrics.hour
    avg_line = f"└ Среднее время: {h.avg_duration_ms()} ms" if h.duration_count else "└ Среднее время: —"
    lines = [
        "╭──────────── 📊 СВОДКА ЗА ЧАС ────────────╮",
        "",
        "📥 Скачивания",
        f"├ Всего: {h.downloads}",
        avg_line,
        "",
        "👥 Новые пользователи",
        f"└ {h.new_users}",
        "",
        "💥 Ошибки",
        f"└ {h.errors}",
    ]
    provider_lines = _provider_avg_lines(h.provider_durations)
    if provider_lines:
        lines += ["", "🔌 Провайдеры (среднее время)", *provider_lines]
    lines += ["", f"🕒 {now_msk_str()}", "", "╰──────────────────────────────────────╯"]

    text = pe("\n".join(lines))
    with contextlib.suppress(Exception):
        await bot.send_message(LOG_CHANNEL_ID, text, parse_mode="HTML")


async def _publish_daily_summary(bot: Bot) -> None:
    d = metrics.day
    avg_line = f"└ Среднее время: {d.avg_duration_ms()} ms" if d.duration_count else "└ Среднее время: —"
    lines = [
        "╭──────────── 📅 ИТОГИ ДНЯ ────────────╮",
        "",
        "📥 Скачивания",
        f"├ Всего: {d.downloads}",
        avg_line,
        "",
        "👥 Новые пользователи",
        f"└ {d.new_users}",
        "",
        "💥 Ошибки",
        f"└ {d.errors}",
    ]
    provider_lines = _provider_avg_lines(d.provider_durations)
    if provider_lines:
        lines += ["", "🔌 Провайдеры (среднее время)", *provider_lines]
    lines += ["", f"🕒 {now_msk_str()}", "", "╰──────────────────────────────────────╯"]

    text = pe("\n".join(lines))
    with contextlib.suppress(Exception):
        await bot.send_message(LOG_CHANNEL_ID, text, parse_mode="HTML")


def start_status_tasks(bot: Bot) -> list:
    """Запускает все фоновые задачи системы статуса/сводок. Вызывать один раз при старте."""
    global _status_task, _hourly_task, _daily_task
    _status_task = asyncio.create_task(_status_update_loop(bot))
    _hourly_task = asyncio.create_task(_hourly_summary_loop(bot))
    _daily_task = asyncio.create_task(_daily_summary_loop(bot))
    return [_status_task, _hourly_task, _daily_task]
