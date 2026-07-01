"""
Буферизованная отправка логов в служебный Telegram-канал,
а также автосейв хранилища в фоне.
"""
import re
import time
import asyncio
import contextlib
from typing import Optional, Dict, Tuple, List

from aiogram import Bot
from aiogram.types import LinkPreviewOptions

from config import LOG_CHANNEL_ID, AUTO_SAVE_INTERVAL_SEC, log
from helpers import html_escape, code, now_msk_str, pe
from storage import store

# ================== AUTOSAVE LOOP ==================

async def autosave_loop() -> None:
    while True:
        try:
            await asyncio.sleep(AUTO_SAVE_INTERVAL_SEC)
            await store.save_unthrottled()
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.exception("autosave_loop: %s", e)

# ================== LOGS TO CHANNEL (BUFFERED + DUAL TAGS) ==================
LOG_RATE_LIMIT_SEC = 0.25

CAT_TAG = {
    "user": "user",
    "userstats": "userstats",
    "help": "help",
    "support": "support",
    "donate_open": "donate_open",
    "gate_ban": "gate_ban",
    "gate_spam": "gate_spam",
    "photodl": "photodl",
    "videodl": "videodl",
    "audiodl": "audiodl",
    "dlerr": "dlerr",
    "spamstrike": "spamstrike",
    "dlstrike": "dlstrike",
    "photostrike": "photostrike",
    "autoban": "autoban",
    "userban": "userban",
    "userunban": "userunban",
    "stars": "stars",
    "broadcast": "broadcast",
    "admin": "admin",
}

def base_tag_for(category: str) -> str:
    return f"#{CAT_TAG.get(category, 'log')}"

def numbered_tag_for(category: str) -> str:
    seq = store.next_seq(category)
    return f"#{CAT_TAG.get(category, 'log')}{seq}"

def format_user_for_log(label: str, uid: int) -> str:
    """
    Кликабельное упоминание пользователя для логов.
    Если есть username — ссылка https://t.me/username (кликабельна всегда).
    Если username нет — tg://user?id=... (работает только если у админа есть
    общий чат с пользователем; Telegram не даёт более надёжного способа
    сослаться на человека без username и без диалога).
    """
    s = (label or "").strip()
    m = re.search(r"\((\d+)\)\s*$", s)
    name_part = s
    if m:
        name_part = s[:m.start()].strip()
    if not name_part:
        name_part = str(uid)

    username = None
    if name_part.startswith("@"):
        username = name_part[1:].strip()

    display = html_escape(name_part)
    if username:
        href = f"https://t.me/{username}"
    else:
        href = f"tg://user?id={uid}"
    return f'<a href="{href}">{display}</a> ({code(uid)})'

_log_queue: "asyncio.Queue[Tuple[int, str]]" = asyncio.Queue(maxsize=2000)
_log_worker_task: Optional[asyncio.Task] = None
_last_log_ts = 0.0

async def _log_worker(bot: Bot) -> None:
    global _last_log_ts
    while True:
        try:
            chat_id, text = await _log_queue.get()
            try:
                dt = time.time() - _last_log_ts
                if dt < LOG_RATE_LIMIT_SEC:
                    await asyncio.sleep(LOG_RATE_LIMIT_SEC - dt)

                await bot.send_message(chat_id, text, parse_mode="HTML", link_preview_options=LinkPreviewOptions(is_disabled=True))
                _last_log_ts = time.time()
            except Exception:
                pass
            finally:
                _log_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception:
            pass

async def start_log_worker(bot: Bot) -> None:
    global _log_worker_task
    if _log_worker_task and not _log_worker_task.done():
        return
    _log_worker_task = asyncio.create_task(_log_worker(bot))

async def stop_log_worker() -> None:
    global _log_worker_task
    try:
        await asyncio.wait_for(_log_queue.join(), timeout=3.0)
    except Exception:
        pass
    if _log_worker_task and not _log_worker_task.done():
        _log_worker_task.cancel()
        with contextlib.suppress(Exception):
            await _log_worker_task

async def send_channel_log(_bot: Bot, text: str) -> None:
    try:
        _log_queue.put_nowait((LOG_CHANNEL_ID, text))
    except asyncio.QueueFull:
        pass

async def log_event(bot: Bot, category: str, lines: List[str]) -> None:
    t_base = base_tag_for(category)
    t_num = numbered_tag_for(category)
    if category == "audiodl":
        t_base = "#audiodl #audiodl23"
    header = f"🧾 Лог: <b>{html_escape(category)}</b>\n🕒 {now_msk_str()}"
    full_text = f"{t_base} {t_num}\n" + "\n".join([header, *lines])
    await send_channel_log(bot, pe(full_text))

async def log_admin_action_to_channel(bot: Bot, title: str, lines: List[str]) -> None:
    """
    Совместимый шим: старый интерфейс (bot, title, lines[]) теперь
    маршрутизируется через новый единый Logger (событие ADMIN).
    lines обычно содержат пары вида "👤 Кто: <b>...</b>" — парсим их
    в extra-словарь для единообразного оформления через build_message().
    """
    from logger import logger, Event
    extra: Dict[str, str] = {}
    for line in lines:
        # Грубый парсинг "Метка: значение" из готовых HTML-строк старого формата
        plain = re.sub(r"<[^>]+>", "", line)
        if ":" in plain:
            k, _, v = plain.partition(":")
            extra[k.strip()] = v.strip()
        else:
            extra[plain.strip()] = ""
    logger.log(Event.ADMIN, title, status="SUCCESS", extra=extra or None, force_telegram=True)
