"""
Лог админ-действий. Пишется и в локальный admin.log (для быстрого просмотра
на сервере), и в БД (поле admin_log в storage) — чтобы не терялся
при перезапуске контейнера на хостингах вроде BotHost, где файловая
система эфемерна.
"""
from datetime import datetime

from config import ADMIN_LOG_FILE


def log_admin(admin_id: int, action: str, details: str = "") -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} | admin={admin_id} | {action}"
    if details:
        line += f" | {details}"

    # 1) Локальный файл (может потеряться при рестарте контейнера — не критично)
    try:
        with ADMIN_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

    # 2) БД — переживает рестарт контейнера
    try:
        from storage import store
        log_list = store.data.setdefault("admin_log", [])
        log_list.append(line)
        # Не даём логу расти бесконечно — храним последние 2000 записей
        if len(log_list) > 2000:
            del log_list[: len(log_list) - 2000]
        store._mark_dirty()
    except Exception:
        pass
