"""
Антиспам без страйков: просто cooldown + бан при многократном флуде.
"""
import time
from typing import Optional
from collections import defaultdict

from aiogram import Bot
from aiogram.types import Message

from config import BAN_DURATION_SEC, BAN_REASON_SPAM, BAN_REASON_DL, SUPPORT_USERNAME
from helpers import html_escape, code, format_msk, pe
from storage import store
from admin_log_file import log_admin
from logger import logger, Event

BAN_SPAM_VIOLATIONS = 4
_spam_violations: dict = defaultdict(int)
_spam_cd_session: dict = {}


def _reset_violation_if_needed(uid: int) -> None:
    sess_start = _spam_cd_session.get(uid, 0)
    from config import SPAM_COOLDOWN_SEC
    if sess_start and time.time() - sess_start > SPAM_COOLDOWN_SEC + 5:
        _spam_violations.pop(uid, None)
        _spam_cd_session.pop(uid, None)


async def add_spam_strike(bot: Bot, uid: int, label: str, reason: str) -> Optional[int]:
    _reset_violation_if_needed(uid)
    _spam_cd_session.setdefault(uid, time.time())
    _spam_violations[uid] += 1
    violations = _spam_violations[uid]

    logger.log(
        Event.SECURITY,
        "Флуд/спам",
        status="WARNING",
        user={"id": uid, "username": label if label.startswith("@") else None},
        extra={
            "Нарушений в сессии": f"{violations}/{BAN_SPAM_VIOLATIONS}",
            "Причина": reason,
        },
    )

    if violations >= BAN_SPAM_VIOLATIONS:
        until = int(time.time()) + BAN_DURATION_SEC
        store.set_ban(uid, until, BAN_REASON_SPAM, by=0)
        store.inc_ban()
        _spam_violations.pop(uid, None)
        _spam_cd_session.pop(uid, None)

        log_admin(0, "autoban_spam", f"target={uid} until={until} reason={BAN_REASON_SPAM}")
        logger.log(
            Event.SECURITY,
            "Авто-бан за флуд",
            status="FAIL",
            user={"id": uid, "username": label if label.startswith("@") else None},
            extra={
                "Бан до": format_msk(until) + " МСК",
                "Причина": BAN_REASON_SPAM,
            },
            force_telegram=True,
        )
        return until

    return None


async def add_download_strike(bot: Bot, uid: int, label: str, reason: str, *, src: Optional[str] = None) -> Optional[int]:
    logger.log(
        Event.SECURITY,
        "Превышен лимит скачиваний",
        status="WARNING",
        user={"id": uid, "username": label if label.startswith("@") else None},
        extra={
            "Причина": reason,
            "Ссылка": src or "—",
        },
    )
    return None


async def ban_message(message: Message, who_label: str, until: int, reason: str) -> None:
    if not message.from_user:
        return
    uid = message.from_user.id
    try:
        await message.answer(
        pe(
            "🚫 <b>Вы заблокированы.</b>\n\n"
            f"⏳ Бан до: <b>{format_msk(until)} МСК</b>\n"
            f"📌 Причина: <b>{html_escape(reason)}</b>\n\n"
            f"🆘 Поддержка: {html_escape(SUPPORT_USERNAME)}"
        ),
        parse_mode="HTML",
        )
    except Exception:
        pass
