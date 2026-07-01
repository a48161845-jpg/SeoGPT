"""
Системные метрики (RAM, CPU, аптайм) для статус-сообщения и системных логов.
Изолировано в отдельный модуль — если psutil не установлен, метрики просто
возвращают None вместо падения бота.
"""
import os
import time
import platform
from typing import Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

_start_time = time.time()
_process = None
if _HAS_PSUTIL:
    try:
        _process = psutil.Process(os.getpid())
        _process.cpu_percent(interval=None)  # первый вызов всегда 0.0 — "прогреваем"
    except Exception:
        _process = None


def uptime_seconds() -> int:
    return int(time.time() - _start_time)


def uptime_human() -> str:
    s = uptime_seconds()
    days, s = divmod(s, 86400)
    hours, s = divmod(s, 3600)
    minutes, s = divmod(s, 60)
    parts = []
    if days:
        parts.append(f"{days}д")
    if hours:
        parts.append(f"{hours}ч")
    parts.append(f"{minutes}м")
    return " ".join(parts)


def ram_usage_mb() -> Optional[float]:
    if not _process:
        return None
    try:
        return round(_process.memory_info().rss / (1024 * 1024), 1)
    except Exception:
        return None


def cpu_percent() -> Optional[float]:
    if not _process:
        return None
    try:
        return round(_process.cpu_percent(interval=None), 1)
    except Exception:
        return None


def python_version() -> str:
    return platform.python_version()


def system_snapshot() -> dict:
    """Единый снимок системных метрик для логов запуска/статус-сообщения."""
    return {
        "uptime": uptime_human(),
        "ram_mb": ram_usage_mb(),
        "cpu_pct": cpu_percent(),
        "python": python_version(),
        "psutil_available": _HAS_PSUTIL,
    }
