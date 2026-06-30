"""
Рейт-лимиты: флуд сообщений/кнопок, лимит скачиваний, лимит объёма фото.
Плюс глобальный семафор на одновременные скачивания.
"""
import time
import asyncio
from collections import defaultdict, deque
from typing import Dict, Tuple

from config import (
    EVENT_WINDOW_SEC,
    EVENT_MAX,
    SPAM_COOLDOWN_SEC,
    DL_WINDOW_SEC,
    DL_MAX_ACTIONS,
    PHOTO_WINDOW_SEC,
    PHOTO_LIMIT_PER_MIN,
    GLOBAL_CONCURRENCY,
)


class Limiters:
    def __init__(self):
        self.events: Dict[int, deque] = defaultdict(deque)
        self.spam_cd_until: Dict[int, float] = {}
        self.spam_cd_striked: Dict[int, bool] = {}
        self.last_warn_ts: Dict[int, float] = {}

        self.dl: Dict[int, deque] = defaultdict(deque)
        self.photo: Dict[int, deque] = defaultdict(deque)

    def _cleanup(self, dq: deque, now: float, window: int) -> None:
        while dq and now - dq[0] > window:
            dq.popleft()

    def spam_left(self, uid: int) -> int:
        now = time.time()
        until = self.spam_cd_until.get(uid, 0.0)
        if now >= until:
            self.spam_cd_until.pop(uid, None)
            self.spam_cd_striked.pop(uid, None)
            return 0
        return int(until - now) if until - now >= 1 else 1

    def spam_can_warn(self, uid: int, gap: float = 1.2) -> bool:
        now = time.time()
        last = self.last_warn_ts.get(uid, 0.0)
        if now - last < gap:
            return False
        self.last_warn_ts[uid] = now
        return True

    def spam_hit_or_cd(self, uid: int) -> Tuple[bool, int, bool]:
        now = time.time()
        left = self.spam_left(uid)
        if left > 0:
            return False, left, False

        dq = self.events[uid]
        self._cleanup(dq, now, EVENT_WINDOW_SEC)

        if len(dq) >= EVENT_MAX:
            self.spam_cd_until[uid] = now + SPAM_COOLDOWN_SEC
            self.spam_cd_striked[uid] = False
            return False, SPAM_COOLDOWN_SEC, True

        dq.append(now)
        return True, 0, False

    def spam_should_strike_once(self, uid: int) -> bool:
        if self.spam_cd_until.get(uid, 0.0) <= time.time():
            return False
        if self.spam_cd_striked.get(uid):
            return False
        self.spam_cd_striked[uid] = True
        return True

    def dl_hit(self, uid: int) -> Tuple[bool, int]:
        now = time.time()
        dq = self.dl[uid]
        self._cleanup(dq, now, DL_WINDOW_SEC)
        if len(dq) >= DL_MAX_ACTIONS:
            wait = int(max(1, DL_WINDOW_SEC - (now - dq[0]))) if dq else DL_WINDOW_SEC
            return False, wait
        dq.append(now)
        return True, 0

    def photo_hit(self, uid: int, count: int) -> Tuple[bool, int]:
        now = time.time()
        dq = self.photo[uid]
        self._cleanup(dq, now, PHOTO_WINDOW_SEC)
        if len(dq) + count > PHOTO_LIMIT_PER_MIN:
            wait = int(max(1, PHOTO_WINDOW_SEC - (now - dq[0]))) if dq else PHOTO_WINDOW_SEC
            return False, wait
        for _ in range(count):
            dq.append(now)
        return True, 0


lim = Limiters()
download_sem = asyncio.Semaphore(GLOBAL_CONCURRENCY)
