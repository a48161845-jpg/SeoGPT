"""
Единая система логирования TikSaves.

Архитектура:
  logger.log(event="DOWNLOAD", title="...", user=..., provider=..., duration=..., status="SUCCESS")

Logger сам:
  - оформляет сообщение в едином стиле (рамка с заголовком, секции, иконки);
  - решает, нужно ли отправлять событие в Telegram-канал (фильтр по важности
    события + status, чтобы не спамить успешными скачиваниями);
  - пишет событие в PostgreSQL (таблица event_log) для последующих агрегатов;
  - накапливает метрики в памяти для почасовых/ежедневных сводок и
    для постоянного статус-сообщения.

Совместимость: старый logging_channel.log_event(...) продолжает работать
(используется как fallback для мест, ещё не переведённых на новый Logger),
но весь новый код должен использовать logger.log(...) из этого модуля.
"""
from __future__ import annotations

import asyncio
import contextlib
import time
import traceback as tb_module
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from aiogram import Bot

from config import log as py_log
from helpers import html_escape, pe, now_msk_str
from storage import db_insert_event, db_pool_available


class Event:
    DOWNLOAD = "DOWNLOAD"
    ERROR = "ERROR"
    WARNING = "WARNING"
    ADMIN = "ADMIN"
    USER = "USER"
    DONATE = "DONATE"
    BROADCAST = "BROADCAST"
    PROVIDER = "PROVIDER"
    DATABASE = "DATABASE"
    SECURITY = "SECURITY"
    SYSTEM = "SYSTEM"


_EVENT_ICON: Dict[str, str] = {
    Event.DOWNLOAD: "🎬",
    Event.ERROR: "💥",
    Event.WARNING: "⚠️",
    Event.ADMIN: "👑",
    Event.USER: "👤",
    Event.DONATE: "⭐",
    Event.BROADCAST: "📣",
    Event.PROVIDER: "🔌",
    Event.DATABASE: "🗄",
    Event.SECURITY: "🛡",
    Event.SYSTEM: "⚙️",
}

_EVENT_TITLE: Dict[str, str] = {
    Event.DOWNLOAD: "СКАЧИВАНИЕ",
    Event.ERROR: "ОШИБКА",
    Event.WARNING: "ПРЕДУПРЕЖДЕНИЕ",
    Event.ADMIN: "АДМИН",
    Event.USER: "ПОЛЬЗОВАТЕЛЬ",
    Event.DONATE: "ДОНАТ",
    Event.BROADCAST: "РАССЫЛКА",
    Event.PROVIDER: "ПРОВАЙДЕР",
    Event.DATABASE: "БАЗА ДАННЫХ",
    Event.SECURITY: "БЕЗОПАСНОСТЬ",
    Event.SYSTEM: "СИСТЕМА",
}

# Какие события по умолчанию отправляются в Telegram-канал.
# Успешные скачивания НЕ отправляются (только пишутся в БД для статистики).
_TELEGRAM_EVENTS: set = {
    Event.ERROR,
    Event.ADMIN,
    Event.DONATE,
    Event.BROADCAST,
    Event.SECURITY,
    Event.SYSTEM,
}

_FAIL_STATUSES = {"FAIL", "ERROR", "FAILED"}


def _icon(event: str) -> str:
    return _EVENT_ICON.get(event, "📋")


def _title(event: str) -> str:
    return _EVENT_TITLE.get(event, event)


@dataclass
class Stopwatch:
    """
    Секундомер для измерения времени отдельных стадий операции.
        sw = Stopwatch()
        ... работа ...
        sw.lap("fetch_url")
        ... работа ...
        sw.lap("get_info")
        durations = sw.as_dict()  # {"fetch_url": 48, "get_info": 81, "_total": 129}
    Время в миллисекундах (int).
    """
    _start: float = field(default_factory=time.perf_counter)
    _last: float = field(default_factory=time.perf_counter)
    _laps: List[tuple] = field(default_factory=list)

    def lap(self, name: str) -> int:
        now = time.perf_counter()
        ms = int((now - self._last) * 1000)
        self._laps.append((name, ms))
        self._last = now
        return ms

    def total_ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)

    def as_dict(self) -> Dict[str, int]:
        d = {name: ms for name, ms in self._laps}
        d["_total"] = self.total_ms()
        return d


def _box_header(icon: str, title: str) -> str:
    return f"╭──────────── {icon} {title} ────────────╮"


def _box_footer() -> str:
    return "╰──────────────────────────────────────╯"


def _section(lines: List[str]) -> str:
    out = []
    for i, line in enumerate(lines):
        prefix = "└" if i == len(lines) - 1 else "├"
        out.append(f"{prefix} {line}")
    return "\n".join(out)


def _fmt_duration(ms: Optional[int]) -> str:
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{ms} ms"
    return f"{ms / 1000:.2f} sec"


def _fmt_size(bytes_n: Optional[int]) -> str:
    if not bytes_n:
        return "—"
    if bytes_n < 1024:
        return f"{bytes_n} B"
    if bytes_n < 1024 * 1024:
        return f"{bytes_n / 1024:.1f} KB"
    return f"{bytes_n / (1024 * 1024):.1f} MB"


_STATUS_ICON = {
    "SUCCESS": "✅", "OK": "✅",
    "FAIL": "❌", "ERROR": "❌", "FAILED": "❌",
    "WARNING": "⚠️", "PENDING": "⏳", "SKIPPED": "⏭",
}


def _status_line(status: Optional[str]) -> Optional[str]:
    if not status:
        return None
    icon = _STATUS_ICON.get(status.upper(), "ℹ️")
    return f"{icon} Статус: {status.upper()}"


def build_message(
    event: str,
    title: str,
    *,
    status: Optional[str] = None,
    user: Optional[Dict[str, Any]] = None,
    content: Optional[Dict[str, Any]] = None,
    performance: Optional[Dict[str, int]] = None,
    error: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
    note: Optional[str] = None,
) -> str:
    """
    Собирает финальный текст лога в едином фирменном стиле (рамка + секции).
    Каждый параметр опционален — секция строится только если данные переданы.
    Результат уже прогнан через pe() (premium-эмодзи), безопасен для
    отправки с parse_mode="HTML".
    """
    icon = _icon(event)
    name = _title(event)
    lines: List[str] = [_box_header(icon, name), ""]

    if title:
        lines.append(f"<b>{html_escape(title)}</b>")
        lines.append("")

    if user:
        u_lines = []
        if "id" in user:
            u_lines.append(f"ID: <code>{user['id']}</code>")
        if user.get("username"):
            u_lines.append(f"Username: @{html_escape(str(user['username']))}")
        if "premium" in user:
            u_lines.append(f"Premium: {'да' if user['premium'] else 'нет'}")
        if u_lines:
            lines.append("👤 Пользователь")
            lines.append(_section(u_lines))
            lines.append("")

    if content:
        c_lines = []
        if content.get("type"):
            c_lines.append(f"Тип: {html_escape(str(content['type']))}")
        if content.get("provider"):
            c_lines.append(f"Провайдер: {html_escape(str(content['provider']))}")
        if content.get("size") is not None:
            c_lines.append(f"Размер: {_fmt_size(content['size'])}")
        if content.get("source"):
            src = str(content["source"])
            if len(src) > 60:
                src = src[:57] + "..."
            c_lines.append(f"Источник: <code>{html_escape(src)}</code>")
        if c_lines:
            lines.append("📥 Контент")
            lines.append(_section(c_lines))
            lines.append("")

    if performance:
        p_lines = []
        ordered = [(k, v) for k, v in performance.items() if k != "_total"]
        labels = {
            "fetch_url": "Получение ссылки",
            "get_info": "Получение информации",
            "download": "Скачивание",
            "upload": "Отправка",
            "send": "Отправка Telegram",
        }
        for k, v in ordered:
            p_lines.append(f"{labels.get(k, k)}: {_fmt_duration(v)}")
        if "_total" in performance:
            p_lines.append(f"Итого: {_fmt_duration(performance['_total'])}")
        if p_lines:
            lines.append("⚡ Производительность")
            lines.append(_section(p_lines))
            lines.append("")

    if error:
        e_lines = []
        if error.get("name"):
            e_lines.append(f"Тип: <code>{html_escape(str(error['name']))}</code>")
        if error.get("module"):
            e_lines.append(f"Модуль: {html_escape(str(error['module']))}")
        if error.get("provider"):
            e_lines.append(f"Провайдер: {html_escape(str(error['provider']))}")
        if error.get("url"):
            u = str(error["url"])
            if len(u) > 60:
                u = u[:57] + "..."
            e_lines.append(f"URL: <code>{html_escape(u)}</code>")
        if error.get("attempt"):
            e_lines.append(f"Попытка: {error['attempt']}")
        if error.get("duration_ms") is not None:
            e_lines.append(f"Время выполнения: {_fmt_duration(error['duration_ms'])}")
        if error.get("reason"):
            e_lines.append(f"Причина: {html_escape(str(error['reason']))}")
        if e_lines:
            lines.append("💥 Детали ошибки")
            lines.append(_section(e_lines))
            lines.append("")
        if error.get("traceback"):
            tb_text = str(error["traceback"])
            if len(tb_text) > 600:
                tb_text = tb_text[-600:]
            lines.append(f"<pre>{html_escape(tb_text)}</pre>")
            lines.append("")

    if extra:
        x_lines = [f"{html_escape(str(k))}: {html_escape(str(v))}" for k, v in extra.items()]
        if x_lines:
            lines.append(_section(x_lines))
            lines.append("")

    st_line = _status_line(status)
    if st_line:
        lines.append(st_line)
        lines.append("")

    if note:
        lines.append(f"<i>{html_escape(note)}</i>")
        lines.append("")

    lines.append(f"🕒 {now_msk_str()}")
    lines.append("")
    lines.append(_box_footer())

    return pe("\n".join(lines))


@dataclass
class _HourBucket:
    downloads: int = 0
    new_users: int = 0
    errors: int = 0
    total_duration_ms: int = 0
    duration_count: int = 0
    provider_durations: Dict[str, List[int]] = field(default_factory=dict)

    def avg_duration_ms(self) -> int:
        if self.duration_count == 0:
            return 0
        return int(self.total_duration_ms / self.duration_count)

    def avg_provider_ms(self, provider: str) -> int:
        durs = self.provider_durations.get(provider) or []
        if not durs:
            return 0
        return int(sum(durs) / len(durs))


class _MetricsAccumulator:
    """
    Копит метрики в памяти для почасовых/ежедневных сводок и live-статуса.
    Часовой бакет сбрасывается после публикации почасовой сводки,
    суточный — после публикации ежедневной.
    """
    def __init__(self) -> None:
        self.hour = _HourBucket()
        self.day = _HourBucket()
        self.errors_recent: List[Dict[str, Any]] = []

    def record_download(self, duration_ms: Optional[int], provider: Optional[str]) -> None:
        for bucket in (self.hour, self.day):
            bucket.downloads += 1
            if duration_ms is not None:
                bucket.total_duration_ms += duration_ms
                bucket.duration_count += 1
                if provider:
                    bucket.provider_durations.setdefault(provider, []).append(duration_ms)

    def record_new_user(self) -> None:
        for bucket in (self.hour, self.day):
            bucket.new_users += 1

    def record_error(self, summary: str) -> None:
        for bucket in (self.hour, self.day):
            bucket.errors += 1
        self.errors_recent.append({"ts": time.time(), "summary": summary})
        self.errors_recent = self.errors_recent[-20:]

    def reset_hour(self) -> None:
        self.hour = _HourBucket()

    def reset_day(self) -> None:
        self.day = _HourBucket()


metrics = _MetricsAccumulator()


class Logger:
    """Единая точка логирования. Используй logger.log(...) из любого места проекта."""

    def __init__(self) -> None:
        self._bot: Optional[Bot] = None

    def bind_bot(self, bot: Bot) -> None:
        self._bot = bot

    def log(
        self,
        event: str,
        title: str = "",
        *,
        status: Optional[str] = None,
        user: Optional[Dict[str, Any]] = None,
        content: Optional[Dict[str, Any]] = None,
        performance: Optional[Dict[str, int]] = None,
        provider: Optional[str] = None,
        error: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
        note: Optional[str] = None,
        force_telegram: bool = False,
        skip_telegram: bool = False,
    ) -> None:
        """
        Планирует асинхронную обработку события и сразу возвращает управление
        (не блокирует вызывающий код). Безопасна для вызова из sync-контекста,
        если уже есть running event loop (стандартный случай внутри хендлеров).
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            py_log.warning("Logger.log() called without a running event loop, event dropped: %s", event)
            return
        loop.create_task(self._handle(
            event, title, status=status, user=user, content=content,
            performance=performance, provider=provider, error=error,
            extra=extra, note=note, force_telegram=force_telegram, skip_telegram=skip_telegram,
        ))

    async def _handle(
        self, event: str, title: str, *,
        status: Optional[str], user: Optional[Dict[str, Any]],
        content: Optional[Dict[str, Any]], performance: Optional[Dict[str, int]],
        provider: Optional[str], error: Optional[Dict[str, Any]],
        extra: Optional[Dict[str, Any]], note: Optional[str],
        force_telegram: bool, skip_telegram: bool,
    ) -> None:
        with contextlib.suppress(Exception):
            self._update_metrics(event, status, performance, error, title)

        with contextlib.suppress(Exception):
            await self._persist(event, title, status, user, content, performance, provider, error, extra)

        should_send = force_telegram or (event in _TELEGRAM_EVENTS and not skip_telegram)
        if should_send and self._bot is not None:
            with contextlib.suppress(Exception):
                await self._send_telegram(event, title, status, user, content, performance, error, extra, note)

    def _update_metrics(
        self, event: str, status: Optional[str],
        performance: Optional[Dict[str, int]], error: Optional[Dict[str, Any]], title: str,
    ) -> None:
        if event == Event.DOWNLOAD and (status or "").upper() in ("SUCCESS", "OK"):
            duration = (performance or {}).get("_total")
            metrics.record_download(duration, None)
        if event == Event.USER and title and "нов" in title.lower():
            metrics.record_new_user()
        if event == Event.ERROR or (status or "").upper() in _FAIL_STATUSES:
            summary = title or (error or {}).get("name") or "Ошибка"
            metrics.record_error(str(summary))

    async def _persist(
        self, event: str, title: str, status: Optional[str],
        user: Optional[Dict[str, Any]], content: Optional[Dict[str, Any]],
        performance: Optional[Dict[str, int]], provider: Optional[str],
        error: Optional[Dict[str, Any]], extra: Optional[Dict[str, Any]],
    ) -> None:
        if not db_pool_available():
            return
        user_id = (user or {}).get("id")
        prov = provider or (content or {}).get("provider") or (error or {}).get("provider")
        duration_ms = (performance or {}).get("_total")
        payload = {"title": title, "content": content, "performance": performance, "error": error, "extra": extra}
        await db_insert_event(event, status, user_id, prov, duration_ms, payload)

    async def _send_telegram(
        self, event: str, title: str, status: Optional[str],
        user: Optional[Dict[str, Any]], content: Optional[Dict[str, Any]],
        performance: Optional[Dict[str, int]], error: Optional[Dict[str, Any]],
        extra: Optional[Dict[str, Any]], note: Optional[str],
    ) -> None:
        from logging_channel import send_channel_log
        text = build_message(
            event, title, status=status, user=user, content=content,
            performance=performance, error=error, extra=extra, note=note,
        )
        await send_channel_log(self._bot, text)

    def log_exception(
        self, exc: BaseException, *,
        module: str = "", user: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None, url: Optional[str] = None,
        attempt: Optional[int] = None, duration_ms: Optional[int] = None,
        title: Optional[str] = None,
    ) -> None:
        """Удобный шорткат для логирования исключений с полным traceback."""
        tb_text = "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__))
        self.log(
            Event.ERROR,
            title=title or f"{type(exc).__name__}: {str(exc)[:120]}",
            status="ERROR",
            user=user,
            error={
                "name": type(exc).__name__,
                "module": module,
                "provider": provider,
                "url": url,
                "attempt": attempt,
                "duration_ms": duration_ms,
                "reason": str(exc)[:300],
                "traceback": tb_text,
            },
        )


logger = Logger()
